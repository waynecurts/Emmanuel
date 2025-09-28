#!/usr/bin/env python3
"""
Python Test Client for Energy Intelligence Hardware API

This script demonstrates how to send energy data to the
Energy Intelligence application using Python requests library.
It can be used for testing or as a basis for integration with
other Python-based energy monitoring systems.
"""
import requests  # Corrected import statement
import json
import time
import random
from datetime import datetime
# API Configuration
SERVER_URL = "http://localhost:5000"  # Change to your server URL (for ngrok use: https://your-ngrok-url.ngrok.io)
API_KEY = "dev_hardware_key"  # Change to your API key
# Reporting configuration
REPORT_INTERVAL = 300  # seconds (5 minutes

def get_server_config():
    """Get configuration from the server"""
    headers = {
        "X-API-Key": API_KEY
    }
    
    try:
        response = requests.get(f"{SERVER_URL}/api/hardware/config", headers=headers)
        
        if response.status_code == 200:
            config = response.json()
            print("Server configuration received:")
            print(json.dumps(config, indent=2))
            return config
        else:
            print(f"Error getting config: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def check_server_status():
    """Check if the server is online"""
    headers = {
        "X-API-Key": API_KEY
    }
    
    try:
        response = requests.get(f"{SERVER_URL}/api/hardware/status", headers=headers)
        
        if response.status_code == 200:
            status = response.json()
            print("Server status:")
            print(json.dumps(status, indent=2))
            return True
        else:
            print(f"Error checking status: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Connection error: {e}")
        return False

def send_sensor_data(energy_produced, energy_consumed, current_load, voltage=None, current=None, frequency=None, power_factor=None):
    """Send energy data to the server"""
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    # Build the data dictionary
    data = {
        "energy_produced": energy_produced,
        "energy_consumed": energy_consumed,
        "current_load": current_load
    }
    
    # Add optional electrical parameters if provided
    if voltage is not None:
        data["voltage"] = voltage
    if current is not None:
        data["current"] = current
    if frequency is not None:
        data["frequency"] = frequency
    if power_factor is not None:
        data["power_factor"] = power_factor
    
    try:
        response = requests.post(
            f"{SERVER_URL}/api/hardware/data", 
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"Data sent successfully. Response: {result}")
            
            # Check if there's an alert
            if 'alert' in result:
                alert = result['alert']
                if alert['level'] == 'critical':
                    print(f"\n⚠️ CRITICAL ALERT: {alert['message']}")
                elif alert['level'] == 'warning':
                    print(f"\n⚠️ WARNING: {alert['message']}")
                elif alert['level'] == 'info':
                    print(f"\nℹ️ INFO: {alert['message']}")
            
            return True
        else:
            print(f"Error sending data: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Connection error: {e}")
        return False

def simulate_energy_readings():
    """Simulate energy sensor readings"""
    # Get the current hour to simulate day/night solar production
    current_hour = datetime.now().hour
    
    # Simulate solar energy production (more during day, less at night)
    if 6 <= current_hour <= 18:
        # Daytime production
        energy_produced = random.uniform(50.0, 100.0)
    else:
        # Nighttime production
        energy_produced = random.uniform(0.0, 10.0)
    
    # Simulate energy consumption
    energy_consumed = random.uniform(30.0, 80.0)
    
    # Simulate current load
    current_load = random.uniform(20.0, 60.0)
    
    # Simulate electrical parameters
    # Normal voltage is around 220V but we'll occasionally generate anomalies
    voltage_anomaly = random.randint(1, 100)  # 1% chance of critical, 5% chance of warning
    
    if voltage_anomaly <= 1:  # Critical high voltage
        voltage = random.uniform(250.0, 260.0)
    elif voltage_anomaly <= 3:  # High voltage warning
        voltage = random.uniform(240.0, 250.0)
    elif voltage_anomaly <= 5:  # Critical low voltage
        voltage = random.uniform(180.0, 190.0)
    elif voltage_anomaly <= 10:  # Low voltage warning
        voltage = random.uniform(190.0, 200.0)
    else:  # Normal voltage
        voltage = random.uniform(215.0, 225.0)
    
    # Other electrical parameters
    current = random.uniform(5.0, 20.0)  # Amperes
    frequency = random.uniform(49.8, 50.2)  # Hz (for 50Hz systems)
    power_factor = random.uniform(0.8, 1.0)  # Power factor (0.8-1.0)
    
    return energy_produced, energy_consumed, current_load, voltage, current, frequency, power_factor

def main():
    """Main function to run the test client"""
    print("Energy Intelligence Python Test Client")
    print("=====================================")
    
    # Check if server is online
    if not check_server_status():
        print("Cannot connect to server. Exiting.")
        return
    
    # Get initial configuration
    config = get_server_config()
    
    # If config was received successfully, we can use its values
    if config and "config" in config and "reporting_interval" in config["config"]:
        report_interval = config["config"]["reporting_interval"]
    else:
        report_interval = REPORT_INTERVAL
    
    print(f"\nSending simulated data every {report_interval} seconds. Press Ctrl+C to stop.\n")
    
    try:
        while True:
            # Get simulated energy readings with electrical parameters
            energy_produced, energy_consumed, current_load, voltage, current, frequency, power_factor = simulate_energy_readings()
            
            print(f"\nTime: {datetime.now().isoformat()}")
            print(f"Energy Produced: {energy_produced:.2f} kWh")
            print(f"Energy Consumed: {energy_consumed:.2f} kWh")
            print(f"Current Load: {current_load:.2f} kW")
            print(f"Voltage: {voltage:.1f}V")
            print(f"Current: {current:.1f}A")
            print(f"Frequency: {frequency:.1f}Hz")
            print(f"Power Factor: {power_factor:.2f}")
            
            # Send data to server with electrical parameters
            send_sensor_data(
                energy_produced, 
                energy_consumed, 
                current_load,
                voltage=voltage,
                current=current,
                frequency=frequency,
                power_factor=power_factor
            )
            
            # Wait for the next reporting interval
            time.sleep(report_interval)
    except KeyboardInterrupt:
        print("\nClient stopped by user")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()