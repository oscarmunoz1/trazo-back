#!/usr/bin/env python3
"""
Test the AI suggestions API endpoint
"""
import os
import sys
import django
import requests
import json

# Setup Django
sys.path.append('/Users/oscarmunoz/dev/trazo/trazo-back')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

def test_ai_suggestions_endpoint():
    """Test the AI suggestions API endpoint"""
    print("🧪 Testing AI Suggestions API Endpoint...")
    print("=" * 50)
    
    # Test data
    test_params = {
        'crop_type': 'Citrus (Oranges)',
        'location': 'CA',
        'season': 'summer',
        'farm_context': json.dumps({
            'establishment_id': '21',
            'parcel_id': '12'
        })
    }
    
    try:
        # Make request to the API endpoint
        # Note: This assumes the Django dev server is running
        url = 'http://localhost:8000/carbon/ai-event-suggestions/'
        
        print(f"📡 Making request to: {url}")
        print(f"📊 Parameters: {test_params}")
        
        response = requests.get(url, params=test_params, timeout=30)
        
        print(f"📈 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS! AI Suggestions received:")
            print(f"🤖 AI Powered: {data.get('ai_powered', False)}")
            print(f"📊 AI Confidence: {data.get('ai_confidence', 0)}%")
            print(f"🎯 Suggestions Count: {len(data.get('suggestions', []))}")
            
            for i, suggestion in enumerate(data.get('suggestions', [])[:2], 1):
                print(f"   {i}. {suggestion.get('name', 'Unknown')}")
                print(f"      Category: {suggestion.get('category', 'N/A')}")
                print(f"      Priority: {suggestion.get('priority', 'N/A')}")
                print(f"      Carbon Impact: {suggestion.get('carbon_impact', 0)} kg CO₂")
                
        else:
            print(f"❌ ERROR: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Django dev server not running?")
        print("💡 Start the server with: poetry run python manage.py runserver")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_ai_suggestions_endpoint() 