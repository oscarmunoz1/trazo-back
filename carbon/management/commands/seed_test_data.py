from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from company.models import Company, Establishment
from product.models import Product, Parcel
from history.models import History, WeatherEvent, ChemicalEvent, ProductionEvent, GeneralEvent, EquipmentEvent, SoilManagementEvent, BusinessEvent
from carbon.models import (
    CarbonSource, CarbonEntry, CarbonCertification, CarbonBenchmark,
    CarbonReport, SustainabilityBadge, CarbonOffsetProject, CarbonOffsetPurchase,
    IoTDevice, IoTDataPoint, AutomationRule
)
from subscriptions.models import Plan, Subscription
from users.models import WorksIn
from django.utils import timezone
import datetime
from users.constants import PRODUCER
import uuid
import random
import math

User = get_user_model()

class Command(BaseCommand):
    help = 'Create comprehensive test data for ROI analysis with real operational events'

    def handle(self, *args, **options):
        # Get or create test user
        user, created = User.objects.get_or_create(
            email='test@example.com',
            defaults={
                'first_name': 'Test',
                'last_name': 'User',
                'is_active': True,
            }
        )
        if created:
        user.set_password('testpass123')
        user.save()

        # Create company
        company, _ = Company.objects.get_or_create(
            name='Test Agricultural Company',
            defaults={
                'description': 'Test company for ROI analysis',
                'address': '123 Farm Road',
                'city': 'Agricultural Valley',
                'state': 'California',
                'country': 'USA',
                'contact_phone': '+1-555-0123',
                'contact_email': 'info@testfarm.com',
                'website': 'https://testfarm.com'
            }
        )

        # Create establishment
        establishment, _ = Establishment.objects.get_or_create(
            name='Main Citrus Farm',
            company=company,
            defaults={
                'description': 'Primary citrus production facility',
                'address': '123 Farm Road',
                'city': 'Agricultural Valley',
                'state': 'California',
                'latitude': 34.0522,
                'longitude': -118.2437
            }
        )

        # Create product
        product, _ = Product.objects.get_or_create(
            name='Valencia Orange',
            defaults={
                'description': 'Premium Valencia oranges'
            }
        )

        # Create parcel
        parcel, _ = Parcel.objects.get_or_create(
            name='North Field',
            establishment=establishment,
            defaults={
                'description': 'Main orange grove - 10 hectares',
                'area': 10.0
            }
        )

        # Create current production
        current_production, _ = History.objects.get_or_create(
            name='Current Orange Production',
            parcel=parcel,
            defaults={
                'type': 'OR',
                'start_date': timezone.now() - datetime.timedelta(days=30),
                'product': product,
                'description': 'Summer 2024 orange production',
                'is_outdoor': True,
                'age_of_plants': '3 years',
                'number_of_plants': '100',
                'soil_ph': '6.5',
                'operator': user
            }
        )

        # Create finished production for comparison
        finished_production, _ = History.objects.get_or_create(
            name='Previous Orange Production',
            parcel=parcel,
            defaults={
                'type': 'OR',
                'start_date': timezone.now() - datetime.timedelta(days=180),
                'finish_date': timezone.now() - datetime.timedelta(days=30),
                'product': product,
                'description': 'Winter 2023-2024 orange production',
                'is_outdoor': True,
                'age_of_plants': '3 years',
                'number_of_plants': '100',
                'soil_ph': '6.8',
                'production_amount': 4800.0,
                'earning': 8400.0,
                'published': True,
                'operator': user
            }
        )

        # Clear existing events to avoid duplicates
        EquipmentEvent.objects.filter(history__in=[current_production, finished_production]).delete()
        ChemicalEvent.objects.filter(history__in=[current_production, finished_production]).delete()
        ProductionEvent.objects.filter(history__in=[current_production, finished_production]).delete()
        GeneralEvent.objects.filter(history__in=[current_production, finished_production]).delete()
        WeatherEvent.objects.filter(history__in=[current_production, finished_production]).delete()
        SoilManagementEvent.objects.filter(history__in=[current_production, finished_production]).delete()
        BusinessEvent.objects.filter(history__in=[current_production, finished_production]).delete()

        # Create operational events for current production (showing poor efficiency)
        self.create_current_production_events(current_production, user)
        
        # Create operational events for finished production (showing better efficiency)
        self.create_finished_production_events(finished_production, user)

        # Create benchmarks and badges
        self.create_benchmarks_and_badges()

        # Create IoT devices and simulate data
        self.create_iot_devices_and_data(establishment, user)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created comprehensive test data for {user.email}:\n'
                f'- Company: {company.name}\n'
                f'- Establishment: {establishment.name}\n'
                f'- Parcel: {parcel.name}\n'
                f'- Current Production: {current_production.name}\n'
                f'- Finished Production: {finished_production.name}\n'
                f'- IoT Devices: Created with realistic data points\n'
                f'This data provides comprehensive operational information for accurate ROI calculations.'
            )
        )

    def create_current_production_events(self, production, user):
        """Create events showing poor efficiency for current production"""
        
        # Equipment Events - Poor efficiency examples
        EquipmentEvent.objects.create(
            history=production,
            created_by=user,
            type='FC',
            description='Field preparation with tractor',
            date=timezone.now() - datetime.timedelta(days=28),
            equipment_name='John Deere 2440',
            fuel_type='diesel',
            fuel_amount=150.0,  # 15L/ha - poor efficiency
            area_covered='10 hectares',
            hours_used=8.0,
            maintenance_cost=200.0,
            certified=True,
            index=1
        )

        EquipmentEvent.objects.create(
            history=production,
            created_by=user,
            type='FC',
            description='Citrus harvesting equipment',
            date=timezone.now() - datetime.timedelta(days=5),
            equipment_name='Citrus Harvester CH-200',
            fuel_type='diesel',
            fuel_amount=280.0,  # 28L/ha - poor efficiency
            area_covered='10 hectares',
            hours_used=12.0,
            maintenance_cost=450.0,
            certified=True,
            index=2
        )

        # Chemical Events - Premium pricing examples
        ChemicalEvent.objects.create(
            history=production,
            created_by=user,
            type='FE',
            description='Premium nitrogen fertilizer application',
            date=timezone.now() - datetime.timedelta(days=22),
            commercial_name='Premium Citrus NPK 15-10-15',
            volume='200 kg',
            concentration='15-10-15',
            area='10 hectares',
            way_of_application='Broadcast',
            time_period='Morning',
            observation='Premium product - $3.8/kg, potential bulk savings available',
            certified=True,
            index=3
        )

        ChemicalEvent.objects.create(
            history=production,
            created_by=user,
            type='PE',
            description='Premium pesticide application',
            date=timezone.now() - datetime.timedelta(days=18),
            commercial_name='Premium Insect Control Pro',
            volume='15 liters',
            concentration='10%',
            area='10 hectares',
            way_of_application='Spray',
            time_period='Evening',
            observation='Premium product - $48/L, bulk options available',
            certified=True,
            index=4
        )

        # Production Events - High energy consumption
        ProductionEvent.objects.create(
            history=production,
            created_by=user,
            type='IR',
            description='High-consumption irrigation',
            date=timezone.now() - datetime.timedelta(days=12),
            observation='1000 m³ water, 24 hours operation, 1.2 kWh/m³ - inefficient pump',
            certified=True,
            index=5
        )

        # Soil Management Events - Conservation practices
        SoilManagementEvent.objects.create(
            history=production,
            created_by=user,
            type='CO',  # Cover crops
            description='Winter cover crop planting - crimson clover',
            date=timezone.now() - datetime.timedelta(days=120),
            amendment_type='Crimson clover seeds',
            amendment_amount='25 kg/hectare',
            carbon_sequestration_potential=1.5,
            certified=True,
            index=6
        )

        SoilManagementEvent.objects.create(
            history=production,
            created_by=user,
            type='TI',  # Tillage
            description='No-till planting implementation',
            date=timezone.now() - datetime.timedelta(days=180),
            amendment_type='Conservation tillage',
            carbon_sequestration_potential=2.0,
            certified=True,
            index=7
        )

        SoilManagementEvent.objects.create(
            history=production,
            created_by=user,
            type='OM',  # Organic matter
            description='Compost application for soil health',
            date=timezone.now() - datetime.timedelta(days=140),
            amendment_type='Organic compost',
            amendment_amount='5 tons/hectare',
            organic_matter_percentage=3.2,
            carbon_sequestration_potential=2.5,
            certified=True,
            index=8
        )

        # General Events - Conservation focus
        GeneralEvent.objects.create(
            history=production,
            created_by=user,
            name='Conservation tillage workshop attendance',
            description='Conservation tillage workshop attendance',
            date=timezone.now() - datetime.timedelta(days=250),
            certified=True,
            index=9
        )

        GeneralEvent.objects.create(
            history=production,
            created_by=user,
            name='Sustainable agriculture certification process',
            description='Sustainable agriculture certification process',
            date=timezone.now() - datetime.timedelta(days=220),
            certified=True,
            index=10
        )

        GeneralEvent.objects.create(
            history=production,
            created_by=user,
            name='Water conservation system upgrade',
            description='Water conservation system upgrade',
            date=timezone.now() - datetime.timedelta(days=150),
            certified=True,
            index=11
        )

        # Additional Production Events for REAP eligibility
        ProductionEvent.objects.create(
            history=production,
            created_by=user,
            type='IR',
            description='Drip irrigation system installation',
            date=timezone.now() - datetime.timedelta(days=200),
            observation='New drip irrigation system for water efficiency - $1,250 investment',
            certified=True,
            index=12
        )

        ProductionEvent.objects.create(
            history=production,
            created_by=user,
            type='IR',
            description='Irrigation efficiency monitoring setup',
            date=timezone.now() - datetime.timedelta(days=180),
            observation='Smart monitoring system for irrigation optimization - $350 investment',
            certified=True,
            index=13
        )

        # Soil Management Events
        SoilManagementEvent.objects.create(
            history=production,
            created_by=user,
            type='ST',  # Soil Test
            description='Annual soil analysis',
            date=timezone.now() - datetime.timedelta(days=30),
            soil_ph=6.8,
            organic_matter_percentage=3.2,
            amendment_type='Lime',
            amendment_amount='200 kg/ha',
            test_results={
                'nitrogen': 'Medium',
                'phosphorus': 'High',
                'potassium': 'Medium',
                'organic_matter': '3.2%',
                'ph': 6.8
            },
            carbon_sequestration_potential=2.5,
            certified=True,
            index=14
        )

    def create_finished_production_events(self, production, user):
        """Create events showing better efficiency for finished production"""
        
        # Equipment Events - Better efficiency examples
        EquipmentEvent.objects.create(
            history=production,
            created_by=user,
            type='FC',
            description='Efficient field preparation',
            date=timezone.now() - datetime.timedelta(days=160),
            equipment_name='John Deere 2440',
            fuel_type='diesel',
            fuel_amount=96.0,  # 12L/ha - good efficiency
            area_covered='8 hectares',
            hours_used=6.0,
            maintenance_cost=120.0,
            certified=True,
            index=1
        )

        EquipmentEvent.objects.create(
            history=production,
            created_by=user,
            type='FC',
            description='Efficient harvesting operation',
            date=timezone.now() - datetime.timedelta(days=35),
            equipment_name='Citrus Harvester CH-200',
            fuel_type='diesel',
            fuel_amount=176.0,  # 22L/ha - good efficiency
            area_covered='8 hectares',
            hours_used=10.0,
            maintenance_cost=300.0,
            certified=True,
            index=2
        )

        # Chemical Events - Bulk purchasing examples
        ChemicalEvent.objects.create(
            history=production,
            created_by=user,
            type='FE',
            description='Bulk fertilizer purchase',
            date=timezone.now() - datetime.timedelta(days=150),
            commercial_name='Bulk Citrus NPK 15-10-15',
            volume='400 kg',
            concentration='15-10-15',
            area='8 hectares',
            way_of_application='Broadcast',
            time_period='Morning',
            observation='Bulk purchase - 18% savings vs premium, $2.3/kg',
            certified=True,
            index=3
        )

        # Business Events
        BusinessEvent.objects.create(
            history=production,
            created_by=user,
            type='HS',
            description='Premium citrus sale',
            date=timezone.now() - datetime.timedelta(days=40),
            revenue_amount=8400.00,
            quantity_sold='4800 kg',
            buyer_name='Premium Citrus Co.',
            certification_type='Organic',
            carbon_credits_earned=2.5,
            certified=True,
            index=4
        )

    def create_benchmarks_and_badges(self):
        """Create industry benchmarks and sustainability badges"""

        # Create carbon benchmark
        CarbonBenchmark.objects.get_or_create(
            industry='Citrus',
            year=2024,
            crop_type='Orange',
            region='California',
            defaults={
                'average_emissions': 2500.0,
                'min_emissions': 1800.0,
                'max_emissions': 3500.0,
                'company_count': 150,
                'unit': 'kg CO2e per hectare',
                'source': 'USDA Agricultural Research Service',
                'usda_verified': True
            }
        )

        # Create sustainability badges
        SustainabilityBadge.objects.get_or_create(
            name='Gold Tier',
            defaults={
                'description': 'Exceptional carbon performance with net negative emissions',
                'minimum_score': 80,
                'is_automatic': True,
                'usda_verified': True
            }
        )

    def create_iot_devices_and_data(self, establishment, user):
        """Create IoT devices and realistic data points to test automatic event generation"""
        
        # Clear existing IoT data to avoid duplicates
        IoTDevice.objects.filter(establishment=establishment).delete()
        IoTDataPoint.objects.filter(device__establishment=establishment).delete()
        
        # Create John Deere Fuel Sensor
        fuel_sensor, _ = IoTDevice.objects.get_or_create(
            device_id='JD_TRACTOR_001',
            establishment=establishment,
            defaults={
                'device_type': 'fuel_sensor',
                'name': 'John Deere 6120M Tractor',
                'manufacturer': 'John Deere',
                'model': '6120M',
                'status': 'online',
                'battery_level': 85,
                'signal_strength': 'strong',
                'latitude': 34.0522,
                'longitude': -118.2437,
                'last_maintenance': timezone.now() - datetime.timedelta(days=30)
            }
        )
        
        # Create Weather Station
        weather_station, _ = IoTDevice.objects.get_or_create(
            device_id='WS_STATION_001',
            establishment=establishment,
            defaults={
                'device_type': 'weather_station',
                'name': 'Davis Vantage Pro2',
                'manufacturer': 'Davis Instruments',
                'model': 'Vantage Pro2',
                'status': 'online',
                'battery_level': 92,
                'signal_strength': 'excellent',
                'latitude': 34.0525,
                'longitude': -118.2435,
                'last_maintenance': timezone.now() - datetime.timedelta(days=15)
            }
        )
        
        # Create Soil Moisture Sensor
        soil_sensor, _ = IoTDevice.objects.get_or_create(
            device_id='SOIL_SENSOR_001',
            establishment=establishment,
            defaults={
                'device_type': 'soil_moisture',
                'name': 'Sentek Drill & Drop Probe',
                'manufacturer': 'Sentek',
                'model': 'Drill & Drop',
                'status': 'offline',  # Simulate offline device
                'battery_level': 15,  # Low battery
                'signal_strength': 'weak',
                'latitude': 34.0520,
                'longitude': -118.2440,
                'last_maintenance': timezone.now() - datetime.timedelta(days=45)
            }
        )
        
        # Create Equipment Monitor
        equipment_monitor, _ = IoTDevice.objects.get_or_create(
            device_id='EQUIP_MONITOR_001',
            establishment=establishment,
            defaults={
                'device_type': 'equipment_monitor',
                'name': 'Citrus Harvester CH-200',
                'manufacturer': 'Custom Harvester',
                'model': 'CH-200',
                'status': 'online',
                'battery_level': 78,
                'signal_strength': 'strong',
                'latitude': 34.0518,
                'longitude': -118.2442,
                'last_maintenance': timezone.now() - datetime.timedelta(days=10)
            }
        )
        
        # Generate realistic fuel sensor data points (last 7 days)
        self.create_fuel_sensor_data(fuel_sensor, user)
        
        # Generate realistic weather station data points (last 7 days)
        self.create_weather_station_data(weather_station, user)
        
        # Generate realistic soil moisture data points (last 3 days before going offline)
        self.create_soil_moisture_data(soil_sensor, user)
        
        # Generate realistic equipment monitor data points (last 5 days)
        self.create_equipment_monitor_data(equipment_monitor, user)
        
        # Create automation rules
        self.create_automation_rules(establishment, user)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Created IoT devices and data:\n'
                f'- Fuel Sensor: {fuel_sensor.device_id} ({fuel_sensor.status})\n'
                f'- Weather Station: {weather_station.device_id} ({weather_station.status})\n'
                f'- Soil Sensor: {soil_sensor.device_id} ({soil_sensor.status})\n'
                f'- Equipment Monitor: {equipment_monitor.device_id} ({equipment_monitor.status})\n'
                f'- Generated realistic data points for automatic carbon calculations'
            )
        )
    
    def create_fuel_sensor_data(self, device, user):
        """Create realistic fuel consumption data that should trigger automatic carbon calculations"""
        for day in range(7):
            date = timezone.now() - datetime.timedelta(days=day)
            
            # Simulate 2-3 fuel readings per day (morning and afternoon operations)
            for reading in range(random.randint(2, 3)):
                hour_offset = random.randint(6, 18)  # Operations between 6 AM and 6 PM
                timestamp = date.replace(hour=hour_offset, minute=random.randint(0, 59))
                
                # Realistic fuel consumption: 12-18 liters per hour of operation
                fuel_consumed = round(random.uniform(12.0, 18.0), 2)
                engine_hours = round(random.uniform(1.0, 3.0), 1)
                
                IoTDataPoint.objects.create(
                    device=device,
                    timestamp=timestamp,
                    data={
                        'fuel_liters': fuel_consumed,
                        'engine_hours': engine_hours,
                        'fuel_efficiency': round(fuel_consumed / engine_hours, 2),
                        'equipment_type': 'tractor',
                        'operation_type': random.choice(['plowing', 'planting', 'harvesting', 'spraying']),
                        'area_covered': round(random.uniform(0.5, 2.0), 1),  # hectares
                        'gps_location': {
                            'lat': 34.0522 + random.uniform(-0.001, 0.001),
                            'lng': -118.2437 + random.uniform(-0.001, 0.001)
                        }
                    },
                )
    
    def create_weather_station_data(self, device, user):
        """Create realistic weather data that should trigger recommendations"""
        for day in range(7):
            # Generate 24 hourly readings per day
            for hour in range(24):
                timestamp = timezone.now() - datetime.timedelta(days=day, hours=23-hour)
                
                # Realistic weather patterns for California citrus region
                base_temp = 22  # Base temperature in Celsius
                temp_variation = 8 * math.sin((hour - 6) * math.pi / 12)  # Daily temperature cycle
                temperature = round(base_temp + temp_variation + random.uniform(-2, 2), 1)
                
                # Humidity inversely related to temperature
                humidity = round(70 - (temperature - 20) * 2 + random.uniform(-10, 10), 1)
                humidity = max(20, min(95, humidity))  # Keep within realistic bounds
                
                # Wind speed - typically higher during day
                wind_speed = round(random.uniform(5, 25) if 8 <= hour <= 18 else random.uniform(2, 12), 1)
                
                # Pressure
                pressure = round(1013 + random.uniform(-15, 15), 1)
                
                IoTDataPoint.objects.create(
                    device=device,
                    timestamp=timestamp,
                    data={
                        'temperature': temperature,
                        'humidity': humidity,
                        'wind_speed': wind_speed,
                        'pressure': pressure,
                        'solar_radiation': round(random.uniform(0, 1200) if 6 <= hour <= 19 else 0, 1),
                        'rainfall': round(random.uniform(0, 2) if random.random() < 0.1 else 0, 1),  # 10% chance of rain
                        'uv_index': round(random.uniform(0, 11) if 8 <= hour <= 17 else 0, 1)
                    },
                )
    
    def create_soil_moisture_data(self, device, user):
        """Create soil moisture data for 3 days before device went offline"""
        for day in range(3, 0, -1):  # 3 days ago to 1 day ago
            # Generate 4 readings per day (every 6 hours)
            for reading in range(4):
                timestamp = timezone.now() - datetime.timedelta(days=day, hours=reading*6)
                
                # Soil moisture decreasing over time (needs irrigation)
                base_moisture = 45 - (3-day) * 5  # Decreasing moisture
                moisture = round(base_moisture + random.uniform(-3, 3), 1)
                moisture = max(15, min(60, moisture))  # Keep within realistic bounds
                
                IoTDataPoint.objects.create(
                    device=device,
                    timestamp=timestamp,
                    data={
                        'soil_moisture_percent': moisture,
                        'soil_temperature': round(random.uniform(18, 25), 1),
                        'soil_ph': round(random.uniform(6.2, 6.8), 1),
                        'electrical_conductivity': round(random.uniform(0.8, 1.5), 2),
                        'depth_cm': 30,
                        'sensor_location': 'North Field - Zone A'
                    },
                )
    
    def create_equipment_monitor_data(self, device, user):
        """Create equipment monitoring data for harvester"""
        for day in range(5):
            date = timezone.now() - datetime.timedelta(days=day)
            
            # Simulate 1-2 harvesting sessions per day
            for session in range(random.randint(1, 2)):
                hour_offset = random.randint(7, 16)  # Harvesting during daylight
                timestamp = date.replace(hour=hour_offset, minute=random.randint(0, 59))
                
                # Harvester performance metrics
                fuel_consumption = round(random.uniform(25, 35), 2)  # L/hour
                harvest_rate = round(random.uniform(800, 1200), 1)  # kg/hour
                
                IoTDataPoint.objects.create(
                    device=device,
                    timestamp=timestamp,
                    data={
                        'fuel_consumption_lph': fuel_consumption,
                        'harvest_rate_kgh': harvest_rate,
                        'engine_rpm': random.randint(1800, 2200),
                        'hydraulic_pressure': round(random.uniform(180, 220), 1),
                        'conveyor_speed': round(random.uniform(1.2, 1.8), 1),
                        'fruit_quality_score': round(random.uniform(8.5, 9.5), 1),
                        'operational_hours': round(random.uniform(2, 6), 1),
                        'maintenance_alerts': random.choice([[], ['Filter replacement due'], ['Oil change recommended']])
                    },
                )
    
    def create_automation_rules(self, establishment, user):
        """Create automation rules for IoT data processing"""
        
        # Rule for high fuel consumption alerts
        AutomationRule.objects.get_or_create(
            name='High Fuel Consumption Alert',
            establishment=establishment,
            defaults={
                'device_type': 'fuel_sensor',
                'trigger_type': 'threshold',
                'trigger_config': {
                    'fuel_efficiency': {'operator': 'greater_than', 'value': 16}  # L/hour
                },
                'action_type': 'send_alert',
                'action_config': {
                    'message': 'High fuel consumption detected - check equipment efficiency',
                    'severity': 'medium',
                    'notify_users': [user.id]
                },
                'is_active': True,
                'created_by': user
            }
        )
        
        # Rule for extreme weather alerts
        AutomationRule.objects.get_or_create(
            name='Extreme Weather Alert',
            establishment=establishment,
            defaults={
                'device_type': 'weather_station',
                'trigger_type': 'threshold',
                'trigger_config': {
                    'temperature': {'operator': 'greater_than', 'value': 35},
                    'wind_speed': {'operator': 'greater_than', 'value': 25}
                },
                'action_type': 'send_alert',
                'action_config': {
                    'message': 'Extreme weather conditions - consider protective measures',
                    'severity': 'high',
                    'notify_users': [user.id]
                },
                'is_active': True,
                'created_by': user
            }
        )
        
        # Rule for low soil moisture irrigation trigger
        AutomationRule.objects.get_or_create(
            name='Low Soil Moisture Irrigation',
            establishment=establishment,
            defaults={
                'device_type': 'soil_moisture',
                'trigger_type': 'threshold',
                'trigger_config': {
                    'soil_moisture_percent': {'operator': 'less_than', 'value': 25}
                },
                'action_type': 'create_event',
                'action_config': {
                    'irrigation_duration': 30,  # minutes
                    'irrigation_zone': 'North Field',
                    'notify_users': [user.id]
                },
                'is_active': True,
                'created_by': user
            }
        ) 