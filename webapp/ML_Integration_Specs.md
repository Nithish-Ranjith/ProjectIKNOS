# ML Integration Specifications & Stubs

This document outlines the exact data contracts, endpoints, and frontend components that interact with the U-Net Boundary Extraction model and dataset.

Because the real dataset and fine-tuned model will be added soon, the frontend and backend are designed to use these **exact contracts** right now with stubbed/mock responses. When the real model is plugged in, *zero frontend changes will be required*.

## 1. Inference Endpoint Contract
The frontend expects a specific route to handle inference.

**Endpoint:** `POST /missions/:mission_id/process` (or a dedicated `/inference/boundary`)

**Request Payload (from Frontend):**
```json
{
  "image_uri": "s3://terratrace/mission-123/orthomosaic_tile_4.tif",
  "bounding_box": [79.432, 11.234, 79.435, 11.237]
}
```

**Expected Response (from U-Net Backend):**
The backend must run inference and return the probability mask converted to a valid `GeoJSON` Polygon, along with confidence metrics.
```json
{
  "status": "success",
  "inference_id": "inf-847294",
  "predicted_boundary": {
    "type": "Feature",
    "geometry": {
      "type": "Polygon",
      "coordinates": [
        [ [79.4321, 11.2345], [79.4342, 11.2345], [79.4342, 11.2367], [79.4321, 11.2345] ]
      ]
    }
  },
  "confidence_score": 0.94,
  "metrics": {
    "iou": 0.88
  }
}
```

## 2. Spatial Comparison Stub
Once the U-Net boundary is returned, it must be compared against the existing cadastral boundary.

**Endpoint:** `GET /cases/:id/geometry-layers`
**Response:**
```json
{
  "cadastral": { /* GeoJSON */ },
  "ai_boundary": { /* GeoJSON from U-Net */ },
  "discrepancy": {
    "area_diff_pct": 7.3,
    "boundary_shift_m": 2.4
  }
}
```

## 3. Frontend Implementation Strategy (For Real-time Sync)
In the frontend, we use standard fetch states for this integration:
- `loading`: While the U-Net model runs, a spinner and "Analyzing boundary pixels..." is shown.
- `error`: If the ML server times out (or throws an OOM error during inference), the actual HTTP error is bubbled up to the user.
- `success`: The `predicted_boundary` GeoJSON is immediately passed to the `Mapbox GL JS` layer state to overlay on the map.

*Note: For the MVP we will use stubbed data returning the above JSON structure. Once the ML backend is deployed, you simply switch the `VITE_API_BASE_URL` and the frontend will instantly ingest the real predictions without refactoring.*
