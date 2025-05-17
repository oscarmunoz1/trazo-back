from typing import Dict, Any, List, Optional
from decimal import Decimal
import logging
from ..models import CarbonSource, CarbonBenchmark

logger = logging.getLogger(__name__)

class CoolFarmService:
    """Service for calculating and managing farm carbon emissions."""

    def __init__(self):
        self.emission_factors = {
            'fertilizer': {
                'nitrogen': 6.7,  # kg CO2e per kg of N
                'phosphorus': 0.6,  # kg CO2e per kg of P2O5
                'potassium': 0.4,  # kg CO2e per kg of K2O
            },
            'fuel': {
                'diesel': 2.7,  # kg CO2e per liter
                'gasoline': 2.3,  # kg CO2e per liter
                'lpg': 1.7,  # kg CO2e per liter
            },
            'electricity': {
                'grid': 0.4,  # kg CO2e per kWh (US average)
                'solar': 0.0,  # kg CO2e per kWh
                'wind': 0.0,  # kg CO2e per kWh
            },
            'water': {
                'irrigation': 0.3,  # kg CO2e per m3
                'pumping': 0.2,  # kg CO2e per m3
            }
        }

    def calculate_farm_emissions(self,
                               inputs: Dict[str, Any],
                               crop_type: str,
                               area: float,
                               region: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate total carbon emissions for a farm based on inputs.
        
        Args:
            inputs: Dictionary of input data (fertilizer, fuel, etc.)
            crop_type: Type of crop being grown
            area: Area in acres
            region: Optional region for more accurate calculations
            
        Returns:
            Dictionary containing total emissions and breakdown
        """
        try:
            total_emissions = 0
            breakdown = {}
            
            # Calculate fertilizer emissions
            if 'fertilizer' in inputs:
                fertilizer_emissions = self._calculate_fertilizer_emissions(
                    inputs['fertilizer']
                )
                total_emissions += fertilizer_emissions
                breakdown['fertilizer'] = fertilizer_emissions
            
            # Calculate fuel emissions
            if 'fuel' in inputs:
                fuel_emissions = self._calculate_fuel_emissions(
                    inputs['fuel']
                )
                total_emissions += fuel_emissions
                breakdown['fuel'] = fuel_emissions
            
            # Calculate electricity emissions
            if 'electricity' in inputs:
                electricity_emissions = self._calculate_electricity_emissions(
                    inputs['electricity']
                )
                total_emissions += electricity_emissions
                breakdown['electricity'] = electricity_emissions
            
            # Calculate water-related emissions
            if 'water' in inputs:
                water_emissions = self._calculate_water_emissions(
                    inputs['water']
                )
                total_emissions += water_emissions
                breakdown['water'] = water_emissions
            
            # Get industry benchmark if available
            benchmark = self._get_industry_benchmark(crop_type, region)
            
            # Calculate efficiency score
            efficiency_score = self._calculate_efficiency_score(
                total_emissions,
                area,
                benchmark
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                breakdown,
                benchmark,
                efficiency_score
            )
            
            return {
                'total_emissions': total_emissions,
                'emissions_per_acre': total_emissions / area,
                'breakdown': breakdown,
                'efficiency_score': efficiency_score,
                'benchmark': benchmark,
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error calculating farm emissions: {str(e)}")
            raise

    def _calculate_fertilizer_emissions(self, fertilizer_data: Dict[str, Any]) -> float:
        """Calculate emissions from fertilizer use"""
        total_emissions = 0
        
        for nutrient, amount in fertilizer_data.items():
            if nutrient in self.emission_factors['fertilizer']:
                total_emissions += amount * self.emission_factors['fertilizer'][nutrient]
        
        return total_emissions

    def _calculate_fuel_emissions(self, fuel_data: Dict[str, Any]) -> float:
        """Calculate emissions from fuel use"""
        total_emissions = 0
        
        for fuel_type, amount in fuel_data.items():
            if fuel_type in self.emission_factors['fuel']:
                total_emissions += amount * self.emission_factors['fuel'][fuel_type]
        
        return total_emissions

    def _calculate_electricity_emissions(self, electricity_data: Dict[str, Any]) -> float:
        """Calculate emissions from electricity use"""
        total_emissions = 0
        
        for source, amount in electricity_data.items():
            if source in self.emission_factors['electricity']:
                total_emissions += amount * self.emission_factors['electricity'][source]
        
        return total_emissions

    def _calculate_water_emissions(self, water_data: Dict[str, Any]) -> float:
        """Calculate emissions from water use"""
        total_emissions = 0
        
        for use_type, amount in water_data.items():
            if use_type in self.emission_factors['water']:
                total_emissions += amount * self.emission_factors['water'][use_type]
        
        return total_emissions

    def _get_industry_benchmark(self, crop_type: str, region: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get industry benchmark data for the crop type and region"""
        try:
            benchmark = CarbonBenchmark.objects.filter(
                crop_type=crop_type,
                region=region
            ).order_by('-year').first()
            
            if benchmark:
                return {
                    'average_emissions': benchmark.average_emissions,
                    'min_emissions': benchmark.min_emissions,
                    'max_emissions': benchmark.max_emissions,
                    'year': benchmark.year,
                    'source': benchmark.source
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting industry benchmark: {str(e)}")
            return None

    def _calculate_efficiency_score(self,
                                  total_emissions: float,
                                  area: float,
                                  benchmark: Optional[Dict[str, Any]]) -> int:
        """Calculate efficiency score (0-100) based on emissions and benchmark"""
        if not benchmark:
            return 50  # Default score if no benchmark available
        
        emissions_per_acre = total_emissions / area
        benchmark_avg = benchmark['average_emissions']
        
        if emissions_per_acre <= benchmark['min_emissions']:
            return 100
        elif emissions_per_acre >= benchmark['max_emissions']:
            return 0
        
        # Linear interpolation between min and max
        score = 100 * (1 - (emissions_per_acre - benchmark['min_emissions']) /
                      (benchmark['max_emissions'] - benchmark['min_emissions']))
        
        return max(0, min(100, int(score)))

    def _generate_recommendations(self,
                                breakdown: Dict[str, float],
                                benchmark: Optional[Dict[str, Any]],
                                efficiency_score: int) -> List[str]:
        """Generate recommendations based on emissions breakdown and score"""
        recommendations = []
        
        # General recommendations based on efficiency score
        if efficiency_score < 50:
            recommendations.append("Consider implementing a comprehensive carbon reduction strategy")
        
        # Specific recommendations based on emission sources
        if 'fertilizer' in breakdown and breakdown['fertilizer'] > 0:
            recommendations.append("Consider using organic fertilizers or implementing precision agriculture")
        
        if 'fuel' in breakdown and breakdown['fuel'] > 0:
            recommendations.append("Explore electric or hybrid equipment options")
        
        if 'electricity' in breakdown and breakdown['electricity'] > 0:
            recommendations.append("Consider installing solar panels or switching to renewable energy")
        
        if 'water' in breakdown and breakdown['water'] > 0:
            recommendations.append("Implement drip irrigation and water conservation practices")
        
        # Add benchmark-based recommendations
        if benchmark and efficiency_score < 75:
            recommendations.append(f"Your emissions are above the {benchmark['year']} industry average. "
                                f"Consider reviewing your practices against industry best practices.")
        
        return recommendations

# Create singleton instance
coolfarm_service = CoolFarmService() 