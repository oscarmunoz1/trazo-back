"""
Weather API Integration Service

This service integrates with NOAA Weather Service and other weather APIs
to provide real-time weather data and automated recommendations for
agricultural operations and carbon tracking.

API Documentation: https://www.weather.gov/documentation/services-web-api
"""

import requests
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from typing import Dict, List, Optional, Any
import json

logger = logging.getLogger(__name__)


class WeatherAPIError(Exception):
    """Custom exception for Weather API errors"""
    pass


class WeatherService:
    """
    NOAA Weather Service API integration for agricultural weather monitoring.
    
    Provides real-time weather data, alerts, and agricultural recommendations
    based on current and forecasted conditions.
    """
    
    def __init__(self):
        self.noaa_base_url = "https://api.weather.gov"
        self.backup_api_key = getattr(settings, 'OPENWEATHER_API_KEY', None)
        self.backup_base_url = "https://api.openweathermap.org/data/2.5"
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Trazo Carbon Tracking Platform (contact@trazo.io)',
            'Accept': 'application/json'
        })
    
    def get_current_conditions(self, lat: float, lng: float) -> Dict[str, Any]:
        """
        Get current weather conditions for a specific location.
        
        Args:
            lat: Latitude coordinate
            lng: Longitude coordinate
            
        Returns:
            Current weather data including temperature, humidity, wind, etc.
        """
        try:
            # First try NOAA API (free, no key required for US locations)
            return self._get_noaa_current_conditions(lat, lng)
        except Exception as e:
            logger.warning(f"NOAA API failed, trying backup: {e}")
            # Fallback to OpenWeatherMap if NOAA fails
            return self._get_backup_current_conditions(lat, lng)
    
    def _get_noaa_current_conditions(self, lat: float, lng: float) -> Dict[str, Any]:
        """Get current conditions from NOAA Weather Service."""
        try:
            # Get the weather station for this location
            points_url = f"{self.noaa_base_url}/points/{lat},{lng}"
            points_response = self.session.get(points_url)
            points_response.raise_for_status()
            points_data = points_response.json()
            
            # Get current observations
            stations_url = points_data['properties']['observationStations']
            stations_response = self.session.get(stations_url)
            stations_response.raise_for_status()
            stations_data = stations_response.json()
            
            if not stations_data['features']:
                raise WeatherAPIError("No weather stations found for location")
            
            # Get observations from the nearest station
            station_id = stations_data['features'][0]['properties']['stationIdentifier']
            obs_url = f"{self.noaa_base_url}/stations/{station_id}/observations/latest"
            obs_response = self.session.get(obs_url)
            obs_response.raise_for_status()
            obs_data = obs_response.json()
            
            properties = obs_data['properties']
            
            # Convert to standardized format
            return {
                'temperature': self._celsius_to_fahrenheit(properties.get('temperature', {}).get('value')),
                'temperature_c': properties.get('temperature', {}).get('value'),
                'humidity': properties.get('relativeHumidity', {}).get('value'),
                'wind_speed': self._mps_to_mph(properties.get('windSpeed', {}).get('value')),
                'wind_direction': properties.get('windDirection', {}).get('value'),
                'pressure': properties.get('barometricPressure', {}).get('value'),
                'visibility': properties.get('visibility', {}).get('value'),
                'description': properties.get('textDescription', ''),
                'timestamp': properties.get('timestamp'),
                'source': 'noaa',
                'station_id': station_id
            }
            
        except Exception as e:
            logger.error(f"NOAA API error: {e}")
            raise WeatherAPIError(f"Failed to get NOAA weather data: {e}")
    
    def _get_backup_current_conditions(self, lat: float, lng: float) -> Dict[str, Any]:
        """Get current conditions from backup weather service."""
        if not self.backup_api_key:
            raise WeatherAPIError("No backup weather API key configured")
        
        try:
            url = f"{self.backup_base_url}/weather"
            params = {
                'lat': lat,
                'lon': lng,
                'appid': self.backup_api_key,
                'units': 'metric'
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return {
                'temperature': self._celsius_to_fahrenheit(data['main']['temp']),
                'temperature_c': data['main']['temp'],
                'humidity': data['main']['humidity'],
                'wind_speed': self._mps_to_mph(data['wind']['speed']),
                'wind_direction': data['wind'].get('deg'),
                'pressure': data['main']['pressure'],
                'visibility': data.get('visibility', 10000),  # Default 10km
                'description': data['weather'][0]['description'],
                'timestamp': datetime.utcnow().isoformat(),
                'source': 'openweather'
            }
            
        except Exception as e:
            logger.error(f"Backup weather API error: {e}")
            raise WeatherAPIError(f"Failed to get backup weather data: {e}")
    
    def get_weather_alerts(self, lat: float, lng: float) -> List[Dict[str, Any]]:
        """
        Get active weather alerts for a location.
        
        Args:
            lat: Latitude coordinate
            lng: Longitude coordinate
            
        Returns:
            List of active weather alerts
        """
        try:
            # Get alerts from NOAA
            alerts_url = f"{self.noaa_base_url}/alerts/active"
            params = {
                'point': f"{lat},{lng}",
                'status': 'actual',
                'message_type': 'alert'
            }
            
            response = self.session.get(alerts_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            alerts = []
            for feature in data.get('features', []):
                properties = feature['properties']
                alerts.append({
                    'id': properties.get('id'),
                    'title': properties.get('headline'),
                    'description': properties.get('description'),
                    'severity': properties.get('severity'),
                    'urgency': properties.get('urgency'),
                    'certainty': properties.get('certainty'),
                    'event': properties.get('event'),
                    'onset': properties.get('onset'),
                    'expires': properties.get('expires'),
                    'areas': properties.get('areaDesc'),
                    'instruction': properties.get('instruction')
                })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to get weather alerts: {e}")
            return []
    
    def get_forecast(self, lat: float, lng: float, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get weather forecast for a location.
        
        Args:
            lat: Latitude coordinate
            lng: Longitude coordinate
            days: Number of days to forecast
            
        Returns:
            List of forecast data
        """
        try:
            # Get forecast from NOAA
            points_url = f"{self.noaa_base_url}/points/{lat},{lng}"
            points_response = self.session.get(points_url)
            points_response.raise_for_status()
            points_data = points_response.json()
            
            forecast_url = points_data['properties']['forecast']
            forecast_response = self.session.get(forecast_url)
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()
            
            forecasts = []
            for period in forecast_data['properties']['periods'][:days * 2]:  # Day and night periods
                forecasts.append({
                    'name': period.get('name'),
                    'temperature': period.get('temperature'),
                    'temperature_unit': period.get('temperatureUnit'),
                    'wind_speed': period.get('windSpeed'),
                    'wind_direction': period.get('windDirection'),
                    'description': period.get('detailedForecast'),
                    'short_forecast': period.get('shortForecast'),
                    'is_daytime': period.get('isDaytime'),
                    'start_time': period.get('startTime'),
                    'end_time': period.get('endTime')
                })
            
            return forecasts
            
        except Exception as e:
            logger.error(f"Failed to get weather forecast: {e}")
            return []
    
    def generate_agricultural_recommendations(self, weather_data: Dict[str, Any], 
                                           establishment_type: str = None) -> List[Dict[str, Any]]:
        """
        Generate agricultural recommendations based on weather conditions.
        
        Args:
            weather_data: Current weather conditions
            establishment_type: Type of agricultural operation
            
        Returns:
            List of recommendations with priorities and actions
        """
        recommendations = []
        
        temperature = weather_data.get('temperature', 70)  # Default to 70°F
        humidity = weather_data.get('humidity', 50)  # Default to 50%
        wind_speed = weather_data.get('wind_speed', 0)  # Default to 0 mph
        
        # Handle None values
        if temperature is None:
            temperature = 70
        if humidity is None:
            humidity = 50
        if wind_speed is None:
            wind_speed = 0
        
        # High temperature alerts
        if temperature > 95:  # >95°F
            recommendations.append({
                'type': 'heat_stress_alert',
                'priority': 'high',
                'title': f'Extreme Heat Alert: {temperature}°F',
                'description': 'Extreme heat conditions detected. Immediate action required to protect crops and livestock.',
                'actions': [
                    'Increase irrigation frequency and duration',
                    'Apply shade cloth or temporary shading',
                    'Monitor livestock for heat stress signs',
                    'Avoid chemical applications during peak heat',
                    'Check irrigation system functionality'
                ],
                'carbon_impact': 'Increased irrigation may raise energy consumption',
                'cost_impact': 'Higher water and energy costs expected',
                'timing': 'Immediate action required'
            })
        elif temperature > 85:  # >85°F
            recommendations.append({
                'type': 'heat_advisory',
                'priority': 'medium',
                'title': f'Heat Advisory: {temperature}°F',
                'description': 'High temperatures may stress crops and increase water needs.',
                'actions': [
                    'Monitor soil moisture levels closely',
                    'Consider early morning irrigation',
                    'Delay non-essential field operations',
                    'Check equipment for overheating'
                ],
                'carbon_impact': 'Moderate increase in irrigation energy use',
                'cost_impact': 'Moderate increase in water costs',
                'timing': 'Within next 6 hours'
            })
        
        # Low temperature alerts
        if temperature < 32:  # <32°F (freezing)
            recommendations.append({
                'type': 'freeze_warning',
                'priority': 'critical',
                'title': f'Freeze Warning: {temperature}°F',
                'description': 'Freezing temperatures detected. Immediate crop protection required.',
                'actions': [
                    'Activate frost protection systems',
                    'Cover sensitive plants',
                    'Run irrigation for radiant heat (if applicable)',
                    'Monitor livestock water sources',
                    'Check equipment for freeze damage'
                ],
                'carbon_impact': 'Frost protection may increase energy use',
                'cost_impact': 'Emergency protection costs',
                'timing': 'Immediate action required'
            })
        
        # High wind alerts
        if wind_speed > 25:  # >25 mph
            recommendations.append({
                'type': 'high_wind_alert',
                'priority': 'high',
                'title': f'High Wind Alert: {wind_speed} mph',
                'description': 'High winds detected. Avoid chemical applications and secure equipment.',
                'actions': [
                    'Postpone all spraying operations',
                    'Secure loose equipment and materials',
                    'Check irrigation systems for damage',
                    'Monitor trees for wind damage',
                    'Delay drone operations'
                ],
                'carbon_impact': 'Delayed operations may affect efficiency',
                'cost_impact': 'Potential equipment damage costs',
                'timing': 'Until wind speeds decrease'
            })
        
        # Humidity-based recommendations
        if humidity < 30:  # Low humidity
            recommendations.append({
                'type': 'low_humidity_alert',
                'priority': 'medium',
                'title': f'Low Humidity Alert: {humidity}%',
                'description': 'Low humidity increases evaporation and plant stress.',
                'actions': [
                    'Increase irrigation duration',
                    'Consider misting systems for sensitive crops',
                    'Monitor soil moisture more frequently',
                    'Adjust chemical application timing'
                ],
                'carbon_impact': 'Increased water pumping energy',
                'cost_impact': 'Higher water usage costs',
                'timing': 'Adjust irrigation schedule today'
            })
        elif humidity > 85:  # High humidity
            recommendations.append({
                'type': 'high_humidity_alert',
                'priority': 'medium',
                'title': f'High Humidity Alert: {humidity}%',
                'description': 'High humidity increases disease risk and affects chemical efficacy.',
                'actions': [
                    'Monitor for fungal disease signs',
                    'Improve air circulation where possible',
                    'Adjust chemical application rates',
                    'Consider preventive fungicide applications'
                ],
                'carbon_impact': 'Additional chemical applications',
                'cost_impact': 'Potential disease treatment costs',
                'timing': 'Monitor closely over next 24-48 hours'
            })
        
        # Optimal conditions recommendations
        if 65 <= temperature <= 80 and 40 <= humidity <= 70 and wind_speed < 15:
            recommendations.append({
                'type': 'optimal_conditions',
                'priority': 'low',
                'title': 'Optimal Weather Conditions',
                'description': 'Current conditions are ideal for most agricultural operations.',
                'actions': [
                    'Ideal time for chemical applications',
                    'Good conditions for field work',
                    'Optimal for equipment maintenance',
                    'Consider scheduling planned operations'
                ],
                'carbon_impact': 'Efficient operations reduce overall emissions',
                'cost_impact': 'Optimal efficiency reduces costs',
                'timing': 'Take advantage of current conditions'
            })
        
        return recommendations
    
    def should_trigger_alert(self, weather_data: Dict[str, Any], 
                           thresholds: Dict[str, Any] = None) -> bool:
        """
        Determine if weather conditions warrant an alert.
        
        Args:
            weather_data: Current weather conditions
            thresholds: Custom alert thresholds
            
        Returns:
            True if alert should be triggered
        """
        if not thresholds:
            thresholds = {
                'high_temp': 85,
                'low_temp': 35,
                'high_wind': 20,
                'low_humidity': 30,
                'high_humidity': 85
            }
        
        temperature = weather_data.get('temperature', 70)
        humidity = weather_data.get('humidity', 50)
        wind_speed = weather_data.get('wind_speed', 0)
        
        # Check if any threshold is exceeded
        if (temperature > thresholds['high_temp'] or 
            temperature < thresholds['low_temp'] or
            wind_speed > thresholds['high_wind'] or
            humidity < thresholds['low_humidity'] or
            humidity > thresholds['high_humidity']):
            return True
        
        return False
    
    def _celsius_to_fahrenheit(self, celsius: Optional[float]) -> Optional[float]:
        """Convert Celsius to Fahrenheit."""
        if celsius is None:
            return None
        return (celsius * 9/5) + 32
    
    def _mps_to_mph(self, mps: Optional[float]) -> Optional[float]:
        """Convert meters per second to miles per hour."""
        if mps is None:
            return None
        return mps * 2.237


# Convenience functions for easy integration

def get_weather_service() -> WeatherService:
    """Get configured Weather Service instance."""
    return WeatherService()


def get_current_weather(lat: float, lng: float) -> Dict[str, Any]:
    """Get current weather conditions for a location."""
    service = WeatherService()
    return service.get_current_conditions(lat, lng)


def get_agricultural_recommendations(lat: float, lng: float, 
                                   establishment_type: str = None) -> List[Dict[str, Any]]:
    """Get weather-based agricultural recommendations."""
    service = WeatherService()
    weather_data = service.get_current_conditions(lat, lng)
    return service.generate_agricultural_recommendations(weather_data, establishment_type)


def check_weather_alerts(lat: float, lng: float) -> List[Dict[str, Any]]:
    """Check for active weather alerts at a location."""
    service = WeatherService()
    return service.get_weather_alerts(lat, lng) 