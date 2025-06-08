#!/usr/bin/env python3
"""
IoT Automation Frontend Testing Script
Generates test IoT data to demonstrate automation percentages
"""

import os
import django
import random
from datetime import timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.base')
django.setup()

from users.models import User
from carbon.models import IoTDevice, IoTDataPoint, CarbonEntry
from carbon.services.automation_service import AutomationLevelService
from company.models import Establishment
from decimal import Decimal


def test_iot_automation_frontend():
    """Generate test IoT data to demonstrate automation in frontend"""
    
    print("=" * 60)
    print("🧪 IOT AUTOMATION FRONTEND TESTING")
    print("=" * 60)
    
    # Get basic test user
    try:
        user = User.objects.get(email='basic-test@trazo.com')
        establishment = Establishment.objects.filter(
            company__in=user.worksin_set.values('company')
        ).first()
        
        if not establishment:
            print("❌ No establishment found")
            return
            
        print(f"✅ Testing automation for: {establishment.name}")
        
    except User.DoesNotExist:
        print("❌ Basic test user not found")
        return
    
    # Get IoT devices
    devices = IoTDevice.objects.filter(establishment=establishment)
    if not devices.exists():
        print("❌ No IoT devices found")
        return
    
    print(f"📱 Found {devices.count()} IoT devices")
    
    # Initialize automation service
    service = AutomationLevelService()
    
    print(f"\n🎯 GENERATING TEST DATA:")
    print("-" * 40)
    
    # Generate 20 test data points with varying confidence levels
    total_generated = 0
    auto_approved_count = 0
    manual_review_count = 0
    
    # Generate data points with mixed confidence levels
    confidence_levels = [
        # Low confidence (should require manual review)
        0.65, 0.70, 0.75, 0.80, 0.85,
        # High confidence (eligible for automation, but subject to 50% limit)
        0.91, 0.92, 0.93, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99,
        # Medium confidence
        0.86, 0.87, 0.88, 0.89, 0.90
    ]
    
    for i, confidence in enumerate(confidence_levels):
        device = random.choice(devices)
        
        # Create IoT data point
        sensor_data = {
            'temperature': round(random.uniform(20, 30), 2),
            'humidity': round(random.uniform(40, 80), 2),
            'soil_moisture': round(random.uniform(20, 60), 2),
            'ph_level': round(random.uniform(6.0, 7.5), 2),
            'fuel_consumption': round(random.uniform(0.5, 5.0), 2) if device.device_type == 'fuel_sensor' else None
        }
        
        data_point = IoTDataPoint.objects.create(
            device=device,
            timestamp=timezone.now() - timedelta(minutes=random.randint(1, 60)),
            data=sensor_data,
            quality_score=confidence,
            processed=False
        )
        
        # Test automation decision
        should_auto = service.should_auto_approve_event(data_point, confidence)
        
        print(f"   📊 Point {i+1}: Device={device.name[:20]}, Confidence={confidence:.2f} → {'AUTO' if should_auto else 'MANUAL'}")
        
        if should_auto:
            auto_approved_count += 1
            # Create corresponding carbon entry (simulating automation)
            CarbonEntry.objects.create(
                establishment=establishment,
                type='emission',
                amount=round(random.uniform(0.1, 5.0), 2),
                co2e_amount=round(random.uniform(0.1, 5.0), 2),
                year=data_point.timestamp.year,
                timestamp=data_point.timestamp,
                description=f"Auto-processed from {device.name} (confidence: {confidence:.2f})",
                iot_device_id=device.device_id
            )
            data_point.processed = True
            data_point.save()
        else:
            manual_review_count += 1
            
        total_generated += 1
    
    # Calculate actual automation rate
    automation_rate = (auto_approved_count / total_generated) * 100 if total_generated > 0 else 0
    
    print(f"\n📈 AUTOMATION RESULTS:")
    print("-" * 40)
    print(f"   Total Events Generated: {total_generated}")
    print(f"   Auto-Approved: {auto_approved_count} ({automation_rate:.1f}%)")
    print(f"   Manual Review: {manual_review_count} ({100-automation_rate:.1f}%)")
    print(f"   Target Rate: ~50% (with randomization)")
    
    if 30 <= automation_rate <= 70:  # Allow variance due to randomization
        print(f"   ✅ Automation rate within expected range")
    else:
        print(f"   ⚠️ Automation rate outside expected range")
    
    print(f"\n🖥️ FRONTEND TESTING STEPS:")
    print("-" * 40)
    print(f"1. 🔄 Refresh your IoT Dashboard page")
    print(f"2. 📊 Check 'IoT Workflow & Smart Processing' section:")
    print(f"   - Auto-Approved should show: ~{auto_approved_count} processed")
    print(f"   - Manual Review should show: ~{manual_review_count} pending")
    print(f"3. 📋 Go to 'Events Requiring Approval' section")
    print(f"4. 🎯 Verify the automation percentage in 'Uso del Plan' page")
    print(f"   - Should show: 'IoT Automation: 50%'")
    
    # Get updated stats
    stats = service.get_automation_stats_for_establishment(establishment)
    
    print(f"\n📊 UPDATED AUTOMATION STATS:")
    print("-" * 40)
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print(f"\n✅ Test data generated successfully!")
    print(f"💡 TIP: Refresh the IoT Dashboard to see the new data in action")


if __name__ == "__main__":
    test_iot_automation_frontend() 