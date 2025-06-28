"""
Django Management Command: Validate Emission Factors Consistency

This command validates that all carbon calculation modules are using consistent
USDA-verified emission factors from the centralized registry.

Usage:
    python manage.py validate_emission_factors
"""

import logging
from django.core.management.base import BaseCommand
from carbon.services.emission_factors import emission_factors
from carbon.services.calculator import CarbonFootprintCalculator
from carbon.services.enhanced_usda_factors import EnhancedUSDAFactors
from carbon.services.event_carbon_calculator import EventCarbonCalculator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Validate emission factors consistency across all calculation modules'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                'Starting emission factors consistency validation...'
            )
        )

        # Perform comprehensive validation
        all_passed = True
        
        # 1. Validate registry integrity
        registry_valid = self._validate_registry()
        all_passed = all_passed and registry_valid
        
        # 2. Validate calculator consistency
        calculator_valid = self._validate_calculators()
        all_passed = all_passed and calculator_valid
        
        # 3. Validate factor values
        values_valid = self._validate_factor_values()
        all_passed = all_passed and values_valid
        
        # 4. Check for legacy issues
        legacy_clean = self._check_legacy_issues()
        all_passed = all_passed and legacy_clean

        # Final result
        if all_passed:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n✅ ALL VALIDATIONS PASSED\n'
                    'Emission factors are consistent across all modules!\n'
                    f'Using USDA-verified factors version {emission_factors.VERSION}'
                )
            )
        else:
            self.stdout.write(
                self.style.ERROR(
                    '\n❌ VALIDATION FAILED\n'
                    'Inconsistencies detected. Please review the issues above.'
                )
            )

    def _validate_registry(self):
        """Validate the emission factors registry"""
        self.stdout.write("\n🔍 Validating Emission Factors Registry...")
        
        try:
            # Test registry metadata
            metadata = emission_factors.get_metadata()
            self.stdout.write(f"✓ Registry version: {metadata['version']}")
            self.stdout.write(f"✓ Data source: {metadata['data_source']}")
            self.stdout.write(f"✓ USDA verified: {metadata['usda_verified']}")
            self.stdout.write(f"✓ Total factors: {metadata['total_factors']}")
            
            # Test factor validation
            validation = emission_factors.validate_factor_consistency()
            if validation['valid']:
                self.stdout.write(f"✓ Factor validation passed: {validation['factor_count']} factors")
            else:
                self.stdout.write(
                    self.style.ERROR(f"✗ Factor validation failed: {len(validation['issues'])} issues")
                )
                for issue in validation['issues']:
                    self.stdout.write(f"  - {issue}")
                return False
            
            # Test individual factor retrieval
            nitrogen = emission_factors.get_fertilizer_factor('nitrogen')
            if nitrogen['value'] == 5.86:
                self.stdout.write("✓ Nitrogen factor correct: 5.86 kg CO2e per kg N")
            else:
                self.stdout.write(
                    self.style.ERROR(f"✗ Nitrogen factor incorrect: {nitrogen['value']}")
                )
                return False
                
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Registry validation failed: {str(e)}")
            )
            return False

    def _validate_calculators(self):
        """Validate that all calculators use consistent factors"""
        self.stdout.write("\n🔍 Validating Calculator Consistency...")
        
        try:
            # Initialize all calculators
            carbon_calc = CarbonFootprintCalculator()
            enhanced_usda = EnhancedUSDAFactors()
            event_calc = EventCarbonCalculator()
            
            # Check nitrogen factor consistency
            n1 = carbon_calc.usda_factors['fertilizer']['nitrogen']
            n2 = enhanced_usda.base_usda_factors['nitrogen']
            n3 = event_calc.USDA_FERTILIZER_FACTORS['nitrogen']
            n_registry = emission_factors.get_fertilizer_factor('nitrogen')['value']
            
            if n1 == n2 == n3 == n_registry == 5.86:
                self.stdout.write("✓ Nitrogen factor consistent across all calculators")
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Nitrogen factor inconsistent:\n"
                        f"  CarbonFootprintCalculator: {n1}\n"
                        f"  EnhancedUSDAFactors: {n2}\n"
                        f"  EventCarbonCalculator: {n3}\n"
                        f"  Registry: {n_registry}"
                    )
                )
                return False
            
            # Check other key factors
            factors_to_check = [
                ('phosphorus', 0.20),
                ('potassium', 0.15)
            ]
            
            for factor_name, expected_value in factors_to_check:
                f1 = carbon_calc.usda_factors['fertilizer'][factor_name]
                f2 = enhanced_usda.base_usda_factors[factor_name]
                f3 = event_calc.USDA_FERTILIZER_FACTORS[factor_name]
                f_registry = emission_factors.get_fertilizer_factor(factor_name)['value']
                
                if f1 == f2 == f3 == f_registry == expected_value:
                    self.stdout.write(f"✓ {factor_name.capitalize()} factor consistent: {expected_value}")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"✗ {factor_name.capitalize()} factor inconsistent")
                    )
                    return False
            
            # Check fuel factors
            fuel_factors = [
                ('diesel', 2.68),
                ('gasoline', 2.31)
            ]
            
            for fuel_name, expected_value in fuel_factors:
                f1 = carbon_calc.usda_factors['fuel'][fuel_name]
                f2 = enhanced_usda.base_usda_factors[fuel_name]
                f3 = event_calc.FUEL_EMISSION_FACTORS[fuel_name]
                f_registry = emission_factors.get_fuel_factor(fuel_name)['value']
                
                if f1 == f2 == f3 == f_registry == expected_value:
                    self.stdout.write(f"✓ {fuel_name.capitalize()} factor consistent: {expected_value}")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"✗ {fuel_name.capitalize()} factor inconsistent")
                    )
                    return False
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Calculator validation failed: {str(e)}")
            )
            return False

    def _validate_factor_values(self):
        """Validate that factor values are reasonable"""
        self.stdout.write("\n🔍 Validating Factor Values...")
        
        try:
            # Check nitrogen factor specifically (main issue we're fixing)
            nitrogen = emission_factors.get_fertilizer_factor('nitrogen')
            if nitrogen['value'] != 5.86:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Nitrogen factor should be 5.86, got {nitrogen['value']}"
                    )
                )
                return False
            else:
                self.stdout.write("✓ Nitrogen factor is correct USDA value: 5.86")
            
            # Check that factors are positive
            all_factors = emission_factors.get_all_factors_simple()
            for name, value in all_factors.items():
                if not isinstance(value, (int, float)) or value < 0:
                    self.stdout.write(
                        self.style.ERROR(f"✗ Invalid factor value for {name}: {value}")
                    )
                    return False
            
            self.stdout.write(f"✓ All {len(all_factors)} factors have valid positive values")
            
            # Check for reasonable ranges
            if all_factors['nitrogen'] > 10 or all_factors['nitrogen'] < 1:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠ Nitrogen factor {all_factors['nitrogen']} outside expected range"
                    )
                )
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Factor value validation failed: {str(e)}")
            )
            return False

    def _check_legacy_issues(self):
        """Check for legacy factor issues"""
        self.stdout.write("\n🔍 Checking for Legacy Issues...")
        
        try:
            # Check for the old incorrect nitrogen factor
            legacy_info = emission_factors.check_legacy_usage('nitrogen_old')
            if legacy_info:
                self.stdout.write(
                    f"✓ Legacy nitrogen factor (6.7) properly marked as deprecated"
                )
            else:
                self.stdout.write("✓ No legacy factor records found")
            
            # Verify no hardcoded 6.7 values in use
            current_nitrogen = emission_factors.get_fertilizer_factor('nitrogen')['value']
            if current_nitrogen == 6.7:
                self.stdout.write(
                    self.style.ERROR("✗ Still using old incorrect nitrogen factor 6.7!")
                )
                return False
            else:
                self.stdout.write("✓ Old incorrect nitrogen factor (6.7) not in use")
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"✗ Legacy check failed: {str(e)}")
            )
            return False

    def _generate_summary_report(self):
        """Generate a summary report of all factors"""
        self.stdout.write("\n📊 Emission Factors Summary Report")
        self.stdout.write("=" * 50)
        
        try:
            all_factors = emission_factors.get_all_factors_simple()
            
            self.stdout.write("\nFertilizer Factors:")
            self.stdout.write(f"  Nitrogen: {all_factors['nitrogen']} kg CO2e per kg N")
            self.stdout.write(f"  Phosphorus: {all_factors['phosphorus']} kg CO2e per kg P2O5")
            self.stdout.write(f"  Potassium: {all_factors['potassium']} kg CO2e per kg K2O")
            
            self.stdout.write("\nFuel Factors:")
            self.stdout.write(f"  Diesel: {all_factors['diesel']} kg CO2e per liter")
            self.stdout.write(f"  Gasoline: {all_factors['gasoline']} kg CO2e per liter")
            self.stdout.write(f"  Natural Gas: {all_factors['natural_gas']} kg CO2e per m³")
            
            self.stdout.write("\nElectricity Factors:")
            self.stdout.write(f"  Grid: {all_factors['electricity_grid']} kg CO2e per kWh")
            self.stdout.write(f"  Solar: {all_factors['electricity_solar']} kg CO2e per kWh")
            self.stdout.write(f"  Wind: {all_factors['electricity_wind']} kg CO2e per kWh")
            
            self.stdout.write("\nWater Factors:")
            self.stdout.write(f"  Irrigation: {all_factors['water_irrigation']} kg CO2e per m³")
            self.stdout.write(f"  Pumping: {all_factors['water_pumping']} kg CO2e per m³")
            
            metadata = emission_factors.get_metadata()
            self.stdout.write(f"\nRegistry Version: {metadata['version']}")
            self.stdout.write(f"Data Source: {metadata['data_source']}")
            self.stdout.write(f"Last Updated: {emission_factors.LAST_UPDATED}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Could not generate summary: {str(e)}")
            )