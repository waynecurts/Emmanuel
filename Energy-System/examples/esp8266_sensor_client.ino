/*
 * ESP8266/ESP32 Energy Sensor Client for Energy Intelligence Platform
 * 
 * This example shows how to send energy data from an ESP8266/ESP32 
 * to the Energy Intelligence application.
 * 
 * Hardware requirements:
 * - ESP8266 or ESP32 board
 * - Energy sensors connected to ADC or digital pins
 */

#include <Arduino.h>

#if defined(ESP8266)
  #include <ESP8266WiFi.h>
  #include <ESP8266HTTPClient.h>
  #include <WiFiClient.h>
#elif defined(ESP32)
  #include <WiFi.h>
  #include <HTTPClient.h>
  #include <WiFiClient.h>
#else
  #error "This code is intended for ESP8266 or ESP32 boards only"
#endif

// WiFi credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Energy Intelligence API settings
const char* serverUrl = "http://your-energy-intelligence-server.com";  // Replace with your server URL
const char* apiKey = "dev_hardware_key";  // Replace with your actual API key

// Sensor pins
const int voltageSensorPin = A0;  // Analog pin for voltage sensor
const int currentSensorPin = A1;  // Analog pin for current sensor

// Calibration values (adjust based on your sensors)
const float voltageCalibration = 0.01;  // Voltage sensor calibration factor
const float currentCalibration = 0.01;  // Current sensor calibration factor

// Reporting interval (in milliseconds)
const unsigned long reportInterval = 300000;  // 5 minutes
unsigned long lastReportTime = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("Energy Intelligence Sensor Client");
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println();
  Serial.print("Connected to WiFi. IP address: ");
  Serial.println(WiFi.localIP());
  
  // Initialize sensors
  pinMode(voltageSensorPin, INPUT);
  pinMode(currentSensorPin, INPUT);
  
  // Get initial configuration from server
  getServerConfig();
}

void loop() {
  // Check if it's time to report data
  unsigned long currentTime = millis();
  if (currentTime - lastReportTime >= reportInterval) {
    // Read sensor data
    float energyProduced = readEnergyProduced();
    float energyConsumed = readEnergyConsumed();
    float currentLoad = readCurrentLoad();
    
    // Send data to server
    sendSensorData(energyProduced, energyConsumed, currentLoad);
    
    // Update last report time
    lastReportTime = currentTime;
  }
  
  // Other sensor monitoring tasks can go here
  
  delay(1000);  // Small delay to prevent CPU hogging
}

// Read energy produced from sensors (example implementation)
float readEnergyProduced() {
  // In a real implementation, this would read from actual sensors
  // For this example, we'll simulate solar panel output based on time of day
  int hour = getHourOfDay();
  if (hour >= 6 && hour <= 18) {
    // Daytime - produce more energy
    return random(50, 100);  // 50-100 kWh
  } else {
    // Nighttime - produce less energy
    return random(0, 10);    // 0-10 kWh
  }
}

// Read energy consumed from sensors (example implementation)
float readEnergyConsumed() {
  // In a real implementation, this would read from actual energy meters
  // For this example, we'll simulate energy consumption
  int analogValue = analogRead(currentSensorPin);
  float current = analogValue * currentCalibration;
  float voltage = analogRead(voltageSensorPin) * voltageCalibration;
  
  // Calculate power and convert to energy
  float power = voltage * current;
  float energy = power * (reportInterval / 3600000.0);  // Convert to kWh
  
  return energy;
}

// Read current load from sensors (example implementation)
float readCurrentLoad() {
  // In a real implementation, this would read from actual load sensors
  // For this example, we'll simulate based on current reading
  int analogValue = analogRead(currentSensorPin);
  return analogValue * currentCalibration * 10;  // Scale for demonstration
}

// Send sensor data to the Energy Intelligence server
void sendSensorData(float energyProduced, float energyConsumed, float currentLoad) {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;
    
    // Prepare URL
    String url = String(serverUrl) + "/api/hardware/data";
    
    // Start HTTP request
    http.begin(client, url);
    
    // Add headers
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-API-Key", apiKey);
    
    // Prepare JSON data
    String jsonData = "{";
    jsonData += "\"energy_produced\":" + String(energyProduced, 2) + ",";
    jsonData += "\"energy_consumed\":" + String(energyConsumed, 2) + ",";
    jsonData += "\"current_load\":" + String(currentLoad, 2);
    jsonData += "}";
    
    // Send POST request
    int httpResponseCode = http.POST(jsonData);
    
    // Check response
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println("HTTP Response code: " + String(httpResponseCode));
      Serial.println("Response: " + response);
    } else {
      Serial.print("Error on sending POST: ");
      Serial.println(httpResponseCode);
    }
    
    // Close connection
    http.end();
  } else {
    Serial.println("WiFi Disconnected. Reconnecting...");
    WiFi.reconnect();
  }
}

// Get configuration from the server
void getServerConfig() {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;
    
    // Prepare URL
    String url = String(serverUrl) + "/api/hardware/config";
    
    // Start HTTP request
    http.begin(client, url);
    
    // Add headers
    http.addHeader("X-API-Key", apiKey);
    
    // Send GET request
    int httpResponseCode = http.GET();
    
    // Check response
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println("Config Response: " + response);
      
      // In a real implementation, parse JSON and update local settings
      // This would update reporting interval, power save mode, etc.
    } else {
      Serial.print("Error getting config: ");
      Serial.println(httpResponseCode);
    }
    
    // Close connection
    http.end();
  }
}

// Helper function to get current hour (0-23)
int getHourOfDay() {
  // In a real implementation, this would use NTP to get actual time
  // For this example, we'll estimate based on millis
  return (millis() / 3600000) % 24;
}