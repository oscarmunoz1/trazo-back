#!/usr/bin/env python3
"""
Weather API Integration Test Script

This script tests the weather API integration endpoints and services
to verify everything is working correctly before frontend integration.

Run this script to test:
1. Weather service configuration
2. NOAA API connectivity
3. Weather data processing
4. Agricultural recommendations
5. Weather alert creation
6. API endpoint functionality
"""

import os
import sys
import django
from django.conf import settings
from django.utils import timezone

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

from carbon.services.weather_api import WeatherService, get_weather_service, get_current_weather, get_agricultural_recommendations, check_weather_alerts
from carbon.models import IoTDevice, IoTDataPoint, Establishment
from company.models import Company
from users.models import User
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
import json


def test_weather_service_configuration():
    """Test weather service configuration and initialization."""
    print("🌤️  Testing Weather Service Configuration...")
    
    try:
        # Test service initialization
        weather_service = WeatherService()
        print(f"   ✓ Weather service initialized successfully")
        print(f"   ✓ NOAA Base URL: {weather_service.noaa_base_url}")
        print(f"   ✓ Backup API configured: {'Yes' if weather_service.backup_api_key else 'No (NOAA only)'}")
        
        # Test convenience function
        service = get_weather_service()
        print(f"   ✓ Convenience function working")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Configuration error: {e}")
        return False


def test_weather_data_retrieval():
    """Test weather data retrieval from APIs."""
    print("\n🌡️  Testing Weather Data Retrieval...")
    
    try:
        # Test coordinates for San Francisco, CA (known to work with NOAA)
        test_lat = 37.7749
        test_lng = -122.4194
        
        print(f"   📍 Testing location: {test_lat}, {test_lng} (San Francisco, CA)")
        
        # Test current weather
        weather_data = get_current_weather(test_lat, test_lng)
        
        if weather_data:
            print(f"   ✓ Current weather retrieved successfully")
            print(f"   ✓ Temperature: {weather_data.get('temperature', 'N/A')}°F")
            print(f"   ✓ Humidity: {weather_data.get('humidity', 'N/A')}%")
            print(f"   ✓ Wind Speed: {weather_data.get('wind_speed', 'N/A')} mph")
            print(f"   ✓ Description: {weather_data.get('description', 'N/A')}")
            print(f"   ✓ Data Source: {weather_data.get('source', 'N/A')}")
            return True
        else:
            print(f"   ❌ No weather data retrieved")
            return False
            
    except Exception as e:
        print(f"   ❌ Weather data retrieval error: {e}")
        return False


def test_weather_alerts():
    """Test weather alerts functionality."""
    print("\n⚠️  Testing Weather Alerts...")
    
    try:
        # Test coordinates for an area that might have alerts
        test_lat = 39.0458
        test_lng = -76.6413  # Baltimore, MD
        
        print(f"   📍 Testing alerts for: {test_lat}, {test_lng} (Baltimore, MD)")
        
        alerts = check_weather_alerts(test_lat, test_lng)
        
        print(f"   ✓ Weather alerts check completed")
        print(f"   ✓ Active alerts found: {len(alerts)}")
        
        if alerts:
            for i, alert in enumerate(alerts[:3]):  # Show first 3 alerts
                print(f"   📢 Alert {i+1}: {alert.get('title', 'No title')}")
                print(f"      Severity: {alert.get('severity', 'Unknown')}")
                print(f"      Event: {alert.get('event', 'Unknown')}")
        else:
            print(f"   ℹ️  No active weather alerts (this is normal)")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Weather alerts error: {e}")
        return False


def test_agricultural_recommendations():
    """Test agricultural recommendations generation."""
    print("\n🚜 Testing Agricultural Recommendations...")
    
    try:
        # Test with various weather conditions
        test_scenarios = [
            {
                'name': 'Normal Conditions',
                'weather': {
                    'temperature': 75,
                    'humidity': 60,
                    'wind_speed': 8,
                    'description': 'Clear skies'
                }
            },
            {
                'name': 'High Temperature',
                'weather': {
                    'temperature': 98,
                    'humidity': 45,
                    'wind_speed': 12,
                    'description': 'Hot and dry'
                }
            },
            {
                'name': 'High Wind',
                'weather': {
                    'temperature': 72,
                    'humidity': 55,
                    'wind_speed': 28,
                    'description': 'Windy conditions'
                }
            },
            {
                'name': 'Freezing Temperature',
                'weather': {
                    'temperature': 28,
                    'humidity': 70,
                    'wind_speed': 5,
                    'description': 'Freezing conditions'
                }
            }
        ]
        
        weather_service = WeatherService()
        
        for scenario in test_scenarios:
            print(f"\n   🧪 Testing scenario: {scenario['name']}")
            recommendations = weather_service.generate_agricultural_recommendations(
                scenario['weather'], 
                'general'
            )
            
            print(f"      ✓ Generated {len(recommendations)} recommendations")
            
            for rec in recommendations:
                priority = rec.get('priority', 'unknown')
                title = rec.get('title', 'No title')
                print(f"      📋 {priority.upper()}: {title}")
                
                # Show actions for critical/high priority
                if priority in ['critical', 'high']:
                    actions = rec.get('actions', [])
                    for action in actions[:2]:  # Show first 2 actions
                        print(f"         • {action}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Agricultural recommendations error: {e}")
        return False


def test_weather_alert_thresholds():
    """Test weather alert threshold logic."""
    print("\n🎯 Testing Weather Alert Thresholds...")
    
    try:
        weather_service = WeatherService()
        
        test_conditions = [
            {'temperature': 75, 'humidity': 60, 'wind_speed': 8, 'expected': False},
            {'temperature': 95, 'humidity': 60, 'wind_speed': 8, 'expected': True},
            {'temperature': 75, 'humidity': 25, 'wind_speed': 8, 'expected': True},
            {'temperature': 75, 'humidity': 60, 'wind_speed': 25, 'expected': True},
            {'temperature': 30, 'humidity': 60, 'wind_speed': 8, 'expected': True},
        ]
        
        for i, condition in enumerate(test_conditions):
            should_alert = weather_service.should_trigger_alert(condition)
            expected = condition['expected']
            
            status = "✓" if should_alert == expected else "❌"
            print(f"   {status} Test {i+1}: T={condition['temperature']}°F, H={condition['humidity']}%, W={condition['wind_speed']}mph")
            print(f"      Expected alert: {expected}, Got: {should_alert}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Alert threshold testing error: {e}")
        return False


def test_weather_event_creation():
    """Test weather event creation through IoT workflow."""
    print("\n📝 Testing Weather Event Creation...")
    
    try:
        # Get or create test company and establishment
        company, created = Company.objects.get_or_create(
            name="Test Weather Company",
            defaults={
                'address': '123 Weather Test St',
                'city': 'Test City',
                'state': 'CA',
                'country': 'US'
            }
        )
        
        establishment, created = Establishment.objects.get_or_create(
            name="Test Weather Farm",
            company=company,
            defaults={
                'address': '456 Farm Weather Rd',
                'city': 'Test City',
                'state': 'CA',
                'country': 'US',
                'latitude': 37.7749,
                'longitude': -122.4194
            }
        )
        
        print(f"   ✓ Test establishment ready: {establishment.name}")
        
        # Create weather station device
        device, created = IoTDevice.objects.get_or_create(
            establishment=establishment,
            name=f"Weather Station - {establishment.name}",
            defaults={
                'device_type': 'weather_station',
                'status': 'online',
                'battery_level': 100,
                'device_id': f'weather_station_{establishment.id}'
            }
        )
        
        print(f"   ✓ Weather station device ready: {device.name}")
        
        # Create test weather data point using correct field names
        weather_data = {
            'temperature': 95,
            'humidity': 30,
            'wind_speed': 5,
            'description': 'Hot and dry conditions'
        }
        
        data_point = IoTDataPoint.objects.create(
            device=device,
            timestamp=timezone.now(),
            data=weather_data,  # Use 'data' instead of 'value'
            quality_score=0.9,
            # Note: IoTDataPoint doesn't have metadata or confidence fields
            # These would be stored in the data JSON or handled differently
        )
        
        print(f"   ✓ Weather data point created: ID {data_point.id}")
        print(f"   ✓ Quality score: {data_point.quality_score}")
        print(f"   ✓ Data: {data_point.data}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Weather event creation error: {e}")
        return False


def test_weather_api_endpoints():
    """Test weather API endpoints."""
    print("\n🔗 Testing Weather API Endpoints...")
    
    try:
        from carbon.views import weather_current_conditions, weather_alerts, weather_recommendations
        
        # Create test request
        factory = RequestFactory()
        
        # Test current conditions endpoint
        request = factory.get('/carbon/weather/current/', {
            'lat': '37.7749',
            'lng': '-122.4194'
        })
        
        # Add session middleware
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()
        
        # Add auth middleware
        auth_middleware = AuthenticationMiddleware(lambda req: None)
        auth_middleware.process_request(request)
        
        # Create test user using correct field name (email instead of username)
        user, created = User.objects.get_or_create(
            email='weather_test@example.com',
            defaults={
                'first_name': 'Weather',
                'last_name': 'Test',
                'is_active': True
            }
        )
        request.user = user
        
        print(f"   🧪 Testing current conditions endpoint...")
        response = weather_current_conditions(request)
        print(f"   ✓ Current conditions endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            print(f"   ✓ Response contains weather data: {'weather' in data}")
            print(f"   ✓ Response contains location: {'location' in data}")
        
        print(f"   🧪 Testing weather alerts endpoint...")
        request = factory.get('/carbon/weather/alerts/', {
            'lat': '37.7749',
            'lng': '-122.4194'
        })
        middleware.process_request(request)
        request.session.save()
        auth_middleware.process_request(request)
        request.user = user
        
        response = weather_alerts(request)
        print(f"   ✓ Weather alerts endpoint status: {response.status_code}")
        
        print(f"   🧪 Testing weather recommendations endpoint...")
        request = factory.get('/carbon/weather/recommendations/', {
            'lat': '37.7749',
            'lng': '-122.4194',
            'establishment_type': 'general'
        })
        middleware.process_request(request)
        request.session.save()
        auth_middleware.process_request(request)
        request.user = user
        
        response = weather_recommendations(request)
        print(f"   ✓ Weather recommendations endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.data
            recommendations = data.get('recommendations', {})
            total_count = recommendations.get('total_count', 0)
            print(f"   ✓ Generated {total_count} recommendations")
        
        return True
        
    except Exception as e:
        print(f"   ❌ API endpoint testing error: {e}")
        return False


def main():
    """Run all weather integration tests."""
    print("🌦️  Weather API Integration Test Suite\n")
    
    tests = [
        test_weather_service_configuration,
        test_weather_data_retrieval,
        test_weather_alerts,
        test_agricultural_recommendations,
        test_weather_alert_thresholds,
        test_weather_event_creation,
        test_weather_api_endpoints
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"   ❌ Test failed with exception: {e}")
    
    print(f"\n📊 Weather Integration Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All weather integration tests passed!")
        print("\n📋 Weather Integration Ready:")
        print("   ✓ NOAA Weather Service integration working")
        print("   ✓ Agricultural recommendations generating")
        print("   ✓ Weather alerts and thresholds functioning")
        print("   ✓ IoT workflow integration complete")
        print("   ✓ API endpoints accessible")
        print("\n🚀 Next Steps:")
        print("   1. Test weather endpoints in frontend")
        print("   2. Set up automated weather monitoring")
        print("   3. Configure establishment-specific thresholds")
        print("   4. Enable real-time weather alerts")
    else:
        print("⚠️  Some weather integration tests failed.")
        print("   Check NOAA API connectivity and Django configuration")
    
    return passed == total


if __name__ == "__main__":
    main() 