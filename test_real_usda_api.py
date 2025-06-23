#!/usr/bin/env python3
"""
Test script for Real USDA API Integration
Run this after setting up your USDA API keys to verify everything works.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

from carbon.services.real_usda_integration import RealUSDAAPIClient, get_real_usda_carbon_data


def test_real_usda_api():
    """Test real USDA API integration"""
    print("🧪 Testing Real USDA API Integration...")
    print("="*60)
    
    client = RealUSDAAPIClient()
    
    # Check API key configuration
    print("\n🔑 Checking API Configuration...")
    if not client.nass_api_key:
        print("❌ NASS API key not configured in settings")
        print("   Add USDA_NASS_API_KEY to your Django settings")
        return False
    else:
        print(f"✅ NASS API key configured: {client.nass_api_key[:8]}...")
    
    # Test 1: Get corn data for Iowa
    print("\n1️⃣ Testing NASS corn data for Iowa...")
    try:
        corn_data = client.get_nass_crop_data('corn', 'IA', 2023)
        
        if corn_data and 'data' in corn_data:
            record_count = len(corn_data['data'])
            print(f"✅ Success! Found {record_count} records")
            
            if corn_data['data']:
                sample = corn_data['data'][0]
                print(f"   📊 Sample record:")
                print(f"      Description: {sample.get('short_desc', 'N/A')}")
                print(f"      Value: {sample.get('Value', 'N/A')}")
                print(f"      Unit: {sample.get('unit_desc', 'N/A')}")
                print(f"      Year: {sample.get('year', 'N/A')}")
        else:
            print("❌ No data returned - possible issues:")
            print("   - Check API key validity")
            print("   - Try different crop/state/year combination")
            print("   - Check USDA server status")
            return False
            
    except Exception as e:
        print(f"❌ Error fetching NASS data: {e}")
        return False
    
    # Test 2: Get benchmark yield
    print("\n2️⃣ Testing benchmark yield calculation...")
    try:
        benchmark = client.get_benchmark_yield('corn', 'IA')
        
        if benchmark:
            print(f"✅ Benchmark yield for Iowa corn: {benchmark:.2f} bushels/acre")
            print(f"   📈 Equivalent: {benchmark * 62.8:.0f} kg/hectare (approximate)")
        else:
            print("⚠️  No benchmark data available - this is normal for some crops/states")
            
    except Exception as e:
        print(f"❌ Error calculating benchmark: {e}")
    
    # Test 3: Full carbon calculation
    print("\n3️⃣ Testing full carbon intensity calculation...")
    
    farm_practices = {
        'inputs': {
            'nitrogen_kg': 150,  # kg per hectare
            'phosphorus_kg': 50,
            'diesel_liters': 80
        },
        'area_hectares': 100,
        'yield_per_hectare': 9000  # kg per hectare (corn)
    }
    
    try:
        carbon_result = client.calculate_carbon_intensity('corn', 'IA', farm_practices)
        
        if carbon_result and not carbon_result.get('error'):
            print(f"✅ Carbon intensity calculation successful!")
            print(f"   🌱 Carbon intensity: {carbon_result['carbon_intensity']:.4f} kg CO2e/kg")
            print(f"   💨 Total emissions: {carbon_result['total_emissions']:.2f} kg CO2e")
            print(f"   📚 Data source: {carbon_result['data_source']}")
            print(f"   🎯 Confidence level: {carbon_result['confidence_level']}")
            
            # Emission breakdown
            if 'emission_breakdown' in carbon_result:
                print(f"   📊 Emission breakdown:")
                breakdown = carbon_result['emission_breakdown']
                for source, amount in breakdown.items():
                    percentage = (amount / carbon_result['total_emissions']) * 100
                    print(f"      {source.capitalize()}: {amount:.2f} kg CO2e ({percentage:.1f}%)")
            
            # Benchmark comparison
            if carbon_result.get('benchmark_comparison'):
                benchmark_comp = carbon_result['benchmark_comparison']
                print(f"   🏆 Benchmark comparison: {benchmark_comp['yield_efficiency']}")
                print(f"      Farm yield: {benchmark_comp['farm_yield']:.0f} kg/ha")
                print(f"      Regional benchmark: {benchmark_comp['regional_benchmark']:.0f} kg/ha")
                print(f"      Performance ratio: {benchmark_comp['performance_ratio']:.2f}")
        else:
            print(f"❌ Carbon calculation failed: {carbon_result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ Error in carbon calculation: {e}")
        return False
    
    # Test 4: Integration function
    print("\n4️⃣ Testing integration function...")
    try:
        integrated_result = get_real_usda_carbon_data('corn', 'IA', farm_practices)
        
        if integrated_result and integrated_result.get('real_data'):
            print("✅ Integration function working!")
            print(f"   📡 API sources: {integrated_result['api_sources']}")
            print(f"   ⏰ Timestamp: {integrated_result['timestamp']}")
            
            if 'validation' in integrated_result:
                validation = integrated_result['validation']
                print(f"   ✅ Validation level: {validation.get('validation_level', 'unknown')}")
                print(f"   📊 Methodology score: {validation.get('methodology_score', 0)}/100")
        else:
            print("❌ Integration function failed")
            return False
            
    except Exception as e:
        print(f"❌ Error in integration test: {e}")
        return False
    
    # Success summary
    print("\n" + "="*60)
    print("🎉 ALL TESTS PASSED!")
    print("✅ Real USDA API integration is working correctly")
    print("\n📋 Next steps:")
    print("   1. Update your enhanced_usda_factors.py to use real data")
    print("   2. Test with your Django API endpoints")
    print("   3. Monitor performance and add caching as needed")
    print("   4. Consider adding more crop types and states")
    
    return True


def test_api_endpoints():
    """Test available API endpoints"""
    print("\n🔗 Testing API endpoint availability...")
    
    import requests
    
    try:
        # Test if Django server is running
        response = requests.get('http://localhost:8000/api/carbon/usda-factors/?crop_type=corn&state=IA', timeout=5)
        
        if response.status_code == 200:
            print("✅ Django API endpoint responding")
            data = response.json()
            print(f"   Response keys: {list(data.keys())}")
        else:
            print(f"⚠️  Django API returned status: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("⚠️  Django server not running - start with 'poetry run python manage.py runserver'")
    except Exception as e:
        print(f"⚠️  Error testing API endpoint: {e}")


if __name__ == "__main__":
    print("🚀 Starting Real USDA API Tests...")
    print("Make sure you have:")
    print("  ✅ USDA API keys configured in Django settings")
    print("  ✅ Internet connection")
    print("  ✅ Django environment setup")
    print()
    
    success = test_real_usda_api()
    
    if success:
        test_api_endpoints()
    
    print("\n" + "="*60)
    if success:
        print("🎯 Ready to use real USDA data in your application!")
    else:
        print("🔧 Fix the issues above and try again")
        print("📖 Check the REAL_USDA_API_SETUP_GUIDE.md for help") 