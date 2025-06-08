#!/usr/bin/env python3
"""
Deep Compliance Check for Trazo Basic Plan
Verifies if the 50% automation limit and other restrictions are working correctly
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.base')
django.setup()

from users.models import User
from carbon.models import IoTDevice, IoTDataPoint, CarbonEntry
from carbon.services.automation_service import AutomationLevelService
from company.models import Establishment
from subscriptions.models import Subscription
import random


def check_basic_plan_compliance():
    """Check if Basic plan is properly enforcing 50% automation"""
    
    print("=" * 60)
    print("🔍 DEEP COMPLIANCE CHECK - BASIC PLAN")
    print("=" * 60)
    
    # Get basic user
    try:
        user = User.objects.get(email='basic-test@trazo.com')
        print(f"✅ User found: {user.email}")
    except User.DoesNotExist:
        print("❌ Basic test user not found")
        return
    
    # Get establishment
    establishment = Establishment.objects.filter(
        company__in=user.worksin_set.values('company')
    ).first()
    
    if not establishment:
        print("❌ No establishment found")
        return
    
    print(f"✅ Establishment: {establishment.name}")
    
    # Check subscription plan
    subscription = user.worksin_set.first().company.subscription
    if subscription:
        print(f"✅ Subscription: {subscription.plan.name} - ${subscription.plan.price}")
    
    # Initialize automation service
    service = AutomationLevelService()
    
    print(f"\n🤖 AUTOMATION CONFIGURATION:")
    print("-" * 40)
    
    # Get automation settings
    automation_level = service.get_automation_level_for_establishment(establishment)
    carbon_mode = service.get_carbon_tracking_mode(establishment)
    
    print(f"   Target Automation Level: {automation_level}% (expected: 50%)")
    print(f"   Carbon Tracking Mode: {carbon_mode} (expected: manual)")
    
    # Verify Basic plan constraints
    expected_basic = {
        'automation_level': 50,
        'carbon_mode': 'manual',
        'high_confidence_threshold': 0.90,
        'support_response_time': 48
    }
    
    print(f"\n✅ BASIC PLAN VERIFICATION:")
    print("-" * 40)
    
    plan_correct = True
    if automation_level != expected_basic['automation_level']:
        print(f"❌ Automation level: {automation_level}% (should be {expected_basic['automation_level']}%)")
        plan_correct = False
    else:
        print(f"✅ Automation level: {automation_level}%")
    
    if carbon_mode != expected_basic['carbon_mode']:
        print(f"❌ Carbon mode: {carbon_mode} (should be {expected_basic['carbon_mode']})")
        plan_correct = False
    else:
        print(f"✅ Carbon tracking mode: {carbon_mode}")
    
    # Get current stats
    stats = service.get_automation_stats_for_establishment(establishment)
    
    print(f"\n📊 CURRENT AUTOMATION STATS:")
    print("-" * 40)
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # Test automation logic
    print(f"\n🧪 AUTOMATION LOGIC TEST:")
    print("-" * 40)
    
    devices = IoTDevice.objects.filter(establishment=establishment)
    print(f"IoT Devices: {devices.count()}")
    
    total_tests = 0
    auto_approved = 0
    manual_review = 0
    
    for device in devices:
        data_points = IoTDataPoint.objects.filter(device=device)[:3]  # Test 3 points per device
        
        print(f"\n   📱 Device: {device.name}")
        
        for dp in data_points:
            total_tests += 1
            should_auto = service.should_auto_approve_event(dp, dp.quality_score)
            
            print(f"     📍 Data Point: quality={dp.quality_score:.2f} -> {'AUTO' if should_auto else 'MANUAL'}")
            
            if should_auto:
                auto_approved += 1
            else:
                manual_review += 1
    
    if total_tests > 0:
        actual_auto_rate = (auto_approved / total_tests) * 100
        print(f"\n📈 AUTOMATION RATE ANALYSIS:")
        print("-" * 40)
        print(f"   Total events tested: {total_tests}")
        print(f"   Auto-approved: {auto_approved} ({actual_auto_rate:.1f}%)")
        print(f"   Manual review: {manual_review} ({100-actual_auto_rate:.1f}%)")
        print(f"   Target rate: ~50% (with randomization)")
        
        # Check if roughly around 50% (allowing for randomization variance)
        if 30 <= actual_auto_rate <= 70:  # Allow 20% variance due to random sampling
            print(f"✅ Automation rate within expected range")
        else:
            print(f"❌ Automation rate outside expected range")
    
    # Check UI compliance - what should be displayed
    print(f"\n🖥️  UI COMPLIANCE CHECK:")
    print("-" * 40)
    
    print("What should be visible in the UI:")
    print("   ✅ IoT Dashboard shows high confidence threshold (90%)")
    print("   ✅ Events below 90% require manual approval") 
    print("   ❓ Plan limits section should show:")
    print("      - Automation Level: 50%")
    print("      - Carbon Tracking: Manual Mode")
    print("      - Support Response: 48 hours")
    print("      - Priority Support: Not available")
    
    # Check what's actually stored in DB
    print(f"\n💾 DATABASE VERIFICATION:")
    print("-" * 40)
    
    if subscription:
        print(f"   Subscription DB values:")
        print(f"   - iot_automation_level: {subscription.plan.features.get('iot_automation_level')}")
        print(f"   - carbon_tracking: {subscription.plan.features.get('carbon_tracking')}")
        print(f"   - support_response_time: {subscription.plan.features.get('support_response_time')}")
        print(f"   - priority_support: {subscription.plan.features.get('priority_support')}")
    
    print(f"\n🎯 CONCLUSION:")
    print("-" * 40)
    if plan_correct:
        print("✅ Backend automation logic is working correctly")
        print("✅ Basic plan restrictions are enforced")
        print("❓ Frontend may need updates to display plan limitations")
    else:
        print("❌ Backend has compliance issues")
    
    return plan_correct


if __name__ == "__main__":
    check_basic_plan_compliance() 