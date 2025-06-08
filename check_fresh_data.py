#!/usr/bin/env python3
"""Simple data verification without triggering certificate font issues"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.base')

import django
django.setup()

from carbon.models import IoTDataPoint
from company.models import Establishment
from django.utils import timezone

# Get establishment
est = Establishment.objects.filter(name='Basic Test Farm').first()

if est:
    # Check fresh data
    fresh_data = IoTDataPoint.objects.filter(
        device__establishment=est,
        data__reading_type='test_fresh_data'
    ).order_by('-created_at')
    
    print(f"🆕 Fresh data points found: {fresh_data.count()}")
    
    for dp in fresh_data[:5]:
        status = "AUTO" if dp.processed else "PENDING"
        print(f"   - {dp.device.name}: {dp.quality_score:.2f} @ {dp.created_at.strftime('%H:%M:%S')} ({status})")
    
    # Check recent data overall
    recent_data = IoTDataPoint.objects.filter(
        device__establishment=est
    ).order_by('-created_at')[:10]
    
    print(f"\n📊 Recent 10 data points:")
    for dp in recent_data:
        batch_id = dp.data.get('batch_id', 'old') if isinstance(dp.data, dict) else 'old'
        status = "AUTO" if dp.processed else "PENDING"
        print(f"   - {dp.device.name}: {dp.quality_score:.2f} ({batch_id}) ({status})")
    
    print(f"\n✅ Data verification complete!")
else:
    print("❌ Establishment not found") 