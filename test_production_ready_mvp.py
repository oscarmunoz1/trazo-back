#!/usr/bin/env python3
"""
Test script to verify production-ready MVP changes
Checks that mock data has been removed and real calculations are working
"""

import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

from django.contrib.auth import get_user_model
from history.models_consumer import UserImpactSummary
from history.models import HistoryScan
from history.views_consumer import ConsumerDashboardViewSet
from carbon.models import CarbonEntry
from django.test import RequestFactory
from rest_framework.test import APIRequestFactory

User = get_user_model()

def test_production_ready_changes():
    """Test that all mock data has been removed and replaced with real calculations"""
    
    print("🔍 Testing Production-Ready MVP Changes...")
    print("="*60)
    
    # Test 1: Check that carbon offset calculation uses real data
    print("\n1. Testing Carbon Offset Calculation...")
    
    # Get a user with scan data
    user_with_scans = User.objects.filter(
        historyscan__isnull=False
    ).distinct().first()
    
    if user_with_scans:
        print(f"   ✓ Found user with scans: {user_with_scans.email}")
        
        # Get their impact summary
        impact_summary, created = UserImpactSummary.objects.get_or_create(user=user_with_scans)
        
        # Check total scans
        actual_scans = HistoryScan.objects.filter(user=user_with_scans).count()
        print(f"   ✓ Actual scans: {actual_scans}")
        print(f"   ✓ Impact summary scans: {impact_summary.total_scans}")
        
        # Check if carbon offset is based on real data (not mock 1.5 * scans)
        expected_mock_offset = actual_scans * 1.5
        actual_offset = impact_summary.total_carbon_offset_kg
        
        if actual_offset != expected_mock_offset:
            print(f"   ✅ GOOD: Carbon offset ({actual_offset}) is NOT using mock calculation ({expected_mock_offset})")
        else:
            print(f"   ❌ WARNING: Carbon offset still appears to use mock calculation")
            
        # Check miles equivalent makes sense
        expected_miles = actual_offset * 2.48 if actual_offset > 0 else 0
        actual_miles = impact_summary.miles_driving_offset
        print(f"   ✓ Miles equivalent: {actual_miles} (calculated from {actual_offset} kg CO₂e)")
        
        # Test better choices calculation
        better_choices = impact_summary.better_choices_made
        certified_scans = HistoryScan.objects.filter(
            user=user_with_scans,
            history__parcel__certified=True
        ).count()
        verified_scans = HistoryScan.objects.filter(
            user=user_with_scans,
            history__carbon_entry__verified=True
        ).count()
        
        print(f"   ✓ Better choices: {better_choices}")
        print(f"   ✓ Certified scans: {certified_scans}")
        print(f"   ✓ Verified scans: {verified_scans}")
        
        if better_choices == max(certified_scans, verified_scans):
            print("   ✅ GOOD: Better choices using real certification data")
        else:
            print("   ❌ WARNING: Better choices calculation may be incorrect")
    else:
        print("   ⚠️  No users with scan data found for testing")
    
    # Test 2: Check retailer recommendations are empty
    print("\n2. Testing Retailer Recommendations...")
    dashboard_view = ConsumerDashboardViewSet()
    recommendations = dashboard_view._get_retailer_recommendations()
    
    if not recommendations:
        print("   ✅ GOOD: Retailer recommendations are now empty (no hardcoded data)")
    else:
        print(f"   ❌ WARNING: Still showing {len(recommendations)} hardcoded recommendations")
    
    # Test 3: Check carbon savings display
    print("\n3. Testing Carbon Savings Display...")
    
    # Test the API endpoint
    factory = APIRequestFactory()
    request = factory.get('/api/consumer/dashboard/impact_dashboard/')
    
    if user_with_scans:
        request.user = user_with_scans
        dashboard_view = ConsumerDashboardViewSet()
        dashboard_view.request = request
        
        try:
            response = dashboard_view.impact_dashboard(request)
            data = response.data
            
            recent_scans = data.get('recent_scans', [])
            print(f"   ✓ Found {len(recent_scans)} recent scans")
            
            for i, scan in enumerate(recent_scans[:3]):  # Check first 3
                carbon_saved = scan.get('carbon_saved', 'N/A')
                print(f"   ✓ Scan {i+1} carbon display: '{carbon_saved}'")
                
                # Check that it's not showing the old "-0.0 kg saved" pattern
                if carbon_saved == "0.0 kg saved" or carbon_saved == "-0.0 kg saved":
                    print(f"   ❌ WARNING: Still showing old format: {carbon_saved}")
                elif "tracked" in carbon_saved.lower() or "pending" in carbon_saved.lower():
                    print(f"   ✅ GOOD: Using new format: {carbon_saved}")
                    
        except Exception as e:
            print(f"   ❌ ERROR testing API: {e}")
    
    # Test 4: Check sustainability practices
    print("\n4. Testing Sustainability Practices...")
    
    if user_with_scans:
        scan_sample = HistoryScan.objects.filter(user=user_with_scans).first()
        if scan_sample:
            from history.serializers_consumer import ShoppingHistoryScanSerializer
            
            # Create a mock request context
            mock_request = type('MockRequest', (), {'user': user_with_scans})()
            context = {'request': mock_request}
            
            serializer = ShoppingHistoryScanSerializer(scan_sample, context=context)
            practices = serializer.get_sustainability_practices(scan_sample)
            
            print(f"   ✓ Sample scan practices: {practices}")
            
            # Check that practices are based on real data
            hardcoded_practices = ["Sustainable farming", "Local production"]
            has_hardcoded = any(practice in hardcoded_practices for practice in practices)
            
            if not has_hardcoded:
                print("   ✅ GOOD: No hardcoded sustainability practices found")
            else:
                print("   ❌ WARNING: Still showing hardcoded practices")
    
    # Test 5: Check local farms calculation
    print("\n5. Testing Local Farms Calculation...")
    if user_with_scans:
        local_farms = impact_summary.local_farms_found
        if local_farms == 0:
            print("   ✅ GOOD: Local farms set to 0 (disabled until location logic implemented)")
        else:
            print(f"   ⚠️  Local farms showing {local_farms} - verify this is correct")
    
    print("\n" + "="*60)
    print("🎯 Production-Ready MVP Test Complete!")
    print("\nNext Steps for Full Production:")
    print("1. Implement user location detection for local farms")
    print("2. Add real industry benchmarks for carbon comparisons") 
    print("3. Create proper 'better choice' comparison algorithm")
    print("4. Add educational tooltips explaining metrics")
    print("5. Implement achievement system with real thresholds")

if __name__ == "__main__":
    test_production_ready_changes()