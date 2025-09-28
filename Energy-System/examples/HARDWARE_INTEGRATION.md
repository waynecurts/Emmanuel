# Hardware Integration Guide for Energy Intelligence Platform

This guide explains how to integrate hardware sensors with the Energy Intelligence platform to collect and transmit real-time energy data.

## Overview

The Energy Intelligence platform provides API endpoints that allow IoT devices and sensors to send energy data directly to the application. This enables real-time monitoring, analysis, and predictions based on actual energy measurements from your facility.

## API Endpoints

The platform exposes the following endpoints for hardware integration:

### 1. Send Sensor Data

**Endpoint:** `/api/hardware/data`
**Method:** POST
**Authentication:** X-API-Key header

Use this endpoint to send energy data from your sensors to the platform.

**Required Data Fields:**
- `energy_produced` (float): Amount of energy produced in kWh
- `energy_consumed` (float): Amount of energy consumed in kWh
- `current_load` (float): Current energy load in kW

**Optional Electrical Parameters:**
- `voltage` (float): Voltage level in Volts (V)
- `current` (float): Current in Amperes (A)
- `frequency` (float): Frequency in Hertz (Hz)
- `power_factor` (float): Power factor (0-1)

**Example Request:**
```http
POST /api/hardware/data HTTP/1.1
Host: your-energy-intelligence-server.com
Content-Type: application/json
X-API-Key: your_api_key_here

{
  "energy_produced": 75.45,
  "energy_consumed": 62.30,
  "current_load": 35.80,
  "voltage": 220.5,
  "current": 15.2,
  "frequency": 50.0,
  "power_factor": 0.95
}
```

**Example Response:**
```json
{
  "status": "success",
  "message": "Data received successfully",
  "data_id": 123,
  "alert": {
    "message": "High voltage condition: 245.2V",
    "level": "warning"
  }
}
```

**Note:** The `alert` field will only be present in the response if a voltage condition is detected.
Alert levels include:
- `warning`: For voltage outside the recommended range but not critical
- `critical`: For voltage conditions that require immediate attention

### 2. Get Configuration

**Endpoint:** `/api/hardware/config`
**Method:** GET
**Authentication:** X-API-Key header

Use this endpoint to retrieve configuration settings for your hardware device.

**Example Request:**
```http
GET /api/hardware/config HTTP/1.1
Host: your-energy-intelligence-server.com
X-API-Key: your_api_key_here
```

**Example Response:**
```json
{
  "status": "success",
  "config": {
    "facility_id": 1,
    "reporting_interval": 300,
    "power_save_mode": false,
    "data_fields": ["energy_produced", "energy_consumed", "current_load"],
    "electrical_monitoring": {
      "enabled": true,
      "voltage_monitoring": true,
      "nominal_voltage": 220,
      "voltage_high_threshold": 242,
      "voltage_low_threshold": 198,
      "voltage_critical_high": 253,
      "voltage_critical_low": 187
    }
  }
}
```

### 3. Check Status

**Endpoint:** `/api/hardware/status`
**Method:** GET
**Authentication:** X-API-Key header

Use this endpoint to verify connectivity with the server.

**Example Request:**
```http
GET /api/hardware/status HTTP/1.1
Host: your-energy-intelligence-server.com
X-API-Key: your_api_key_here
```

**Example Response:**
```json
{
  "status": "success",
  "server_time": "2025-04-19T13:45:22.123456",
  "message": "System online and ready to receive data"
}
```

## Hardware Requirements

To integrate with the Energy Intelligence platform, you'll need:

1. An IoT device with internet connectivity (e.g., ESP8266, ESP32, Raspberry Pi)
2. Energy sensors capable of measuring:
   - Energy production (for renewable sources)
   - Energy consumption
   - Current load
3. For advanced electrical monitoring (optional):
   - Voltage sensors (for voltage monitoring and alerts)
   - Current sensors
   - Frequency meter
   - Power factor monitoring

## Example Implementations

We provide example code for common hardware platforms:

1. **ESP8266/ESP32**: See `esp8266_sensor_client.ino`
2. **Python (for Raspberry Pi or testing)**: See `python_sensor_client.py`

## Security Considerations

1. Keep your API key secure and don't hardcode it in publicly accessible code
2. Use HTTPS for production deployments to encrypt data transmission
3. Update the firmware of your IoT devices regularly
4. Consider implementing additional authentication if deploying in sensitive environments

## Troubleshooting

If you encounter issues with the hardware integration:

1. Check your internet connectivity
2. Verify that your API key is valid
3. Ensure that your device time is synchronized (for timestamped data)
4. Check the server logs for error messages
5. Validate the format of your JSON payload

## Support

For technical support with hardware integration, contact the Energy Intelligence support team.

---

This guide provides basic information for hardware integration. For more advanced scenarios or custom integrations, please refer to the full API documentation or contact our development team.