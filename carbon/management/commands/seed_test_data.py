from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from company.models import Company, Establishment
from product.models import Product, Parcel
from history.models import History, WeatherEvent, ChemicalEvent, ProductionEvent, GeneralEvent, EquipmentEvent, SoilManagementEvent, BusinessEvent
from carbon.models import (
    CarbonSource, CarbonEntry, CarbonCertification, CarbonBenchmark,
    CarbonReport, SustainabilityBadge, CarbonOffsetProject, CarbonOffsetPurchase
)
from subscriptions.models import Plan, Subscription
from users.models import WorksIn
from django.utils import timezone
import datetime
from users.constants import PRODUCER
import uuid

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

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created comprehensive test data for {user.email}:\n'
                f'- Company: {company.name}\n'
                f'- Establishment: {establishment.name}\n'
                f'- Parcel: {parcel.name}\n'
                f'- Current Production: {current_production.name}\n'
                f'- Finished Production: {finished_production.name}\n'
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