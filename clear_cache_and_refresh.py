#!/usr/bin/env python3
"""
Clear Django Cache and Refresh IoT Data
Comprehensive cache clearing and data verification
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.base')
django.setup()

from django.core.cache import cache
from django.core.management import call_command
from carbon.models import IoTDataPoint, CarbonEntry, IoTDevice
from company.models import Establishment
from carbon.services.automation_service import AutomationLevelService
from users.models import User
from datetime import datetime, timedelta
from django.utils import timezone


def clear_all_caches_and_refresh():
    """Clear all caches and refresh IoT data"""
    
    print("=" * 60)
    print("🧹 CLEARING CACHES & REFRESHING DATA")
    print("=" * 60)
    
    # 1. Clear Django cache
    print("1. 🗑️ Clearing Django cache...")
    cache.clear()
    print("   ✅ Django cache cleared")
    
    # 2. Clear any sessions
    print("2. 🗑️ Clearing sessions...")
    try:
        call_command('clearsessions')
        print("   ✅ Sessions cleared")
    except:
        print("   ⚠️ Sessions clear skipped")
    
    # 3. Get establishment
    try:
        user = User.objects.get(email='basic-test@trazo.com')
        establishment = Establishment.objects.filter(
            company__in=user.worksin_set.values('company')
        ).first()
        
        if not establishment:
            print("❌ No establishment found")
            return
            
        print(f"3. 🏢 Working with: {establishment.name}")
        
    except User.DoesNotExist:
        print("❌ Basic test user not found")
        return
    
    # 4. Clean old test data (keep only recent)
    print("4. 🧽 Cleaning old test data...")
    cutoff_time = timezone.now() - timedelta(hours=2)
    
    # Delete old IoT data points (older than 2 hours)
    old_data_points = IoTDataPoint.objects.filter(
        device__establishment=establishment,
        created_at__lt=cutoff_time
    )
    deleted_count = old_data_points.count()
    old_data_points.delete()
    print(f"   🗑️ Deleted {deleted_count} old IoT data points")
    
    # Delete old carbon entries
    old_carbon_entries = CarbonEntry.objects.filter(
        establishment=establishment,
        created_at__lt=cutoff_time,
        iot_device_id__isnull=False
    )
    deleted_carbon_count = old_carbon_entries.count()
    old_carbon_entries.delete()
    print(f"   🗑️ Deleted {deleted_carbon_count} old carbon entries")
    
    # 5. Show current data
    print("5. 📊 Current IoT Data:")
    print("-" * 40)
    
    devices = IoTDevice.objects.filter(establishment=establishment)
    print(f"   📱 IoT Devices: {devices.count()}")
    
    for device in devices:
        recent_points = IoTDataPoint.objects.filter(device=device).order_by('-created_at')[:3]
        print(f"   📡 {device.name}:")
        for point in recent_points:
            status = "AUTO" if point.processed else "PENDING"
            print(f"      - {point.quality_score:.2f} confidence @ {point.created_at.strftime('%H:%M')} ({status})")
    
    # 6. Get automation stats
    print("6. 🤖 Current Automation Stats:")
    print("-" * 40)
    
    service = AutomationLevelService()
    stats = service.get_automation_stats_for_establishment(establishment)
    
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    # 7. Show recent carbon entries
    print("7. 💨 Recent Carbon Entries:")
    print("-" * 40)
    
    recent_carbon = CarbonEntry.objects.filter(
        establishment=establishment
    ).order_by('-created_at')[:5]
    
    for entry in recent_carbon:
        source = entry.iot_device_id if entry.iot_device_id else "Manual"
        print(f"   - {entry.amount}kg CO2e from {source} @ {entry.created_at.strftime('%H:%M')}")
    
    print(f"\n✅ Cache cleared and data refreshed!")
    print(f"💡 Now refresh your browser and check the IoT Dashboard")
    print(f"🔄 You may also need to do a hard refresh (Ctrl+F5 or Cmd+Shift+R)")


if __name__ == "__main__":
    clear_all_caches_and_refresh() 