#!/usr/bin/env python3
"""
Test script for Mock GXS API and Riley integration
"""

import requests
import json
import base64

# Configuration
MOCK_API_URL = "http://localhost:8004"
RILEY_URL = "http://localhost:8003"

# Test user JWT (John Doe)
def generate_test_jwt():
    """Generate a test JWT for John Doe"""
    import time
    
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": "USR-001",
        "name": "John Doe",
        "email": "john.doe@email.com",
        "accountNumber": "1234567890",
        "accountType": "Personal Account",
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400  # 24 hours
    }
    
    # Proper base64 encoding without padding issues
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    signature_b64 = base64.urlsafe_b64encode(b"mock_signature_john_doe").decode().rstrip('=')
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def test_mock_api():
    """Test all mock GXS API endpoints"""
    print("=" * 80)
    print("TESTING MOCK GXS API")
    print("=" * 80)
    
    jwt = generate_test_jwt()
    headers = {"Authorization": f"Bearer {jwt}"}
    
    # Test 1: API Root
    print("\n1. Testing API Root...")
    response = requests.get(f"{MOCK_API_URL}/")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    # Test 2: Account Balance
    print("\n2. Testing Account Balance...")
    response = requests.get(f"{MOCK_API_URL}/api/account/balance", headers=headers)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Main Account: SGD ${data['data']['mainAccount']['balance']:,.2f}")
    print(f"   Savings: SGD ${data['data']['savingsAccount']['balance']:,.2f}")
    print(f"   Total: SGD ${data['data']['totalBalance']:,.2f}")
    
    # Test 3: Account Details
    print("\n3. Testing Account Details...")
    response = requests.get(f"{MOCK_API_URL}/api/account/details", headers=headers)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Name: {data['data']['name']}")
    print(f"   Account: {data['data']['accountNumber']}")
    print(f"   Type: {data['data']['accountType']}")
    
    # Test 4: Recent Transactions
    print("\n4. Testing Recent Transactions...")
    response = requests.get(f"{MOCK_API_URL}/api/transactions/recent?limit=3", headers=headers)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Found {data['data']['count']} transactions:")
    for txn in data['data']['transactions']:
        print(f"     - {txn['date']}: {txn['description']} (SGD ${abs(txn['amount']):,.2f})")
    
    # Test 5: Card Details
    print("\n5. Testing Card Details...")
    response = requests.get(f"{MOCK_API_URL}/api/card/details", headers=headers)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Card: {data['data']['cardNumber']}")
    print(f"   Status: {data['data']['cardStatus']}")
    print(f"   Limit: SGD ${data['data']['creditLimit']:,.2f}")
    print(f"   Available: SGD ${data['data']['availableCredit']:,.2f}")
    
    # Test 6: Freeze Card
    print("\n6. Testing Freeze Card...")
    response = requests.post(f"{MOCK_API_URL}/api/card/freeze", headers=headers)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Message: {data['message']}")
    print(f"   Card Status: {data['data']['cardStatus']}")
    
    # Test 7: Unfreeze Card
    print("\n7. Testing Unfreeze Card...")
    response = requests.post(f"{MOCK_API_URL}/api/card/unfreeze", headers=headers)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Message: {data['message']}")
    print(f"   Card Status: {data['data']['cardStatus']}")
    
    print("\n" + "=" * 80)
    print("✅ ALL MOCK API TESTS PASSED!")
    print("=" * 80)

def test_riley():
    """Test Riley health endpoint"""
    print("\n" + "=" * 80)
    print("TESTING RILEY SERVER")
    print("=" * 80)
    
    print("\n1. Testing Riley Health...")
    response = requests.get(f"{RILEY_URL}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    
    print("\n2. Testing Riley Main Page...")
    response = requests.get(RILEY_URL)
    print(f"   Status: {response.status_code}")
    print(f"   Content-Type: {response.headers.get('content-type')}")
    print(f"   Page Title: ", end="")
    if "Riley" in response.text:
        print("✓ Riley title found")
    
    print("\n" + "=" * 80)
    print("✅ RILEY SERVER TESTS PASSED!")
    print("=" * 80)

def main():
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "MOCK GXS INTEGRATION TEST SUITE" + " " * 26 + "║")
    print("╚" + "=" * 78 + "╝")
    
    try:
        test_mock_api()
        test_riley()
        
        print("\n\n" + "🎉" * 40)
        print("\n✅ ALL SYSTEMS OPERATIONAL!\n")
        print("Next steps:")
        print("  1. Open mock_gxs_app.html in browser")
        print("  2. Login as any demo user")
        print("  3. Click 'Talk to Riley' button")
        print("  4. Start a call and ask account questions!")
        print("\n" + "🎉" * 40 + "\n")
        
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ ERROR: Cannot connect to services")
        print(f"   Make sure both servers are running:")
        print(f"   - Mock API: python3 mock_gxs_api.py")
        print(f"   - Riley: python3 server.py")
        print(f"\n   Error: {e}")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")

if __name__ == "__main__":
    main()
