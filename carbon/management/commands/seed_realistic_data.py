from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from company.models import Company, Establishment
from product.models import Product, Parcel
from history.models import History, WeatherEvent, ChemicalEvent, ProductionEvent, GeneralEvent, EquipmentEvent, SoilManagementEvent, PestManagementEvent
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

User = get_user_model()

class Command(BaseCommand):
    help = 'Create realistic agricultural operation data for California mid-sized producer'

    def handle(self, *args, **options):
        # Create realistic user - Maria Rodriguez, Farm Manager
        user, created = User.objects.get_or_create(
            email='oscar+test@trazo.io',
            defaults={
                'first_name': 'Oscar',
                'last_name': 'Muñoz',
                'is_active': True,
            }
        )
        if created:
            user.set_password('om123456')
            user.save()

        # Create realistic company - Valley Green Acres
        company, _ = Company.objects.get_or_create(
            name='Valley Green Acres LLC',
            defaults={
                'description': 'Sustainable family-owned citrus and almond operation serving premium markets since 1987. Committed to regenerative agriculture and carbon-neutral farming practices.',
                'address': '2847 Valley View Drive',
                'city': 'Fresno',
                'state': 'California',
                'country': 'USA',
                'contact_phone': '+1-559-555-0187',
                'contact_email': 'info@valleygreenacres.com',
                'website': 'https://valleygreenacres.com'
            }
        )

        # Create subscription
        plan, _ = Plan.objects.get_or_create(
            name='Professional',
            defaults={
                'slug': 'professional',
                'description': 'Professional plan for mid-sized agricultural operations',
                'price': 99.00,
                'interval': 'monthly',
                'features': {
                    'max_establishments': 5,
                    'max_parcels': 50,
                    'max_productions_per_year': 100,
                    'monthly_scan_limit': 10000,
                    'storage_limit_gb': 100,
                    'carbon_tracking': True,
                    'analytics': True,
                    'qr_codes': True,
                    'api_access': True
                }
            }
        )

        subscription, _ = Subscription.objects.get_or_create(
            company=company,
            plan=plan,
            defaults={
                'status': 'active',
                'current_period_start': timezone.now() - datetime.timedelta(days=30),
                'current_period_end': timezone.now() + datetime.timedelta(days=30)
            }
        )

        # Create realistic establishment
        establishment, _ = Establishment.objects.get_or_create(
            name='Valley Green Main Ranch',
            company=company,
            defaults={
                'description': 'Primary production facility spanning 285 acres with certified organic citrus groves and sustainable almond orchards. Features state-of-the-art irrigation systems and integrated pest management.',
                'address': '2847 Valley View Drive',
                'city': 'Fresno',
                'state': 'California',
                'zip_code': '93711',
                'latitude': 36.7378,
                'longitude': -119.7871
            }
        )

        # Create realistic products
        valencia_orange, _ = Product.objects.get_or_create(
            name='Valencia Orange',
            defaults={
                'description': 'Premium Valencia oranges, certified organic, hand-picked at optimal ripeness'
            }
        )

        navel_orange, _ = Product.objects.get_or_create(
            name='Navel Orange',
            defaults={
                'description': 'Sweet Navel oranges, organic certified, perfect for fresh consumption'
            }
        )

        nonpareil_almond, _ = Product.objects.get_or_create(
            name='Nonpareil Almond',
            defaults={
                'description': 'Premium Nonpareil almonds, sustainably grown, ideal for premium markets'
            }
        )

        # Create realistic parcels
        valencia_grove, _ = Parcel.objects.get_or_create(
            name='Valencia Grove East',
            establishment=establishment,
            defaults={
                'description': 'Mature Valencia orange grove, 15-year-old trees, drip irrigation, 125 acres',
                'area': 125.0
            }
        )

        navel_grove, _ = Parcel.objects.get_or_create(
            name='Navel Grove West',
            establishment=establishment,
            defaults={
                'description': 'Navel orange grove, 12-year-old trees, micro-sprinkler irrigation, 85 acres',
                'area': 85.0
            }
        )

        almond_orchard, _ = Parcel.objects.get_or_create(
            name='Nonpareil Orchard North',
            establishment=establishment,
            defaults={
                'description': 'Nonpareil almond orchard, 8-year-old trees, advanced drip system, 75 acres',
                'area': 75.0
            }
        )

        # Create current and finished productions for each parcel
        self.create_valencia_productions(valencia_grove, valencia_orange, user)
        self.create_navel_productions(navel_grove, navel_orange, user)
        self.create_almond_productions(almond_orchard, nonpareil_almond, user)

        # Create IoT devices
        self.create_realistic_iot_devices(establishment, user)

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created realistic agricultural data:\n'
                f'- Company: {company.name}\n'
                f'- User: {user.first_name} {user.last_name} ({user.email})\n'
                f'- Establishment: {establishment.name}\n'
                f'- Parcels: 3 (Valencia, Navel, Almond)\n'
                f'- Productions: 6 total (3 current, 3 finished)\n'
                f'- Events: 7+ per production with realistic agricultural data'
            )
        )

    def create_valencia_productions(self, parcel, product, user):
        """Create Valencia orange productions with realistic events"""
        
        # Current production
        current_production, _ = History.objects.get_or_create(
            name='Valencia Orange Harvest 2024',
            parcel=parcel,
            defaults={
                'type': 'OR',
                'start_date': timezone.now() - datetime.timedelta(days=45),
                'product': product,
                'description': 'Current Valencia orange production cycle, targeting 850 tons yield',
                'is_outdoor': True,
                'age_of_plants': '15 years',
                'number_of_plants': '2,850',
                'soil_ph': '6.8',
                'operator': user
            }
        )

        # Finished production
        finished_production, _ = History.objects.get_or_create(
            name='Valencia Orange Harvest 2023',
            parcel=parcel,
            defaults={
                'type': 'OR',
                'start_date': timezone.now() - datetime.timedelta(days=410),
                'finish_date': timezone.now() - datetime.timedelta(days=45),
                'product': product,
                'description': 'Completed Valencia orange production, excellent yield of 875 tons',
                'is_outdoor': True,
                'age_of_plants': '14 years',
                'number_of_plants': '2,850',
                'soil_ph': '6.9',
                'production_amount': 875000.0,
                'earning': 437500.0,
                'published': True,
                'operator': user,
            }
        )

        # Create events for current production
        self.create_valencia_events(current_production, user)
        # Create events for finished production
        self.create_valencia_events(finished_production, user, is_finished=True)

    def create_navel_productions(self, parcel, product, user):
        """Create Navel orange productions with realistic events"""
        
        # Current production
        current_production, _ = History.objects.get_or_create(
            name='Navel Orange Harvest 2024',
            parcel=parcel,
            defaults={
                'type': 'OR',
                'start_date': timezone.now() - datetime.timedelta(days=30),
                'product': product,
                'description': 'Current Navel orange production, early harvest variety',
                'is_outdoor': True,
                'age_of_plants': '12 years',
                'number_of_plants': '1,950',
                'soil_ph': '6.7',
                'operator': user,
            }
        )

        # Finished production
        finished_production, _ = History.objects.get_or_create(
            name='Navel Orange Harvest 2023',
            parcel=parcel,
            defaults={
                'type': 'OR',
                'start_date': timezone.now() - datetime.timedelta(days=395),
                'finish_date': timezone.now() - datetime.timedelta(days=30),
                'product': product,
                'description': 'Completed Navel orange harvest, premium quality fruit',
                'is_outdoor': True,
                'age_of_plants': '11 years',
                'number_of_plants': '1,950',
                'soil_ph': '6.8',
                'production_amount': 585000.0,
                'earning': 350100.0,
                'published': True,
                'operator': user,
            }
        )

        # Create events
        self.create_navel_events(current_production, user)
        self.create_navel_events(finished_production, user, is_finished=True)

    def create_almond_productions(self, parcel, product, user):
        """Create Nonpareil almond productions with realistic events"""
        
        # Current production
        current_production, _ = History.objects.get_or_create(
            name='Nonpareil Almond Harvest 2024',
            parcel=parcel,
            defaults={
                'type': 'AL',
                'start_date': timezone.now() - datetime.timedelta(days=60),
                'product': product,
                'description': 'Current almond production cycle, targeting 225,000 lbs',
                'is_outdoor': True,
                'age_of_plants': '8 years',
                'number_of_plants': '1,125',
                'soil_ph': '7.1',
                'operator': user,
            }
        )

        # Finished production
        finished_production, _ = History.objects.get_or_create(
            name='Nonpareil Almond Harvest 2023',
            parcel=parcel,
            defaults={
                'type': 'AL',
                'start_date': timezone.now() - datetime.timedelta(days=425),
                'finish_date': timezone.now() - datetime.timedelta(days=60),
                'product': product,
                'description': 'Completed almond harvest, record yield of 240,000 lbs',
                'is_outdoor': True,
                'age_of_plants': '7 years',
                'number_of_plants': '1,125',
                'soil_ph': '7.0',
                'production_amount': 240000.0,
                'earning': 720000.0,
                'published': True,
                'operator': user,
            }
        )

        # Create events
        self.create_almond_events(current_production, user)
        self.create_almond_events(finished_production, user, is_finished=True)

    def create_valencia_events(self, production, user, is_finished=False):
        """Create realistic events for Valencia orange production"""
        
        days_offset = 365 if is_finished else 0
        
        # Clear existing events
        EquipmentEvent.objects.filter(history=production).delete()
        ChemicalEvent.objects.filter(history=production).delete()
        ProductionEvent.objects.filter(history=production).delete()
        GeneralEvent.objects.filter(history=production).delete()
        SoilManagementEvent.objects.filter(history=production).delete()

        # Equipment Event - Pruning
        EquipmentEvent.objects.create(
            history=production,
            created_by=user,
            type='FC',
            description='Annual pruning with specialized citrus equipment',
            date=timezone.now() - datetime.timedelta(days=280 + days_offset),
            equipment_name='Kubota M7-172 with Phoenix Pruner',
            fuel_type='diesel',
            fuel_amount=85.0,
            area_covered='125 hectares',
            hours_used=12.0,
            maintenance_cost=450.0,
            index=1
        )

        # Chemical Event - Organic fertilizer
        ChemicalEvent.objects.create(
            history=production,
            created_by=user,
            type='FE',
            description='Organic citrus fertilizer application',
            date=timezone.now() - datetime.timedelta(days=220 + days_offset),
            commercial_name='Citrus-Tone Organic Fertilizer 6-3-3',
            volume='3,500 lbs',
            concentration='6-3-3',
            area='125 hectares',
            way_of_application='Broadcast spreader',
            time_period='Early morning',
            observation='OMRI certified organic fertilizer, slow-release nitrogen',
            index=2
        )

        # Production Event - Irrigation
        ProductionEvent.objects.create(
            history=production,
            created_by=user,
            type='IR',
            description='Drip irrigation system operation',
            date=timezone.now() - datetime.timedelta(days=180 + days_offset),
            observation='Micro-emitter drip irrigation, 2.5 GPH per tree, 18 hours total',
            index=3
        )

        # Chemical Event - Pest management
        ChemicalEvent.objects.create(
            history=production,
            created_by=user,
            type='PE',
            description='Organic pest control application',
            date=timezone.now() - datetime.timedelta(days=150 + days_offset),
            commercial_name='Neem Oil Plus (OMRI Certified)',
            volume='25 gallons',
            concentration='70% neem oil',
            area='125 hectares',
            way_of_application='Airblast sprayer',
            time_period='Late evening',
            observation='Targeting citrus leafminer and aphids, organic approved',
            index=4
        )

        # Soil Management Event
        SoilManagementEvent.objects.create(
            history=production,
            created_by=user,
            type='CO',
            description='Cover crop establishment - crimson clover',
            date=timezone.now() - datetime.timedelta(days=200 + days_offset),
            amendment_type='Crimson clover seed',
            amendment_amount='35 lbs/hectare',
            carbon_sequestration_potential=2.2,
            index=5
        )

        # Equipment Event - Harvest preparation
        EquipmentEvent.objects.create(
            history=production,
            created_by=user,
            type='FC',
            description='Harvest equipment preparation and calibration',
            date=timezone.now() - datetime.timedelta(days=30 + days_offset),
            equipment_name='Oxbo 6040 Citrus Harvester',
            fuel_type='diesel',
            fuel_amount=45.0,
            area_covered='125 hectares',
            hours_used=6.0,
            maintenance_cost=275.0,
            index=6
        )

        # General Event - Quality inspection
        GeneralEvent.objects.create(
            history=production,
            created_by=user,
            name='USDA Organic Certification Inspection',
            description='Annual organic certification inspection by CCOF',
            date=timezone.now() - datetime.timedelta(days=90 + days_offset),
            index=7
        )

        # Business Event (only for finished production)
        if is_finished:
            GeneralEvent.objects.create(
                history=production,
                created_by=user,
                name='Premium Valencia Orange Sale',
                description='Valencia orange premium sale to Whole Foods - 875,000 lbs sold for $437,500. Certified Organic, earned 15.5 carbon credits.',
                date=timezone.now() - datetime.timedelta(days=60 + days_offset),
                index=8
            )

    def create_navel_events(self, production, user, is_finished=False):
        """Create realistic events for Navel orange production"""
        
        days_offset = 365 if is_finished else 0
        
        # Clear existing events
        EquipmentEvent.objects.filter(history=production).delete()
        ChemicalEvent.objects.filter(history=production).delete()
        ProductionEvent.objects.filter(history=production).delete()
        GeneralEvent.objects.filter(history=production).delete()
        SoilManagementEvent.objects.filter(history=production).delete()

        # Equipment Event - Soil cultivation
        EquipmentEvent.objects.create(
            history=production,
            created_by=user,
            type='FC',
            description='Spring soil cultivation and weed management',
            date=timezone.now() - datetime.timedelta(days=260 + days_offset),
            equipment_name='John Deere 5100M with Disc Harrow',
            fuel_type='diesel',
            fuel_amount=65.0,
            area_covered='85 hectares',
            hours_used=8.0,
            maintenance_cost=320.0,
            index=1
        )

        # Chemical Event - Micronutrient application
        ChemicalEvent.objects.create(
            history=production,
            created_by=user,
            type='FE',
            description='Micronutrient foliar spray application',
            date=timezone.now() - datetime.timedelta(days=200 + days_offset),
            commercial_name='Citrus Micromax (Zinc, Iron, Manganese)',
            volume='150 gallons',
            concentration='2% solution',
            area='85 hectares',
            way_of_application='Foliar spray',
            time_period='Early morning',
            observation='Targeting micronutrient deficiencies in sandy soils',
            index=2
        )

        # Production Event - Pollination support
        ProductionEvent.objects.create(
            history=production,
            created_by=user,
            type='PL',
            description='Bee hive placement for enhanced pollination',
            date=timezone.now() - datetime.timedelta(days=240 + days_offset),
            observation='24 hives strategically placed, partnership with local beekeeper',
            index=3
        )

        # Soil Management Event
        SoilManagementEvent.objects.create(
            history=production,
            created_by=user,
            type='OM',
            description='Organic compost incorporation',
            date=timezone.now() - datetime.timedelta(days=180 + days_offset),
            amendment_type='Composted green waste',
            amendment_amount='4.5 tons/hectare',
            organic_matter_percentage=3.8,
            carbon_sequestration_potential=3.1,
            index=4
        )

        # Production Event - Irrigation upgrade
        ProductionEvent.objects.create(
            history=production,
            created_by=user,
            type='IR',
            description='Micro-sprinkler system upgrade',
            date=timezone.now() - datetime.timedelta(days=160 + days_offset),
            observation='Installation of pressure-compensating micro-sprinklers, 30% water savings',
            index=5
        )

        # Chemical Event - Disease prevention
        ChemicalEvent.objects.create(
            history=production,
            created_by=user,
            type='PE',
            description='Copper-based fungicide for citrus canker prevention',
            date=timezone.now() - datetime.timedelta(days=120 + days_offset),
            commercial_name='Kocide 3000 (Copper Hydroxide)',
            volume='45 lbs',
            concentration='46.1% copper hydroxide',
            area='85 hectares',
            way_of_application='Airblast sprayer',
            time_period='Late afternoon',
            observation='Preventive application during humid conditions',
            index=6
        )

        # General Event - Worker training
        GeneralEvent.objects.create(
            history=production,
            created_by=user,
            name='Integrated Pest Management Training',
            description='Annual IPM training for field workers',
            date=timezone.now() - datetime.timedelta(days=100 + days_offset),
            index=7
        )

        # Business Event (only for finished production)
        if is_finished:
            GeneralEvent.objects.create(
                history=production,
                created_by=user,
                name='Premium Navel Orange Direct Sales',
                description='Fresh Navel orange direct sales to Premium Produce Distributors - 585,000 lbs sold for $350,100. Certified Organic, earned 12.8 carbon credits.',
                date=timezone.now() - datetime.timedelta(days=45 + days_offset),
                index=8
            )

    def create_almond_events(self, production, user, is_finished=False):
        """Create realistic events for Nonpareil almond production"""
        
        days_offset = 365 if is_finished else 0
        
        # Clear existing events
        EquipmentEvent.objects.filter(history=production).delete()
        ChemicalEvent.objects.filter(history=production).delete()
        ProductionEvent.objects.filter(history=production).delete()
        GeneralEvent.objects.filter(history=production).delete()
        SoilManagementEvent.objects.filter(history=production).delete()

        # Equipment Event - Dormant season pruning
        EquipmentEvent.objects.create(
            history=production,
            created_by=user,
            type='FC',
            description='Dormant season mechanical pruning',
            date=timezone.now() - datetime.timedelta(days=300 + days_offset),
            equipment_name='Weiss McNair Hedger SW2400',
            fuel_type='diesel',
            fuel_amount=55.0,
            area_covered='75 hectares',
            hours_used=10.0,
            maintenance_cost=380.0,
            index=1
        )

        # Chemical Event - Pre-bloom nutrition
        ChemicalEvent.objects.create(
            history=production,
            created_by=user,
            type='FE',
            description='Pre-bloom nitrogen and potassium application',
            date=timezone.now() - datetime.timedelta(days=250 + days_offset),
            commercial_name='Almond Special 16-0-16 with Sulfur',
            volume='2,200 lbs',
            concentration='16-0-16-12S',
            area='75 hectares',
            way_of_application='Band application',
            time_period='Early morning',
            observation='Targeted pre-bloom nutrition for optimal flower development',
            index=2
        )

        # Production Event - Bee pollination
        ProductionEvent.objects.create(
            history=production,
            created_by=user,
            type='PL',
            description='Commercial bee hive placement for pollination',
            date=timezone.now() - datetime.timedelta(days=230 + days_offset),
            observation='2.5 hives per acre, strong colonies from certified beekeeper',
            index=3
        )

        # Production Event - Irrigation management
        ProductionEvent.objects.create(
            history=production,
            created_by=user,
            type='IR',
            description='Precision drip irrigation with soil moisture monitoring',
            date=timezone.now() - datetime.timedelta(days=180 + days_offset),
            observation='Smart irrigation system with neutron probes, 25% water reduction',
            index=4
        )

        # Chemical Event - Pest monitoring and treatment
        ChemicalEvent.objects.create(
            history=production,
            created_by=user,
            type='PE',
            description='Navel orangeworm moth control',
            date=timezone.now() - datetime.timedelta(days=130 + days_offset),
            commercial_name='Intrepid 2F (Methoxyfenozide)',
            volume='32 fl oz',
            concentration='22.8% methoxyfenozide',
            area='75 hectares',
            way_of_application='Airblast sprayer',
            time_period='Evening',
            observation='Targeted application based on trap monitoring, 450 degree days',
            index=5
        )

        # Soil Management Event
        SoilManagementEvent.objects.create(
            history=production,
            created_by=user,
            type='TI',
            description='Minimum tillage with cover crop integration',
            date=timezone.now() - datetime.timedelta(days=200 + days_offset),
            amendment_type='Legume cover crop mix',
            amendment_amount='45 lbs/hectare',
            carbon_sequestration_potential=2.8,
            index=6
        )

        # Equipment Event - Harvest
        EquipmentEvent.objects.create(
            history=production,
            created_by=user,
            type='FC',
            description='Mechanical almond harvest with shaker and sweeper',
            date=timezone.now() - datetime.timedelta(days=15 + days_offset),
            equipment_name='Exact 240 Shaker + Flory 850 Sweeper',
            fuel_type='diesel',
            fuel_amount=125.0,
            area_covered='75 hectares',
            hours_used=18.0,
            maintenance_cost=650.0,
            index=7
        )

        # General Event - Quality testing
        GeneralEvent.objects.create(
            history=production,
            created_by=user,
            name='Almond quality testing and grading',
            description='Post-harvest quality assessment by independent lab',
            date=timezone.now() - datetime.timedelta(days=10 + days_offset),
            index=8
        )

        # Business Event (only for finished production)
        if is_finished:
            GeneralEvent.objects.create(
                history=production,
                created_by=user,
                name='Premium Nonpareil Almond Sale',
                description='Premium Nonpareil almond sale to Blue Diamond Growers - 240,000 lbs sold for $720,000. Sustainable Agriculture certified, earned 22.5 carbon credits.',
                date=timezone.now() - datetime.timedelta(days=20 + days_offset),
                index=9
            )

    def create_realistic_iot_devices(self, establishment, user):
        """Create realistic IoT devices for the operation"""
        
        # Clear existing IoT data
        IoTDevice.objects.filter(establishment=establishment).delete()
        
        # Weather Station
        weather_station, _ = IoTDevice.objects.get_or_create(
            device_id='WS_DAVIS_001',
            establishment=establishment,
            defaults={
                'device_type': 'weather_station',
                'name': 'Davis Vantage Pro2 Plus',
                'manufacturer': 'Davis Instruments',
                'model': 'Vantage Pro2 Plus',
                'status': 'online',
                'battery_level': 94,
                'signal_strength': 'excellent',
                'latitude': 36.7378,
                'longitude': -119.7871,
                'last_maintenance': timezone.now() - datetime.timedelta(days=12)
            }
        )
        
        # Soil Moisture Sensors
        soil_sensor_valencia, _ = IoTDevice.objects.get_or_create(
            device_id='SOIL_SENTEK_001',
            establishment=establishment,
            defaults={
                'device_type': 'soil_moisture',
                'name': 'Sentek Drill & Drop Probe - Valencia',
                'manufacturer': 'Sentek',
                'model': 'Drill & Drop',
                'status': 'online',
                'battery_level': 87,
                'signal_strength': 'strong',
                'latitude': 36.7385,
                'longitude': -119.7865,
                'last_maintenance': timezone.now() - datetime.timedelta(days=8)
            }
        )
        
        # Equipment Monitor
        equipment_monitor, _ = IoTDevice.objects.get_or_create(
            device_id='KUBOTA_M7172_001',
            establishment=establishment,
            defaults={
                'device_type': 'equipment_monitor',
                'name': 'Kubota M7-172 Tractor Monitor',
                'manufacturer': 'Kubota',
                'model': 'M7-172',
                'status': 'online',
                'battery_level': 92,
                'signal_strength': 'strong',
                'latitude': 36.7375,
                'longitude': -119.7875,
                'last_maintenance': timezone.now() - datetime.timedelta(days=5)
            }
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Created realistic IoT devices:\n'
                f'- Weather Station: {weather_station.device_id}\n'
                f'- Soil Moisture: {soil_sensor_valencia.device_id}\n'
                f'- Equipment Monitor: {equipment_monitor.device_id}'
            )
        ) 