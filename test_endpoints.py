import requests
import json
import random

BASE_URL = "http://127.0.0.1:8000"
headers = {
    "X-Demo-Email": "admin@example.com",
    "X-Demo-Role": "admin",
    "Content-Type": "application/json"
}

def test_api():
    print("Testing Backend API Endpoints (Admin Role)...\n")
    
    # 0. Get a valid parcel ID
    res = requests.get(f"{BASE_URL}/map/parcels")
    if res.status_code == 200:
        data = res.json()
        target_parcel = data['features'][0]['properties']['parcel_id']
        print(f"✅ Success: Found valid parcel {target_parcel}")
    else:
        print(f"❌ Failed to fetch parcels: {res.status_code} - {res.text}")
        return

    # 1. Test POST /objections
    print(f"\n1. Submitting Objection for Parcel {target_parcel}...")
    payload = {
        "parcel_id": target_parcel,
        "text": "Admin test: There is a massive discrepancy on my eastern boundary.",
        "evidence_photo_ref": "blob:http://localhost:3000/some-fake-uuid"
    }
    res = requests.post(f"{BASE_URL}/objections", json=payload, headers=headers)
    if res.status_code == 200:
        data = res.json()
        print(f"✅ Success: Objection created. ID: {data.get('objection_id')}")
    else:
        print(f"❌ Failed: {res.status_code} - {res.text}")

    # 2. Test GET /objections
    print(f"\n2. Fetching Objections for Parcel {target_parcel}...")
    res = requests.get(f"{BASE_URL}/objections/{target_parcel}", headers=headers)
    if res.status_code == 200:
        objections = res.json()
        print(f"✅ Success: Retrieved {len(objections)} objection(s).")
        for obj in objections:
            print(f"  - {obj['objection_id']}: {obj['text']}")
    else:
        print(f"❌ Failed: {res.status_code} - {res.text}")

if __name__ == "__main__":
    test_api()
