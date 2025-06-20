from django.core.management.base import BaseCommand
from django.utils.text import slugify
from carbon.models import CropType, EventTemplate, CarbonSource
from django.db import transaction
import json


class Command(BaseCommand):
    help = 'Seed database with USDA-verified crop types and event templates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing crop types and templates before seeding',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Deleting existing crop types and templates...')
            EventTemplate.objects.all().delete()
            CropType.objects.all().delete()

        self.stdout.write('Creating crop types and event templates...')
        
        with transaction.atomic():
            # Create crop types with USDA-verified data
            self.create_citrus_crop_type()
            self.create_almonds_crop_type()
            self.create_soybeans_crop_type()
            self.create_corn_crop_type()
            self.create_wheat_crop_type()
            self.create_cotton_crop_type()
            
            # Create carbon sources if they don't exist
            self.create_carbon_sources()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {CropType.objects.count()} crop types '
                f'and {EventTemplate.objects.count()} event templates'
            )
        )

    def create_citrus_crop_type(self):
        """Create Citrus crop type with USDA data from California citrus production"""
        crop_type, created = CropType.objects.get_or_create(
            slug='citrus_oranges',
            defaults={
                'name': 'Citrus (Oranges)',
                'category': 'tree_fruit',
                'description': 'Premium California citrus including oranges, lemons, and grapefruits. Year-round production with high water requirements and established markets.',
                'typical_farm_size': '20-100 hectares',
                'growing_season': '12 months (evergreen)',
                'harvest_season': 'November - April',
                'emissions_per_hectare': 3200.0,  # kg CO2e/ha
                'industry_average': 3200.0,
                'best_practice': 2100.0,
                'carbon_credit_potential': 500.0,
                'typical_cost_per_hectare': 2250.0,
                'fertilizer_cost_per_hectare': 450.0,
                'fuel_cost_per_hectare': 280.0,
                'irrigation_cost_per_hectare': 320.0,
                'labor_cost_per_hectare': 1200.0,
                'organic_premium': '25-40%',
                'sustainable_premium': '10-20%',
                'local_premium': '5-15%',
                'sustainability_opportunities': [
                    'Install solar panels for irrigation pumps (reduce emissions by 360 kg CO2e/ha)',
                    'Implement cover cropping (sequester 1200 kg CO2e/ha/year)',
                    'Use precision fertilizer application (reduce fertilizer emissions by 20%)',
                    'Convert to organic practices (premium pricing 15-30%)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - California Citrus Production'
            }
        )
        
        if created:
            self.stdout.write(f'Created crop type: {crop_type.name}')
            
            # Create event templates for citrus
            citrus_events = [
                {
                    'name': 'Winter Pruning',
                    'event_type': 'pruning',
                    'description': 'Annual pruning to maintain tree structure and improve fruit quality',
                    'timing': 'December - February',
                    'frequency': 'annual',
                    'typical_duration': '2-3 hours per hectare',
                    'carbon_impact': 32.0,
                    'carbon_category': 'low',
                    'carbon_sources': ['Citrus Pruning Equipment'],
                    'typical_amounts': {'fuel': '12 liters per hectare'},
                    'cost_estimate': 180.0,
                    'efficiency_tips': 'Use precision pruning to reduce fuel consumption by 15%',
                    'sustainability_score': 8,
                    'qr_visibility': 'low',
                    'backend_event_type': 2,  # Production Event
                    'backend_event_fields': {'type': 'PR', 'observation': 'Winter pruning operation'},
                    'is_default_enabled': True
                },
                {
                    'name': 'Spring Fertilization',
                    'event_type': 'fertilization',
                    'description': 'NPK fertilizer application for spring growth',
                    'timing': 'March - April',
                    'frequency': 'annual',
                    'typical_duration': '4-6 hours per hectare',
                    'carbon_impact': 596.0,
                    'carbon_category': 'high',
                    'carbon_sources': ['Citrus Fertilizer (NPK 10-10-10)'],
                    'typical_amounts': {'fertilizer': '200 kg per hectare'},
                    'cost_estimate': 450.0,
                    'efficiency_tips': 'Soil testing can reduce fertilizer needs by 20-30%',
                    'sustainability_score': 6,
                    'qr_visibility': 'high',
                    'backend_event_type': 1,  # Chemical Event
                    'backend_event_fields': {
                        'type': 'FE',
                        'commercial_name': 'NPK Fertilizer 10-10-10',
                        'volume': '200 kg/ha',
                        'way_of_application': 'broadcast',
                        'time_period': 'spring'
                    },
                    'is_default_enabled': True
                },
                {
                    'name': 'Drip Irrigation',
                    'event_type': 'irrigation',
                    'description': 'Efficient drip irrigation system operation',
                    'timing': 'April - October',
                    'frequency': 'seasonal',
                    'typical_duration': 'Continuous operation',
                    'carbon_impact': 360.0,
                    'carbon_category': 'medium',
                    'carbon_sources': ['Citrus Irrigation System'],
                    'typical_amounts': {'energy': '800 kWh per hectare'},
                    'cost_estimate': 320.0,
                    'efficiency_tips': 'Smart irrigation controllers can save 25% energy',
                    'sustainability_score': 8,
                    'qr_visibility': 'medium',
                    'backend_event_type': 2,  # Production Event
                    'backend_event_fields': {'type': 'IR', 'observation': 'Drip irrigation cycle'},
                    'is_default_enabled': True
                },
                {
                    'name': 'Harvest',
                    'event_type': 'harvest',
                    'description': 'Manual and mechanical citrus harvesting',
                    'timing': 'November - April',
                    'frequency': 'annual',
                    'typical_duration': '3-5 days per hectare',
                    'carbon_impact': 67.0,
                    'carbon_category': 'low',
                    'carbon_sources': ['Citrus Harvest Equipment'],
                    'typical_amounts': {'fuel': '25 liters per hectare'},
                    'cost_estimate': 400.0,
                    'efficiency_tips': 'Mechanical harvesting reduces labor costs and emissions',
                    'sustainability_score': 7,
                    'qr_visibility': 'high',
                    'backend_event_type': 2,  # Production Event
                    'backend_event_fields': {'type': 'HA', 'observation': 'Citrus harvest operation'},
                    'is_default_enabled': True
                }
            ]
            
            for event_data in citrus_events:
                EventTemplate.objects.create(crop_type=crop_type, **event_data)

    def create_almonds_crop_type(self):
        """Create Almonds crop type with USDA data from California almond production"""
        crop_type, created = CropType.objects.get_or_create(
            slug='almonds',
            defaults={
                'name': 'Almonds',
                'category': 'tree_nut',
                'description': "California's premium tree nut crop with high water requirements and strong export markets. Requires bee pollination and precision water management.",
                'typical_farm_size': '40-200 hectares',
                'growing_season': '12 months (deciduous)',
                'harvest_season': 'August - October',
                'emissions_per_hectare': 4100.0,
                'industry_average': 4100.0,
                'best_practice': 2800.0,
                'carbon_credit_potential': 650.0,
                'typical_cost_per_hectare': 1750.0,
                'fertilizer_cost_per_hectare': 380.0,
                'fuel_cost_per_hectare': 420.0,
                'irrigation_cost_per_hectare': 450.0,
                'labor_cost_per_hectare': 500.0,
                'organic_premium': '30-50%',
                'sustainable_premium': '15-25%',
                'local_premium': '10-20%',
                'sustainability_opportunities': [
                    'Install bee-friendly cover crops (improve pollination + sequester carbon)',
                    'Use deficit irrigation strategies (reduce water use by 20%)',
                    'Implement integrated pest management (reduce chemical inputs)',
                    'Convert hull waste to biochar (carbon sequestration opportunity)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - California Almond Board'
            }
        )
        
        if created:
            self.stdout.write(f'Created crop type: {crop_type.name}')
            
            almond_events = [
                {
                    'name': 'Dormant Pruning',
                    'event_type': 'pruning',
                    'description': 'Winter pruning for tree structure and sunlight penetration',
                    'timing': 'December - January',
                    'frequency': 'annual',
                    'typical_duration': '3-4 hours per hectare',
                    'carbon_impact': 40.0,
                    'carbon_category': 'low',
                    'carbon_sources': ['Almond Pruning Equipment'],
                    'typical_amounts': {'fuel': '15 liters per hectare'},
                    'cost_estimate': 220.0,
                    'efficiency_tips': 'Mechanical pruning reduces labor and fuel costs',
                    'sustainability_score': 8,
                    'qr_visibility': 'low',
                    'backend_event_type': 2,
                    'backend_event_fields': {'type': 'PR', 'observation': 'Dormant season pruning'},
                    'is_default_enabled': True
                },
                {
                    'name': 'Bloom Nutrition',
                    'event_type': 'fertilization',
                    'description': 'Nitrogen fertilizer application for bloom and nut development',
                    'timing': 'February - March',
                    'frequency': 'annual',
                    'typical_duration': '5-7 hours per hectare',
                    'carbon_impact': 704.0,
                    'carbon_category': 'high',
                    'carbon_sources': ['Almond Fertilizer (Nitrogen)'],
                    'typical_amounts': {'nitrogen': '120 kg N per hectare'},
                    'cost_estimate': 380.0,
                    'efficiency_tips': 'Leaf tissue analysis optimizes fertilizer timing',
                    'sustainability_score': 6,
                    'qr_visibility': 'high',
                    'backend_event_type': 1,
                    'backend_event_fields': {
                        'type': 'FE',
                        'commercial_name': 'Nitrogen Fertilizer',
                        'volume': '120 kg N/ha',
                        'way_of_application': 'fertigation',
                        'time_period': 'bloom'
                    },
                    'is_default_enabled': True
                },
                {
                    'name': 'Pollination',
                    'event_type': 'other',
                    'description': 'Bee hive placement for almond pollination',
                    'timing': 'February - March',
                    'frequency': 'annual',
                    'typical_duration': '2-3 weeks',
                    'carbon_impact': 24.0,
                    'carbon_category': 'low',
                    'carbon_sources': ['Bee Transport and Management'],
                    'typical_amounts': {'transport': '200 km per hectare'},
                    'cost_estimate': 500.0,
                    'efficiency_tips': 'Local bee colonies reduce transport emissions',
                    'sustainability_score': 9,
                    'qr_visibility': 'medium',
                    'backend_event_type': 3,
                    'backend_event_fields': {'name': 'Bee Pollination', 'observation': 'Bee hive placement for pollination'},
                    'is_default_enabled': True
                },
                {
                    'name': 'Harvest',
                    'event_type': 'harvest',
                    'description': 'Mechanical shaking and sweeping of almonds',
                    'timing': 'August - October',
                    'frequency': 'annual',
                    'typical_duration': '2-3 days per hectare',
                    'carbon_impact': 75.0,
                    'carbon_category': 'low',
                    'carbon_sources': ['Almond Harvest Equipment'],
                    'typical_amounts': {'fuel': '28 liters per hectare'},
                    'cost_estimate': 350.0,
                    'efficiency_tips': 'Modern shakers improve efficiency by 20%',
                    'sustainability_score': 7,
                    'qr_visibility': 'high',
                    'backend_event_type': 2,
                    'backend_event_fields': {'type': 'HA', 'observation': 'Mechanical almond harvest'},
                    'is_default_enabled': True
                }
            ]
            
            for event_data in almond_events:
                EventTemplate.objects.create(crop_type=crop_type, **event_data)

    def create_soybeans_crop_type(self):
        """Create Soybeans crop type with USDA data from Midwest production"""
        crop_type, created = CropType.objects.get_or_create(
            slug='soybeans',
            defaults={
                'name': 'Soybeans',
                'category': 'oilseed',
                'description': 'Nitrogen-fixing legume crop primarily grown in the Midwest. Excellent for crop rotation and soil health improvement.',
                'typical_farm_size': '100-500 hectares',
                'growing_season': '4-5 months',
                'harvest_season': 'September - November',
                'emissions_per_hectare': 1800.0,
                'industry_average': 1800.0,
                'best_practice': 1200.0,
                'carbon_credit_potential': 800.0,
                'typical_cost_per_hectare': 450.0,
                'fertilizer_cost_per_hectare': 50.0,  # Lower due to N-fixation
                'fuel_cost_per_hectare': 150.0,
                'irrigation_cost_per_hectare': 80.0,
                'labor_cost_per_hectare': 170.0,
                'organic_premium': '40-60%',
                'sustainable_premium': '5-15%',
                'local_premium': '10-25%',
                'sustainability_opportunities': [
                    'Implement no-till practices (sequester 800 kg CO2e/ha/year)',
                    'Plant cover crops after harvest (additional 1200 kg CO2e/ha)',
                    'Use precision agriculture (reduce inputs by 15-20%)',
                    'Maximize nitrogen fixation (reduce synthetic fertilizer needs)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Economic Research Service - Soybean Production'
            }
        )
        
        if created:
            self.stdout.write(f'Created crop type: {crop_type.name}')
            
            soybean_events = [
                {
                    'name': 'Planting',
                    'event_type': 'planting',
                    'description': 'No-till or conventional soybean planting with inoculation',
                    'timing': 'April - June',
                    'frequency': 'annual',
                    'typical_duration': '6-8 hours per hectare',
                    'carbon_impact': 21.0,
                    'carbon_category': 'low',
                    'carbon_sources': ['Soybean Planting Equipment'],
                    'typical_amounts': {'fuel': '8 liters per hectare'},
                    'cost_estimate': 80.0,
                    'efficiency_tips': 'No-till planting reduces fuel use by 40%',
                    'sustainability_score': 9,
                    'qr_visibility': 'medium',
                    'backend_event_type': 2,
                    'backend_event_fields': {'type': 'PL', 'observation': 'Soybean planting with inoculation'},
                    'is_default_enabled': True
                },
                {
                    'name': 'Weed Control',
                    'event_type': 'pest_control',
                    'description': 'Pre and post-emergence herbicide application',
                    'timing': 'May - July',
                    'frequency': 'seasonal',
                    'typical_duration': '3-4 hours per hectare',
                    'carbon_impact': 26.0,
                    'carbon_category': 'low',
                    'carbon_sources': ['Soybean Herbicide Application'],
                    'typical_amounts': {'herbicide': '3 liters per hectare'},
                    'cost_estimate': 120.0,
                    'efficiency_tips': 'Precision spraying reduces herbicide use by 25%',
                    'sustainability_score': 6,
                    'qr_visibility': 'high',
                    'backend_event_type': 1,
                    'backend_event_fields': {
                        'type': 'HE',
                        'commercial_name': 'Glyphosate Herbicide',
                        'volume': '3 L/ha',
                        'way_of_application': 'spray',
                        'time_period': 'growing_season'
                    },
                    'is_default_enabled': True
                },
                {
                    'name': 'Nitrogen Fixation',
                    'event_type': 'other',
                    'description': 'Natural biological nitrogen fixation process',
                    'timing': 'June - August',
                    'frequency': 'natural',
                    'typical_duration': 'Continuous process',
                    'carbon_impact': -881.0,  # Negative = carbon sequestration
                    'carbon_category': 'negative',
                    'carbon_sources': ['Biological Nitrogen Fixation'],
                    'typical_amounts': {'nitrogen_fixed': '150 kg N per hectare'},
                    'cost_estimate': 0.0,
                    'efficiency_tips': 'Proper inoculation maximizes nitrogen fixation',
                    'sustainability_score': 10,
                    'qr_visibility': 'high',
                    'backend_event_type': 3,
                    'backend_event_fields': {'name': 'Nitrogen Fixation', 'observation': 'Biological nitrogen fixation by rhizobia'},
                    'is_default_enabled': True
                },
                {
                    'name': 'Harvest',
                    'event_type': 'harvest',
                    'description': 'Combine harvesting of mature soybeans',
                    'timing': 'September - November',
                    'frequency': 'annual',
                    'typical_duration': '4-6 hours per hectare',
                    'carbon_impact': 32.0,
                    'carbon_category': 'low',
                    'carbon_sources': ['Soybean Harvest Equipment'],
                    'typical_amounts': {'fuel': '12 liters per hectare'},
                    'cost_estimate': 150.0,
                    'efficiency_tips': 'Combine efficiency reduces fuel consumption',
                    'sustainability_score': 8,
                    'qr_visibility': 'high',
                    'backend_event_type': 2,
                    'backend_event_fields': {'type': 'HA', 'observation': 'Combine harvesting'},
                    'is_default_enabled': True
                }
            ]
            
            for event_data in soybean_events:
                EventTemplate.objects.create(crop_type=crop_type, **event_data)

    def create_corn_crop_type(self):
        """Create Corn crop type with USDA data from Midwest production"""
        crop_type, created = CropType.objects.get_or_create(
            slug='corn_field',
            defaults={
                'name': 'Corn (Field)',
                'category': 'grain',
                'description': 'Major grain crop for feed, ethanol, and food production. High nitrogen requirements but excellent yields.',
                'typical_farm_size': '200-800 hectares',
                'growing_season': '4-5 months',
                'harvest_season': 'September - November',
                'emissions_per_hectare': 2900.0,
                'industry_average': 2900.0,
                'best_practice': 2000.0,
                'carbon_credit_potential': 450.0,
                'typical_cost_per_hectare': 1030.0,
                'fertilizer_cost_per_hectare': 420.0,
                'fuel_cost_per_hectare': 180.0,
                'irrigation_cost_per_hectare': 150.0,
                'labor_cost_per_hectare': 280.0,
                'organic_premium': '25-40%',
                'sustainable_premium': '5-15%',
                'local_premium': '10-25%',
                'sustainability_opportunities': [
                    'Implement precision fertilizer application (reduce N2O emissions by 20%)',
                    'Use cover crops in rotation (sequester 1000 kg CO2e/ha)',
                    'Adopt no-till practices (reduce fuel consumption by 35%)',
                    'Install variable rate technology (optimize input efficiency)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Economic Research Service - Corn Production'
            }
        )
        
        if created:
            self.stdout.write(f'Created crop type: {crop_type.name}')
            
            corn_events = [
                {
                    'name': 'Planting',
                    'event_type': 'planting',
                    'description': 'Spring corn planting with precision seed placement',
                    'timing': 'April - May',
                    'frequency': 'annual',
                    'typical_duration': '6-8 hours per hectare',
                    'carbon_impact': 27.0,
                    'carbon_category': 'low',
                    'carbon_sources': ['Corn Planting Equipment'],
                    'typical_amounts': {'fuel': '10 liters per hectare'},
                    'cost_estimate': 100.0,
                    'efficiency_tips': 'Variable rate planting optimizes seed placement',
                    'sustainability_score': 8,
                    'qr_visibility': 'medium',
                    'backend_event_type': 2,
                    'backend_event_fields': {'type': 'PL', 'observation': 'Corn planting with precision'},
                    'is_default_enabled': True
                },
                {
                    'name': 'Nitrogen Application',
                    'event_type': 'fertilization',
                    'description': 'Pre-plant and side-dress nitrogen fertilizer application',
                    'timing': 'May - June',
                    'frequency': 'annual',
                    'typical_duration': '4-6 hours per hectare',
                    'carbon_impact': 1057.0,
                    'carbon_category': 'high',
                    'carbon_sources': ['Corn Nitrogen Fertilizer'],
                    'typical_amounts': {'nitrogen': '180 kg N per hectare'},
                    'cost_estimate': 420.0,
                    'efficiency_tips': 'Split applications improve efficiency by 15%',
                    'sustainability_score': 5,
                    'qr_visibility': 'high',
                    'backend_event_type': 1,
                    'backend_event_fields': {
                        'type': 'FE',
                        'commercial_name': 'Anhydrous Ammonia',
                        'volume': '180 kg N/ha',
                        'way_of_application': 'injection',
                        'time_period': 'growing_season'
                    },
                    'is_default_enabled': True
                },
                {
                    'name': 'Harvest',
                    'event_type': 'harvest',
                    'description': 'Combine harvesting and grain drying',
                    'timing': 'September - November',
                    'frequency': 'annual',
                    'typical_duration': '5-7 hours per hectare',
                    'carbon_impact': 48.0,
                    'carbon_category': 'low',
                    'carbon_sources': ['Corn Harvest Equipment'],
                    'typical_amounts': {'fuel': '18 liters per hectare'},
                    'cost_estimate': 180.0,
                    'efficiency_tips': 'Modern combines reduce fuel use per ton',
                    'sustainability_score': 7,
                    'qr_visibility': 'high',
                    'backend_event_type': 2,
                    'backend_event_fields': {'type': 'HA', 'observation': 'Combine harvest with drying'},
                    'is_default_enabled': True
                }
            ]
            
            for event_data in corn_events:
                EventTemplate.objects.create(crop_type=crop_type, **event_data)

    def create_wheat_crop_type(self):
        """Create Wheat crop type with USDA data"""
        crop_type, created = CropType.objects.get_or_create(
            slug='wheat',
            defaults={
                'name': 'Wheat',
                'category': 'grain',
                'description': 'Major cereal grain crop for flour and feed production. Lower input requirements than corn.',
                'typical_farm_size': '300-1000 hectares',
                'growing_season': '8-9 months',
                'harvest_season': 'July - August',
                'emissions_per_hectare': 1900.0,
                'industry_average': 1900.0,
                'best_practice': 1400.0,
                'carbon_credit_potential': 300.0,
                'typical_cost_per_hectare': 620.0,
                'fertilizer_cost_per_hectare': 280.0,
                'fuel_cost_per_hectare': 120.0,
                'irrigation_cost_per_hectare': 100.0,
                'labor_cost_per_hectare': 120.0,
                'organic_premium': '30-50%',
                'sustainable_premium': '10-20%',
                'local_premium': '15-25%',
                'sustainability_opportunities': [
                    'Implement precision fertilizer management (reduce emissions by 25%)',
                    'Use drought-resistant varieties (reduce irrigation needs)',
                    'Practice crop rotation with legumes (improve soil health)',
                    'Adopt conservation tillage (reduce fuel consumption)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Economic Research Service - Wheat Production'
            }
        )
        
        if created:
            self.stdout.write(f'Created crop type: {crop_type.name}')

    def create_cotton_crop_type(self):
        """Create Cotton crop type with USDA data"""
        crop_type, created = CropType.objects.get_or_create(
            slug='cotton',
            defaults={
                'name': 'Cotton',
                'category': 'other',
                'description': 'Major fiber crop with high input requirements. Primarily grown in Southern states.',
                'typical_farm_size': '150-600 hectares',
                'growing_season': '5-6 months',
                'harvest_season': 'September - November',
                'emissions_per_hectare': 3800.0,
                'industry_average': 3800.0,
                'best_practice': 2600.0,
                'carbon_credit_potential': 400.0,
                'typical_cost_per_hectare': 1850.0,
                'fertilizer_cost_per_hectare': 380.0,
                'fuel_cost_per_hectare': 250.0,
                'irrigation_cost_per_hectare': 420.0,
                'labor_cost_per_hectare': 800.0,
                'organic_premium': '50-100%',
                'sustainable_premium': '20-30%',
                'local_premium': '5-15%',
                'sustainability_opportunities': [
                    'Implement integrated pest management (reduce pesticide use by 40%)',
                    'Use precision irrigation (reduce water consumption by 30%)',
                    'Plant cover crops for soil health (sequester carbon)',
                    'Adopt sustainable cotton certification (premium markets)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - Cotton Production'
            }
        )
        
        if created:
            self.stdout.write(f'Created crop type: {crop_type.name}')

    def create_carbon_sources(self):
        """Create carbon sources referenced in event templates"""
        carbon_sources = [
            {
                'name': 'Citrus Pruning Equipment',
                'category': 'Equipment',
                'default_emission_factor': 2.68,  # kg CO2e per liter diesel
                'unit': 'kg CO2e/L',
                'usda_verified': True
            },
            {
                'name': 'Citrus Fertilizer (NPK 10-10-10)',
                'category': 'Fertilizer',
                'default_emission_factor': 2.98,  # kg CO2e per kg NPK
                'unit': 'kg CO2e/kg',
                'usda_verified': True
            },
            {
                'name': 'Citrus Irrigation System',
                'category': 'Energy',
                'default_emission_factor': 0.45,  # kg CO2e per kWh
                'unit': 'kg CO2e/kWh',
                'usda_verified': True
            },
            {
                'name': 'Almond Fertilizer (Nitrogen)',
                'category': 'Fertilizer',
                'default_emission_factor': 5.87,  # kg CO2e per kg N
                'unit': 'kg CO2e/kg N',
                'usda_verified': True
            },
            {
                'name': 'Soybean Planting Equipment',
                'category': 'Equipment',
                'default_emission_factor': 2.68,  # kg CO2e per liter diesel
                'unit': 'kg CO2e/L',
                'usda_verified': True
            },
            {
                'name': 'Corn Nitrogen Fertilizer',
                'category': 'Fertilizer',
                'default_emission_factor': 5.87,  # kg CO2e per kg N
                'unit': 'kg CO2e/kg N',
                'usda_verified': True
            }
        ]
        
        for source_data in carbon_sources:
            CarbonSource.objects.get_or_create(
                name=source_data['name'],
                defaults=source_data
            ) 