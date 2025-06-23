#!/usr/bin/env python3
"""
Test script for AI Event Suggestions functionality
"""

import os
import sys
import django
import asyncio
import json
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

from carbon.services.ai_voice_processor import generate_ai_event_suggestions

async def test_ai_suggestions():
    """Test AI event suggestions generation"""
    print("🤖 Testing AI Event Suggestions...")
    print("=" * 60)
    
    test_cases = [
        {
            "crop_type": "strawberries",
            "location": "California",
            "season": "summer",
            "recent_events": ["irrigation", "fertilization"],
            "farm_context": {
                "establishment_id": "1",
                "parcel_id": "1",
                "current_month": 6
            }
        },
        {
            "crop_type": "corn",
            "location": "Iowa",
            "season": "fall",
            "recent_events": ["planting", "pest_control"],
            "farm_context": {
                "establishment_id": "2",
                "parcel_id": "2", 
                "current_month": 10
            }
        },
        {
            "crop_type": "citrus",
            "location": "Florida",
            "season": "winter",
            "recent_events": [],
            "farm_context": {
                "establishment_id": "3",
                "parcel_id": "3",
                "current_month": 12
            }
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}️⃣ Testing: {test_case['crop_type']} in {test_case['season']}")
        print(f"   Location: {test_case['location']}")
        print(f"   Recent events: {test_case['recent_events']}")
        
        try:
            result = await generate_ai_event_suggestions(**test_case)
            
            print(f"   ✅ Success! Generated {len(result.get('suggestions', []))} suggestions")
            print(f"   🤖 AI Powered: {result.get('ai_powered', False)}")
            print(f"   📊 AI Confidence: {result.get('ai_confidence', 0)}%")
            print(f"   🎯 Reasoning: {result.get('reasoning', 'N/A')[:100]}...")
            
            # Display suggestions
            for j, suggestion in enumerate(result.get('suggestions', [])[:2], 1):
                print(f"      {j}. {suggestion['name']}")
                print(f"         Category: {suggestion['category']}")
                print(f"         Priority: {suggestion['priority']}")
                print(f"         Carbon Impact: {suggestion['carbon_impact']} kg CO₂")
                print(f"         Confidence: {suggestion['confidence']}%")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 AI Suggestions test completed!")

def test_django_endpoint():
    """Test the Django API endpoint"""
    print("\n🌐 Testing Django API Endpoint...")
    print("=" * 40)
    
    import requests
    from django.contrib.auth import get_user_model
    from django.test import Client
    from django.urls import reverse
    
    try:
        # Create a test client
        client = Client()
        
        # Create or get test user
        User = get_user_model()
        user, created = User.objects.get_or_create(
            email='test_ai@example.com',
            defaults={
                'username': 'test_ai_user',
                'first_name': 'Test',
                'last_name': 'AI User',
                'role': 'admin'
            }
        )
        
        # Login the user
        client.force_login(user)
        
        # Test the AI suggestions endpoint
        url = '/api/carbon/ai-event-suggestions/'
        params = {
            'crop_type': 'strawberries',
            'location': 'California',
            'season': 'summer'
        }
        
        response = client.get(url, params)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Success! Status: {response.status_code}")
            print(f"🤖 AI Powered: {data.get('ai_powered', False)}")
            print(f"📊 Suggestions: {len(data.get('suggestions', []))}")
            print(f"🎯 AI Confidence: {data.get('ai_confidence', 0)}%")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.content.decode()}")
            
    except Exception as e:
        print(f"❌ Django endpoint test failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting AI Event Suggestions Tests...")
    print("Make sure you have:")
    print("  ✅ OpenAI API key configured")
    print("  ✅ Django environment setup")
    print("  ✅ Internet connection")
    print()
    
    # Test async AI suggestions
    asyncio.run(test_ai_suggestions())
    
    # Test Django endpoint
    test_django_endpoint() 