#!/usr/bin/env python3
"""
Test API Endpoints
Simulate what the frontend calls to verify fresh data
"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.base')

import django
django.setup()

from carbon.models import IoTDevice, IoTDataPoint
from company.models import Establishment
from django.utils import timezone
from datetime import timedelta

establishment_id = 14
establishment = Establishment.objects.get(id=establishment_id)

print("🧪 Testing API Endpoints (Frontend perspective)")
print("=" * 60)

# 1. Test IoT Device Status API (what frontend calls)
print("1. 📡 IoT Device Status API:")
print("   GET /carbon/iot-devices/device_status/?establishment_id=14")
print("-" * 50)

devices = IoTDevice.objects.filter(establishment_id=establishment_id)
total_devices = devices.count()
online_devices = 0

for device in devices:
    # Count data points for today
    today = timezone.now().date()
    data_points_today = IoTDataPoint.objects.filter(
        device=device,
        timestamp__date=today
    ).count()
    
    # Signal strength calculation (from API)
    signal_strength = 'offline'
    if device.last_seen:
        time_diff = timezone.now() - device.last_seen
        if time_diff < timedelta(minutes=5):
            signal_strength = 'excellent'
            online_devices += 1
        elif time_diff < timedelta(minutes=15):
            signal_strength = 'strong'
            online_devices += 1
    
    print(f"   📱 {device.name}:")
    print(f"      Status: {device.status}")
    print(f"      Signal: {signal_strength}")
    print(f"      Last Seen: {device.last_seen.strftime('%H:%M:%S') if device.last_seen else 'Never'}")
    print(f"      Data Points Today: {data_points_today}")
    print(f"      Battery: {device.battery_level}%")

print(f"\n   📊 Summary:")
print(f"      Total Devices: {total_devices}")
print(f"      Online Devices: {online_devices}")
print(f"      Total Data Points Today: {sum(IoTDataPoint.objects.filter(device=d, timestamp__date=timezone.now().date()).count() for d in devices)}")

# 2. Test Recent Data Points (what frontend displays)
print(f"\n2. 📈 Recent IoT Data Points:")
print("   (What shows in dashboard charts)")
print("-" * 50)

recent_data = IoTDataPoint.objects.filter(
    device__establishment=establishment,
    timestamp__gte=timezone.now() - timedelta(hours=2)
).order_by('-timestamp')[:10]

for i, dp in enumerate(recent_data, 1):
    status = "AUTO-PROCESSED" if dp.processed else "PENDING REVIEW"
    time_str = dp.timestamp.strftime("%H:%M:%S")
    batch_info = dp.data.get('batch_id', 'no-batch') if hasattr(dp.data, 'get') else 'no-batch'
    
    print(f"   {i:2d}. {dp.device.name}: {dp.quality_score:.2f} @ {time_str} [{status}] batch:{batch_info}")

# 3. Test Automation Stats (what frontend shows in plan usage)
print(f"\n3. 🤖 Automation Level API:")
print("   GET /carbon/automation-rules/pending_events/")
print("-" * 50)

from carbon.services.automation_service import AutomationLevelService
service = AutomationLevelService()
stats = service.get_automation_stats_for_establishment(establishment)

print(f"   Target Automation Level: {stats['target_automation_level']}%")
print(f"   Actual Automation Rate: {stats['actual_automation_rate']:.1f}%")
print(f"   Carbon Tracking Mode: {stats['carbon_tracking_mode']}")
print(f"   Compliance Status: {stats['compliance_status']}")
print(f"   Total Data Points: {stats['total_data_points']}")
print(f"   Auto Processed: {stats['auto_processed']}")
print(f"   Pending Review: {stats['pending_review']}")

# 4. Check what frontend sees right now
print(f"\n4. ⏰ Current Frontend Status:")
print("-" * 50)
now = timezone.now()
print(f"   Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"   Latest Data Point: {recent_data[0].timestamp.strftime('%H:%M:%S') if recent_data else 'None'}")
print(f"   Data Age: {(now - recent_data[0].timestamp).total_seconds()/60:.1f} minutes ago" if recent_data else "No data")

# Show last few data points timestamps
print(f"\n   🕐 Last 5 data timestamps:")
for i, dp in enumerate(recent_data[:5], 1):
    time_diff = (now - dp.timestamp).total_seconds() / 60
    print(f"      {i}. {dp.timestamp.strftime('%H:%M:%S')} ({time_diff:.1f}min ago)")

print(f"\n✅ API Testing Complete!")
print(f"💡 Frontend should now see fresh data with timestamps from the last hour")
print(f"🔗 Refresh: http://app.localhost:3000/admin/dashboard/establishment/14/iot") 