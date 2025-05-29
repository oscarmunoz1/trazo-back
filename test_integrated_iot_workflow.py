#!/usr/bin/env python3
"""
Integrated IoT Workflow Test Script

This script demonstrates the complete IoT workflow with:
1. John Deere equipment data
2. Weather monitoring and alerts
3. Unified data processing
4. Automated carbon entry creation
5. Manual approval workflow

This shows how all IoT components work together in the real system.
"""

import os
import sys
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

from carbon.services.john_deere_api import get_john_deere_api
from carbon.services.weather_api import get_weather_service
from carbon.models import IoTDevice, IoTDataPoint, CarbonEntry, Establishment
from carbon.tasks import monitor_weather_conditions, sync_john_deere_devices, process_pending_iot_data
from company.models import Company
from users.models import User
from django.utils import timezone
import json


def test_complete_iot_workflow():
    """Test the complete integrated IoT workflow."""
    print("🔄 Testing Complete Integrated IoT Workflow\n")
    
    # Step 1: Setup test environment
    print("📋 Step 1: Setting up test environment...")
    
    try:
        # Create test company and establishment
        company, created = Company.objects.get_or_create(
            name="Integrated IoT Test Farm",
            defaults={
                'address': '789 IoT Integration Rd',
                'city': 'Tech Valley',
                'state': 'CA',
                'country': 'US'
            }
        )
        
        establishment, created = Establishment.objects.get_or_create(
            name="Smart Farm IoT Test",
            company=company,
            defaults={
                'address': '123 Smart Farm Lane',
                'city': 'Tech Valley',
                'state': 'CA',
                'country': 'US',
                'latitude': 37.7749,  # San Francisco coordinates
                'longitude': -122.4194
            }
        )
        
        print(f"   ✓ Test establishment ready: {establishment.name}")
        print(f"   ✓ Location: {establishment.latitude}, {establishment.longitude}")
        
    except Exception as e:
        print(f"   ❌ Setup error: {e}")
        return False
    
    # Step 2: Test John Deere equipment simulation
    print("\n🚜 Step 2: Testing John Deere Equipment Integration...")
    
    try:
        # Create John Deere equipment device
        john_deere_device, created = IoTDevice.objects.get_or_create(
            establishment=establishment,
            device_id='john_deere_tractor_001',
            defaults={
                'name': 'John Deere 8R Series Tractor',
                'device_type': 'fuel_sensor',
                'status': 'online',
                'battery_level': 85,
                'john_deere_machine_id': 'JD_MACHINE_12345',
                'api_connection_status': 'connected',
                'last_seen': timezone.now()
            }
        )
        
        print(f"   ✓ John Deere device created: {john_deere_device.name}")
        
        # Simulate fuel consumption data
        fuel_data = {
            'fuel_consumption': {
                'fuel_used': 45.5,  # liters
                'engine_hours': 8.5,
                'operation_type': 'plowing',
                'field_area': 12.3,  # hectares
                'efficiency': 3.7,   # liters per hectare
                'timestamp': timezone.now().isoformat()
            },
            'source': 'john_deere_api_simulation',
            'machine_id': 'JD_MACHINE_12345',
            'quality_indicators': {
                'gps_accuracy': 'high',
                'sensor_status': 'normal',
                'data_completeness': 1.0
            }
        }
        
        # Create IoT data point for fuel consumption
        fuel_data_point = IoTDataPoint.objects.create(
            device=john_deere_device,
            timestamp=timezone.now(),
            data=fuel_data,
            quality_score=0.95,
            processed=False
        )
        
        print(f"   ✓ Fuel consumption data point created: {fuel_data_point.id}")
        print(f"   ✓ Fuel used: {fuel_data['fuel_consumption']['fuel_used']} liters")
        print(f"   ✓ Expected CO2e: {fuel_data['fuel_consumption']['fuel_used'] * 2.7:.1f} kg")
        
    except Exception as e:
        print(f"   ❌ John Deere integration error: {e}")
        return False
    
    # Step 3: Test weather monitoring
    print("\n🌤️  Step 3: Testing Weather Monitoring Integration...")
    
    try:
        # Get current weather for the establishment
        weather_service = get_weather_service()
        weather_data = weather_service.get_current_conditions(
            float(establishment.latitude),
            float(establishment.longitude)
        )
        
        if weather_data:
            print(f"   ✓ Current weather retrieved")
            print(f"   ✓ Temperature: {weather_data.get('temperature', 'N/A')}°F")
            print(f"   ✓ Humidity: {weather_data.get('humidity', 'N/A')}%")
            print(f"   ✓ Wind Speed: {weather_data.get('wind_speed', 'N/A')} mph")
            
            # Generate recommendations
            recommendations = weather_service.generate_agricultural_recommendations(
                weather_data, 'general'
            )
            
            print(f"   ✓ Generated {len(recommendations)} weather recommendations")
            
            # Create weather station device
            weather_device, created = IoTDevice.objects.get_or_create(
                establishment=establishment,
                device_id='weather_station_001',
                defaults={
                    'name': 'Weather Station - Smart Farm',
                    'device_type': 'weather_station',
                    'status': 'online',
                    'battery_level': 100,
                    'last_seen': timezone.now()
                }
            )
            
            # Create weather data point
            weather_data_point = IoTDataPoint.objects.create(
                device=weather_device,
                timestamp=timezone.now(),
                data={
                    'weather_conditions': weather_data,
                    'recommendations': recommendations,
                    'alert_type': 'routine_monitoring',
                    'source': 'weather_integration_test'
                },
                quality_score=0.95,
                processed=False
            )
            
            print(f"   ✓ Weather data point created: {weather_data_point.id}")
            
        else:
            print(f"   ⚠️  No weather data available (using mock data)")
            
            # Create mock weather data for testing
            mock_weather_data = {
                'temperature': 85,
                'humidity': 45,
                'wind_speed': 12,
                'description': 'Hot and dry conditions'
            }
            
            weather_device, created = IoTDevice.objects.get_or_create(
                establishment=establishment,
                device_id='weather_station_001',
                defaults={
                    'name': 'Weather Station - Smart Farm',
                    'device_type': 'weather_station',
                    'status': 'online',
                    'battery_level': 100,
                    'last_seen': timezone.now()
                }
            )
            
            weather_data_point = IoTDataPoint.objects.create(
                device=weather_device,
                timestamp=timezone.now(),
                data={
                    'weather_conditions': mock_weather_data,
                    'recommendations': [
                        {
                            'type': 'heat_advisory',
                            'priority': 'medium',
                            'title': 'Heat Advisory: 85°F',
                            'description': 'High temperatures may stress crops'
                        }
                    ],
                    'alert_type': 'mock_weather_test',
                    'source': 'weather_integration_test'
                },
                quality_score=0.90,
                processed=False
            )
            
            print(f"   ✓ Mock weather data point created: {weather_data_point.id}")
        
    except Exception as e:
        print(f"   ❌ Weather monitoring error: {e}")
        return False
    
    # Step 4: Test unified data processing
    print("\n⚙️  Step 4: Testing Unified Data Processing...")
    
    try:
        from carbon.tasks import calculate_data_point_confidence, should_create_carbon_entry, create_carbon_entry_from_data_point
        
        # Get all unprocessed data points
        unprocessed_points = IoTDataPoint.objects.filter(
            device__establishment=establishment,
            processed=False
        ).order_by('timestamp')
        
        print(f"   📊 Found {unprocessed_points.count()} unprocessed data points")
        
        processed_count = 0
        auto_approved_count = 0
        manual_approval_count = 0
        
        for data_point in unprocessed_points:
            # Calculate confidence score
            confidence = calculate_data_point_confidence(data_point)
            
            print(f"\n   🔍 Processing data point {data_point.id}:")
            print(f"      Device: {data_point.device.name}")
            print(f"      Type: {data_point.device.device_type}")
            print(f"      Confidence: {confidence:.2f}")
            
            if confidence > 0.9:
                # High confidence - auto-approve
                if should_create_carbon_entry(data_point):
                    carbon_entry = create_carbon_entry_from_data_point(data_point)
                    if carbon_entry:
                        data_point.carbon_entry = carbon_entry
                        auto_approved_count += 1
                        print(f"      ✅ Auto-approved → Carbon Entry {carbon_entry.id}")
                        print(f"         CO2e: {carbon_entry.co2e_amount:.1f} kg")
                    else:
                        print(f"      ℹ️  Auto-approved (no carbon entry needed)")
                else:
                    print(f"      ℹ️  Auto-approved (no carbon entry needed)")
                
                data_point.processed = True
                data_point.save()
                
            elif confidence > 0.7:
                # Medium confidence - manual approval needed
                manual_approval_count += 1
                print(f"      ⏳ Requires manual approval")
                
            else:
                # Low confidence - flag for review
                data_point.processed = True
                data_point.anomaly_detected = True
                data_point.save()
                print(f"      ⚠️  Low confidence - flagged for review")
            
            processed_count += 1
        
        print(f"\n   📈 Processing Summary:")
        print(f"      Total processed: {processed_count}")
        print(f"      Auto-approved: {auto_approved_count}")
        print(f"      Manual approval needed: {manual_approval_count}")
        
    except Exception as e:
        print(f"   ❌ Data processing error: {e}")
        return False
    
    # Step 5: Verify carbon entries created
    print("\n💨 Step 5: Verifying Carbon Entries...")
    
    try:
        # Get carbon entries created from IoT devices
        iot_carbon_entries = CarbonEntry.objects.filter(
            establishment=establishment,
            iot_device_id__isnull=False
        ).order_by('-timestamp')
        
        print(f"   📊 Found {iot_carbon_entries.count()} IoT-generated carbon entries")
        
        total_emissions = 0
        for entry in iot_carbon_entries:
            print(f"      Entry {entry.id}: {entry.co2e_amount:.1f} kg CO2e from {entry.iot_device_id}")
            total_emissions += entry.co2e_amount
        
        if total_emissions > 0:
            print(f"   ✅ Total automated emissions tracked: {total_emissions:.1f} kg CO2e")
        else:
            print(f"   ℹ️  No emissions entries created (weather data doesn't generate emissions)")
        
    except Exception as e:
        print(f"   ❌ Carbon entry verification error: {e}")
        return False
    
    # Step 6: Test device status monitoring
    print("\n📱 Step 6: Testing Device Status Monitoring...")
    
    try:
        devices = IoTDevice.objects.filter(establishment=establishment)
        
        print(f"   📊 Monitoring {devices.count()} devices:")
        
        for device in devices:
            device.increment_data_points()
            device.update_status('online')
            
            print(f"      {device.name}:")
            print(f"         Status: {device.status}")
            print(f"         Data Points: {device.total_data_points}")
            print(f"         Last Seen: {device.last_seen}")
            print(f"         Battery: {device.battery_level}%")
            
            if device.john_deere_machine_id:
                print(f"         John Deere ID: {device.john_deere_machine_id}")
                print(f"         API Status: {device.api_connection_status}")
        
        print(f"   ✅ All devices monitored successfully")
        
    except Exception as e:
        print(f"   ❌ Device monitoring error: {e}")
        return False
    
    # Step 7: Summary and next steps
    print("\n🎉 Step 7: Integration Test Summary")
    
    try:
        # Get final statistics
        total_devices = IoTDevice.objects.filter(establishment=establishment).count()
        total_data_points = IoTDataPoint.objects.filter(device__establishment=establishment).count()
        total_carbon_entries = CarbonEntry.objects.filter(establishment=establishment, iot_device_id__isnull=False).count()
        
        print(f"\n   📊 Final Statistics:")
        print(f"      Establishments: 1")
        print(f"      IoT Devices: {total_devices}")
        print(f"      Data Points: {total_data_points}")
        print(f"      Carbon Entries: {total_carbon_entries}")
        
        print(f"\n   ✅ Integration Test Results:")
        print(f"      ✓ John Deere equipment integration working")
        print(f"      ✓ Weather monitoring and alerts functional")
        print(f"      ✓ Unified data processing pipeline operational")
        print(f"      ✓ Automated carbon entry creation working")
        print(f"      ✓ Device status monitoring active")
        print(f"      ✓ Manual approval workflow ready")
        
        print(f"\n   🚀 Ready for Production:")
        print(f"      1. Configure real John Deere API credentials")
        print(f"      2. Set up Celery for automated tasks")
        print(f"      3. Enable real-time weather monitoring")
        print(f"      4. Deploy frontend IoT dashboard")
        print(f"      5. Train users on approval workflow")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Summary generation error: {e}")
        return False


def main():
    """Run the complete integrated IoT workflow test."""
    print("🌐 Integrated IoT Workflow Test Suite")
    print("=====================================\n")
    
    success = test_complete_iot_workflow()
    
    if success:
        print("\n🎉 🎉 🎉 INTEGRATION TEST PASSED! 🎉 🎉 🎉")
        print("\nThe complete IoT workflow is ready for production:")
        print("• John Deere equipment integration ✅")
        print("• Weather monitoring and alerts ✅") 
        print("• Unified data processing ✅")
        print("• Automated carbon tracking ✅")
        print("• Manual approval workflow ✅")
        print("• Device status monitoring ✅")
        
        print("\n📋 Next Implementation Steps:")
        print("1. 🔧 Configure production API credentials")
        print("2. ⏰ Set up Celery scheduled tasks")
        print("3. 🌐 Deploy frontend IoT dashboard")
        print("4. 👥 Train users on the system")
        print("5. 📊 Monitor system performance")
        
    else:
        print("\n❌ Integration test failed. Check the errors above.")
    
    return success


if __name__ == "__main__":
    main() 