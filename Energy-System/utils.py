"""
Utility functions for the Energy Management application
"""
import random
from datetime import datetime, timedelta
import numpy as np

def generate_mock_data():
    """
    Generate random energy data for demonstration purposes
    """
    # Generate realistic values based on time of day
    current_hour = datetime.now().hour
    
    # Production is higher during daylight hours (8am-6pm)
    is_peak_production = 8 <= current_hour <= 18
    
    # Base values
    base_production = 50 if is_peak_production else 15
    base_consumption = 60
    
    # Random fluctuations
    production_fluctuation = random.uniform(-5, 5)
    consumption_fluctuation = random.uniform(-10, 10)
    
    # Calculate values
    energy_produced = max(0, base_production + production_fluctuation)
    energy_consumed = max(10, base_consumption + consumption_fluctuation)
    
    # Efficiency: how well the system is using produced energy
    efficiency = min(98, max(60, (energy_produced / max(1, energy_consumed)) * 100))
    
    # Current load as percentage of capacity
    current_load = min(95, max(30, (energy_consumed / 100) * 100))
    
    return {
        'energy_produced': round(energy_produced, 1),
        'energy_consumed': round(energy_consumed, 1),
        'efficiency': round(efficiency, 1),
        'current_load': round(current_load, 1)
    }

def get_ai_recommendations(data):
    """
    Generate smart recommendations based on current energy data
    """
    recommendations = []
    
    # Analyze production vs consumption
    if data['energy_consumed'] > data['energy_produced'] * 1.5:
        recommendations.append({
            'type': 'warning',
            'message': 'Energy consumption is significantly higher than production. Consider reducing non-essential loads during peak hours.'
        })
    
    # Check efficiency
    if data['efficiency'] < 70:
        recommendations.append({
            'type': 'alert',
            'message': 'System efficiency is below optimal levels. Maintenance check recommended.'
        })
    
    # Analyze load
    if data['current_load'] > 85:
        recommendations.append({
            'type': 'critical',
            'message': 'System is operating at high load ({}%). Risk of overload.'.format(data['current_load'])
        })
    
    # If no recommendations, provide a positive one
    if not recommendations:
        recommendations.append({
            'type': 'info',
            'message': 'All systems operating within optimal parameters.'
        })
    
    return recommendations

def analyze_trends(data_points):
    """
    Analyze historical energy data to identify trends
    """
    if not data_points:
        return {
            'statistics': {
                'production': {'mean': 0, 'max': 0, 'min': 0, 'std': 0},
                'consumption': {'mean': 0, 'max': 0, 'min': 0, 'std': 0}
            },
            'trend': 'neutral',
            'peak_hours': {}
        }
    
    # Extract production and consumption values
    production_values = [d['energy_produced'] for d in data_points]
    consumption_values = [d['energy_consumed'] for d in data_points]
    
    # Calculate basic statistics
    stats = {
        'production': {
            'mean': np.mean(production_values),
            'max': np.max(production_values),
            'min': np.min(production_values),
            'std': np.std(production_values)
        },
        'consumption': {
            'mean': np.mean(consumption_values),
            'max': np.max(consumption_values),
            'min': np.min(consumption_values),
            'std': np.std(consumption_values)
        }
    }
    
    # Determine trend (increasing, decreasing, or neutral)
    if len(data_points) > 1:
        first_half = consumption_values[:len(consumption_values)//2]
        second_half = consumption_values[len(consumption_values)//2:]
        
        if np.mean(second_half) > np.mean(first_half) * 1.05:
            trend = 'increasing'
        elif np.mean(first_half) > np.mean(second_half) * 1.05:
            trend = 'decreasing'
        else:
            trend = 'neutral'
    else:
        trend = 'neutral'
    
    # Identify peak hours
    peak_hours = {}
    for d in data_points:
        hour = d['timestamp'].hour
        if hour not in peak_hours:
            peak_hours[hour] = 0
        
        # Count as peak if consumption is above average
        if d['energy_consumed'] > stats['consumption']['mean']:
            peak_hours[hour] += 1
    
    return {
        'statistics': stats,
        'trend': trend,
        'peak_hours': peak_hours
    }

def get_trend_insights(trend_analysis):
    """
    Generate insights based on trend analysis
    """
    insights = []
    
    # Check consumption trend
    if trend_analysis['trend'] == 'increasing':
        insights.append({
            'type': 'warning',
            'message': 'Energy consumption is trending upward. Review recent changes in operations or equipment.'
        })
    elif trend_analysis['trend'] == 'decreasing':
        insights.append({
            'type': 'success',
            'message': 'Energy consumption is trending downward. Recent efficiency measures appear to be working.'
        })
    
    # Analyze peak hours
    if trend_analysis['peak_hours']:
        peak_hour = max(trend_analysis['peak_hours'], key=trend_analysis['peak_hours'].get)
        peak_count = trend_analysis['peak_hours'][peak_hour]
        
        if peak_count > 3:  # If occurs multiple times
            insights.append({
                'type': 'alert',
                'message': f'Consistent peak usage detected around {peak_hour}:00. Consider load shifting to reduce costs.'
            })
    
    # Check variability
    if trend_analysis['statistics']['consumption']['std'] > 20:
        insights.append({
            'type': 'warning',
            'message': 'High variability in energy consumption detected. Stabilizing usage patterns can improve efficiency.'
        })
    
    # Production vs Consumption
    if trend_analysis['statistics']['production']['mean'] < trend_analysis['statistics']['consumption']['mean'] * 0.7:
        insights.append({
            'type': 'alert',
            'message': 'Energy production is significantly below consumption. Consider expanding renewable capacity.'
        })
    
    # If no insights, provide a positive one
    if not insights:
        insights.append({
            'type': 'success',
            'message': 'Energy consumption patterns are stable and within expected parameters.'
        })
    
    return insights