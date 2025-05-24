from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from company.models import Establishment
from product.models import Product
from history.models import History, WeatherEvent, ChemicalEvent, ProductionEvent
from carbon.models import (
    CarbonSource, CarbonEntry, CarbonBenchmark, CarbonReport, SustainabilityBadge
)
from django.utils import timezone
import datetime
import json

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds carbon data for 2025'

    def handle(self, *args, **kwargs):
        # Get existing user, establishment, and productions
        try:
            user = User.objects.get(email='test@example.com')
            establishment = Establishment.objects.get(name='Test Farm')
            current_production = History.objects.filter(
                name__contains='Current Orange Production',
                parcel__establishment=establishment
            ).first()
            
            if not current_production:
                self.stdout.write(self.style.ERROR('Current production not found. Run seed_test_data first.'))
                return
                
        except (User.DoesNotExist, Establishment.DoesNotExist):
            self.stdout.write(self.style.ERROR('Basic test data not found. Run seed_test_data first.'))
            return
            
        # Get carbon sources
        try:
            fertilizer = CarbonSource.objects.get(name='Citrus Fertilizer')
            diesel = CarbonSource.objects.get(name='Diesel Fuel')
            transportation = CarbonSource.objects.get_or_create(
                name='Transportation',
                defaults={
                    'description': 'Emissions from product transport',
                    'unit': 'kg',
                    'category': 'transportation',
                    'default_emission_factor': 1.5,
                    'usda_verified': True,
                    'cost_per_unit': 2.0
                }
            )[0]
            energy = CarbonSource.objects.get_or_create(
                name='Electricity',
                defaults={
                    'description': 'Electricity usage',
                    'unit': 'kWh',
                    'category': 'energy',
                    'default_emission_factor': 0.8,
                    'usda_verified': True,
                    'cost_per_unit': 0.15
                }
            )[0]
            waste = CarbonSource.objects.get_or_create(
                name='Organic Waste',
                defaults={
                    'description': 'Composting and waste management',
                    'unit': 'kg',
                    'category': 'waste',
                    'default_emission_factor': 0.3,
                    'usda_verified': True,
                    'cost_per_unit': 0.05
                }
            )[0]
            offset_trees = CarbonSource.objects.get_or_create(
                name='Tree Planting',
                defaults={
                    'description': 'Carbon sequestration through tree planting',
                    'unit': 'tree',
                    'category': 'offset',
                    'default_emission_factor': -25.0,
                    'usda_verified': True,
                    'cost_per_unit': 10.0
                }
            )[0]
            offset_renewable = CarbonSource.objects.get_or_create(
                name='Renewable Energy Credits',
                defaults={
                    'description': 'Purchased renewable energy credits',
                    'unit': 'credit',
                    'category': 'offset',
                    'default_emission_factor': -10.0,
                    'usda_verified': True,
                    'cost_per_unit': 15.0
                }
            )[0]
        except CarbonSource.DoesNotExist:
            self.stdout.write(self.style.ERROR('Carbon sources not found. Run seed_test_data first.'))
            return
        
        # Clear existing 2025 carbon entries
        CarbonEntry.objects.filter(year=2025).delete()
        
        # Create 2025 emission entries
        entries_2025 = [
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'emission',
                'source': fertilizer,
                'amount': 60.0,
                'co2e_amount': 60.0,
                'year': 2025,
                'description': '2025 fertilization',
                'cost': 150.0,
                'usda_verified': True,
                'timestamp': timezone.now() - datetime.timedelta(days=45)
            },
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'emission',
                'source': diesel,
                'amount': 35.0,
                'co2e_amount': 35.0,
                'year': 2025,
                'description': '2025 equipment operation',
                'cost': 63.0,
                'usda_verified': True,
                'timestamp': timezone.now() - datetime.timedelta(days=40)
            },
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'emission',
                'source': transportation,
                'amount': 15.0,
                'co2e_amount': 15.0,
                'year': 2025,
                'description': '2025 product transport',
                'cost': 30.0,
                'usda_verified': True,
                'timestamp': timezone.now() - datetime.timedelta(days=35)
            },
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'emission',
                'source': energy,
                'amount': 10.0,
                'co2e_amount': 10.0,
                'year': 2025,
                'description': '2025 electricity usage',
                'cost': 15.0,
                'usda_verified': True,
                'timestamp': timezone.now() - datetime.timedelta(days=30)
            },
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'emission',
                'source': waste,
                'amount': 5.0,
                'co2e_amount': 5.0,
                'year': 2025,
                'description': '2025 waste management',
                'cost': 2.5,
                'usda_verified': True,
                'timestamp': timezone.now() - datetime.timedelta(days=25)
            },
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'offset',
                'source': offset_trees,
                'amount': 20.0,
                'co2e_amount': 20.0,
                'year': 2025,
                'description': '2025 tree planting offset (20 trees)',
                'cost': 200.0,
                'usda_verified': True,
                'timestamp': timezone.now() - datetime.timedelta(days=20)
            },
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'offset',
                'source': offset_renewable,
                'amount': 10.0,
                'co2e_amount': 10.0,
                'year': 2025,
                'description': '2025 renewable energy credits',
                'cost': 150.0,
                'usda_verified': True,
                'timestamp': timezone.now() - datetime.timedelta(days=15)
            }
        ]
        
        for entry_data in entries_2025:
            entry, created = CarbonEntry.objects.get_or_create(
                establishment=entry_data['establishment'],
                production=entry_data['production'],
                type=entry_data['type'],
                source=entry_data['source'],
                year=entry_data['year'],
                description=entry_data['description'],
                defaults=entry_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created 2025 {entry_data['type']} entry: {entry_data['amount']} kg CO2e"))
            else:
                entry.amount = entry_data['amount']
                entry.co2e_amount = entry_data['co2e_amount']
                entry.cost = entry_data['cost']
                entry.timestamp = entry_data['timestamp']
                entry.save()
                self.stdout.write(self.style.WARNING(f"Updated 2025 {entry_data['type']} entry: {entry_data['amount']} kg CO2e"))
        
        # Create 2025 benchmark
        benchmark, created = CarbonBenchmark.objects.get_or_create(
            industry='Citrus',
            year=2025,
            defaults={
                'average_emissions': 0.5,
                'min_emissions': 0.3,
                'max_emissions': 0.8,
                'company_count': 120,
                'unit': 'kg CO2e/kg',
                'source': 'USDA 2025',
                'usda_verified': True,
                'crop_type': 'Oranges'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created 2025 benchmark for Citrus industry"))
        else:
            self.stdout.write(self.style.WARNING(f"2025 benchmark already exists"))
        
        # Create timeline events for the production
        # First, remove any existing events
        WeatherEvent.objects.filter(history=current_production).delete()
        ChemicalEvent.objects.filter(history=current_production).delete()
        ProductionEvent.objects.filter(history=current_production).delete()
        
        # Add planting event
        planting_event = ProductionEvent.objects.create(
            history=current_production,
            created_by=user,
            index=1,
            type='PL',  # Planting
            description='Planted organic orange trees using sustainable methods',
            date=timezone.now() - datetime.timedelta(days=180),
            observation='Used non-GMO seedlings and organic soil amendments',
            certified=True
        )
        
        # Add fertilization event
        chemical_event = ChemicalEvent.objects.create(
            history=current_production,
            created_by=user,
            index=2,
            type='FE',  # Fertilizer
            description='Applied organic fertilizer',
            date=timezone.now() - datetime.timedelta(days=120),
            commercial_name='Organic Citrus Boost',
            volume='40 kg',
            concentration='10-10-10',
            area='Full field',
            way_of_application='Drip system',
            time_period='Morning',
            observation='Used 40% less fertilizer than conventional methods',
            certified=True
        )
        
        # Add irrigation event
        irrigation_event = ProductionEvent.objects.create(
            history=current_production,
            created_by=user,
            index=3,
            type='IR',  # Irrigation
            description='Installed water-efficient drip irrigation',
            date=timezone.now() - datetime.timedelta(days=90),
            observation='Reduced water usage by 30% compared to industry average',
            certified=True
        )
        
        # Add weather event
        weather_event = WeatherEvent.objects.create(
            history=current_production,
            created_by=user,
            index=4,
            type='HT',  # High Temperature
            description='Heat wave managed with shade cloths',
            date=timezone.now() - datetime.timedelta(days=60),
            observation='Used renewable-powered fans and shade systems instead of conventional cooling',
            certified=True
        )
        
        # Add harvest event
        harvest_event = ProductionEvent.objects.create(
            history=current_production,
            created_by=user,
            index=5,
            type='HA',  # Harvesting
            description='Low-emission harvest using efficient equipment',
            date=timezone.now() - datetime.timedelta(days=30),
            observation='Used electric equipment charged with solar power',
            certified=True
        )
            
        # Create 2025 carbon report with proper fields
        report, created = CarbonReport.objects.get_or_create(
            establishment=establishment,
            production=current_production,
            period_start=datetime.date(2025, 1, 1),
            period_end=datetime.date(2025, 12, 31),
            defaults={
                'total_emissions': 125.0,
                'total_offsets': 30.0,
                'net_footprint': 95.0,
                'carbon_score': 85,
                'usda_verified': True,
                'cost_savings': 450.0,
                'recommendations': json.dumps([
                    {'action': 'Implement renewable energy sources', 'savings': 250.0},
                    {'action': 'Expand cover cropping practices', 'savings': 150.0},
                    {'action': 'Optimize irrigation scheduling', 'savings': 120.0},
                    {'action': 'Use more fuel-efficient equipment', 'savings': 180.0}
                ])
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created 2025 carbon report"))
        else:
            report.total_emissions = 125.0
            report.total_offsets = 30.0
            report.net_footprint = 95.0
            report.carbon_score = 85
            report.cost_savings = 450.0
            report.recommendations = json.dumps([
                {'action': 'Implement renewable energy sources', 'savings': 250.0},
                {'action': 'Expand cover cropping practices', 'savings': 150.0},
                {'action': 'Optimize irrigation scheduling', 'savings': 120.0},
                {'action': 'Use more fuel-efficient equipment', 'savings': 180.0}
            ])
            report.save()
            self.stdout.write(self.style.WARNING(f"Updated 2025 carbon report"))
        
        # Add or update badges
        gold_tier, _ = SustainabilityBadge.objects.get_or_create(
            name='Gold Tier',
            defaults={
                'description': 'This farm or production has a carbon score in the top 10% of all producers in its industry.',
                'minimum_score': 90,
                'is_automatic': True,
                'criteria': json.dumps({'carbon_score': 90}),
                'usda_verified': True
            }
        )
        
        silver_tier, _ = SustainabilityBadge.objects.get_or_create(
            name='Silver Tier',
            defaults={
                'description': 'This farm or production has a carbon score in the top 25% of all producers in its industry.',
                'minimum_score': 75,
                'is_automatic': True,
                'criteria': json.dumps({'carbon_score': 75}),
                'usda_verified': True
            }
        )
        
        usda_organic, _ = SustainabilityBadge.objects.get_or_create(
            name='USDA Organic',
            defaults={
                'description': 'USDA certified organic production.',
                'minimum_score': 0,
                'is_automatic': False,
                'criteria': json.dumps({'usda_organic': True}),
                'usda_verified': True
            }
        )
        
        # Add badges to production
        silver_tier.productions.add(current_production)
        usda_organic.productions.add(current_production)
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded 2025 carbon data')) 