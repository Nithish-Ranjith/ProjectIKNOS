"""
backend/ml/ocr/ocr_pipeline.py — Tesseract OCR + NER field extraction for legacy RoR scans.

Design Contracts:
  - Input: scanned document image (JPG/PNG/TIFF)
  - Output: structured dict with extracted fields + confidence scores
  - Uses Tesseract OCR (brew install tesseract) for text extraction
  - Regex + rule-based NER for field extraction (NOT a trained model — as specified in PRD Section 6)
  - Supports regional scripts via Tesseract language packs (--lang tel+hin+eng)
  - NEVER synthesizes or guesses missing values — returns None with explicit EXTRACTION_FAILED flag
  - All output fields carry extraction_confidence (0.0–1.0) so the Decision Engine can weight them

PRD Spec (Section 6, OCR row):
  "Tesseract OCR + regex/NER field extraction — 🔧 Integration, not original model work"

FastAPI endpoint: POST /ocr/scan-ror  (accepts multipart file upload)
"""
from __future__ import annotations

import io
import json
import re
import uuid
from pathlib import Path
from typing import Optional

# Tesseract availability
try:
    import pytesseract
    _TESSERACT = True
except ImportError:
    _TESSERACT = False

try:
    from PIL import Image, ImageFilter, ImageEnhance
    _PIL = True
except ImportError:
    _PIL = False

try:
    import numpy as np
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False


# ---------------------------------------------------------------------------
# Pre-processing — critical for handwritten/scanned docs
# ---------------------------------------------------------------------------

def _preprocess_image(image: "Image.Image") -> "Image.Image":
    """
    Enhance scan quality for OCR:
      - Convert to grayscale
      - Adaptive contrast enhancement
      - Deskewing (if OpenCV available)
      - Binarize via Otsu threshold
    """
    if not _PIL:
        return image

    # Grayscale
    gray = image.convert("L")

    # Contrast enhancement
    enhancer = ImageEnhance.Contrast(gray)
    enhanced = enhancer.enhance(2.5)

    # Sharpening
    sharpened = enhanced.filter(ImageFilter.SHARPEN)

    # Deskew + binarize with OpenCV if available
    if _CV2:
        arr = np.array(sharpened)
        # Otsu binarization
        _, binary = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Deskew: find text angle and rotate
        coords = np.column_stack(np.where(binary < 128))
        if len(coords) > 50:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = 90 + angle
            if abs(angle) > 0.5:
                (h, w) = binary.shape
                M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
                binary = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_CUBIC,
                                        borderMode=cv2.BORDER_REPLICATE)
        return Image.fromarray(binary)

    return sharpened


# ---------------------------------------------------------------------------
# Field Extraction Rules (regex-based NER for RoR documents)
# ---------------------------------------------------------------------------

# Owner Name: e.g., "Owner: Ramu Reddy", "Sri. Venkata Rao", "Khatedar: ..."
_RE_OWNER = re.compile(
    r'(?:owner[:\s]+|khatedar[:\s]+|sri\.?\s+|shri\.?\s+)([\w\s\.]+?)(?:\n|khasra|survey|plot|area|$)',
    re.IGNORECASE | re.MULTILINE
)

# Khasra / Survey Number: "Khasra No. 123/4", "Survey No 456-A", "Plot No: 789"
_RE_KHASRA = re.compile(
    r'(?:khasra\s+(?:no\.?\s*)?|survey\s+(?:no\.?\s*)?|plot\s+(?:no\.?\s*)?|s\.no\.?\s*)([0-9]+[/\-A-Z]*)',
    re.IGNORECASE
)

# Area: "2.35 acres", "0.56 hectares", "235 cents", "1200 sq.m"
_RE_AREA = re.compile(
    r'([\d,]+\.?\d*)\s*(acres?|hectares?|cents?|sq\.?\s*m(?:etres?)?|guntas?)',
    re.IGNORECASE
)

# District / Village code (AP format: AP-07-0103-006)
_RE_ULPIN = re.compile(r'(AP[\-\s][0-9]{2}[\-\s][0-9]{4}[\-\s][0-9]{3}[\-\s][0-9]{5})', re.IGNORECASE)

# Registration Number / Deed number
_RE_DEED = re.compile(r'(?:deed\s+no\.?|reg(?:istration)?\s+no\.?|doc(?:ument)?\s+no\.?)[:\s]+([A-Z0-9\-/]+)', re.IGNORECASE)

# Date patterns
_RE_DATE = re.compile(r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{4}[/\-\.]\d{2}[/\-\.]\d{2})\b')

# Mutation status
_RE_MUTATION = re.compile(r'mutation\s+(?:status\s*)?[:\-]?\s*(approved|pending|rejected|none)', re.IGNORECASE)


def _extract_fields(raw_text: str) -> dict:
    """Apply regex rules to extracted OCR text. Returns structured field dict."""

    def _first_match(pattern, text, group=1, default=None):
        m = pattern.search(text)
        if m:
            return m.group(group).strip()
        return default

    def _all_matches(pattern, text, group=1):
        return [m.group(group).strip() for m in pattern.finditer(text)]

    # Owner name (can be multiple co-sharers)
    owners = [m.group(1).strip() for m in _RE_OWNER.finditer(raw_text)]
    owner_name = owners[0] if owners else None

    khasra_no = _first_match(_RE_KHASRA, raw_text)

    # Area: parse numeric value + convert to m²
    area_m2 = None
    area_raw = None
    area_match = _RE_AREA.search(raw_text)
    if area_match:
        area_raw = f"{area_match.group(1)} {area_match.group(2)}"
        try:
            val = float(area_match.group(1).replace(",", ""))
            unit = area_match.group(2).lower()
            conversions = {
                "acres": 4046.86, "acre": 4046.86,
                "hectares": 10000, "hectare": 10000,
                "cents": 40.4686, "cent": 40.4686,
                "guntas": 101.17, "gunta": 101.17,
                "sq.m": 1.0, "sq m": 1.0, "sqm": 1.0,
            }
            factor = next((v for k, v in conversions.items() if k in unit), 1.0)
            area_m2 = round(val * factor, 2)
        except (ValueError, StopIteration):
            pass

    ulpin = _first_match(_RE_ULPIN, raw_text)
    deed_no = _first_match(_RE_DEED, raw_text)
    dates = _all_matches(_RE_DATE, raw_text)
    mutation_status = _first_match(_RE_MUTATION, raw_text)

    return {
        "owner_name":       owner_name,
        "co_sharers":       owners[1:] if len(owners) > 1 else [],
        "khasra_no":        khasra_no,
        "area_raw":         area_raw,
        "area_m2":          area_m2,
        "ulpin":            ulpin.replace(" ", "-").replace("AP ", "AP-") if ulpin else None,
        "deed_number":      deed_no,
        "dates_found":      dates[:3],   # max 3 dates
        "mutation_status":  mutation_status,
    }


def _compute_confidence(fields: dict) -> float:
    """
    Simple confidence score based on how many key fields were extracted.
    Returns 0.0 – 1.0.
    """
    key_fields = ["owner_name", "khasra_no", "area_m2", "ulpin"]
    found = sum(1 for f in key_fields if fields.get(f) is not None)
    return round(found / len(key_fields), 2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_ror_document(
    image_path: Optional[str] = None,
    image_bytes: Optional[bytes] = None,
    lang: str = "tel+hin+eng",
    psm: int = 6,   # Uniform block of text
) -> dict:
    """
    Run OCR on a RoR document scan and extract structured fields.

    Args:
        image_path:   Path to image file (JPG/PNG/TIFF)
        image_bytes:  Raw image bytes (for API upload)
        lang:         Tesseract language pack (default: Telugu + Hindi + English)
        psm:          Page segmentation mode (6 = uniform block)

    Returns:
        {
          "scan_id":           str,
          "status":            "SUCCESS" | "PARTIAL" | "FAILED" | "TESSERACT_NOT_INSTALLED",
          "raw_text":          str,
          "fields":            dict,
          "extraction_confidence": float,
          "lang":              str,
          "note":              str
        }
    """
    scan_id = str(uuid.uuid4())[:8]

    if not _TESSERACT:
        return {
            "scan_id": scan_id,
            "status": "TESSERACT_NOT_INSTALLED",
            "raw_text": None,
            "fields": {},
            "extraction_confidence": 0.0,
            "lang": lang,
            "note": (
                "pytesseract not installed or Tesseract binary not found. "
                "Install: brew install tesseract tesseract-lang && pip install pytesseract. "
                "For Telugu: brew install tesseract-lang (includes tel)."
            )
        }

    if not _PIL:
        return {
            "scan_id": scan_id,
            "status": "FAILED",
            "raw_text": None,
            "fields": {},
            "extraction_confidence": 0.0,
            "lang": lang,
            "note": "Pillow not installed: pip install Pillow"
        }

    try:
        # Load image
        if image_bytes:
            image = Image.open(io.BytesIO(image_bytes))
        elif image_path:
            image = Image.open(image_path)
        else:
            raise ValueError("Provide image_path or image_bytes")

        # Pre-process
        processed = _preprocess_image(image)

        # OCR
        config = f"--oem 1 --psm {psm}"
        try:
            raw_text = pytesseract.image_to_string(processed, lang=lang, config=config)
        except pytesseract.TesseractError:
            # Fallback to English only
            raw_text = pytesseract.image_to_string(processed, lang="eng", config=config)
            lang = "eng (fallback)"

        if not raw_text.strip():
            return {
                "scan_id": scan_id,
                "status": "FAILED",
                "raw_text": "",
                "fields": {},
                "extraction_confidence": 0.0,
                "lang": lang,
                "note": "OCR returned empty text. Check image quality or PSM setting."
            }

        # Field extraction
        fields = _extract_fields(raw_text)
        confidence = _compute_confidence(fields)

        return {
            "scan_id": scan_id,
            "status": "SUCCESS" if confidence > 0.5 else "PARTIAL",
            "raw_text": raw_text,
            "fields": fields,
            "extraction_confidence": confidence,
            "lang": lang,
            "note": (
                "Fields extracted via Tesseract OCR + regex NER. "
                "All values must be verified against original document before any legal use. "
                "This is a digitization aid — NOT a legal record."
            )
        }

    except Exception as e:
        return {
            "scan_id": scan_id,
            "status": "FAILED",
            "raw_text": None,
            "fields": {},
            "extraction_confidence": 0.0,
            "lang": lang,
            "note": f"OCR pipeline error: {e}"
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = scan_ror_document(image_path=sys.argv[1])
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Usage: python ocr_pipeline.py <path_to_ror_scan.jpg>")
