"""
ML Predictor module for energy consumption forecasting
"""
import numpy as np
from datetime import datetime, timedelta

class EnergyPredictor:
    """
    Simple energy consumption predictor using historical data patterns
    """
    def __init__(self):
        self.is_trained = False
        self.hourly_patterns = None
        self.daily_patterns = None
        self.baseline = None
        self.validation_score = None
    
    def train(self, historical_data):
        """
        Train the predictor on historical energy data
        Returns: validation score (mean absolute percentage error)
        """
        if len(historical_data) < 24:
            return 0
        
        # Extract consumption values and timestamps
        consumption = np.array([d['energy_consumed'] for d in historical_data])
        timestamps = [d['timestamp'] for d in historical_data]
        
        # Calculate baseline (average consumption)
        self.baseline = np.mean(consumption)
        
        # Extract hourly patterns (how consumption varies by hour of day)
        self.hourly_patterns = {}
        for i, ts in enumerate(timestamps):
            hour = ts.hour
            if hour not in self.hourly_patterns:
                self.hourly_patterns[hour] = []
            
            # Store relative value (compared to baseline)
            self.hourly_patterns[hour].append(consumption[i] / max(1, self.baseline))
        
        # Average hourly patterns
        for hour in self.hourly_patterns:
            if self.hourly_patterns[hour]:
                self.hourly_patterns[hour] = np.mean(self.hourly_patterns[hour])
            else:
                self.hourly_patterns[hour] = 1.0
        
        # Extract daily patterns (how consumption varies by day of week)
        self.daily_patterns = {}
        for i, ts in enumerate(timestamps):
            day = ts.weekday()
            if day not in self.daily_patterns:
                self.daily_patterns[day] = []
            
            # Store relative value (compared to baseline)
            self.daily_patterns[day].append(consumption[i] / max(1, self.baseline))
        
        # Average daily patterns
        for day in self.daily_patterns:
            if self.daily_patterns[day]:
                self.daily_patterns[day] = np.mean(self.daily_patterns[day])
            else:
                self.daily_patterns[day] = 1.0
        
        # Simple validation: predict last 24 points and compare with actual
        if len(historical_data) > 48:
            train_data = historical_data[:-24]
            test_data = historical_data[-24:]
            
            # Create temporary predictor for validation
            temp_predictor = EnergyPredictor()
            temp_predictor.train(train_data)
            
            # Make predictions for test data
            test_timestamps = [d['timestamp'] for d in test_data]
            actual_values = [d['energy_consumed'] for d in test_data]
            predicted_values = []
            
            for ts in test_timestamps:
                hour_factor = temp_predictor.hourly_patterns.get(ts.hour, 1.0)
                day_factor = temp_predictor.daily_patterns.get(ts.weekday(), 1.0)
                
                # Combine factors to predict consumption
                prediction = temp_predictor.baseline * hour_factor * day_factor
                predicted_values.append(prediction)
            
            # Calculate Mean Absolute Percentage Error
            mape = np.mean(np.abs((np.array(actual_values) - np.array(predicted_values)) / np.array(actual_values))) * 100
            self.validation_score = max(0, 100 - mape)  # Convert to accuracy score
        else:
            self.validation_score = 70  # Default score for limited data
        
        self.is_trained = True
        return self.validation_score
    
    def predict(self, current_data, horizon=24):
        """
        Predict energy consumption for the next 'horizon' hours
        Returns: list of predicted values
        """
        if not self.is_trained:
            # Return flat prediction based on latest values
            if current_data:
                latest_value = current_data[-1]['energy_consumed']
                return [latest_value] * horizon
            return [50.0] * horizon  # Default value if no data
        
        # Start with the last known timestamp
        if current_data:
            last_timestamp = current_data[-1]['timestamp']
        else:
            last_timestamp = datetime.now()
        
        predictions = []
        for i in range(horizon):
            next_timestamp = last_timestamp + timedelta(hours=i+1)
            
            # Apply hourly and daily patterns
            hour_factor = self.hourly_patterns.get(next_timestamp.hour, 1.0)
            day_factor = self.daily_patterns.get(next_timestamp.weekday(), 1.0)
            
            # Add small random variation to make predictions more realistic
            random_factor = np.random.normal(1.0, 0.05)  # 5% random variation
            
            # Combine factors to predict consumption
            prediction = self.baseline * hour_factor * day_factor * random_factor
            
            # Ensure prediction is reasonable
            prediction = max(10, min(200, prediction))
            predictions.append(round(prediction, 1))
        
        return predictions

# Create a singleton instance
predictor = EnergyPredictor()