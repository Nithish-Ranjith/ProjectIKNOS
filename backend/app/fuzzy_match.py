"""
backend/app/fuzzy_match.py — Jaro-Winkler fuzzy matching for text records.

Design contracts:
  - Used for strings like owner_name, khasra_no when ULPIN is missing.
  - Returns explicit MATCHED / AMBIGUOUS / UNRESOLVED states.
  - Never forces an ambiguous match.
  - Pure rule-based algorithm — deliberately NOT a trained deep learning model.
"""
from typing import Optional

def jaro_winkler(s1: str, s2: str) -> float:
    """
    Compute Jaro-Winkler similarity between two strings.
    Returns 0.0 to 1.0.
    """
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    len1, len2 = len(s1), len(s2)
    match_distance = max(len1, len2) // 2 - 1

    matches = 0
    hash1 = [0] * len1
    hash2 = [0] * len2

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(len2, i + match_distance + 1)
        for j in range(start, end):
            if hash2[j] == 0 and s1[i] == s2[j]:
                hash1[i] = 1
                hash2[j] = 1
                matches += 1
                break

    if matches == 0:
        return 0.0

    t = 0
    point = 0
    for i in range(len1):
        if hash1[i]:
            while hash2[point] == 0:
                point += 1
            if s1[i] != s2[point]:
                t += 1
            point += 1
    t //= 2

    # Jaro similarity
    jaro = (matches / len1 + matches / len2 + (matches - t) / matches) / 3.0

    # Winkler prefix scaling (max 4 characters)
    prefix = 0
    for i in range(min(len1, len2)):
        if s1[i] == s2[i]:
            prefix += 1
            if prefix == 4:
                break
        else:
            break

    # Standard Winkler scale factor is 0.1
    return jaro + prefix * 0.1 * (1.0 - jaro)


def match_record_fields(
    name1: Optional[str], name2: Optional[str],
    id1: Optional[str], id2: Optional[str]
) -> dict:
    """
    Match two records based on name and ID (e.g., Khasra number).
    Returns {"status": MatchStatus, "similarity": float, "reason": str}.
    """
    # Normalize inputs
    n1 = (name1 or "").strip().lower()
    n2 = (name2 or "").strip().lower()
    i1 = (id1 or "").strip().lower()
    i2 = (id2 or "").strip().lower()

    if not n1 and not n2 and not i1 and not i2:
        return {"status": "UNRESOLVED", "similarity": 0.0, "reason": "No valid input strings"}

    # Exact ID match is a strong signal
    id_match = False
    if i1 and i2:
        if i1 == i2:
            id_match = True
        else:
            # For IDs/numbers, any difference is generally a non-match, we don't fuzzy match them
            return {"status": "UNRESOLVED", "similarity": 0.0, "reason": f"IDs do not match: {i1} != {i2}"}

    # If only IDs are available and they match
    if not n1 or not n2:
        if id_match:
            return {"status": "MATCHED", "similarity": 1.0, "reason": "Exact ID match, names missing"}
        return {"status": "UNRESOLVED", "similarity": 0.0, "reason": "Missing fields"}

    # Fuzzy match names
    name_sim = jaro_winkler(n1, n2)

    if name_sim >= 0.90:
        if i1 and i2 and id_match:
            return {"status": "MATCHED", "similarity": name_sim, "reason": "Strong name match and exact ID match"}
        if not i1 and not i2:
            return {"status": "MATCHED", "similarity": name_sim, "reason": "Strong name match, IDs missing"}
        # If we have one ID but not the other, it's ambiguous despite strong name match
        return {"status": "AMBIGUOUS", "similarity": name_sim, "reason": "Strong name match but missing corroborating ID"}

    elif name_sim >= 0.75:
        if id_match:
            return {"status": "MATCHED", "similarity": name_sim, "reason": "Plausible name match corroborated by exact ID"}
        return {"status": "AMBIGUOUS", "similarity": name_sim, "reason": "Name match too weak without ID corroboration"}

def levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def levenshtein_similarity(s1: str, s2: str) -> float:
    if not s1 or not s2: return 0.0
    dist = levenshtein(s1, s2)
    max_len = max(len(s1), len(s2))
    return 1.0 - (dist / max_len)

def multi_field_fuzzy_score(record_a: dict, record_b: dict) -> dict:
    """
    Score multiple fields (owner, khasra, area) and combine using weighted sum.
    Fallback to Levenshtein if Jaro-Winkler score is borderline.
    """
    owner_a = str(record_a.get("owner_name", "")).strip().lower()
    owner_b = str(record_b.get("owner_name", "")).strip().lower()
    khasra_a = str(record_a.get("khasra_no", "")).strip().lower()
    khasra_b = str(record_b.get("khasra_no", "")).strip().lower()
    
    # 1. Owner Name Matching
    name_score = jaro_winkler(owner_a, owner_b)
    if 0.70 < name_score < 0.85:
        # Fallback to Levenshtein for borderline cases (e.g. slight typos)
        lev_score = levenshtein_similarity(owner_a, owner_b)
        name_score = max(name_score, lev_score)
        
    # 2. Khasra Match
    khasra_score = 0.0
    if khasra_a and khasra_b:
        khasra_score = 1.0 if khasra_a == khasra_b else 0.0
        
    # 3. Area Match (allow 5% tolerance)
    area_score = 0.0
    area_a = float(record_a.get("area_m2") or 0.0)
    area_b = float(record_b.get("area_m2") or 0.0)
    if area_a > 0 and area_b > 0:
        diff_pct = abs(area_a - area_b) / max(area_a, area_b)
        area_score = 1.0 if diff_pct <= 0.05 else (1.0 - diff_pct if diff_pct < 0.5 else 0.0)
        
    # Weighted combination
    weights = {"name": 0.5, "khasra": 0.3, "area": 0.2}
    total_score = (name_score * weights["name"]) + (khasra_score * weights["khasra"]) + (area_score * weights["area"])
    
    status = "UNRESOLVED"
    if total_score >= 0.85:
        status = "MATCHED"
    elif total_score >= 0.65:
        status = "AMBIGUOUS"
        
    return {
        "status": status,
        "combined_score": round(total_score, 3),
        "component_scores": {
            "name": round(name_score, 3),
            "khasra": round(khasra_score, 3),
            "area": round(area_score, 3)
        }
    }
