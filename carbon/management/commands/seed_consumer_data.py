from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from company.models import Company, Establishment
from product.models import Product, Parcel
from history.models import History, WeatherEvent, ChemicalEvent, ProductionEvent, GeneralEvent
from carbon.models import (
    CarbonSource, CarbonEntry, CarbonCertification, CarbonBenchmark,
    CarbonReport, SustainabilityBadge, CarbonOffsetProject, CarbonOffsetPurchase
)
import datetime
import uuid

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds comprehensive consumer-facing data for the ProductDetail screen'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting consumer data seeding...'))
        
        # Create or get badges first
        self.seed_badges()
        
        # Find a published production
        production = History.objects.filter(published=True).first()
        
        if not production:
            self.stdout.write(self.style.WARNING('No published production found. Creating a new one...'))
            production = self.create_sample_production()
        
        # Enhance the production with consumer-facing data
        self.enhance_production(production)
        
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded consumer data for production {production.id}'))
        self.stdout.write(self.style.SUCCESS(f'Use this production ID in your URLs: {production.id}'))
    
    def seed_badges(self):
        """Create sustainability badges if they don't exist"""
        badges = [
            {
                'name': 'Carbon Neutral',
                'description': 'This farm has achieved carbon neutrality by balancing emissions with an equivalent amount of carbon offsets.',
                'minimum_score': 50,
                'is_automatic': True,
                'criteria': {'net_footprint': 0},
                'usda_verified': True
            },
            {
                'name': 'Water Conservation',
                'description': 'This farm uses advanced water conservation techniques to minimize water usage.',
                'minimum_score': 30,
                'is_automatic': False,
                'criteria': {'water_conservation': True},
                'usda_verified': True
            },
            {
                'name': 'Organic Practices',
                'description': 'This farm uses organic farming practices and avoids synthetic chemicals.',
                'minimum_score': 40,
                'is_automatic': False,
                'criteria': {'organic': True},
                'usda_verified': True
            },
            {
                'name': 'Renewable Energy',
                'description': 'This farm uses renewable energy sources for most of its operations.',
                'minimum_score': 35,
                'is_automatic': False,
                'criteria': {'renewable_energy': True},
                'usda_verified': True
            }
        ]
        
        badges_created = 0
        for badge_data in badges:
            try:
                badge, created = SustainabilityBadge.objects.get_or_create(
                    name=badge_data['name'],
                    defaults=badge_data
                )
                if created:
                    badges_created += 1
                    self.stdout.write(self.style.SUCCESS(f'Created badge: {badge.name}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'Badge already exists: {badge.name}'))
            except IntegrityError:
                self.stdout.write(self.style.WARNING(f'Badge already exists (integrity error): {badge_data["name"]}'))
        
        self.stdout.write(self.style.SUCCESS(f'Created {badges_created} new badges'))
    
    def create_sample_production(self):
        """Create a sample production with all necessary related objects"""
        # Create or get user
        user, _ = User.objects.get_or_create(
            email='consumer_test@example.com',
            defaults={
                'first_name': 'Consumer',
                'last_name': 'Test',
                'is_active': True
            }
        )
        
        # Create or get company
        company, _ = Company.objects.get_or_create(
            name='Sustainable Farms Co.',
            defaults={
                'description': 'A company focused on sustainable farming practices',
                'tradename': 'EcoFarms'
            }
        )
        
        # Create or get establishment
        establishment, _ = Establishment.objects.get_or_create(
            name='Sunshine Valley Farm',
            company=company,
            defaults={
                'address': '1234 Farm Road',
                'city': 'Farmville',
                'state': 'California',
                'country': 'USA',
                'description': 'A beautiful farm in the heart of California\'s agricultural region'
            }
        )
        
        # Create or get product
        product, _ = Product.objects.get_or_create(
            name='Organic Oranges',
            defaults={
                'description': 'Juicy, sweet organic oranges grown with sustainable practices'
            }
        )
        
        # Create or get parcel
        parcel, _ = Parcel.objects.get_or_create(
            name='South Orchard',
            establishment=establishment,
            defaults={
                'description': 'Our premium citrus orchard with optimal sun exposure',
                'area': 12.5,
                'product': product
            }
        )
        
        # Create finished production
        start_date = timezone.now() - datetime.timedelta(days=150)
        finish_date = timezone.now() - datetime.timedelta(days=30)
        
        production = History.objects.create(
            name='Spring 2024 Orange Harvest',
            parcel=parcel,
            type='OR',  # Orchard
            start_date=start_date,
            finish_date=finish_date,
            product=product,
            description='Our premium spring orange harvest with exceptional flavor and sustainability',
            is_outdoor=True,
            age_of_plants='5 years',
            number_of_plants='500',
            soil_ph='6.8',
            published=True,
            production_amount=8000.0,  # 8 tons
            lot_id=f'OR-{timezone.now().year}-{uuid.uuid4().hex[:6]}',
            operator=user
        )
        
        # Add events
        events = [
            # Planting event (happened before this production)
            {
                'model': ProductionEvent,
                'type': 'PL',  # Planting
                'description': 'Initial planting of orange trees',
                'date': start_date - datetime.timedelta(days=1825),  # 5 years ago
                'observation': 'Used organic seedlings and compost-enriched soil',
                'certified': True
            },
            # Irrigation event
            {
                'model': ProductionEvent,
                'type': 'IR',  # Irrigation
                'description': 'Installation of water-efficient drip irrigation system',
                'date': start_date + datetime.timedelta(days=10),
                'observation': 'System reduces water consumption by 30% compared to traditional methods',
                'certified': True
            },
            # Fertilizer application
            {
                'model': ChemicalEvent,
                'type': 'FE',  # Fertilizer
                'description': 'Application of organic compost fertilizer',
                'date': start_date + datetime.timedelta(days=30),
                'commercial_name': 'NaturGrow Organic Compost',
                'volume': '2000 kg',
                'concentration': '100% organic',
                'area': 'Full field',
                'way_of_application': 'Ground spread',
                'time_period': 'Morning',
                'observation': 'Enhanced soil structure and nutrient content',
                'certified': True
            },
            # Weather event
            {
                'model': WeatherEvent,
                'type': 'HT',  # High Temperature
                'description': 'Heat wave affecting the orchard',
                'date': start_date + datetime.timedelta(days=60),
                'observation': 'Increased irrigation frequency to protect trees',
                'certified': True
            },
            # Harvesting event
            {
                'model': ProductionEvent,
                'type': 'HA',  # Harvesting
                'description': 'Main harvest of ripe oranges',
                'date': finish_date - datetime.timedelta(days=5),
                'observation': 'Exceptional yield and quality. Used renewable energy powered equipment.',
                'certified': True
            }
        ]
        
        for i, event_data in enumerate(events, 1):
            event = event_data['model'].objects.create(
                history=production,
                created_by=user,
                index=i,
                **{k: v for k, v in event_data.items() if k != 'model'}
            )
        
        self.stdout.write(self.style.SUCCESS(f'Created sample production: {production.name}'))
        return production
    
    def enhance_production(self, production):
        """Add consumer-facing data to an existing production"""
        
        # Add farmer story data
        production.farmer_name = "Maria Rodriguez"
        production.farmer_bio = "Third-generation farmer committed to sustainable practices"
        production.farmer_photo = "https://images.unsplash.com/photo-1599579133940-8ceaa7054ed0?q=80&w=3024&auto=format&fit=crop"
        production.farmer_location = "Central Valley, California"
        production.farmer_certifications = ["USDA Organic", "Fair Trade", "Regenerative Agriculture"]
        production.sustainability_initiatives = [
            "Solar-powered irrigation",
            "Compost-based fertilization",
            "Cover cropping for soil health",
            "Water conservation through drip irrigation",
            "Renewable energy use"
        ]
        production.carbon_reduction = 25000  # kg CO2e reduced annually
        production.years_of_practice = 15
        production.farmer_generation = 3
        production.farmer_story = "Our farm has been in my family since my grandfather started it in 1952. We've always believed in working with nature, not against it. When I took over from my father, I committed to converting fully to organic practices, which took three challenging but rewarding years. Today, we use 40% less water than conventional farms and have eliminated synthetic chemicals entirely. The soil health has improved dramatically, and we're seeing more biodiversity than ever before - from beneficial insects to native bird species. Our carbon footprint is a fraction of conventional citrus farms, and we're proud to be leading the way in sustainable agriculture."
        production.save()
        
        # Create carbon sources if they don't exist
        sources = {
            'Organic Fertilizer': {
                'description': 'Compost-based organic fertilizer',
                'unit': 'kg',
                'category': 'fertilizer',
                'default_emission_factor': 0.2,  # Low compared to synthetic
                'usda_verified': True
            },
            'Solar-Powered Equipment': {
                'description': 'Equipment powered by on-farm solar panels',
                'unit': 'kWh',
                'category': 'energy',
                'default_emission_factor': 0.05,
                'usda_verified': True
            },
            'Drip Irrigation': {
                'description': 'Water-efficient irrigation system',
                'unit': 'liter',
                'category': 'water',
                'default_emission_factor': 0.01,
                'usda_verified': True
            },
            'Local Transportation': {
                'description': 'Short-distance transportation to local markets',
                'unit': 'km',
                'category': 'transport',
                'default_emission_factor': 0.1,
                'usda_verified': True
            },
            'Cover Cropping': {
                'description': 'Carbon sequestration through cover crops',
                'unit': 'hectare',
                'category': 'offset',
                'default_emission_factor': -0.5,  # Negative = carbon removal
                'usda_verified': True
            },
            'Renewable Energy Credits': {
                'description': 'Investment in renewable energy projects',
                'unit': 'credit',
                'category': 'offset',
                'default_emission_factor': -1.0,
                'usda_verified': True
            }
        }
        
        for name, data in sources.items():
            CarbonSource.objects.get_or_create(
                name=name,
                defaults=data
            )
        
        # Create carbon entries for the production
        total_production_weight = production.production_amount or 5000  # kg
        # Production emissions per kg of product
        emissions_per_kg = {
            'Organic Fertilizer': 0.08,
            'Solar-Powered Equipment': 0.05,
            'Drip Irrigation': 0.03,
            'Local Transportation': 0.04
        }
        
        # Add emission entries
        for source_name, emission_factor in emissions_per_kg.items():
            source = CarbonSource.objects.get(name=source_name)
            amount = emission_factor * total_production_weight
            
            CarbonEntry.objects.get_or_create(
                production=production,
                source=source,
                type='emission',
                defaults={
                    'amount': amount,
                    'co2e_amount': amount,
                    'year': production.finish_date.year if production.finish_date else timezone.now().year,
                    'description': f'Emissions from {source_name.lower()} for {production.name}',
                    'usda_verified': True
                }
            )
        
        # Add offset entries
        offsets_per_kg = {
            'Cover Cropping': 0.07,
            'Renewable Energy Credits': 0.08
        }
        
        for source_name, offset_factor in offsets_per_kg.items():
            source = CarbonSource.objects.get(name=source_name)
            amount = offset_factor * total_production_weight
            
            CarbonEntry.objects.get_or_create(
                production=production,
                source=source,
                type='offset',
                defaults={
                    'amount': amount,
                    'co2e_amount': amount,
                    'year': production.finish_date.year if production.finish_date else timezone.now().year,
                    'description': f'Offsets from {source_name.lower()} for {production.name}',
                    'usda_verified': True
                }
            )
        
        # Calculate total emissions and offsets
        total_emissions = sum(emissions_per_kg.values()) * total_production_weight
        total_offsets = sum(offsets_per_kg.values()) * total_production_weight
        net_footprint = total_emissions - total_offsets
        
        # Create benchmark
        benchmark, _ = CarbonBenchmark.objects.get_or_create(
            industry='Citrus',
            year=timezone.now().year,
            crop_type='Orange',
            defaults={
                'average_emissions': 0.5,  # kg CO2e per kg of oranges (industry average)
                'min_emissions': 0.3,
                'max_emissions': 0.8,
                'company_count': 50,
                'unit': 'kg CO2e/kg',
                'source': 'USDA SOE 2024',
                'usda_verified': True,
                'region': 'California'
            }
        )
        
        # Calculate carbon score against benchmark
        carbon_score = CarbonEntry.calculate_carbon_score(
            total_emissions,
            total_offsets,
            benchmark.average_emissions * total_production_weight
        )
        
        # Create carbon report
        carbon_report, _ = CarbonReport.objects.get_or_create(
            production=production,
            defaults={
                'period_start': production.start_date,
                'period_end': production.finish_date or timezone.now(),
                'total_emissions': total_emissions,
                'total_offsets': total_offsets,
                'net_footprint': net_footprint,
                'carbon_score': carbon_score,
                'usda_verified': True,
                'cost_savings': 5000.0,
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
        
        # Add sustainability badges to the production
        badges = SustainabilityBadge.objects.all()
        for badge in badges:
            production.badges.add(badge)
        
        self.stdout.write(self.style.SUCCESS(f'Enhanced production {production.id} with consumer-facing data'))
        self.stdout.write(self.style.SUCCESS(f'Carbon Score: {carbon_score}/100'))
        self.stdout.write(self.style.SUCCESS(f'Net Footprint: {net_footprint:.2f} kg CO2e')) 