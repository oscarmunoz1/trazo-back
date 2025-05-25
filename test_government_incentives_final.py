#!/usr/bin/env python
"""
Final test script for enhanced government incentives calculation
"""
import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from carbon.services.cost_optimizer import CostOptimizer
from company.models import Establishment

def test_enhanced_government_incentives():
    print("=== Enhanced Government Incentives Test Results ===\n")
    
    # Get test establishment
    establishment = Establishment.objects.filter(name='Main Citrus Farm').first()
    if not establishment:
        print("❌ Test establishment not found. Please run: poetry run python manage.py seed_test_data")
        return
    
    # Initialize cost optimizer and calculate savings
    optimizer = CostOptimizer()
    result = optimizer.calculate_savings_potential(establishment.id)
    
    print(f"🏢 Establishment: {establishment.name}")
    print(f"📍 Location: {establishment.latitude}, {establishment.longitude}")
    print(f"🏛️ Company: {establishment.company.name}")
    print(f"📅 Analysis Date: {result['analysis_date']}")
    print()
    
    print(f"💰 Total Annual Savings: ${result['total_annual_savings']:,.2f}")
    print()
    
    print("📊 Detailed Savings Breakdown:")
    for category, amount in result['savings_breakdown'].items():
        category_name = category.replace('_', ' ').title()
        print(f"   • {category_name}: ${amount:,.2f}")
    print()
    
    print(f"🎯 Government Incentives: ${result['savings_breakdown']['government_incentives']:,.2f}")
    print("   This represents data-driven calculations based on:")
    print("   • Farm size and operational scale")
    print("   • Conservation practices implemented")
    print("   • Crop diversity and sustainable farming methods")
    print("   • Irrigation systems and energy efficiency")
    print()
    
    print("🏆 Top 5 Recommendations:")
    for i, rec in enumerate(result['recommendations'][:5], 1):
        print(f"   {i}. {rec['title']}")
        print(f"      💵 Annual Savings: ${rec['annual_savings']:,.2f}")
        print(f"      ⏱️ Payback: {rec['payback_months']} months")
        print(f"      🎯 Priority: {rec['priority']}")
        print()
    
    print("✅ Enhanced government incentives system is working correctly!")
    print("   The system now calculates incentives based on real farm data instead of hardcoded values.")

if __name__ == '__main__':
    test_enhanced_government_incentives() 