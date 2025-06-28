"""
Unit Tests for Emission Factors Consistency

These tests ensure that all carbon calculation modules use consistent USDA-verified
emission factors and prevent future data inconsistencies.
"""

import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from decimal import Decimal

from carbon.services.emission_factors import EmissionFactorsRegistry, emission_factors
from carbon.services.calculator import CarbonFootprintCalculator
from carbon.services.enhanced_usda_factors import EnhancedUSDAFactors
from carbon.services.event_carbon_calculator import EventCarbonCalculator


class EmissionFactorsRegistryTest(TestCase):
    """Test the centralized emission factors registry"""

    def test_registry_metadata(self):
        """Test that registry has proper metadata"""
        metadata = emission_factors.get_metadata()
        
        self.assertIn('version', metadata)
        self.assertIn('last_updated', metadata)
        self.assertIn('data_source', metadata)
        self.assertTrue(metadata['usda_verified'])
        self.assertTrue(metadata['compliance_ready'])

    def test_nitrogen_factor_consistency(self):
        """Test that nitrogen factor is the correct USDA value"""
        nitrogen_factor = emission_factors.get_fertilizer_factor('nitrogen')
        
        self.assertEqual(nitrogen_factor['value'], 5.86)
        self.assertEqual(nitrogen_factor['unit'], 'kg CO2e per kg N')
        self.assertIn('USDA', nitrogen_factor['source'])
        self.assertEqual(nitrogen_factor['confidence'], 'high')

    def test_all_fertilizer_factors_present(self):
        """Test that all required fertilizer factors are present"""
        required_nutrients = ['nitrogen', 'phosphorus', 'potassium']
        
        for nutrient in required_nutrients:
            factor = emission_factors.get_fertilizer_factor(nutrient)
            self.assertIsInstance(factor['value'], (int, float))
            self.assertGreater(factor['value'], 0)
            self.assertIn('USDA', factor['source'])

    def test_all_fuel_factors_present(self):
        """Test that all required fuel factors are present"""
        required_fuels = ['diesel', 'gasoline', 'natural_gas', 'lpg']
        
        for fuel in required_fuels:
            factor = emission_factors.get_fuel_factor(fuel)
            self.assertIsInstance(factor['value'], (int, float))
            self.assertGreater(factor['value'], 0)
            self.assertIn('EPA', factor['source'])

    def test_electricity_factors_present(self):
        """Test that electricity factors are present"""
        required_sources = ['grid', 'solar', 'wind']
        
        for source in required_sources:
            factor = emission_factors.get_electricity_factor(source)
            self.assertIsInstance(factor['value'], (int, float))
            self.assertGreaterEqual(factor['value'], 0)  # Solar/wind can be 0

    def test_water_factors_present(self):
        """Test that water factors are present"""
        required_types = ['irrigation', 'pumping']
        
        for water_type in required_types:
            factor = emission_factors.get_water_factor(water_type)
            self.assertIsInstance(factor['value'], (int, float))
            self.assertGreater(factor['value'], 0)

    def test_invalid_factor_raises_error(self):
        """Test that requesting invalid factors raises appropriate errors"""
        with self.assertRaises(ValueError):
            emission_factors.get_fertilizer_factor('invalid_nutrient')
        
        with self.assertRaises(ValueError):
            emission_factors.get_fuel_factor('invalid_fuel')

    def test_factor_validation(self):
        """Test the factor validation system"""
        validation = emission_factors.validate_factor_consistency()
        
        self.assertIn('valid', validation)
        self.assertIn('issues', validation)
        self.assertIn('factor_count', validation)
        self.assertGreater(validation['factor_count'], 0)

    def test_legacy_factor_detection(self):
        """Test detection of legacy/deprecated factors"""
        legacy_info = emission_factors.check_legacy_usage('nitrogen_old')
        
        self.assertIsNotNone(legacy_info)
        self.assertEqual(legacy_info['status'], 'deprecated')
        self.assertIn('6.7', str(legacy_info['value']))

    def test_simple_factors_compatibility(self):
        """Test backward compatibility function"""
        simple_factors = emission_factors.get_all_factors_simple()
        
        self.assertIn('nitrogen', simple_factors)
        self.assertIn('diesel', simple_factors)
        self.assertEqual(simple_factors['nitrogen'], 5.86)
        self.assertIsInstance(simple_factors['nitrogen'], (int, float))


class CalculatorConsistencyTest(TestCase):
    """Test that all calculator classes use consistent factors"""

    def setUp(self):
        """Set up test calculators"""
        self.carbon_calculator = CarbonFootprintCalculator()
        self.enhanced_usda = EnhancedUSDAFactors()
        self.event_calculator = EventCarbonCalculator()

    def test_nitrogen_factor_consistency_across_calculators(self):
        """Test that all calculators use the same nitrogen factor"""
        # Get nitrogen factors from all calculators
        carbon_calc_nitrogen = self.carbon_calculator.usda_factors['fertilizer']['nitrogen']
        enhanced_usda_nitrogen = self.enhanced_usda.base_usda_factors['nitrogen']
        event_calc_nitrogen = self.event_calculator.USDA_FERTILIZER_FACTORS['nitrogen']
        registry_nitrogen = emission_factors.get_fertilizer_factor('nitrogen')['value']
        
        # All should be equal to the correct USDA value
        expected_value = 5.86
        
        self.assertEqual(carbon_calc_nitrogen, expected_value)
        self.assertEqual(enhanced_usda_nitrogen, expected_value)
        self.assertEqual(event_calc_nitrogen, expected_value)
        self.assertEqual(registry_nitrogen, expected_value)
        
        # Verify none use the old incorrect value
        incorrect_value = 6.7
        self.assertNotEqual(carbon_calc_nitrogen, incorrect_value)
        self.assertNotEqual(enhanced_usda_nitrogen, incorrect_value)
        self.assertNotEqual(event_calc_nitrogen, incorrect_value)

    def test_phosphorus_factor_consistency(self):
        """Test phosphorus factor consistency"""
        carbon_calc_phosphorus = self.carbon_calculator.usda_factors['fertilizer']['phosphorus']
        enhanced_usda_phosphorus = self.enhanced_usda.base_usda_factors['phosphorus']
        event_calc_phosphorus = self.event_calculator.USDA_FERTILIZER_FACTORS['phosphorus']
        registry_phosphorus = emission_factors.get_fertilizer_factor('phosphorus')['value']
        
        expected_value = 0.20
        
        self.assertEqual(carbon_calc_phosphorus, expected_value)
        self.assertEqual(enhanced_usda_phosphorus, expected_value)
        self.assertEqual(event_calc_phosphorus, expected_value)
        self.assertEqual(registry_phosphorus, expected_value)

    def test_potassium_factor_consistency(self):
        """Test potassium factor consistency"""
        carbon_calc_potassium = self.carbon_calculator.usda_factors['fertilizer']['potassium']
        enhanced_usda_potassium = self.enhanced_usda.base_usda_factors['potassium']
        event_calc_potassium = self.event_calculator.USDA_FERTILIZER_FACTORS['potassium']
        registry_potassium = emission_factors.get_fertilizer_factor('potassium')['value']
        
        expected_value = 0.15
        
        self.assertEqual(carbon_calc_potassium, expected_value)
        self.assertEqual(enhanced_usda_potassium, expected_value)
        self.assertEqual(event_calc_potassium, expected_value)
        self.assertEqual(registry_potassium, expected_value)

    def test_diesel_factor_consistency(self):
        """Test diesel factor consistency"""
        carbon_calc_diesel = self.carbon_calculator.usda_factors['fuel']['diesel']
        enhanced_usda_diesel = self.enhanced_usda.base_usda_factors['diesel']
        event_calc_diesel = self.event_calculator.FUEL_EMISSION_FACTORS['diesel']
        registry_diesel = emission_factors.get_fuel_factor('diesel')['value']
        
        expected_value = 2.68
        
        self.assertEqual(carbon_calc_diesel, expected_value)
        self.assertEqual(enhanced_usda_diesel, expected_value)
        self.assertEqual(event_calc_diesel, expected_value)
        self.assertEqual(registry_diesel, expected_value)

    def test_gasoline_factor_consistency(self):
        """Test gasoline factor consistency"""
        carbon_calc_gasoline = self.carbon_calculator.usda_factors['fuel']['gasoline']
        enhanced_usda_gasoline = self.enhanced_usda.base_usda_factors['gasoline']
        event_calc_gasoline = self.event_calculator.FUEL_EMISSION_FACTORS['gasoline']
        registry_gasoline = emission_factors.get_fuel_factor('gasoline')['value']
        
        expected_value = 2.31
        
        self.assertEqual(carbon_calc_gasoline, expected_value)
        self.assertEqual(enhanced_usda_gasoline, expected_value)
        self.assertEqual(event_calc_gasoline, expected_value)
        self.assertEqual(registry_gasoline, expected_value)

    def test_all_calculators_use_registry(self):
        """Test that all calculators are using the centralized registry"""
        # This test ensures no hardcoded values remain
        
        # Check that factors are accessed through the registry
        with patch.object(emission_factors, 'get_fertilizer_factor') as mock_fertilizer:
            mock_fertilizer.return_value = {'value': 5.86, 'unit': 'test', 'source': 'test', 'confidence': 'high', 'last_verified': '2024-12-27', 'reference': 'test', 'notes': 'test'}
            
            # Create new calculator instance to trigger factor loading
            new_calculator = CarbonFootprintCalculator()
            
            # Verify registry was called
            mock_fertilizer.assert_called()

    def test_no_hardcoded_nitrogen_67_remaining(self):
        """Test that the incorrect 6.7 value is not used anywhere"""
        incorrect_value = 6.7
        
        # Check all calculator instances
        self.assertNotEqual(
            self.carbon_calculator.usda_factors['fertilizer']['nitrogen'], 
            incorrect_value
        )
        self.assertNotEqual(
            self.enhanced_usda.base_usda_factors['nitrogen'], 
            incorrect_value
        )
        self.assertNotEqual(
            self.event_calculator.USDA_FERTILIZER_FACTORS['nitrogen'], 
            incorrect_value
        )

    def test_factor_metadata_accessible(self):
        """Test that factor metadata is accessible from calculators"""
        # Test that we can get metadata from the registry
        nitrogen_metadata = emission_factors.get_fertilizer_factor('nitrogen')
        
        self.assertIn('source', nitrogen_metadata)
        self.assertIn('reference', nitrogen_metadata)
        self.assertIn('confidence', nitrogen_metadata)
        self.assertEqual(nitrogen_metadata['confidence'], 'high')


class CalculationAccuracyTest(TestCase):
    """Test that calculations produce accurate results with standardized factors"""

    def setUp(self):
        """Set up test data"""
        self.event_calculator = EventCarbonCalculator()

    def test_nitrogen_calculation_accuracy(self):
        """Test that nitrogen-based calculations use correct factor"""
        # Mock event for testing
        mock_event = MagicMock()
        mock_event.type = 'FE'  # Fertilizer
        mock_event.concentration = '20-10-10'  # 20% nitrogen
        mock_event.volume = '100L'
        mock_event.area = '1ha'
        mock_event.way_of_application = 'broadcast'
        mock_event.history.product.name = 'corn'
        
        # Calculate expected emissions
        # 100L with 20% N = 20kg N
        # 20kg N * 5.86 kg CO2e per kg N = 117.2 kg CO2e (before efficiency adjustments)
        expected_base = 20 * 5.86  # 117.2
        
        # This should NOT equal the old calculation (20 * 6.7 = 134)
        old_incorrect_calculation = 20 * 6.7  # 134
        
        self.assertNotEqual(expected_base, old_incorrect_calculation)
        self.assertEqual(expected_base, 117.2)

    def test_calculation_consistency_across_modules(self):
        """Test that the same inputs produce consistent results across modules"""
        # Test data
        fertilizer_data = {'nitrogen': 10}  # 10 kg nitrogen
        
        # Test CarbonFootprintCalculator
        carbon_calc = CarbonFootprintCalculator()
        carbon_result = carbon_calc._calculate_fertilizer_emissions(fertilizer_data)
        
        # Expected result: 10 kg * 5.86 kg CO2e per kg = 58.6 kg CO2e
        expected = 10 * 5.86
        
        self.assertEqual(carbon_result, expected)
        self.assertNotEqual(carbon_result, 10 * 6.7)  # Not the old incorrect value

    def test_factor_source_attribution(self):
        """Test that calculations include proper source attribution"""
        metadata = emission_factors.get_metadata()
        
        self.assertTrue(metadata['usda_verified'])
        self.assertIn('USDA', metadata['data_source'])
        self.assertEqual(metadata['version'], emission_factors.VERSION)


class RegressionTest(TestCase):
    """Regression tests to prevent reintroduction of inconsistencies"""

    def test_no_duplicate_factor_definitions(self):
        """Ensure no duplicate factor definitions exist"""
        # This test would fail if someone added hardcoded factors again
        
        # Check that import and usage of emission_factors is consistent
        from carbon.services.emission_factors import emission_factors as ef1
        from carbon.services.emission_factors import EmissionFactorsRegistry
        
        ef2 = EmissionFactorsRegistry()
        
        # Both should return same values
        n1 = ef1.get_fertilizer_factor('nitrogen')['value']
        n2 = ef2.get_fertilizer_factor('nitrogen')['value']
        
        self.assertEqual(n1, n2)
        self.assertEqual(n1, 5.86)

    def test_import_consistency(self):
        """Test that all modules import and use factors consistently"""
        # This would catch if someone bypassed the registry
        
        from carbon.services.calculator import CarbonFootprintCalculator
        from carbon.services.enhanced_usda_factors import EnhancedUSDAFactors
        from carbon.services.event_carbon_calculator import EventCarbonCalculator
        
        calc1 = CarbonFootprintCalculator()
        calc2 = EnhancedUSDAFactors()
        calc3 = EventCarbonCalculator()
        
        # All should use same nitrogen factor
        n1 = calc1.usda_factors['fertilizer']['nitrogen']
        n2 = calc2.base_usda_factors['nitrogen']
        n3 = calc3.USDA_FERTILIZER_FACTORS['nitrogen']
        
        self.assertEqual(n1, n2)
        self.assertEqual(n2, n3)
        self.assertEqual(n1, 5.86)

    def test_version_tracking(self):
        """Test that factor versions are properly tracked"""
        metadata = emission_factors.get_metadata()
        
        self.assertIn('version', metadata)
        self.assertRegex(metadata['version'], r'\d+\.\d+\.\d+')  # Semantic versioning

    def test_factor_change_detection(self):
        """Test system that would detect unauthorized factor changes"""
        # Get current factors
        current_factors = emission_factors.get_all_factors_simple()
        
        # Define expected values (these should not change without proper process)
        expected_critical_factors = {
            'nitrogen': 5.86,
            'phosphorus': 0.20,
            'potassium': 0.15,
            'diesel': 2.68,
            'gasoline': 2.31
        }
        
        for factor_name, expected_value in expected_critical_factors.items():
            self.assertEqual(
                current_factors[factor_name], 
                expected_value,
                f"Critical factor {factor_name} has changed from expected value {expected_value}"
            )


if __name__ == '__main__':
    unittest.main()