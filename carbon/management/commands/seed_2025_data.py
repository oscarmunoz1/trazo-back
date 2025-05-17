from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from company.models import Establishment
from product.models import Product
from history.models import History
from carbon.models import (
    CarbonSource, CarbonEntry, CarbonBenchmark, CarbonReport
)
from django.utils import timezone
import datetime

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
        except CarbonSource.DoesNotExist:
            self.stdout.write(self.style.ERROR('Carbon sources not found. Run seed_test_data first.'))
            return
        
        # Create 2025 emission entries
        entries_2025 = [
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'emission',
                'source': fertilizer,
                'amount': 80.0,
                'co2e_amount': 80.0,
                'year': 2025,
                'description': '2025 fertilization',
                'cost': 200.0,
                'usda_verified': True,
                'timestamp': timezone.now()
            },
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'emission',
                'source': diesel,
                'amount': 40.0,
                'co2e_amount': 40.0,
                'year': 2025,
                'description': '2025 equipment operation',
                'cost': 72.0,
                'usda_verified': True,
                'timestamp': timezone.now()
            },
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'offset',
                'source': fertilizer,  # Using fertilizer as a placeholder source
                'amount': 30.0,
                'co2e_amount': 30.0,
                'year': 2025,
                'description': '2025 tree planting offset',
                'cost': 50.0,
                'usda_verified': True,
                'timestamp': timezone.now()
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
                self.stdout.write(self.style.WARNING(f"2025 {entry_data['type']} entry already exists"))
        
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
            
        # Create 2025 carbon report
        report, created = CarbonReport.objects.get_or_create(
            establishment=establishment,
            period_start=datetime.date(2025, 1, 1),
            period_end=datetime.date(2025, 12, 31),
            defaults={
                'total_emissions': 120.0,
                'total_offsets': 30.0,
                'net_footprint': 90.0,
                'carbon_score': 80,
                'usda_verified': True,
                'cost_savings': 400.0,
                'recommendations': [
                    {'action': 'Implement renewable energy sources', 'savings': 250.0},
                    {'action': 'Expand cover cropping practices', 'savings': 150.0}
                ]
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created 2025 carbon report"))
        else:
            self.stdout.write(self.style.WARNING(f"2025 carbon report already exists"))
            
        self.stdout.write(self.style.SUCCESS('Successfully seeded 2025 carbon data')) 