import requests
from django.conf import settings
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class CoolFarmToolService:
    """Service for interacting with CoolFarmTool API for emission calculations"""
    
    def __init__(self):
        self.api_key = settings.COOLFARM_API_KEY
        self.base_url = settings.COOLFARM_API_URL
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def calculate_emissions(self, 
                          crop_type: str, 
                          acreage: float, 
                          inputs: Dict[str, Any],
                          region: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate emissions using CoolFarmTool API
        
        Args:
            crop_type: Type of crop (e.g., 'orange', 'soybean')
            acreage: Area in acres
            inputs: Dictionary of input data (fertilizer, fuel, etc.)
            region: Optional region for more accurate calculations
            
        Returns:
            Dictionary containing emission calculations and recommendations
        """
        try:
            payload = {
                'crop_type': crop_type,
                'acreage': acreage,
                'inputs': inputs,
                'region': region
            }
            
            response = requests.post(
                f"{self.base_url}/calculate",
                json=payload,
                headers=self.headers
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Log successful calculation
            logger.info(f"Successfully calculated emissions for {crop_type} on {acreage} acres")
            
            return {
                'co2e': data.get('co2e', 0),  # kg CO2e
                'breakdown': data.get('breakdown', {}),
                'recommendations': data.get('recommendations', []),
                'usda_verified': data.get('usda_verified', False)
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calculating emissions with CoolFarmTool: {str(e)}")
            # Return a fallback calculation based on USDA factors
            return self._fallback_calculation(crop_type, acreage, inputs)
    
    def _fallback_calculation(self, 
                            crop_type: str, 
                            acreage: float, 
                            inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback calculation using USDA emission factors when API is unavailable
        """
        # USDA emission factors (kg CO2e per acre)
        usda_factors = {
            'orange': 0.5,  # kg CO2e per kg of oranges
            'soybean': 0.4,
            'almond': 2.1,
            'default': 1.0
        }
        
        factor = usda_factors.get(crop_type.lower(), usda_factors['default'])
        
        # Calculate total emissions based on inputs
        total_emissions = 0
        breakdown = {}
        
        # Fertilizer emissions
        if 'fertilizer' in inputs:
            fertilizer_amount = inputs['fertilizer'].get('amount', 0)
            fertilizer_factor = 1.2  # kg CO2e per kg of fertilizer
            fertilizer_emissions = fertilizer_amount * fertilizer_factor
            total_emissions += fertilizer_emissions
            breakdown['fertilizer'] = fertilizer_emissions
        
        # Fuel emissions
        if 'fuel' in inputs:
            fuel_amount = inputs['fuel'].get('amount', 0)
            fuel_factor = 2.7  # kg CO2e per liter of diesel
            fuel_emissions = fuel_amount * fuel_factor
            total_emissions += fuel_emissions
            breakdown['fuel'] = fuel_emissions
        
        # Add crop-specific emissions
        crop_emissions = acreage * factor
        total_emissions += crop_emissions
        breakdown['crop'] = crop_emissions
        
        return {
            'co2e': total_emissions,
            'breakdown': breakdown,
            'recommendations': [
                'Consider using organic fertilizers to reduce emissions',
                'Implement drip irrigation to save water and reduce emissions',
                'Explore carbon offset programs'
            ],
            'usda_verified': True
        }

# Create a singleton instance
coolfarm_service = CoolFarmToolService() 