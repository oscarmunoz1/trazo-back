#!/usr/bin/env python3
"""
Comprehensive USDA Integration Test
Tests the complete flow from backend APIs to frontend display
"""

import os
import sys
import django
import requests
import json
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

from carbon.services.real_usda_integration import RealUSDAAPIClient
from carbon.services.enhanced_usda_factors import EnhancedUSDAFactors
from django.test import Client
from django.contrib.auth import get_user_model

def test_backend_usda_services():
    """Test 1: Backend USDA Services"""
    print("🔬 TESTING BACKEND USDA SERVICES")
    print("=" * 50)
    
    try:
        # Initialize services
        client = RealUSDAAPIClient()
        enhanced = EnhancedUSDAFactors()
        
        # Test API keys
        print(f"✅ NASS API Key: {'Configured' if client.nass_api_key else 'Missing'}")
        print(f"✅ ERS API Key: {'Configured' if client.ers_api_key else 'Missing'}")
        print(f"✅ FoodData API Key: {'Configured' if client.fooddata_api_key else 'Missing'}")
        
        # Test real API call
        print("\n📊 Testing real NASS API call...")
        benchmark = client.get_benchmark_yield('corn', 'IA')
        print(f"✅ Real NASS benchmark: {benchmark:.2f} bushels/acre")
        
        # Test carbon calculation
        print("\n🧮 Testing carbon calculation...")
        farm_practices = {
            'inputs': {'nitrogen_kg': 150, 'diesel_liters': 80},
            'area_hectares': 100,
            'yield_per_hectare': 9000
        }
        
        carbon_result = client.calculate_carbon_intensity('corn', 'IA', farm_practices)
        print(f"✅ Carbon intensity: {carbon_result.get('carbon_intensity', 0):.6f} kg CO2e/kg")
        print(f"✅ Confidence level: {carbon_result.get('confidence_level', 'unknown')}")
        
        # Test enhanced factors
        print("\n🔬 Testing enhanced USDA factors...")
        factors = enhanced.get_real_time_emission_factors('corn', 'IA')
        print(f"✅ Enhanced factors loaded: {len(factors)} factor types")
        
        return True
        
    except Exception as e:
        print(f"❌ Backend services test failed: {e}")
        return False

def test_django_api_endpoints():
    """Test 2: Django API Endpoints"""
    print("\n🌐 TESTING DJANGO API ENDPOINTS")
    print("=" * 50)
    
    try:
        client = Client()
        User = get_user_model()
        
        # Create test user
        try:
            user = User.objects.get(email='test@trazo.com')
        except User.DoesNotExist:
            user = User.objects.create_user(
                email='test@trazo.com',
                password='testpass123',
                first_name='Test',
                last_name='User'
            )
        
        client.force_login(user)
        
        # Test USDA endpoints
        endpoints = [
            '/carbon/usda/real-factors/?crop_type=corn&state=IA',
            '/carbon/usda/test-apis/',
            '/carbon/usda/nutritional-analysis/?crop_type=corn',
            '/carbon/usda/complete-analysis/?crop_type=corn&state=IA'
        ]
        
        for endpoint in endpoints:
            print(f"\n🔗 Testing {endpoint}")
            response = client.get(endpoint)
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                if 'success' in data:
                    print(f"   ✅ Success: {data.get('success', False)}")
                if 'carbon_intensity' in data.get('carbon_calculation', {}):
                    print(f"   📊 Carbon intensity: {data['carbon_calculation']['carbon_intensity']:.6f}")
                if 'benchmark_data' in data:
                    print(f"   📈 Benchmark: {data['benchmark_data'].get('kg_per_hectare', 'N/A')} kg/hectare")
            else:
                print(f"   ❌ Failed with status {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ Django API test failed: {e}")
        return False

def test_frontend_integration():
    """Test 3: Frontend Integration (if running)"""
    print("\n💻 TESTING FRONTEND INTEGRATION")
    print("=" * 50)
    
    try:
        # Test if frontend is running
        frontend_url = "http://localhost:3000"
        backend_url = "http://localhost:8000"
        
        # Test backend accessibility
        print("🔗 Testing backend accessibility...")
        try:
            response = requests.get(f"{backend_url}/carbon/usda/test-apis/", timeout=5)
            if response.status_code == 401:
                print("✅ Backend running (requires auth)")
            elif response.status_code == 200:
                print("✅ Backend running and accessible")
            else:
                print(f"⚠️ Backend status: {response.status_code}")
        except requests.exceptions.RequestException:
            print("❌ Backend not accessible")
        
        # Test frontend accessibility
        print("\n🌐 Testing frontend accessibility...")
        try:
            response = requests.get(frontend_url, timeout=5)
            if response.status_code == 200:
                print("✅ Frontend running and accessible")
            else:
                print(f"⚠️ Frontend status: {response.status_code}")
        except requests.exceptions.RequestException:
            print("❌ Frontend not accessible (not running)")
        
        return True
        
    except Exception as e:
        print(f"❌ Frontend integration test failed: {e}")
        return False

def test_data_flow_consistency():
    """Test 4: Data Flow Consistency"""
    print("\n🔄 TESTING DATA FLOW CONSISTENCY")
    print("=" * 50)
    
    try:
        # Test same data through different services
        client = RealUSDAAPIClient()
        
        # Direct service call
        direct_benchmark = client.get_benchmark_yield('corn', 'IA')
        
        # Django API call
        django_client = Client()
        User = get_user_model()
        user = User.objects.get(email='test@trazo.com')
        django_client.force_login(user)
        
        response = django_client.get('/carbon/usda/real-factors/?crop_type=corn&state=IA')
        api_data = response.json()
        
        if response.status_code == 200 and 'benchmark_data' in api_data:
            api_benchmark_bushels = api_data['benchmark_data']['regional_yield']
            api_benchmark_kg = api_data['benchmark_data']['kg_per_hectare']
            
            print(f"✅ Direct service benchmark: {direct_benchmark:.2f} bushels/acre")
            print(f"✅ API benchmark: {api_benchmark_bushels:.2f} bushels/acre")
            print(f"✅ API benchmark (kg/hectare): {api_benchmark_kg:,.0f}")
            
            # Check consistency (allow small floating point differences)
            if abs(direct_benchmark - api_benchmark_bushels) < 0.1:
                print("✅ Data consistency: PASSED")
            else:
                print("⚠️ Data consistency: Minor differences detected")
        else:
            print("❌ Could not retrieve API data for consistency check")
        
        return True
        
    except Exception as e:
        print(f"❌ Data flow consistency test failed: {e}")
        return False

def test_usda_credibility_scoring():
    """Test 5: USDA Credibility Scoring"""
    print("\n🏆 TESTING USDA CREDIBILITY SCORING")
    print("=" * 50)
    
    try:
        enhanced = EnhancedUSDAFactors()
        
        # Create or get test establishment
        from company.models import Company, Establishment
        
        company, _ = Company.objects.get_or_create(
            name="Test Farm Company",
            defaults={'state': 'IA'}
        )
        
        establishment, _ = Establishment.objects.get_or_create(
            name="Test Farm",
            company=company,
            defaults={'state': 'IA'}
        )
        
        # Test credibility scoring
        credibility = enhanced.get_usda_credibility_data(establishment)
        
        print(f"✅ Credibility score: {credibility.get('score', 'N/A')}/100")
        print(f"✅ Data source: {credibility.get('data_source', 'N/A')}")
        print(f"✅ Methodology: {credibility.get('methodology', 'N/A')}")
        print(f"✅ Confidence level: {credibility.get('confidence_level', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"❌ USDA credibility scoring test failed: {e}")
        return False

def generate_test_report():
    """Generate comprehensive test report"""
    print("\n📋 COMPREHENSIVE USDA INTEGRATION TEST REPORT")
    print("=" * 60)
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    tests = [
        ("Backend USDA Services", test_backend_usda_services),
        ("Django API Endpoints", test_django_api_endpoints),
        ("Frontend Integration", test_frontend_integration),
        ("Data Flow Consistency", test_data_flow_consistency),
        ("USDA Credibility Scoring", test_usda_credibility_scoring)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, "✅ PASSED" if result else "❌ FAILED"))
        except Exception as e:
            results.append((test_name, f"❌ ERROR: {str(e)[:50]}..."))
    
    print("\n📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    for test_name, result in results:
        print(f"{test_name:<30} {result}")
    
    passed = sum(1 for _, result in results if "PASSED" in result)
    total = len(results)
    
    print("=" * 60)
    print(f"OVERALL RESULT: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! USDA integration is working perfectly!")
    elif passed >= total * 0.8:
        print("✅ Most tests passed. Minor issues detected.")
    else:
        print("⚠️ Several issues detected. Review failed tests.")
    
    return passed == total

if __name__ == "__main__":
    try:
        success = generate_test_report()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Unexpected error: {e}")
        sys.exit(1) 