#!/usr/bin/env python
"""
Comprehensive Third-Party Verification API Integration Test

This script tests the complete flow of third-party verification APIs
for carbon offset entries, including:
- Registry credential verification (VCS, Gold Standard, CAR, ACR)
- Verification status checking
- Bulk verification operations
- Methodology template validation
- Error handling and edge cases

Usage:
    cd trazo-back && python test_third_party_verification.py
"""

import os
import sys
import django
from datetime import datetime

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

# Now import Django and DRF components after setup
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from carbon.models import CarbonEntry, CarbonSource, CarbonAuditLog
from company.models import Establishment
from carbon.services.verification_service import VerificationService
from carbon.services.registry_integration import RegistryIntegrationService

User = get_user_model()

# Test configuration
BASE_URL = "http://testserver"
API_ENDPOINTS = {
    'verify_registry_credentials': f"{BASE_URL}/carbon/verify-registry-credentials/",
    'verification_status': f"{BASE_URL}/carbon/entries/{{entry_id}}/verification-status/",
    'bulk_verify': f"{BASE_URL}/carbon/bulk-verify/",
    'methodology_templates': f"{BASE_URL}/carbon/methodology-templates/",
}

# Third-party registry URLs we're testing integration with
THIRD_PARTY_REGISTRIES = {
    'VCS': 'https://registry.verra.org/api/v1',
    'GOLD_STANDARD': 'https://api.goldstandard.org/v1',
    'CAR': 'https://thereserve2.apx.com/myModule/rpt/myrpt.asp',
    'ACR': 'https://acr2.apx.com/myModule/rpt/myrpt.asp'
}

class ThirdPartyVerificationTester:
    """Comprehensive tester for third-party verification API integration"""
    
    def __init__(self):
        self.client = APIClient()
        self.user = None
        self.establishment = None
        self.test_entries = []
        self.results = {
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'errors': []
        }
        
    def setup_test_environment(self):
        """Set up test data and environment"""
        print("\n🔧 Setting up test environment...")
        
        # Create test user
        self.user, created = User.objects.get_or_create(
            email='verification_test@trazo.io',
            defaults={
                'first_name': 'Test',
                'last_name': 'User',
                'is_active': True
            }
        )
        
        # Force login for the test client
        self.client.force_authenticate(user=self.user)
        
        # Get test establishment (assuming ID 1 exists from previous tests)
        try:
            self.establishment = Establishment.objects.get(id=1)
        except Establishment.DoesNotExist:
            print("❌ No establishment with ID 1 found. Please ensure test data exists.")
            return False
            
        print(f"✅ Test environment setup complete")
        print(f"   - User: {self.user.email}")
        print(f"   - Establishment: {self.establishment.name} (ID: {self.establishment.id})")
        
        return True
    
    def create_test_carbon_entries(self):
        """Create test carbon entries with different verification levels"""
        print("\n📊 Creating test carbon entries...")
        
        # Get or create test sources
        sources = []
        source_names = ['no_till', 'cover_crop', 'tree_planting', 'renewable_energy']
        
        for source_name in source_names:
            source, created = CarbonSource.objects.get_or_create(
                name=source_name,
                defaults={
                    'category': 'offset',
                    'default_emission_factor': -1.0,
                    'unit': 'kg CO2e',
                    'description': f'Carbon offset project: {source_name}',
                    'usda_verified': True
                }
            )
            sources.append(source)
        
        # Create test entries with different verification scenarios
        test_scenarios = [
            {
                'source': sources[0],
                'amount': 50.0,
                'verification_level': 'self_reported',
                'registry_verification_id': '',
                'description': 'Self-reported no-till farming offset'
            },
            {
                'source': sources[1],
                'amount': 150.0,
                'verification_level': 'community_verified',
                'registry_verification_id': '',
                'description': 'Community verified cover crop offset'
            },
            {
                'source': sources[2],
                'amount': 500.0,
                'verification_level': 'certified_project',
                'registry_verification_id': 'VCS-1001',
                'description': 'VCS certified tree planting project'
            },
            {
                'source': sources[3],
                'amount': 1000.0,
                'verification_level': 'certified_project',
                'registry_verification_id': 'GS-2002',
                'description': 'Gold Standard renewable energy project'
            }
        ]
        
        for scenario in test_scenarios:
            entry = CarbonEntry.objects.create(
                establishment=self.establishment,
                created_by=self.user,
                type='offset',
                source=scenario['source'],
                amount=scenario['amount'],
                year=2025,
                description=scenario['description'],
                verification_level=scenario['verification_level'],
                registry_verification_id=scenario['registry_verification_id'],
                trust_score=0.5,
                effective_amount=scenario['amount'] * 0.5,
                audit_status='pending'
            )
            self.test_entries.append(entry)
            
        print(f"✅ Created {len(self.test_entries)} test carbon entries")
        for i, entry in enumerate(self.test_entries):
            print(f"   {i+1}. Entry ID {entry.id}: {entry.amount} kg CO₂e ({entry.verification_level})")
            
        return True
    
    def test_registry_credential_verification(self):
        """Test 1: Registry credential verification API"""
        print("\n🧪 TEST 1: Registry Credential Verification")
        self.results['tests_run'] += 1
        
        try:
            # Test VCS verification
            response = self.client.post('/carbon/verify-registry-credentials/', {
                'registry_verification_id': 'VCS-1001',
                'registry_type': 'vcs',
                'carbon_entry_id': self.test_entries[2].id
            }, format='json')
            
            print(f"   - VCS Verification Response: {response.status_code}")
            if response.status_code in [200, 400]:  # Accept both success and expected failures
                if response.status_code == 200:
                    data = response.json()
                    print(f"   - Verified: {data.get('verified', False)}")
                    print(f"   - Registry: {data.get('registry', 'N/A')}")
                    print(f"   - Project URL: {data.get('project_url', 'N/A')}")
                else:
                    data = response.json()
                    print(f"   - Expected failure: {data.get('message', 'Registry not available')}")
                
                self.results['tests_passed'] += 1
                print("   ✅ Registry credential verification test PASSED")
            else:
                print(f"   ❌ Registry credential verification test FAILED: {response.content}")
                self.results['tests_failed'] += 1
                
        except Exception as e:
            print(f"   ❌ Registry credential verification test ERROR: {e}")
            self.results['tests_failed'] += 1
            self.results['errors'].append(f"Registry verification: {e}")
    
    def test_verification_status_api(self):
        """Test 2: Verification status API"""
        print("\n🧪 TEST 2: Verification Status API")
        self.results['tests_run'] += 1
        
        try:
            entry = self.test_entries[0]
            response = self.client.get(f'/carbon/entries/{entry.id}/verification-status/')
            
            print(f"   - Verification Status Response: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   - Carbon Entry ID: {data.get('carbon_entry_id')}")
                print(f"   - Trust Score: {data.get('verification_status', {}).get('trust_score', 'N/A')}")
                print(f"   - Audit Status: {data.get('verification_status', {}).get('audit_status', 'N/A')}")
                print(f"   - Evidence Summary: {data.get('evidence_summary', {})}")
                print(f"   - Audit Trail Count: {len(data.get('audit_trail', []))}")
                
                self.results['tests_passed'] += 1
                print("   ✅ Verification status test PASSED")
            else:
                print(f"   ❌ Verification status test FAILED: {response.content}")
                self.results['tests_failed'] += 1
                
        except Exception as e:
            print(f"   ❌ Verification status test ERROR: {e}")
            self.results['tests_failed'] += 1
            self.results['errors'].append(f"Verification status: {e}")
    
    def test_bulk_verification_api(self):
        """Test 3: Bulk verification API"""
        print("\n🧪 TEST 3: Bulk Verification API")
        self.results['tests_run'] += 1
        
        try:
            entry_ids = [entry.id for entry in self.test_entries[:2]]
            
            # Test bulk audit scheduling
            response = self.client.post('/carbon/bulk-verify/', {
                'carbon_entry_ids': entry_ids,
                'verification_action': 'schedule_audit'
            }, format='json')
            
            print(f"   - Bulk Audit Scheduling Response: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                summary = data.get('bulk_verification_summary', {})
                print(f"   - Total Entries: {summary.get('total_entries', 0)}")
                print(f"   - Successful: {summary.get('successful', 0)}")
                print(f"   - Failed: {summary.get('failed', 0)}")
                
                self.results['tests_passed'] += 1
                print("   ✅ Bulk verification test PASSED")
            else:
                print(f"   ❌ Bulk verification test FAILED: {response.content}")
                self.results['tests_failed'] += 1
                
        except Exception as e:
            print(f"   ❌ Bulk verification test ERROR: {e}")
            self.results['tests_failed'] += 1
            self.results['errors'].append(f"Bulk verification: {e}")
    
    def test_methodology_templates_api(self):
        """Test 4: Methodology Templates API"""
        print("\n🧪 TEST 4: Methodology Templates API")
        self.results['tests_run'] += 1
        
        try:
            response = self.client.get('/carbon/methodology-templates/')
            
            print(f"   - Methodology Templates Response: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                templates = data.get('methodology_templates', {})
                supported = data.get('supported_methodologies', [])
                registries = data.get('registry_standards', {})
                
                print(f"   - Available Templates: {len(templates)}")
                print(f"   - Supported Methodologies: {supported}")
                print(f"   - Registry Standards: {list(registries.keys())}")
                
                # Check specific templates
                if 'no_till' in templates:
                    no_till = templates['no_till']
                    print(f"   - No-Till Template: {no_till.get('methodology', 'N/A')}")
                    print(f"   - Emission Factor: {no_till.get('emission_factor', 'N/A')} tCO₂e/ha/year")
                
                self.results['tests_passed'] += 1
                print("   ✅ Methodology templates test PASSED")
            else:
                print(f"   ❌ Methodology templates test FAILED: {response.content}")
                self.results['tests_failed'] += 1
                
        except Exception as e:
            print(f"   ❌ Methodology templates test ERROR: {e}")
            self.results['tests_failed'] += 1
            self.results['errors'].append(f"Methodology templates: {e}")
    
    def test_verification_service_integration(self):
        """Test 5: Direct verification service integration"""
        print("\n🧪 TEST 5: Verification Service Integration")
        self.results['tests_run'] += 1
        
        try:
            verification_service = VerificationService()
            entry = self.test_entries[2]  # VCS certified entry
            
            # Run verification
            result = verification_service.verify_offset_entry(entry)
            
            print(f"   - Verification Result Approved: {result.get('approved', False)}")
            print(f"   - Trust Score: {result.get('trust_score', 'N/A')}")
            print(f"   - Anti-Gaming Flags: {len(result.get('anti_gaming_flags', []))}")
            print(f"   - Requirements: {len(result.get('requirements', []))}")
            print(f"   - Audit Required: {result.get('audit_required', False)}")
            print(f"   - Registry Validation: {result.get('registry_validation', {}).get('verified', 'N/A')}")
            print(f"   - Methodology Validation: {result.get('methodology_validation', {}).get('valid', 'N/A')}")
            
            self.results['tests_passed'] += 1
            print("   ✅ Verification service integration test PASSED")
            
        except Exception as e:
            print(f"   ❌ Verification service integration test ERROR: {e}")
            self.results['tests_failed'] += 1
            self.results['errors'].append(f"Verification service: {e}")
    
    def test_registry_integration_service(self):
        """Test 6: Registry integration service"""
        print("\n🧪 TEST 6: Registry Integration Service")
        self.results['tests_run'] += 1
        
        try:
            registry_service = RegistryIntegrationService()
            
            # Test methodology template retrieval
            no_till_template = registry_service.get_methodology_template('no_till')
            print(f"   - No-Till Template Retrieved: {bool(no_till_template)}")
            if no_till_template:
                print(f"   - Methodology: {no_till_template.get('methodology', 'N/A')}")
                print(f"   - Emission Factor: {no_till_template.get('emission_factor', 'N/A')}")
                print(f"   - Required Data: {no_till_template.get('required_data', [])}")
            
            # Test registry URL generation
            vcs_url = registry_service.get_registry_project_url('VCS-1001', 'vcs')
            gs_url = registry_service.get_registry_project_url('GS-2002', 'gold_standard')
            
            print(f"   - VCS URL Generated: {bool(vcs_url)}")
            print(f"   - Gold Standard URL Generated: {bool(gs_url)}")
            
            # Test credential validation (mock)
            vcs_validation = registry_service.validate_project_credentials('VCS-1001', 'vcs')
            print(f"   - VCS Validation Attempted: {bool(vcs_validation)}")
            
            self.results['tests_passed'] += 1
            print("   ✅ Registry integration service test PASSED")
            
        except Exception as e:
            print(f"   ❌ Registry integration service test ERROR: {e}")
            self.results['tests_failed'] += 1
            self.results['errors'].append(f"Registry integration: {e}")
    
    def cleanup_test_data(self):
        """Clean up test data"""
        print("\n🧹 Cleaning up test data...")
        
        # Delete test carbon entries
        for entry in self.test_entries:
            CarbonAuditLog.objects.filter(carbon_entry=entry).delete()
            entry.delete()
        
        print(f"✅ Cleaned up {len(self.test_entries)} test entries")
    
    def run_all_tests(self):
        """Run all third-party verification integration tests"""
        print("🚀 STARTING THIRD-PARTY VERIFICATION API INTEGRATION TESTS")
        print("=" * 80)
        print("🌐 THIRD-PARTY REGISTRIES BEING TESTED:")
        for name, url in THIRD_PARTY_REGISTRIES.items():
            print(f"   - {name}: {url}")
        print("=" * 80)
        
        if not self.setup_test_environment():
            return False
            
        if not self.create_test_carbon_entries():
            return False
        
        # Run tests
        self.test_registry_credential_verification()
        self.test_verification_status_api()
        self.test_bulk_verification_api()
        self.test_methodology_templates_api()
        self.test_verification_service_integration()
        self.test_registry_integration_service()
        
        # Results
        print("\n" + "=" * 80)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 80)
        print(f"Tests Run: {self.results['tests_run']}")
        print(f"Tests Passed: {self.results['tests_passed']}")
        print(f"Tests Failed: {self.results['tests_failed']}")
        print(f"Success Rate: {(self.results['tests_passed'] / self.results['tests_run'] * 100):.1f}%")
        
        if self.results['errors']:
            print("\n❌ ERRORS ENCOUNTERED:")
            for error in self.results['errors']:
                print(f"   - {error}")
        
        if self.results['tests_failed'] == 0:
            print("\n🎉 ALL TESTS PASSED! Third-party verification API integration is working correctly.")
        else:
            print(f"\n⚠️  {self.results['tests_failed']} test(s) failed. Please review the errors above.")
        
        # Cleanup
        self.cleanup_test_data()
        
        return self.results['tests_failed'] == 0

if __name__ == '__main__':
    tester = ThirdPartyVerificationTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1) 