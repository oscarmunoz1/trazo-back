#!/usr/bin/env python3
"""
Generate Fresh IoT Data with Current Timestamps
Forces cache refresh by creating new data
"""

import os
import django
import random

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.base')
django.setup()

from carbon.models import IoTDataPoint, IoTDevice, CarbonEntry
from carbon.services.automation_service import AutomationLevelService
from company.models import Establishment
from users.models import User
from django.utils import timezone


def generate_fresh_iot_data():
    """Generate fresh IoT data with current timestamps"""
    
    print("🔄 GENERATING FRESH IOT DATA")
    print("=" * 40)
    
    # Get user and establishment
    user = User.objects.get(email='basic-test@trazo.com')
    establishment = Establishment.objects.filter(
        company__in=user.worksin_set.values('company')
    ).first()
    
    if not establishment:
        print("❌ No establishment found")
        return
    
    devices = IoTDevice.objects.filter(establishment=establishment)
    service = AutomationLevelService()
    
    print(f"🏢 Establishment: {establishment.name}")
    print(f"📱 Devices: {devices.count()}")
    
    # Delete today's test data to start fresh
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    IoTDataPoint.objects.filter(
        device__establishment=establishment,
        created_at__gte=today_start,
        data__reading_type='test_fresh_data'
    ).delete()
    
    print("\n🎯 Creating fresh data points:")
    print("-" * 40)
    
    # Create 8 fresh data points with varying confidence
    confidence_levels = [0.89, 0.91, 0.95, 0.88, 0.93, 0.97, 0.86, 0.99]
    
    auto_count = 0
    manual_count = 0
    
    for i, confidence in enumerate(confidence_levels):
        device = random.choice(devices)
        
        # Create sensor data
        sensor_data = {
            'temperature': round(random.uniform(20, 30), 2),
            'humidity': round(random.uniform(40, 80), 2),
            'fuel_consumption': round(random.uniform(1, 5), 2) if device.device_type == 'fuel_sensor' else None,
            'reading_type': 'test_fresh_data',
            'batch_id': f'fresh_{timezone.now().strftime("%H%M%S")}'
        }
        
        # Create IoT data point
        data_point = IoTDataPoint.objects.create(
            device=device,
            timestamp=timezone.now(),
            data=sensor_data,
            quality_score=confidence,
            processed=False
        )
        
        # Test automation decision
        should_auto = service.should_auto_approve_event(data_point, confidence)
        
        print(f"   📊 {device.name[:20]}: {confidence:.2f} → {'AUTO' if should_auto else 'MANUAL'}")
        
        # If auto-approved, create carbon entry and mark as processed
        if should_auto:
            CarbonEntry.objects.create(
                establishment=establishment,
                type='emission',
                amount=round(random.uniform(0.5, 3.0), 2),
                co2e_amount=round(random.uniform(0.5, 3.0), 2),
                year=data_point.timestamp.year,
                timestamp=data_point.timestamp,
                description=f"Fresh auto-processed from {device.name} (confidence: {confidence:.2f})",
                iot_device_id=device.device_id
            )
            data_point.processed = True
            data_point.save()
            auto_count += 1
        else:
            manual_count += 1
    
    print(f"\n📈 Results:")
    print(f"   Auto-approved: {auto_count}")
    print(f"   Manual review: {manual_count}")
    print(f"   Automation rate: {(auto_count / len(confidence_levels)) * 100:.1f}%")
    
    # Show updated stats
    stats = service.get_automation_stats_for_establishment(establishment)
    print(f"\n📊 Updated automation stats:")
    print(f"   Current automation rate: {stats.get('actual_automation_rate', 0):.1f}%")
    print(f"   Total pending review: {stats.get('pending_review', 0)}")
    
    print(f"\n✅ Fresh data generated!")
    print(f"🔄 Now do the following:")
    print(f"   1. Hard refresh your browser (Ctrl+F5 or Cmd+Shift+R)")
    print(f"   2. Check IoT Dashboard for new data")
    print(f"   3. Look for 'Fresh auto-processed' entries")
    print(f"   4. Verify automation percentage in 'Uso del Plan'")


if __name__ == "__main__":
    generate_fresh_iot_data() 