#!/usr/bin/env python
"""
Test script for the carbon calculation API endpoint
"""
import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from carbon.views import calculate_event_carbon_impact
import json

def test_carbon_calculation():
    """Test the carbon calculation API with the user's example payload"""
    
    # Create a test request factory
    factory = RequestFactory()
    
    # User's example payload
    data = {
        "event_type": "general",
        "event_data": {
            "description": "<p>Pollination: Local bee colonies reduce transport emissions</p>",
            "observation": "s",
            "duration": None,
            "amount": None,
            "unit": None,
            "event_id": 33
        }
    }
    
    # Create POST request
    request = factory.post(
        '/carbon/calculate-event-impact/', 
        data=json.dumps(data), 
        content_type='application/json'
    )
    
    # Get or create a test user
    try:
        user = User.objects.first()
        if not user:
            user = User.objects.create_user('testuser', 'test@example.com', 'password')
    except Exception as e:
        print(f"Error creating user: {e}")
        return
    
    request.user = user
    
    # Test the API endpoint
    try:
        print("Testing carbon calculation API...")
        print(f"Input payload: {json.dumps(data, indent=2)}")
        print("-" * 50)
        
        response = calculate_event_carbon_impact(request)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Data: {json.dumps(response.data, indent=2)}")
        
        # Verify expected fields are present
        expected_fields = ['co2e', 'efficiency_score', 'usda_verified', 'calculation_method', 'event_type', 'timestamp']
        missing_fields = [field for field in expected_fields if field not in response.data]
        
        if missing_fields:
            print(f"⚠️  Missing expected fields: {missing_fields}")
        else:
            print("✅ All expected fields present")
            
        # Check if we're getting real calculations vs hardcoded values
        if response.data.get('co2e') == 0.1 and response.data.get('efficiency_score') == 50.0:
            print("ℹ️  Using general event standard calculation (expected for general events)")
        else:
            print("✅ Using sophisticated carbon calculation")
            
    except Exception as e:
        print(f"❌ Error testing API: {e}")
        import traceback
        traceback.print_exc()

def test_production_event():
    """Test with a production event that should use the sophisticated calculator"""
    
    factory = RequestFactory()
    
    # Production event with irrigation data
    data = {
        "event_type": "production",
        "event_data": {
            "description": "Riego - Sistema de riego",
            "observation": "Standard irrigation cycle 2 hours",
            "duration": 2,
            "amount": 100,
            "unit": "liters",
            "event_id": 70
        }
    }
    
    request = factory.post(
        '/carbon/calculate-event-impact/', 
        data=json.dumps(data), 
        content_type='application/json'
    )
    
    user = User.objects.first()
    request.user = user
    
    try:
        print("\nTesting production event calculation...")
        print(f"Input payload: {json.dumps(data, indent=2)}")
        print("-" * 50)
        
        response = calculate_event_carbon_impact(request)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Data: {json.dumps(response.data, indent=2)}")
        
        # Check if we get more sophisticated calculation for production events
        if 'breakdown' in response.data:
            print("✅ Sophisticated calculation with breakdown data")
        else:
            print("ℹ️  Basic calculation without breakdown")
            
    except Exception as e:
        print(f"❌ Error testing production event: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_carbon_calculation()
    test_production_event() 