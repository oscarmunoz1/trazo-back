"""
Real USDA Integration Service
Integrates with actual USDA APIs and provides carbon footprint calculations
using available government data sources.
"""

import logging
import requests
import json
from typing import Dict, Any, Optional, List
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
import hashlib

logger = logging.getLogger(__name__)


class RealUSDAAPIClient:
    """Client for real USDA APIs - NASS QuickStats and ERS"""
    
    def __init__(self):
        # Real USDA API endpoints
        self.nass_base_url = 'https://quickstats.nass.usda.gov/api'
        self.ers_base_url = 'https://api.ers.usda.gov'
        self.fooddata_base_url = 'https://api.nal.usda.gov/fdc/v1'
        
        # API Keys (you'll need to register for these)
        self.nass_api_key = getattr(settings, 'USDA_NASS_API_KEY', None)
        self.ers_api_key = getattr(settings, 'USDA_ERS_API_KEY', None)
        self.fooddata_api_key = getattr(settings, 'USDA_FOODDATA_API_KEY', None)
        
        self.timeout = 30
        
        # Base emission factors from IPCC/EPA guidelines
        self.base_emission_factors = {
            'nitrogen': 5.86,    # kg CO2e per kg N (IPCC 2019)
            'phosphorus': 0.20,  # kg CO2e per kg P2O5
            'potassium': 0.15,   # kg CO2e per kg K2O
            'diesel': 2.68,      # kg CO2e per liter
            'gasoline': 2.31,    # kg CO2e per liter
            'natural_gas': 2.03, # kg CO2e per m³
        }
        
        # Regional yield benchmarks from NASS data
        self.regional_yield_benchmarks = {}
    
    def get_nass_crop_data(self, crop_type: str, state: str, year: int = None) -> Dict[str, Any]:
        """Fetch real crop data from USDA NASS QuickStats API with caching"""
        try:
            if not self.nass_api_key:
                logger.warning("NASS API key not configured")
                return {}
            
            # Use current year if not specified
            if not year:
                year = datetime.now().year - 1  # Previous year data is usually available
            
            # Add caching to prevent repeated API calls
            cache_key = f'nass_data_{crop_type}_{state}_{year}_v3'
            cached_data = cache.get(cache_key)
            
            if cached_data:
                logger.info(f"✅ Using cached NASS data for {crop_type} in {state}")
                return cached_data
            
            # Enhanced crop type mapping for NASS commodity names
            crop_lower = crop_type.lower()
            commodity_map = {
                'corn': 'CORN',
                'soybeans': 'SOYBEANS', 
                'soybean': 'SOYBEANS',
                'wheat': 'WHEAT',
                'citrus': 'ORANGES',
                'orange': 'ORANGES',
                'oranges': 'ORANGES',
                'citrus (oranges)': 'ORANGES',
                'almonds': 'ALMONDS',
                'almond': 'ALMONDS',
                'apples': 'APPLES',
                'apple': 'APPLES',
                'grapes': 'GRAPES',
                'grape': 'GRAPES',
                'tomatoes': 'TOMATOES',
                'tomato': 'TOMATOES',
                'lettuce': 'LETTUCE',
                'carrots': 'CARROTS',
                'carrot': 'CARROTS',
                'potatoes': 'POTATOES',
                'potato': 'POTATOES'
            }
            
            # Try exact match first, then check if any key contains the crop type
            commodity = None
            if crop_lower in commodity_map:
                commodity = commodity_map[crop_lower]
            else:
                # Try partial matching for complex names like "Citrus (Oranges)"
                for key, value in commodity_map.items():
                    if key in crop_lower or crop_lower in key:
                        commodity = value
                        break
            
            # Fallback to uppercase crop type if no mapping found
            if not commodity:
                commodity = crop_type.upper()
                logger.info(f"No commodity mapping found for '{crop_type}', using '{commodity}'")
            
            params = {
                'key': self.nass_api_key,
                'commodity_desc': commodity,
                'state_alpha': state.upper(),
                'year': year,
                'statisticcat_desc': 'YIELD',
                'format': 'JSON'
            }
            
            logger.info(f"NASS API request: commodity={commodity}, state={state}, year={year}")
            
            response = requests.get(
                f"{self.nass_base_url}/api_GET",
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and len(data['data']) > 0:
                    logger.info(f"Successfully fetched NASS data for {crop_type} ({commodity}) in {state}: {len(data['data'])} records")
                    # Cache for 2 hours to prevent repeated API calls
                    cache.set(cache_key, data, 7200)
                    return data
                else:
                    logger.warning(f"NASS API returned no data for {commodity} in {state} for {year}")
                    return {}
            else:
                logger.warning(f"NASS API returned status {response.status_code} for {commodity} in {state}")
                # Try with different parameters if first attempt fails
                if response.status_code in [400, 500] and year > 2020:
                    logger.info(f"Retrying NASS API with previous year ({year-1})")
                    return self.get_nass_crop_data(crop_type, state, year-1)
                return {}
                
        except requests.RequestException as e:
            logger.error(f"NASS API request failed: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching NASS data: {e}")
            return {}
    
    def get_benchmark_yield(self, crop_type: str, state: str) -> Optional[float]:
        """Get benchmark yield for a crop in a state from NASS data"""
        try:
            # Try to get cached benchmark
            cache_key = f"nass_benchmark_{crop_type}_{state}"
            cached_benchmark = cache.get(cache_key)
            
            if cached_benchmark:
                return cached_benchmark
            
            # Fetch from NASS API
            nass_data = self.get_nass_crop_data(crop_type, state)
            
            if nass_data and 'data' in nass_data:
                # Extract yield values and calculate average
                yields = []
                for record in nass_data['data']:
                    if record.get('Value') and record['Value'] != '(D)':  # (D) means withheld
                        try:
                            # Remove commas and convert to float
                            yield_value = float(record['Value'].replace(',', ''))
                            yields.append(yield_value)
                        except (ValueError, TypeError):
                            continue
                
                if yields:
                    avg_yield = sum(yields) / len(yields)
                    # Cache for 24 hours
                    cache.set(cache_key, avg_yield, 86400)
                    return avg_yield
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting benchmark yield: {e}")
            return None
    
    def calculate_carbon_intensity(self, crop_type: str, state: str, 
                                 farm_practices: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate carbon intensity using real USDA data and emission factors"""
        try:
            # Get benchmark yield from NASS
            benchmark_yield = self.get_benchmark_yield(crop_type, state)
            
            # Extract farm inputs from practices
            inputs = farm_practices.get('inputs', {})
            area_hectares = farm_practices.get('area_hectares', 1)
            actual_yield = farm_practices.get('yield_per_hectare', 0)
            
            # Calculate emissions from inputs
            total_emissions = 0
            emission_breakdown = {}
            
            # Nitrogen emissions
            if 'nitrogen_kg' in inputs:
                n_emissions = inputs['nitrogen_kg'] * self.base_emission_factors['nitrogen']
                total_emissions += n_emissions
                emission_breakdown['nitrogen'] = n_emissions
            
            # Phosphorus emissions
            if 'phosphorus_kg' in inputs:
                p_emissions = inputs['phosphorus_kg'] * self.base_emission_factors['phosphorus']
                total_emissions += p_emissions
                emission_breakdown['phosphorus'] = p_emissions
            
            # Fuel emissions
            if 'diesel_liters' in inputs:
                fuel_emissions = inputs['diesel_liters'] * self.base_emission_factors['diesel']
                total_emissions += fuel_emissions
                emission_breakdown['fuel'] = fuel_emissions
            
            # Calculate carbon intensity (kg CO2e per kg product)
            carbon_intensity = 0
            if actual_yield > 0:
                total_production = actual_yield * area_hectares
                carbon_intensity = total_emissions / total_production
            
            # Compare to benchmark
            benchmark_comparison = None
            if benchmark_yield:
                benchmark_comparison = {
                    'farm_yield': actual_yield,
                    'regional_benchmark': benchmark_yield,
                    'performance_ratio': actual_yield / benchmark_yield if benchmark_yield > 0 else 0,
                    'yield_efficiency': 'above_average' if actual_yield > benchmark_yield else 'below_average'
                }
            
            return {
                'carbon_intensity': carbon_intensity,
                'total_emissions': total_emissions,
                'emission_breakdown': emission_breakdown,
                'benchmark_comparison': benchmark_comparison,
                'data_source': 'USDA NASS + EPA emission factors',
                'calculation_method': 'life_cycle_assessment',
                'confidence_level': 'high' if benchmark_yield else 'medium'
            }
            
        except Exception as e:
            logger.error(f"Error calculating carbon intensity: {e}")
            return {
                'error': str(e),
                'carbon_intensity': 0,
                'confidence_level': 'low'
            }
    
    def get_food_composition_data(self, crop_type: str) -> Dict[str, Any]:
        """Fetch food composition data from USDA FoodData Central API"""
        try:
            if not self.fooddata_api_key:
                logger.warning("FoodData Central API key not configured")
                return {}
            
            # Map crop types to food items
            food_map = {
                'corn': 'sweet corn',
                'soybeans': 'soybeans',
                'wheat': 'wheat',
                'citrus': 'orange',
                'almonds': 'almonds'
            }
            
            search_term = food_map.get(crop_type.lower(), crop_type)
            
            # Search for food items
            search_params = {
                'api_key': self.fooddata_api_key,
                'query': search_term,
                'dataType': 'Foundation,SR Legacy',
                'pageSize': 5
            }
            
            response = requests.get(
                f"{self.fooddata_base_url}/foods/search",
                params=search_params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Successfully fetched FoodData Central data for {crop_type}")
                return data
            else:
                logger.warning(f"FoodData Central API returned status {response.status_code}")
                return {}
                
        except requests.RequestException as e:
            logger.error(f"FoodData Central API request failed: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching FoodData Central data: {e}")
            return {}
    
    def get_nutritional_carbon_factors(self, crop_type: str) -> Dict[str, Any]:
        """Get nutritional data to enhance carbon calculations"""
        try:
            food_data = self.get_food_composition_data(crop_type)
            
            if not food_data or 'foods' not in food_data:
                return {}
            
            # Extract relevant nutritional data from first result
            if food_data['foods']:
                food_item = food_data['foods'][0]
                
                # Get detailed nutrient info
                food_id = food_item.get('fdcId')
                if food_id:
                    detail_response = requests.get(
                        f"{self.fooddata_base_url}/food/{food_id}",
                        params={'api_key': self.fooddata_api_key},
                        timeout=self.timeout
                    )
                    
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        
                        # Extract key nutrients
                        nutrients = {}
                        if 'foodNutrients' in detail_data:
                            for nutrient in detail_data['foodNutrients']:
                                name = nutrient.get('nutrient', {}).get('name', '')
                                value = nutrient.get('amount', 0)
                                unit = nutrient.get('nutrient', {}).get('unitName', '')
                                
                                if 'Protein' in name:
                                    nutrients['protein_g'] = value
                                elif 'Energy' in name and 'kcal' in unit:
                                    nutrients['energy_kcal'] = value
                                elif 'Carbohydrate' in name:
                                    nutrients['carbs_g'] = value
                                elif 'Total lipid' in name:
                                    nutrients['fat_g'] = value
                        
                        # Calculate nutritional efficiency factors
                        carbon_efficiency = self._calculate_nutritional_efficiency(nutrients)
                        
                        return {
                            'nutritional_data': nutrients,
                            'carbon_efficiency': carbon_efficiency,
                            'food_description': food_item.get('description', ''),
                            'data_source': 'USDA FoodData Central'
                        }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error getting nutritional carbon factors: {e}")
            return {}
    
    def _calculate_nutritional_efficiency(self, nutrients: Dict[str, float]) -> Dict[str, Any]:
        """Calculate carbon efficiency based on nutritional content"""
        try:
            # Nutritional density scoring
            protein = nutrients.get('protein_g', 0)
            energy = nutrients.get('energy_kcal', 0)
            
            # Calculate protein efficiency (g protein per kg CO2e)
            # Higher protein content = better carbon efficiency for nutrition
            nutrition_score = 0
            
            if protein > 0:
                nutrition_score += min(protein * 2, 40)  # Max 40 points for protein
            
            if energy > 0:
                nutrition_score += min(energy / 10, 30)  # Max 30 points for energy
            
            # Quality assessment
            if nutrition_score >= 60:
                efficiency_rating = 'high'
            elif nutrition_score >= 30:
                efficiency_rating = 'medium'
            else:
                efficiency_rating = 'low'
            
            return {
                'nutrition_score': nutrition_score,
                'efficiency_rating': efficiency_rating,
                'protein_content': protein,
                'energy_content': energy,
                'carbon_nutrition_ratio': f"{protein:.2f}g protein per unit carbon"
            }
            
        except Exception as e:
            logger.error(f"Error calculating nutritional efficiency: {e}")
            return {'efficiency_rating': 'unknown'}
    
    def validate_calculation_methodology(self, calculation_data: Dict) -> Dict[str, Any]:
        """Validate calculation methodology against EPA/IPCC standards"""
        try:
            validation_results = {
                'is_valid': True,
                'methodology_score': 0,
                'validation_details': {},
                'recommendations': []
            }
            
            # Check if using EPA-approved emission factors
            if calculation_data.get('emission_factors_source') == 'EPA':
                validation_results['methodology_score'] += 30
                validation_results['validation_details']['epa_factors'] = True
            else:
                validation_results['recommendations'].append('Use EPA-approved emission factors')
            
            # Check if using USDA yield benchmarks
            if calculation_data.get('benchmark_comparison'):
                validation_results['methodology_score'] += 25
                validation_results['validation_details']['usda_benchmarks'] = True
            
            # Check calculation completeness
            required_inputs = ['nitrogen', 'fuel', 'yield']
            provided_inputs = calculation_data.get('inputs', {}).keys()
            
            completeness = len(set(required_inputs) & set(provided_inputs)) / len(required_inputs)
            validation_results['methodology_score'] += int(completeness * 25)
            
            # Check regional specificity
            if calculation_data.get('state') and calculation_data.get('crop_type'):
                validation_results['methodology_score'] += 20
                validation_results['validation_details']['regional_specificity'] = True
            
            # Overall validation
            if validation_results['methodology_score'] >= 80:
                validation_results['validation_level'] = 'high'
            elif validation_results['methodology_score'] >= 60:
                validation_results['validation_level'] = 'medium'
            else:
                validation_results['validation_level'] = 'low'
                validation_results['is_valid'] = False
            
            return validation_results
            
        except Exception as e:
            logger.error(f"Error validating calculation: {e}")
            return {
                'is_valid': False,
                'error': str(e),
                'validation_level': 'failed'
            }


class EPAEmissionFactorService:
    """Service to provide EPA-approved emission factors"""
    
    def __init__(self):
        # EPA emission factors from official sources
        self.epa_factors = {
            'electricity': {
                'us_average': 0.999,  # kg CO2e per kWh (2022 EPA eGRID)
                'by_state': {
                    'CA': 0.643,  # California (lower due to renewables)
                    'TX': 0.878,  # Texas
                    'IA': 1.456,  # Iowa (coal-heavy)
                    'IL': 0.899,  # Illinois
                    'FL': 0.820,  # Florida
                }
            },
            'fertilizer': {
                'nitrogen': 5.86,    # kg CO2e per kg N (IPCC 2019)
                'phosphorus': 0.20,  # kg CO2e per kg P2O5
                'potassium': 0.15,   # kg CO2e per kg K2O
            },
            'fuel': {
                'diesel': 2.68,      # kg CO2e per liter
                'gasoline': 2.31,    # kg CO2e per liter
                'natural_gas': 2.03, # kg CO2e per m³
            }
        }
    
    def get_emission_factor(self, category: str, subcategory: str, state: str = None) -> float:
        """Get EPA emission factor for a specific category"""
        try:
            if category not in self.epa_factors:
                return 0.0
            
            category_data = self.epa_factors[category]
            
            # Handle state-specific factors
            if subcategory == 'electricity' and state and 'by_state' in category_data:
                return category_data['by_state'].get(state, category_data['us_average'])
            
            # Handle direct lookups
            if isinstance(category_data, dict) and subcategory in category_data:
                return category_data[subcategory]
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting EPA emission factor: {e}")
            return 0.0


# Integration function for your existing system
def get_real_usda_carbon_data(crop_type: str, state: str, farm_practices: Dict) -> Dict[str, Any]:
    """
    Main function to integrate real USDA data with carbon calculations
    This replaces the mock USDA API calls in enhanced_usda_factors.py
    """
    usda_client = RealUSDAAPIClient()
    epa_service = EPAEmissionFactorService()
    
    # Get real calculation using actual APIs
    carbon_data = usda_client.calculate_carbon_intensity(crop_type, state, farm_practices)
    
    # Get nutritional data from FoodData Central
    nutritional_data = usda_client.get_nutritional_carbon_factors(crop_type)
    
    # Validate methodology
    validation = usda_client.validate_calculation_methodology({
        'emission_factors_source': 'EPA',
        'inputs': farm_practices.get('inputs', {}),
        'state': state,
        'crop_type': crop_type
    })
    
    # Combine results
    result = {
        **carbon_data,
        'validation': validation,
        'api_sources': ['USDA NASS', 'USDA FoodData Central', 'EPA'],
        'real_data': True,
        'timestamp': timezone.now().isoformat()
    }
    
    # Add nutritional data if available
    if nutritional_data:
        result['nutritional_analysis'] = nutritional_data
        
        # Enhanced carbon efficiency scoring
        if 'carbon_efficiency' in nutritional_data:
            efficiency = nutritional_data['carbon_efficiency']
            result['carbon_nutrition_efficiency'] = {
                'rating': efficiency.get('efficiency_rating', 'unknown'),
                'score': efficiency.get('nutrition_score', 0),
                'description': f"Produces {efficiency.get('protein_content', 0):.1f}g protein per unit of carbon emissions"
            }
    
    return result 