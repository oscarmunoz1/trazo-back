#!/usr/bin/env python3
"""
Frontend Integration Test Script for John Deere API

This script tests the John Deere integration endpoints that the frontend will use.
Run this to verify everything is working before testing in the UI.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_iot_device_status():
    """Test IoT device status endpoint"""
    print("🔍 Testing IoT Device Status...")
    
    url = f"{BASE_URL}/carbon/iot-devices/device_status/"
    params = {"establishment_id": 1}
    
    try:
        response = requests.get(url, params=params)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Found {data.get('summary', {}).get('total_devices', 0)} devices")
            return True
        else:
            print(f"   ❌ Error: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")
        return False

def test_simulate_john_deere_data():
    """Test John Deere data simulation"""
    print("\n🚜 Testing John Deere Data Simulation...")
    
    url = f"{BASE_URL}/carbon/iot-devices/simulate_data/"
    data = {
        "establishment_id": 1,
        "device_type": "fuel_sensor"
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            print(f"   ✓ Simulated: {result.get('message', 'Data created')}")
            print(f"   ✓ Data Point ID: {result.get('data_point_id')}")
            return True
        else:
            print(f"   ❌ Error: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")
        return False

def test_pending_events():
    """Test pending events endpoint"""
    print("\n📋 Testing Pending Events...")
    
    url = f"{BASE_URL}/carbon/iot-devices/pending_events/"
    params = {"establishment_id": 1}
    
    try:
        response = requests.get(url, params=params)
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            pending_count = data.get('total_count', 0)
            auto_processed = data.get('auto_processed_count', 0)
            
            print(f"   ✓ Pending Events: {pending_count}")
            print(f"   ✓ Auto-Processed: {auto_processed}")
            
            if pending_count > 0:
                print("   📝 Sample Event:")
                event = data['pending_events'][0]
                print(f"      - Type: {event.get('event_type')}")
                print(f"      - Device: {event.get('device_name')}")
                print(f"      - Confidence: {event.get('confidence', 0):.2f}")
            
            return True
        else:
            print(f"   ❌ Error: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")
        return False

def test_john_deere_auth_endpoints():
    """Test John Deere authentication endpoints"""
    print("\n🔐 Testing John Deere Auth Endpoints...")
    
    # Test auth start endpoint
    url = f"{BASE_URL}/carbon/john-deere/auth/"
    
    try:
        response = requests.get(url)
        print(f"   Auth Start Status: {response.status_code}")
        
        if response.status_code in [200, 503]:  # 503 expected without credentials
            print("   ✓ Auth endpoint accessible")
            return True
        else:
            print(f"   ❌ Unexpected response: {response.text}")
            return False
    except Exception as e:
        print(f"   ❌ Connection Error: {e}")
        return False

def main():
    """Run all frontend integration tests"""
    print("🧪 Frontend Integration Tests for John Deere API\n")
    
    tests = [
        test_iot_device_status,
        test_simulate_john_deere_data,
        test_pending_events,
        test_john_deere_auth_endpoints
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            time.sleep(1)  # Brief pause between tests
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Frontend integration is ready.")
        print("\n📋 Next Steps:")
        print("   1. Open http://localhost:3001 in your browser")
        print("   2. Navigate to an establishment's IoT Dashboard")
        print("   3. Look for 'Simulate Data' or 'Test Equipment' buttons")
        print("   4. Test the John Deere equipment simulation")
        print("   5. Check the Pending Events section for approval workflow")
    else:
        print("⚠️  Some tests failed. Check Django server is running on port 8000")
    
    return passed == total

if __name__ == "__main__":
    main() 