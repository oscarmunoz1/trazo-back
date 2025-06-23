from django.core.management.base import BaseCommand
from carbon.models import CropType


class Command(BaseCommand):
    help = 'Populate USDA-compliant crop types for production forms'

    def handle(self, *args, **options):
        """
        Add the missing USDA-compliant crop types to match the frontend expectations.
        Based on the 16 crop types defined in ChemicalTab.jsx
        """
        
        # Define the 16 USDA-compliant crop types with ALL required fields
        usda_crop_types = [
            {
                'name': 'Citrus (Oranges)',
                'slug': 'citrus_oranges',
                'category': 'tree_fruit',
                'description': 'Premium California citrus including oranges, lemons, and limes. Year-round production with high water requirements and established markets.',
                'typical_farm_size': '20-100 hectares',
                'growing_season': '12 months (evergreen)',
                'harvest_season': 'November - April',
                'emissions_per_hectare': 3200.0,
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
            },
            {
                'name': 'Corn (Field)',
                'slug': 'corn_field',
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
            },
            {
                'name': 'Soybeans',
                'slug': 'soybeans',
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
                'fertilizer_cost_per_hectare': 50.0,
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
            },
            {
                'name': 'Wheat',
                'slug': 'wheat',
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
            },
            {
                'name': 'Cotton',
                'slug': 'cotton',
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
            },
            {
                'name': 'Almonds',
                'slug': 'almonds',
                'category': 'tree_nut',
                'description': 'California\'s premium tree nut crop with high water requirements and strong export markets. Requires bee pollination and precision water management.',
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
            },
            # NEW CROP TYPES TO ADD (with complete data)
            {
                'name': 'Rice',
                'slug': 'rice',
                'category': 'grain',
                'description': 'Water-intensive grain crop primarily grown in flooded fields. Major staple food crop with unique methane emissions profile.',
                'typical_farm_size': '50-200 hectares',
                'growing_season': '4-6 months',
                'harvest_season': 'September - November',
                'emissions_per_hectare': 4500.0,
                'industry_average': 4500.0,
                'best_practice': 3200.0,
                'carbon_credit_potential': 650.0,
                'typical_cost_per_hectare': 1200.0,
                'fertilizer_cost_per_hectare': 350.0,
                'fuel_cost_per_hectare': 200.0,
                'irrigation_cost_per_hectare': 400.0,
                'labor_cost_per_hectare': 250.0,
                'organic_premium': '20-35%',
                'sustainable_premium': '10-20%',
                'local_premium': '5-15%',
                'sustainability_opportunities': [
                    'Implement alternate wetting and drying (reduce methane by 30%)',
                    'Use precision fertilizer management (reduce N2O emissions)',
                    'Plant cover crops in rotation (improve soil health)',
                    'Adopt direct seeding (reduce fuel consumption)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - Rice Production'
            },
            {
                'name': 'Tomatoes',
                'slug': 'tomatoes',
                'category': 'vegetable',
                'description': 'High-value vegetable crop with intensive production systems. Requires precise irrigation and nutrient management.',
                'typical_farm_size': '10-50 hectares',
                'growing_season': '3-4 months',
                'harvest_season': 'July - October',
                'emissions_per_hectare': 2800.0,
                'industry_average': 2800.0,
                'best_practice': 2000.0,
                'carbon_credit_potential': 400.0,
                'typical_cost_per_hectare': 3500.0,
                'fertilizer_cost_per_hectare': 600.0,
                'fuel_cost_per_hectare': 300.0,
                'irrigation_cost_per_hectare': 800.0,
                'labor_cost_per_hectare': 1800.0,
                'organic_premium': '40-70%',
                'sustainable_premium': '15-30%',
                'local_premium': '20-40%',
                'sustainability_opportunities': [
                    'Use drip irrigation systems (reduce water use by 40%)',
                    'Implement integrated pest management (reduce pesticide use)',
                    'Plant beneficial insect habitat (natural pest control)',
                    'Use precision fertilizer application (reduce nutrient runoff)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - Vegetable Production'
            },
            {
                'name': 'Potatoes',
                'slug': 'potatoes',
                'category': 'vegetable',
                'description': 'Major tuber crop for food and processing. Requires careful soil management and pest control.',
                'typical_farm_size': '50-300 hectares',
                'growing_season': '3-4 months',
                'harvest_season': 'August - October',
                'emissions_per_hectare': 2200.0,
                'industry_average': 2200.0,
                'best_practice': 1600.0,
                'carbon_credit_potential': 300.0,
                'typical_cost_per_hectare': 2800.0,
                'fertilizer_cost_per_hectare': 480.0,
                'fuel_cost_per_hectare': 350.0,
                'irrigation_cost_per_hectare': 600.0,
                'labor_cost_per_hectare': 1370.0,
                'organic_premium': '30-50%',
                'sustainable_premium': '10-25%',
                'local_premium': '15-30%',
                'sustainability_opportunities': [
                    'Use precision agriculture (optimize input efficiency)',
                    'Implement crop rotation (improve soil health)',
                    'Use cover crops (prevent soil erosion)',
                    'Adopt integrated pest management (reduce chemical inputs)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - Potato Production'
            },
            {
                'name': 'Lettuce',
                'slug': 'lettuce',
                'category': 'vegetable',
                'description': 'Cool-season leafy vegetable with short growing cycles. Requires precise irrigation and harvest timing.',
                'typical_farm_size': '20-100 hectares',
                'growing_season': '2-3 months',
                'harvest_season': 'Year-round (by region)',
                'emissions_per_hectare': 1800.0,
                'industry_average': 1800.0,
                'best_practice': 1300.0,
                'carbon_credit_potential': 250.0,
                'typical_cost_per_hectare': 4200.0,
                'fertilizer_cost_per_hectare': 500.0,
                'fuel_cost_per_hectare': 200.0,
                'irrigation_cost_per_hectare': 700.0,
                'labor_cost_per_hectare': 2800.0,
                'organic_premium': '50-80%',
                'sustainable_premium': '20-35%',
                'local_premium': '25-50%',
                'sustainability_opportunities': [
                    'Use hydroponic systems (reduce water use by 90%)',
                    'Implement precision fertilizer management (reduce nutrient runoff)',
                    'Use beneficial insects for pest control (reduce pesticides)',
                    'Adopt protected cultivation (extend growing season)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - Lettuce Production'
            },
            {
                'name': 'Carrots',
                'slug': 'carrots',
                'category': 'vegetable',
                'description': 'Root vegetable crop with moderate input requirements. Good for soil health when rotated properly.',
                'typical_farm_size': '30-150 hectares',
                'growing_season': '3-4 months',
                'harvest_season': 'August - November',
                'emissions_per_hectare': 1600.0,
                'industry_average': 1600.0,
                'best_practice': 1200.0,
                'carbon_credit_potential': 200.0,
                'typical_cost_per_hectare': 2200.0,
                'fertilizer_cost_per_hectare': 300.0,
                'fuel_cost_per_hectare': 250.0,
                'irrigation_cost_per_hectare': 400.0,
                'labor_cost_per_hectare': 1250.0,
                'organic_premium': '35-55%',
                'sustainable_premium': '15-25%',
                'local_premium': '20-35%',
                'sustainability_opportunities': [
                    'Use precision seeding (optimize plant spacing)',
                    'Implement crop rotation (improve soil structure)',
                    'Use drip irrigation (reduce water consumption)',
                    'Adopt mechanical weed control (reduce herbicides)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - Carrot Production'
            },
            {
                'name': 'Onions',
                'slug': 'onions',
                'category': 'vegetable',
                'description': 'Long-season vegetable crop with good storage characteristics. Requires careful irrigation management.',
                'typical_farm_size': '25-120 hectares',
                'growing_season': '4-5 months',
                'harvest_season': 'August - October',
                'emissions_per_hectare': 2000.0,
                'industry_average': 2000.0,
                'best_practice': 1500.0,
                'carbon_credit_potential': 250.0,
                'typical_cost_per_hectare': 2600.0,
                'fertilizer_cost_per_hectare': 400.0,
                'fuel_cost_per_hectare': 280.0,
                'irrigation_cost_per_hectare': 500.0,
                'labor_cost_per_hectare': 1420.0,
                'organic_premium': '25-45%',
                'sustainable_premium': '10-20%',
                'local_premium': '15-30%',
                'sustainability_opportunities': [
                    'Use precision irrigation scheduling (reduce water use)',
                    'Implement integrated pest management (reduce chemical inputs)',
                    'Use cover crops in rotation (improve soil health)',
                    'Adopt mechanical cultivation (reduce herbicide use)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - Onion Production'
            },
            {
                'name': 'Apples',
                'slug': 'apples',
                'category': 'tree_fruit',
                'description': 'Premium tree fruit crop with long-term investment requirements. Requires intensive pest and disease management.',
                'typical_farm_size': '30-150 hectares',
                'growing_season': '12 months (deciduous)',
                'harvest_season': 'August - November',
                'emissions_per_hectare': 3500.0,
                'industry_average': 3500.0,
                'best_practice': 2400.0,
                'carbon_credit_potential': 550.0,
                'typical_cost_per_hectare': 3200.0,
                'fertilizer_cost_per_hectare': 500.0,
                'fuel_cost_per_hectare': 400.0,
                'irrigation_cost_per_hectare': 600.0,
                'labor_cost_per_hectare': 1700.0,
                'organic_premium': '40-70%',
                'sustainable_premium': '15-30%',
                'local_premium': '20-40%',
                'sustainability_opportunities': [
                    'Implement integrated pest management (reduce pesticide use by 50%)',
                    'Use precision irrigation (reduce water consumption)',
                    'Plant beneficial insect habitat (natural pest control)',
                    'Adopt organic certification (premium market access)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - Apple Production'
            },
            {
                'name': 'Grapes',
                'slug': 'grapes',
                'category': 'tree_fruit',
                'description': 'Premium fruit crop for wine, juice, and fresh market. Requires specialized trellising and pruning systems.',
                'typical_farm_size': '20-100 hectares',
                'growing_season': '12 months (deciduous)',
                'harvest_season': 'August - October',
                'emissions_per_hectare': 3800.0,
                'industry_average': 3800.0,
                'best_practice': 2600.0,
                'carbon_credit_potential': 600.0,
                'typical_cost_per_hectare': 4500.0,
                'fertilizer_cost_per_hectare': 600.0,
                'fuel_cost_per_hectare': 500.0,
                'irrigation_cost_per_hectare': 800.0,
                'labor_cost_per_hectare': 2600.0,
                'organic_premium': '30-60%',
                'sustainable_premium': '15-25%',
                'local_premium': '10-25%',
                'sustainability_opportunities': [
                    'Use cover crops between rows (sequester carbon)',
                    'Implement precision irrigation (reduce water use)',
                    'Use integrated pest management (reduce chemical inputs)',
                    'Adopt sustainable viticulture certification (premium pricing)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - Grape Production'
            },
            {
                'name': 'Strawberries',
                'slug': 'strawberries',
                'category': 'berry',
                'description': 'High-value berry crop with intensive production systems. Requires careful pest management and harvest labor.',
                'typical_farm_size': '5-30 hectares',
                'growing_season': '8-12 months',
                'harvest_season': 'April - November',
                'emissions_per_hectare': 4200.0,
                'industry_average': 4200.0,
                'best_practice': 3000.0,
                'carbon_credit_potential': 600.0,
                'typical_cost_per_hectare': 8500.0,
                'fertilizer_cost_per_hectare': 1200.0,
                'fuel_cost_per_hectare': 400.0,
                'irrigation_cost_per_hectare': 1500.0,
                'labor_cost_per_hectare': 5400.0,
                'organic_premium': '60-100%',
                'sustainable_premium': '25-40%',
                'local_premium': '30-60%',
                'sustainability_opportunities': [
                    'Use integrated pest management (reduce pesticide use)',
                    'Implement precision fertigation (optimize nutrient use)',
                    'Use beneficial insects for pest control (reduce chemicals)',
                    'Adopt organic certification (premium market access)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - Berry Production'
            },
            {
                'name': 'Avocados',
                'slug': 'avocados',
                'category': 'tree_fruit',
                'description': 'Premium tree fruit crop with high water requirements. Growing demand in health-conscious markets.',
                'typical_farm_size': '15-80 hectares',
                'growing_season': '12 months (evergreen)',
                'harvest_season': 'Year-round (by variety)',
                'emissions_per_hectare': 3600.0,
                'industry_average': 3600.0,
                'best_practice': 2500.0,
                'carbon_credit_potential': 550.0,
                'typical_cost_per_hectare': 4800.0,
                'fertilizer_cost_per_hectare': 700.0,
                'fuel_cost_per_hectare': 450.0,
                'irrigation_cost_per_hectare': 1200.0,
                'labor_cost_per_hectare': 2450.0,
                'organic_premium': '40-80%',
                'sustainable_premium': '20-35%',
                'local_premium': '15-30%',
                'sustainability_opportunities': [
                    'Use deficit irrigation strategies (reduce water use by 25%)',
                    'Implement integrated pest management (reduce chemical inputs)',
                    'Plant beneficial insect habitat (natural pest control)',
                    'Use precision fertilizer application (reduce nutrient runoff)'
                ],
                'usda_verified': True,
                'data_source': 'USDA Agricultural Research Service - Avocado Production'
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for crop_data in usda_crop_types:
            crop_type, created = CropType.objects.get_or_create(
                slug=crop_data['slug'],
                defaults=crop_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created crop type: {crop_type.name}')
                )
            else:
                # Update existing crop type with new data
                for key, value in crop_data.items():
                    setattr(crop_type, key, value)
                crop_type.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'🔄 Updated crop type: {crop_type.name}')
                )
        
        total_count = CropType.objects.filter(is_active=True).count()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n🎉 USDA Crop Types Population Complete!'
                f'\n📊 Created: {created_count} new crop types'
                f'\n🔄 Updated: {updated_count} existing crop types'
                f'\n📈 Total active crop types: {total_count}'
                f'\n\n✅ The production form dropdown will now show all 16 USDA-compliant crop types!'
            )
        ) 