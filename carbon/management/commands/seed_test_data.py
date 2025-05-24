from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from company.models import Company, Establishment
from product.models import Product, Parcel
from history.models import History, WeatherEvent, ChemicalEvent, ProductionEvent, GeneralEvent
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
    help = 'Seeds test data for carbon features'

    def handle(self, *args, **kwargs):
        # Create test user
        user, _ = User.objects.get_or_create(
            email='test@example.com',
            defaults={
                'first_name': 'Test',
                'last_name': 'User',
                'is_active': True,
                'user_type': PRODUCER
            }
        )
        user.set_password('testpass123')
        user.save()

        # Create test plan
        plan, _ = Plan.objects.get_or_create(
            name='Enterprise',
            slug='enterprise',
            defaults={
                'description': 'Enterprise plan with all features',
                'price': 99.99,
                'interval': 'monthly',
                'features': {
                    'max_establishments': 10,
                    'max_productions': 100,
                    'max_storage_gb': 100,
                    'max_scans': 1000,
                    'carbon_tracking': True,
                    'carbon_certificates': True,
                    'carbon_analytics': True,
                    'carbon_benchmarks': True,
                    'carbon_recommendations': True
                }
            }
        )

        # Create test company
        company, _ = Company.objects.get_or_create(
            name='Test Company',
            defaults={
                'description': 'Test company for carbon features'
            }
        )

        # Create subscription for company
        subscription, _ = Subscription.objects.get_or_create(
            company=company,
            defaults={
                'plan': plan,
                'status': 'active',
                'current_period_start': timezone.now(),
                'current_period_end': timezone.now() + datetime.timedelta(days=30)
            }
        )

        # Create test establishment
        establishment, _ = Establishment.objects.get_or_create(
            name='Test Farm',
            company=company,
            defaults={
                'address': '123 Test St',
                'city': 'Test City',
                'state': 'Test State',
                'country': 'Test Country',
                'description': 'Test farm for carbon features'
            }
        )

        # Associate user with company and establishment
        works_in, _ = WorksIn.objects.get_or_create(
            user=user,
            company=company,
            defaults={
                'role': 'CA'  # Company Admin
            }
        )
        works_in.establishments_in_charge.add(establishment)

        # Create test product
        product, _ = Product.objects.get_or_create(
            name='Oranges',
            defaults={
                'description': 'Organic oranges'
            }
        )

        # Create test parcel
        parcel, _ = Parcel.objects.get_or_create(
            name='Orange Field 1',
            establishment=establishment,
            defaults={
                'description': 'Main orange field',
                'area': 10.0,
                'product': product,
                'crop_type': 'Citrus',
                'soil_type': 'Loam'
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

        # Add events to current production
        events = [
            # Weather Events
            {
                'model': WeatherEvent,
                'type': 'HT',  # High Temperature
                'description': 'Heat wave affecting irrigation needs',
                'date': timezone.now() - datetime.timedelta(days=25),
                'observation': 'Temperatures above 35°C for 3 consecutive days',
                'certified': True
            },
            # Chemical Events
            {
                'model': ChemicalEvent,
                'type': 'FE',  # Fertilizer
                'description': 'Spring fertilization',
                'date': timezone.now() - datetime.timedelta(days=20),
                'commercial_name': 'Organic Citrus Fertilizer',
                'volume': '50 kg',
                'concentration': '10-10-10',
                'area': 'Full field',
                'way_of_application': 'Broadcast',
                'time_period': 'Morning',
                'observation': 'Applied before irrigation',
                'certified': True
            },
            # Production Events
            {
                'model': ProductionEvent,
                'type': 'IR',  # Irrigation
                'description': 'Drip irrigation maintenance',
                'date': timezone.now() - datetime.timedelta(days=15),
                'observation': 'Adjusted drip lines for better coverage',
                'certified': True
            }
        ]

        for i, event_data in enumerate(events, 1):
            event = event_data['model'].objects.create(
                history=current_production,
                created_by=user,
                index=i,
                **{k: v for k, v in event_data.items() if k != 'model'}
            )

        # Create finished and published production
        finished_production, _ = History.objects.get_or_create(
            name='Winter 2023 Orange Production',
            parcel=parcel,
            defaults={
                'type': 'OR',
                'start_date': timezone.now() - datetime.timedelta(days=180),
                'finish_date': timezone.now() - datetime.timedelta(days=30),
                'product': product,
                'description': 'Winter 2023 orange production',
                'is_outdoor': True,
                'age_of_plants': '2.5 years',
                'number_of_plants': '100',
                'soil_ph': '6.5',
                'published': True,
                'production_amount': 5000.0,
                'lot_id': 'W23-001',
                'operator': user
            }
        )

        # Add events to finished production
        events = [
            # Weather Events
            {
                'model': WeatherEvent,
                'type': 'FR',  # Frost
                'description': 'Early morning frost',
                'date': timezone.now() - datetime.timedelta(days=150),
                'observation': 'Temperature dropped to -2°C',
                'certified': True
            },
            # Chemical Events
            {
                'model': ChemicalEvent,
                'type': 'PE',  # Pesticide
                'description': 'Pest control application',
                'date': timezone.now() - datetime.timedelta(days=120),
                'commercial_name': 'Organic Pest Control',
                'volume': '20 L',
                'concentration': '5%',
                'area': 'Full field',
                'way_of_application': 'Spray',
                'time_period': 'Evening',
                'observation': 'Applied after sunset',
                'certified': True
            },
            # Production Events
            {
                'model': ProductionEvent,
                'type': 'HA',  # Harvesting
                'description': 'Main harvest',
                'date': timezone.now() - datetime.timedelta(days=30),
                'observation': 'Harvested 5000 kg of oranges',
                'certified': True
            }
        ]

        for i, event_data in enumerate(events, 1):
            event = event_data['model'].objects.create(
                history=finished_production,
                created_by=user,
                index=i,
                **{k: v for k, v in event_data.items() if k != 'model'}
            )

        # Create carbon sources
        sources = [
            {
                'name': 'Citrus Fertilizer',
                'description': 'Organic citrus fertilizer',
                'unit': 'kg',
                'category': 'fertilizer',
                'default_emission_factor': 1.2,
                'usda_verified': True,
                'cost_per_unit': 2.5
            },
            {
                'name': 'Diesel Fuel',
                'description': 'Farm equipment fuel',
                'unit': 'liter',
                'category': 'fuel',
                'default_emission_factor': 2.7,
                'usda_verified': True,
                'cost_per_unit': 1.8
            }
        ]

        for source_data in sources:
            CarbonSource.objects.get_or_create(
                name=source_data['name'],
                defaults=source_data
            )

        # Create carbon entries for current production
        entries = [
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'emission',
                'source': CarbonSource.objects.get(name='Citrus Fertilizer'),
                'amount': 100.0,
                'year': 2024,
                'description': 'Spring fertilization',
                'cost': 250.0,
                'usda_verified': True
            },
            {
                'establishment': establishment,
                'production': current_production,
                'created_by': user,
                'type': 'emission',
                'source': CarbonSource.objects.get(name='Diesel Fuel'),
                'amount': 50.0,
                'year': 2024,
                'description': 'Irrigation maintenance',
                'cost': 90.0,
                'usda_verified': True
            }
        ]

        for entry_data in entries:
            CarbonEntry.objects.get_or_create(
                establishment=entry_data['establishment'],
                production=entry_data['production'],
                type=entry_data['type'],
                source=entry_data['source'],
                year=entry_data['year'],
                defaults=entry_data
            )

        # Create carbon entries for finished production
        entries = [
            {
                'establishment': establishment,
                'production': finished_production,
                'created_by': user,
                'type': 'emission',
                'source': CarbonSource.objects.get(name='Citrus Fertilizer'),
                'amount': 120.0,
                'year': 2023,
                'description': 'Winter fertilization',
                'cost': 300.0,
                'usda_verified': True
            },
            {
                'establishment': establishment,
                'production': finished_production,
                'created_by': user,
                'type': 'emission',
                'source': CarbonSource.objects.get(name='Diesel Fuel'),
                'amount': 80.0,
                'year': 2023,
                'description': 'Harvesting equipment',
                'cost': 144.0,
                'usda_verified': True
            }
        ]

        for entry_data in entries:
            CarbonEntry.objects.get_or_create(
                establishment=entry_data['establishment'],
                production=entry_data['production'],
                type=entry_data['type'],
                source=entry_data['source'],
                year=entry_data['year'],
                defaults=entry_data
            )

        # Create carbon certification with unique ID
        unique_id = f'USDA-ORG-{establishment.id}-{uuid.uuid4().hex[:8]}'
        CarbonCertification.objects.get_or_create(
            establishment=establishment,
            production=None,  # Only associate with establishment
            defaults={
                'certifier': 'USDA Organic',
                'certificate_id': unique_id,
                'issue_date': timezone.now().date(),
                'is_usda_soe_verified': True
            }
        )

        # Create benchmark for carbon footprint reference
        benchmark, _ = CarbonBenchmark.objects.get_or_create(
            industry='Citrus',
            year=timezone.now().year,
            defaults={
                'average_emissions': 0.5,  # kg CO2e per kg of oranges
                'min_emissions': 0.3,
                'max_emissions': 0.8,
                'company_count': 50,
                'unit': 'kg CO2e/kg',
                'source': 'USDA SOE 2024',
                'usda_verified': True,
                'crop_type': 'Orange',
                'region': 'California'
            }
        )

        # Create carbon report for current production
        CarbonReport.objects.get_or_create(
            establishment=establishment,
            production=current_production,
            period_start=datetime.date(2024, 1, 1),
            period_end=datetime.date(2024, 12, 31),
            defaults={
                'total_emissions': 150.0,
                'total_offsets': 50.0,
                'net_footprint': 100.0,
                'carbon_score': 75,
                'usda_verified': True,
                'cost_savings': 340.0,
                'recommendations': [
                    {'action': 'Switch to drip irrigation', 'savings': 200.0},
                    {'action': 'Use organic fertilizer', 'savings': 140.0}
                ]
            }
        )

        # Create carbon report for finished production
        CarbonReport.objects.get_or_create(
            establishment=establishment,
            production=finished_production,
            period_start=datetime.date(2023, 7, 1),
            period_end=datetime.date(2023, 12, 31),
            defaults={
                'total_emissions': 200.0,
                'total_offsets': 80.0,
                'net_footprint': 120.0,
                'carbon_score': 65,
                'usda_verified': True,
                'cost_savings': 444.0,
                'recommendations': [
                    {'action': 'Optimize harvesting schedule', 'savings': 200.0},
                    {'action': 'Use more efficient equipment', 'savings': 244.0}
                ]
            }
        )

        # Create sustainability badge
        SustainabilityBadge.objects.get_or_create(
            name='Gold Tier',
            criteria={'net_footprint': 0},
            description='Achieved carbon neutrality',
            usda_verified=True
        )

        # Create carbon offset project
        project, _ = CarbonOffsetProject.objects.get_or_create(
            name='California Reforestation',
            description='Tree planting in California',
            project_type='Reforestation',
            certification_standard='USDA',
            location='California',
            price_per_ton=50.00,
            available_capacity=1000.00
        )

        # Create carbon offset purchase
        CarbonOffsetPurchase.objects.get_or_create(
            project=project,
            user=user,
            amount=10.00,
            price_per_ton=50.00,
            total_price=500.00,
            status='completed',
            is_verified=True
        )

        # Enhanced finished production with consumer-facing data
        if finished_production:
            # Add farmer story data
            finished_production.farmer_name = "John Smith"
            finished_production.farmer_bio = "Third-generation farmer committed to sustainable practices since 1980"
            finished_production.farmer_photo = "https://images.unsplash.com/photo-1520052203542-d3095f1b6cf0?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMTc3M3wwfDF8c2VhcmNofDI0fHxmYXJtZXJ8ZW58MHx8fHwxNzA0ODQ1NzE1fDA&ixlib=rb-4.0.3&q=80&w=1080"
            finished_production.farmer_location = "Central Valley, California"
            finished_production.farmer_certifications = ["USDA Organic", "Fair Trade"]
            finished_production.sustainability_initiatives = [
                "Solar-powered irrigation",
                "Compost-based fertilization",
                "Cover cropping for soil health",
                "Water conservation through drip irrigation",
                "Renewable energy use"
            ]
            finished_production.carbon_reduction = 25000  # kg CO2e reduced annually
            finished_production.years_of_practice = 15
            finished_production.save()
            
            # Add carbon data with relatable footprint
            total_emissions = 0.3  # kg CO2e per kg
            total_offsets = 0.2    # kg CO2e per kg
            net_footprint = total_emissions - total_offsets
            relatable_footprint = "like driving 1 mile"  # For consumer understanding
            
            carbon_report, _ = CarbonReport.objects.get_or_create(
                production=finished_production,
                defaults={
                    'period_start': finished_production.start_date,
                    'period_end': finished_production.finish_date or timezone.now(),
                    'total_emissions': total_emissions * finished_production.production_amount,
                    'total_offsets': total_offsets * finished_production.production_amount,
                    'net_footprint': net_footprint * finished_production.production_amount,
                    'carbon_score': CarbonEntry.calculate_carbon_score(
                        total_emissions * finished_production.production_amount,
                        total_offsets * finished_production.production_amount,
                        benchmark.average_emissions * finished_production.production_amount
                    ),
                    'usda_verified': True,
                    'cost_savings': 1500.0,
                    'recommendations': [
                        {
                            'title': 'Efficient Irrigation',
                            'description': 'This producer uses water-saving irrigation techniques',
                            'impact': 'Reduces water usage by up to 30% compared to conventional methods',
                            'cost_savings': 'Saves approximately $500 per acre annually',
                            'implementation': 'Drip irrigation and soil moisture monitoring',
                            'category': 'water'
                        },
                        {
                            'title': 'Organic Fertilizers',
                            'description': 'This product is grown with natural fertilizers',
                            'impact': 'Reduces chemical runoff and builds soil health',
                            'cost_savings': 'Improves soil quality over time',
                            'implementation': 'Compost and natural nutrient sources',
                            'category': 'soil'
                        },
                        {
                            'title': 'Solar Power',
                            'description': 'This farm uses solar energy in its operations',
                            'impact': 'Reduces fossil fuel emissions by up to 40%',
                            'cost_savings': 'Saves approximately $2,000 annually in energy costs',
                            'implementation': 'Solar panels power farm operations',
                            'category': 'energy'
                        },
                        {
                            'title': 'Reduced Pesticide Use',
                            'description': 'Uses integrated pest management to minimize chemical use',
                            'impact': 'Reduces harmful chemical runoff by up to 50%',
                            'cost_savings': 'Saves on expensive pesticides',
                            'implementation': 'Natural predators and targeted treatments',
                            'category': 'biodiversity'
                        }
                    ]
                }
            )
            
            # Add emissions by category for consumer view
            emissions_by_category = {
                'fertilizer': 0.12,
                'fuel': 0.08,
                'irrigation': 0.05,
                'transportation': 0.05
            }
            
            for category, amount in emissions_by_category.items():
                source, _ = CarbonSource.objects.get_or_create(
                    name=f'{category.capitalize()} Emissions',
                    defaults={
                        'description': f'Emissions from {category}',
                        'category': category,
                        'default_emission_factor': 1.0,
                        'unit': 'kg CO2e'
                    }
                )
                
                CarbonEntry.objects.get_or_create(
                    production=finished_production,
                    type='emission',
                    source=source,
                    amount=amount * finished_production.production_amount,
                    co2e_amount=amount * finished_production.production_amount,
                    year=timezone.now().year,
                    description=f'{category.capitalize()} emissions for {finished_production.name}',
                    usda_verified=True
                )
            
            # Add offset entries for consumer view
            offset_by_action = {
                'tree planting': 0.12,
                'renewable energy credits': 0.08
            }
            
            for action, amount in offset_by_action.items():
                source, _ = CarbonSource.objects.get_or_create(
                    name=f'{action.capitalize()}',
                    defaults={
                        'description': f'Carbon offsets from {action}',
                        'category': 'offset',
                        'default_emission_factor': -1.0,
                        'unit': 'kg CO2e'
                    }
                )
                
                CarbonEntry.objects.get_or_create(
                    production=finished_production,
                    type='offset',
                    source=source,
                    amount=amount * finished_production.production_amount,
                    co2e_amount=amount * finished_production.production_amount,
                    year=timezone.now().year,
                    description=f'{action.capitalize()} for {finished_production.name}',
                    usda_verified=True
                )
            
            # Add sustainability badges to the production
            badges = SustainabilityBadge.objects.all()
            if not badges.exists():
                from django.core.management import call_command
                call_command('seed_sustainability_badges')
                badges = SustainabilityBadge.objects.all()
            
            for badge in badges[:4]:  # Assign first 4 badges
                finished_production.badges.add(badge)
                
            self.stdout.write(self.style.SUCCESS(
                f'Added enhanced consumer data to production {finished_production.name}'
            ))

        self.stdout.write(self.style.SUCCESS('Successfully seeded test data')) 