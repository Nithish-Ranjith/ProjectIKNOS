import io
import requests
from PIL import Image, ImageDraw, ImageFont

# Simple in-memory cache for MVP to prevent hitting the upstream too hard
# In production, use Redis or local disk cache
TILE_CACHE = {}

def get_wmts_tile(z: int, x: int, y: int) -> bytes:
    """
    Fetches a satellite tile, caches it, and applies a secure watermark.
    """
    cache_key = f"{z}_{x}_{y}"
    if cache_key in TILE_CACHE:
        return TILE_CACHE[cache_key]

    # Upstream open satellite tile provider (ESRI World Imagery as fallback)
    url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            image_data = resp.content
            
            # Open image to apply watermark
            try:
                img = Image.open(io.BytesIO(image_data))
                draw = ImageDraw.Draw(img)
                
                # Add a security watermark
                text = "IKNOS SECURE WMTS"
                draw.text((10, 10), text, fill=(255, 255, 255, 128))
                
                # Save back to bytes
                output = io.BytesIO()
                img.save(output, format="PNG")
                processed_image_data = output.getvalue()
                
                # Cache and return
                TILE_CACHE[cache_key] = processed_image_data
                return processed_image_data
            except Exception as e:
                print(f"WMTS Watermark Error: {e}")
                # Fallback to raw if PIL fails
                TILE_CACHE[cache_key] = image_data
                return image_data
        else:
            # Generate a blank/error tile if upstream fails (256x256)
            return _generate_blank_tile(z, x, y)
    except Exception as e:
        print(f"WMTS Fetch Error: {e}")
        return _generate_blank_tile(z, x, y)

def _generate_blank_tile(z: int, x: int, y: int) -> bytes:
    """Fallback generator for empty or failed tiles"""
    img = Image.new('RGB', (256, 256), color=(20, 24, 34))
    draw = ImageDraw.Draw(img)
    draw.text((50, 120), f"TILE NOT FOUND\nz:{z} x:{x} y:{y}", fill=(100, 100, 100))
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()
