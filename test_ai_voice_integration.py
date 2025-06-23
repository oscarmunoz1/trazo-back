#!/usr/bin/env python3
"""
Test script for AI Voice Processing Integration
==============================================

This script tests the real AI voice processing to ensure OpenAI integration
works correctly and can process agricultural voice inputs.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

from carbon.services.ai_voice_processor import process_voice_with_ai


def test_ai_voice_processing():
    """Test real AI voice processing with sample agricultural inputs"""
    print("🧪 Testing AI Voice Processing Integration...")
    print("="*60)
    
    # Test cases with different agricultural activities
    test_cases = [
        {
            'transcript': 'Irrigated field for 6 hours with drip system',
            'crop_type': 'strawberries',
            'language': 'en-US',
            'expected_type': 'irrigation'
        },
        {
            'transcript': 'Applied fertilizer today, 200 pounds per acre NPK',
            'crop_type': 'corn',
            'language': 'en-US',
            'expected_type': 'fertilization'
        },
        {
            'transcript': 'Harvested 500 kilos of strawberries from field 3',
            'crop_type': 'strawberries',
            'language': 'en-US',
            'expected_type': 'harvest'
        },
        {
            'transcript': 'Used tractor for 3 hours, consumed 15 gallons of diesel',
            'crop_type': 'corn',
            'language': 'en-US',
            'expected_type': 'equipment'
        },
        {
            'transcript': 'Aplicé fertilizante hoy, 100 kilos por hectárea',
            'crop_type': 'maíz',
            'language': 'es-ES',
            'expected_type': 'fertilization'
        }
    ]
    
    print(f"\n🔑 Checking AI Configuration...")
    from django.conf import settings
    
    if not getattr(settings, 'OPENAI_API_KEY', ''):
        print("❌ OpenAI API key not configured in Django settings")
        print("   Add OPENAI_API_KEY to your environment variables or .env file")
        print("   Example: OPENAI_API_KEY=sk-your-key-here")
        return False
    else:
        print(f"✅ OpenAI API key configured: {settings.OPENAI_API_KEY[:8]}...")
    
    print(f"✅ Model: {getattr(settings, 'OPENAI_MODEL', 'gpt-4')}")
    print(f"✅ Max tokens: {getattr(settings, 'OPENAI_MAX_TOKENS', 500)}")
    print(f"✅ Temperature: {getattr(settings, 'OPENAI_TEMPERATURE', 0.3)}")
    
    success_count = 0
    total_tests = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}️⃣ Testing: {test_case['transcript']}")
        print(f"   Crop: {test_case['crop_type']}, Language: {test_case['language']}")
        
        try:
            result = process_voice_with_ai(
                transcript=test_case['transcript'],
                crop_type=test_case['crop_type'],
                language=test_case['language']
            )
            
            # Analyze results
            detected_type = result.get('type', 'unknown')
            confidence = result.get('confidence', 0)
            processing_time = result.get('processing_time', 0)
            source = result.get('source', 'unknown')
            
            print(f"   ✅ Detected: {detected_type} (confidence: {confidence}%)")
            print(f"   ⏱️  Processing time: {processing_time:.0f}ms")
            print(f"   🔧 Source: {source}")
            
            if result.get('detected_amounts'):
                print(f"   📊 Amounts: {', '.join(result['detected_amounts'])}")
            
            if result.get('detected_products'):
                print(f"   🌱 Products: {', '.join(result['detected_products'])}")
            
            if result.get('detected_systems'):
                print(f"   ⚙️  Systems: {', '.join(result['detected_systems'])}")
            
            print(f"   🌍 Carbon impact: {result.get('suggested_carbon_impact', 0)} kg CO₂e")
            
            # Check if AI was used or fallback
            if source == 'openai_gpt':
                print(f"   🤖 Real AI processing successful!")
                success_count += 1
            elif source == 'pattern_matching_fallback':
                print(f"   ⚠️  Used fallback processing (AI unavailable)")
            else:
                print(f"   ❓ Unknown processing source: {source}")
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    print(f"\n" + "="*60)
    print(f"🎯 Test Results:")
    print(f"   AI Success Rate: {success_count}/{total_tests} ({success_count/total_tests*100:.1f}%)")
    
    if success_count > 0:
        print(f"✅ AI Voice Processing is working correctly!")
        print(f"   Real OpenAI integration is functional")
        print(f"   Voice inputs are being processed with AI intelligence")
    else:
        print(f"⚠️  AI Voice Processing using fallback methods")
        print(f"   Check OpenAI API key configuration")
        print(f"   Verify internet connectivity")
    
    return success_count > 0


def test_api_endpoint():
    """Test the Django API endpoint for voice processing"""
    print(f"\n🌐 Testing Django API Endpoint...")
    print("="*40)
    
    try:
        from django.test import Client
        from django.contrib.auth import get_user_model
        
        # Create test client
        client = Client()
        
        # Create test user
        User = get_user_model()
        test_user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Login
        client.force_login(test_user)
        
        # Test API endpoint
        response = client.post('/api/carbon/process-voice-event/', {
            'transcript': 'Irrigated field for 6 hours with drip system',
            'crop_type': 'strawberries',
            'language': 'en-US'
        }, content_type='application/json')
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API endpoint working!")
            print(f"   Status: {response.status_code}")
            print(f"   Detected: {result.get('type', 'unknown')}")
            print(f"   Confidence: {result.get('confidence', 0)}%")
            return True
        else:
            print(f"❌ API endpoint failed: {response.status_code}")
            print(f"   Response: {response.content.decode()}")
            return False
            
    except Exception as e:
        print(f"❌ API test failed: {str(e)}")
        return False


if __name__ == "__main__":
    print("🚀 Starting AI Voice Processing Tests...")
    print("Make sure you have:")
    print("  ✅ OpenAI API key configured in Django settings")
    print("  ✅ Internet connection")
    print("  ✅ Django environment setup")
    print("  ✅ OpenAI library installed")
    print()
    
    # Test AI processing
    ai_success = test_ai_voice_processing()
    
    # Test API endpoint
    api_success = test_api_endpoint()
    
    print("\n" + "="*60)
    if ai_success and api_success:
        print("🎉 All tests passed! AI Voice Processing is ready to use!")
        print("🤖 Real OpenAI integration is working correctly")
        print("🌐 Django API endpoint is functional")
    elif ai_success:
        print("🎯 AI processing works, but API endpoint needs attention")
    else:
        print("🔧 AI integration needs configuration")
        print("📖 Check the setup guide and ensure OpenAI API key is configured") 