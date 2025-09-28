
#!/usr/bin/env python3
"""
Test script to verify hardware connection to Energy Intelligence platform
"""
import requests
import json
import sys

def test_hardware_connection(server_url, api_key):
    """Test hardware connection with the server"""
    print(f"Testing connection to: {server_url}")
    print(f"Using API key: {api_key}")
    print("-" * 50)
    
    # Test 1: Check server status
    print("1. Testing server status...")
    try:
        response = requests.get(
            f"{server_url}/api/hardware/status",
            headers={"X-API-Key": api_key},
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Server is online and accessible")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Server status check failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False
    
    # Test 2: Send test data
    print("\n2. Testing data submission...")
    test_data = {
        "energy_produced": 75.5,
        "energy_consumed": 62.3,
        "current_load": 35.8,
        "voltage": 220.5,
        "current": 15.2,
        "frequency": 50.0,
        "power_factor": 0.95
    }
    
    try:
        response = requests.post(
            f"{server_url}/api/hardware/data",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": api_key
            },
            json=test_data,
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Data submission successful")
            result = response.json()
            print(f"   Response: {result}")
            if 'alert' in result:
                print(f"   Alert: {result['alert']}")
        else:
            print(f"❌ Data submission failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Data submission failed: {e}")
        return False
    
    # Test 3: Get configuration
    print("\n3. Testing configuration retrieval...")
    try:
        response = requests.get(
            f"{server_url}/api/hardware/config",
            headers={"X-API-Key": api_key},
            timeout=10
        )
        if response.status_code == 200:
            print("✅ Configuration retrieval successful")
            print(f"   Config: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"❌ Configuration retrieval failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Configuration retrieval failed: {e}")
        return False
    
    print("\n✅ All tests passed! Hardware connection is working correctly.")
    return True

if __name__ == "__main__":
    # Default values
    server_url = "http://localhost:5000"
    api_key = "dev_hardware_key"
    
    # Check command line arguments
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    if len(sys.argv) > 2:
        api_key = sys.argv[2]
    
    print("Energy Intelligence Hardware Connection Test")
    print("=" * 50)
    
    if not test_hardware_connection(server_url, api_key):
        print("\n❌ Hardware connection test failed!")
        sys.exit(1)
    else:
        print("\n🎉 Hardware connection test completed successfully!")
