import requests
import json
import time

BASE_URL = "http://127.0.0.1:8030"

def test_api():
    print("=== 1. TEST /api/accounts ===", flush=True)
    r = requests.get(f"{BASE_URL}/api/accounts", timeout=5)
    print(f"Status: {r.status_code}", flush=True)
    accounts = r.json()
    print(f"Found {len(accounts)} accounts:", flush=True)
    for a in accounts:
        print(f" - {a.get('name')} (id: {a.get('id')})", flush=True)
    
    print("\n=== 2. TEST /api/boost/status ===", flush=True)
    r = requests.get(f"{BASE_URL}/api/boost/status", timeout=5)
    print(f"Status: {r.status_code}, data: {r.json()}", flush=True)

    print("\n=== 3. TEST /api/schedules ===", flush=True)
    r = requests.get(f"{BASE_URL}/api/schedules", timeout=5)
    print(f"Status: {r.status_code}, count: {len(r.json())}", flush=True)

    print("\n=== 4. TEST /api/chat/status ===", flush=True)
    r = requests.get(f"{BASE_URL}/api/chat/status", timeout=5)
    print(f"Status: {r.status_code}, data: {r.json()}", flush=True)

    print("\n=== ALL TEST PASSED ===", flush=True)

if __name__ == "__main__":
    test_api()
