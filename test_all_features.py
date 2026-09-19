import requests
import json
import time

BASE_URL = "http://127.0.0.1:8030"

def test_api():
    print("=== 1. TEST /api/accounts ===")
    r = requests.get(f"{BASE_URL}/api/accounts")
    print(f"Status: {r.status_code}")
    accounts = r.json()
    print(f"Found {len(accounts)} accounts:")
    for a in accounts:
        print(f" - {a.get('name')} (id: {a.get('id')}, profile: {a.get('profile_dir')})")
    
    if not accounts:
        print("No accounts configured.")
        return

    account_id = accounts[0]["id"]

    print("\n=== 2. TEST /api/boost/status ===")
    r = requests.get(f"{BASE_URL}/api/boost/status")
    print(f"Status: {r.status_code}, data: {r.json()}")

    print("\n=== 3. TEST /api/boost/products ===")
    try:
        r = requests.get(f"{BASE_URL}/api/boost/products?account_id={account_id}", timeout=60)
        print(f"Status: {r.status_code}")
        products = r.json()
        print(f"Received {len(products)} products.")
        if products and len(products) > 0:
            print(f"Sample product: {products[0]}")
    except Exception as e:
        print(f"Error fetching boost products: {e}")

    print("\n=== 4. TEST /api/flashsale/products ===")
    try:
        r = requests.get(f"{BASE_URL}/api/flashsale/products?account_id={account_id}", timeout=60)
        print(f"Status: {r.status_code}")
        fs_products = r.json()
        print(f"Received {len(fs_products)} flashsale products.")
    except Exception as e:
        print(f"Error fetching flashsale products: {e}")

    print("\n=== 5. TEST /api/schedules ===")
    r = requests.get(f"{BASE_URL}/api/schedules")
    print(f"Status: {r.status_code}, count: {len(r.json())}")

    print("\n=== 6. TEST /api/chat/status ===")
    r = requests.get(f"{BASE_URL}/api/chat/status")
    print(f"Status: {r.status_code}, data: {r.json()}")

    print("\n=== ALL BASIC API TESTS COMPLETED ===")

if __name__ == "__main__":
    test_api()
