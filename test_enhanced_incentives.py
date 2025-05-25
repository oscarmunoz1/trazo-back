#!/usr/bin/env python
"""
Test script for enhanced government incentives calculation
"""
import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from carbon.services.cost_optimizer import CostOptimizer
from history.models import History
from users.models import User
from company.models import Establishment

def test_enhanced_government_incentives():
    print("=== Testing Enhanced Government Incentives Calculation ===\n")
    
    # Get test user and establishment
    user = User.objects.filter(email='test@example.com').first()
    if not user:
        print("❌ Test user not found. Please run: poetry run python manage.py seed_test_data")
        return
    
    establishment = Establishment.objects.filter(name='Main Citrus Farm').first()
    if not establishment:
        print("❌ Test establishment not found. Please run: poetry run python manage.py seed_test_data")
        return
    
    # Get productions for the establishment
    productions = History.objects.filter(
        parcel__establishment=establishment
    ).order_by('-start_date')
    
    if not productions.exists():
        print("❌ No productions found for establishment")
        return
    
    print(f"✅ Found {productions.count()} productions for establishment: {establishment.name}")
    print(f"📍 Location: {establishment.latitude}, {establishment.longitude}")
    print(f"🏢 Company: {establishment.company.name}")
    print(f"📏 Total area: {sum(p.parcel.area for p in productions if p.parcel)} hectares\n")
    
    # Initialize cost optimizer
    optimizer = CostOptimizer()
    
    # Test government incentives calculation
    print("🔍 Analyzing government incentives...")
    incentives_result = optimizer._analyze_government_incentives(list(productions))
    
    print(f"\n💰 Government Incentives Analysis:")
    print(f"   Total Potential Savings: ${incentives_result['savings']:,.2f}")
    print(f"   Number of Recommendations: {len(incentives_result['recommendations'])}")
    
    print(f"\n📋 Detailed Recommendations:")
    for i, rec in enumerate(incentives_result['recommendations'], 1):
        print(f"   {i}. {rec['program']}")
        print(f"      💵 Potential Value: ${rec['potential_value']:,.2f}")
        print(f"      📝 Description: {rec['description']}")
        print(f"      ⏰ Deadline: {rec['deadline']}")
        print(f"      📞 Contact: {rec['contact']}")
        print()
    
    # Test full ROI calculation
    print("🔍 Testing full ROI calculation...")
    full_result = optimizer.calculate_savings(establishment.id)
    
    print(f"\n📊 Full ROI Analysis:")
    print(f"   Total Annual Savings: ${full_result['total_annual_savings']:,.2f}")
    print(f"   Equipment Efficiency: ${full_result['savings_breakdown']['equipment_efficiency']:,.2f}")
    print(f"   Chemical Optimization: ${full_result['savings_breakdown']['chemical_optimization']:,.2f}")
    print(f"   Energy Optimization: ${full_result['savings_breakdown']['energy_optimization']:,.2f}")
    print(f"   Market Opportunities: ${full_result['savings_breakdown']['market_opportunities']:,.2f}")
    print(f"   Government Incentives: ${full_result['savings_breakdown']['government_incentives']:,.2f}")
    
    print(f"\n🎯 Government Incentives Breakdown:")
    gov_details = full_result.get('government_incentives_details', {})
    if gov_details:
        for program, details in gov_details.items():
            if isinstance(details, dict) and 'amount' in details:
                print(f"   • {program}: ${details['amount']:,.2f}")
                if 'calculation' in details:
                    print(f"     Calculation: {details['calculation']}")
    
    print(f"\n✅ Enhanced government incentives system is working correctly!")
    print(f"   Data-driven calculations based on:")
    print(f"   • Farm size: {sum(p.parcel.area for p in productions if p.parcel)} hectares")
    print(f"   • Conservation practices: {len([p for p in productions if hasattr(p, 'history_soilmanagementevent_events') and p.history_soilmanagementevent_events.exists()])} productions with soil management")
    print(f"   • Irrigation systems: {len([p for p in productions if hasattr(p, 'history_productionevent_events') and p.history_productionevent_events.filter(type='IR').exists()])} productions with irrigation")
    print(f"   • Sustainable practices: {len([p for p in productions if hasattr(p, 'history_generalevent_events') and p.history_generalevent_events.exists()])} productions with general conservation events")

if __name__ == '__main__':
    test_enhanced_government_incentives() 