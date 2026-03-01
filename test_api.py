
import requests
import json
from datetime import datetime, timezone

url = "http://localhost:5001/api/traffic/add"
payload = {
    "gate_id": "A",
    "count_in": 12,
    "count_out": 4,
    "source": "test_script",
    "timestamp": datetime.now(timezone.utc).isoformat()
}

headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
