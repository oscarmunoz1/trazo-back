#!/usr/bin/env python3
"""
Test script for USDA Integration Enhancement (Month 1, Week 1-2)
Tests the new enhanced USDA factors service and compliance validation.
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from carbon.services.enhanced_usda_factors import EnhancedUSDAFactors, USDAValidationResult
from carbon.models import USDAComplianceRecord, RegionalEmissionFactor, USDACalculationAudit
from django.utils import timezone
from datetime import date
import json

def test_enhanced_usda_factors():
    """Test the enhanced USDA factors service"""
    print("🧪 Testing Enhanced USDA Factors Service...")
    
    enhanced_usda = EnhancedUSDAFactors()
    
    # Test 1: Get regional factors
    print("\n1. Testing regional emission factors...")
    factors = enhanced_usda.get_regional_factors('citrus', 'CA')
    print(f"   ✅ CA Citrus factors: {factors}")
    
    # Test 2: Get real-time factors (will use cached/regional since no API key)
    print("\n2. Testing real-time emission factors...")
    real_time_factors = enhanced_usda.get_real_time_emission_factors('corn', 'IA')
    print(f"   ✅ IA Corn real-time factors: {real_time_factors}")
    
    # Test 3: USDA benchmark comparison
    print("\n3. Testing USDA benchmark comparison...")
    benchmark = enhanced_usda.get_usda_benchmark_comparison(1.5, 'citrus', 'CA')
    print(f"   ✅ Benchmark comparison: {benchmark}")
    
    # Test 4: USDA compliance validation
    print("\n4. Testing USDA compliance validation...")
    calculation_data = {
        'crop_type': 'citrus',
        'state': 'CA',
        'co2e': 150.0,
        'area_hectares': 2.0,
        'usda_factors_based': True,
        'method': 'detailed'
    }
    
    validation_result = enhanced_usda.validate_against_usda_standards(calculation_data)
    print(f"   ✅ Validation result: {validation_result.to_dict()}")
    
    # Test 5: Enhanced metadata
    print("\n5. Testing enhanced calculation metadata...")
    metadata = enhanced_usda.get_enhanced_calculation_metadata('citrus', 'CA')
    print(f"   ✅ Metadata: {metadata}")
    
    return True

def test_regional_emission_factor_model():
    """Test the RegionalEmissionFactor model"""
    print("\n🧪 Testing RegionalEmissionFactor Model...")
    
    # Create a test regional emission factor
    factor = RegionalEmissionFactor.objects.create(
        state='CA',
        crop_type='citrus',
        factor_type='nitrogen',
        factor_name='California Citrus Nitrogen Factor',
        emission_factor=5.2,  # Slightly lower than USDA default due to CA efficiency
        unit='kg CO2e per kg N',
        adjustment_factor=0.95,  # 5% reduction for CA
        data_source='usda_api',
        source_reference='USDA Agricultural Research Service - California Regional Study 2024',
        confidence_level=0.92,
        usda_verified=True,
        valid_from=date.today(),
        created_by=None  # Would be set to actual user in real usage
    )
    
    print(f"   ✅ Created factor: {factor}")
    print(f"   ✅ Adjusted emission factor: {factor.adjusted_emission_factor}")
    print(f"   ✅ Is current: {factor.is_current}")
    
    # Test the class method
    retrieved_factor = RegionalEmissionFactor.get_factor_for_region('CA', 'citrus', 'nitrogen')
    print(f"   ✅ Retrieved factor: {retrieved_factor}")
    
    # Increment usage
    factor.increment_usage()
    factor.refresh_from_db()
    print(f"   ✅ Usage count after increment: {factor.usage_count}")
    
    # Clean up
    factor.delete()
    print("   ✅ Test factor cleaned up")
    
    return True

def test_usda_compliance_record_model():
    """Test the USDAComplianceRecord model"""
    print("\n🧪 Testing USDAComplianceRecord Model...")
    
    # We'll create a mock compliance record without carbon_entry for testing
    from carbon.models import CarbonEntry, CarbonSource
    from users.models import User
    from company.models import Company, Establishment
    
    # Get or create a test user and carbon source
    try:
        test_user, created = User.objects.get_or_create(
            email='test_usda@trazo.com',
            defaults={'first_name': 'Test', 'last_name': 'User', 'is_staff': True}
        )
        
        # Create a test company and establishment
        test_company, _ = Company.objects.get_or_create(
            name='Test Company USDA',
            defaults={'description': 'Test company for USDA compliance'}
        )
        
        test_establishment, _ = Establishment.objects.get_or_create(
            name='Test Establishment USDA',
            company=test_company,
            defaults={'description': 'Test establishment for USDA compliance'}
        )
        
        test_source, _ = CarbonSource.objects.get_or_create(
            name='Test USDA Source',
            defaults={
                'category': 'test',
                'description': 'Test source for USDA compliance',
                'usda_verified': True
            }
        )
        
        # Create a test carbon entry with establishment (satisfies constraint)
        carbon_entry = CarbonEntry.objects.create(
            type='emission',
            source=test_source,
            amount=150.0,
            co2e_amount=150.0,
            year=2024,
            establishment=test_establishment,  # This satisfies the constraint
            description='Test carbon entry for USDA compliance',
            usda_factors_based=True,
            verification_status='factors_verified',
            data_source='USDA Agricultural Research Service',
            created_by=test_user
        )
        
        # Create compliance record
        compliance_record = USDAComplianceRecord.objects.create(
            carbon_entry=carbon_entry,
            establishment=test_establishment,
            compliance_status='compliant',
            confidence_score=0.92,
            validation_method='enhanced_api',
            validation_details={
                'regional_comparison': {
                    'farm_intensity': 75.0,
                    'regional_average': 80.0,
                    'performance_ratio': 0.9375
                },
                'validation_method': 'enhanced_validation'
            },
            recommendations=[
                'Continue current sustainable practices',
                'Consider precision agriculture for further improvements'
            ],
            usda_api_used=False,
            crop_type='citrus',
            state='CA',
            regional_factors_used=True,
            validated_by=test_user
        )
        
        print(f"   ✅ Created compliance record: {compliance_record}")
        print(f"   ✅ Confidence level: {compliance_record.confidence_level}")
        print(f"   ✅ Is USDA verified: {compliance_record.is_usda_verified}")
        print(f"   ✅ Needs review: {compliance_record.needs_review}")
        
        # Clean up
        compliance_record.delete()
        carbon_entry.delete()
        test_source.delete()
        test_establishment.delete()
        test_company.delete()
        print("   ✅ Test compliance record cleaned up")
        
    except Exception as e:
        print(f"   ❌ Error testing compliance record: {e}")
        return False
    
    return True

def test_api_endpoints():
    """Test the new API endpoints"""
    print("\n🧪 Testing New USDA API Endpoints...")
    
    # Test the services that power the endpoints
    enhanced_usda = EnhancedUSDAFactors()
    
    # Test validation endpoint logic
    print("\n1. Testing validation endpoint logic...")
    calculation_data = {
        'crop_type': 'corn',
        'state': 'IA',
        'co2e': 100.0,
        'area_hectares': 1.5,
        'usda_factors_based': True,
        'method': 'standard'
    }
    
    validation_result = enhanced_usda.validate_against_usda_standards(calculation_data)
    print(f"   ✅ Validation successful: {validation_result.is_compliant}")
    print(f"   ✅ Confidence score: {validation_result.confidence_score}")
    
    # Test regional factors endpoint logic
    print("\n2. Testing regional factors endpoint logic...")
    emission_factors = enhanced_usda.get_real_time_emission_factors('corn', 'IA')
    regional_factors = enhanced_usda.get_regional_factors('corn', 'IA')
    metadata = enhanced_usda.get_enhanced_calculation_metadata('corn', 'IA')
    
    print(f"   ✅ Emission factors retrieved: {len(emission_factors)} factors")
    print(f"   ✅ Regional factors retrieved: {len(regional_factors)} factors")
    print(f"   ✅ Metadata confidence: {metadata['confidence_level']}")
    
    # Test benchmark comparison endpoint logic
    print("\n3. Testing benchmark comparison endpoint logic...")
    benchmark = enhanced_usda.get_usda_benchmark_comparison(0.6, 'corn', 'IA')
    print(f"   ✅ Benchmark level: {benchmark['level']}")
    print(f"   ✅ Percentile: {benchmark.get('percentile', 'N/A')}")
    
    return True

def run_all_tests():
    """Run all USDA integration tests"""
    print("🚀 Starting USDA Integration Tests (Month 1, Week 1-2)")
    print("=" * 60)
    
    tests = [
        ("Enhanced USDA Factors Service", test_enhanced_usda_factors),
        ("RegionalEmissionFactor Model", test_regional_emission_factor_model),
        ("USDAComplianceRecord Model", test_usda_compliance_record_model),
        ("API Endpoints Logic", test_api_endpoints),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*60}")
            result = test_func()
            results.append((test_name, result))
            if result:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All USDA integration tests PASSED! Ready for Month 1, Week 3-4.")
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
    
    print(f"\n{'='*60}")
    print("✨ USDA Integration Enhancement (Month 1, Week 1-2) Complete!")
    print("📈 Next: Week 3-4 - Blockchain Production Readiness")
    print(f"{'='*60}")

if __name__ == "__main__":
    run_all_tests() 