import requests
import logging
from typing import Dict, Any
from django.conf import settings
import json

logger = logging.getLogger(__name__)

class RegistryIntegrationService:
    """Integration with carbon registries - ICR (real API) + VCS/Gold Standard/CAR/ACR (mock services)"""

    def __init__(self):
        # ICR - Real API Integration
        self.icr_sandbox_url = getattr(settings, 'ICR_SANDBOX_URL', 'https://sandbox-api.carbonregistry.com')
        self.icr_production_url = getattr(settings, 'ICR_PRODUCTION_URL', 'https://api.carbonregistry.com')
        self.icr_api_key = getattr(settings, 'ICR_API_KEY', '')
        self.use_icr_sandbox = getattr(settings, 'USE_ICR_SANDBOX', True)  # Default to sandbox
        
        # Legacy URLs (for documentation - these APIs don't exist)
        self.vcs_url = getattr(settings, 'VCS_REGISTRY_URL', 'https://registry.verra.org/api/v1')
        self.vcs_api_key = getattr(settings, 'VCS_API_KEY', '')
        self.gold_standard_url = getattr(settings, 'GOLD_STANDARD_API_URL', 'https://api.goldstandard.org/v1')
        self.gold_standard_api_key = getattr(settings, 'GOLD_STANDARD_API_KEY', '')

    @property
    def icr_base_url(self):
        """Get ICR base URL based on environment"""
        return self.icr_sandbox_url if self.use_icr_sandbox else self.icr_production_url

    def verify_with_icr(self, project_data: Dict) -> Dict[str, Any]:
        """Verify project against ICR registry - REAL API INTEGRATION"""
        try:
            headers = {
                'Authorization': f'Bearer {self.icr_api_key}',
                'Content-Type': 'application/json'
            }
            
            # ICR API endpoint for project verification
            response = requests.get(
                f"{self.icr_base_url}/v1/projects/{project_data['project_id']}",
                headers=headers,
                timeout=30
            )

            logger.info(f"ICR API Request: {self.icr_base_url}/v1/projects/{project_data['project_id']}")
            logger.info(f"ICR Response Status: {response.status_code}")

            if response.status_code == 200:
                project_info = response.json()
                return {
                    'verified': True,
                    'registry': 'ICR',
                    'methodology': project_info.get('methodology', 'ICR Standard'),
                    'status': project_info.get('status', 'active'),
                    'credits_available': project_info.get('credits_available', 0),
                    'verification_body': project_info.get('verification_body'),
                    'last_audit_date': project_info.get('last_audit_date'),
                    'project_url': f"{self.icr_base_url.replace('/api', '')}/projects/{project_data['project_id']}",
                    'api_response': project_info
                }
            elif response.status_code == 404:
                return {
                    'verified': False, 
                    'registry': 'ICR',
                    'error': 'Project not found in ICR registry',
                    'project_id': project_data['project_id']
                }
            else:
                return {
                    'verified': False, 
                    'registry': 'ICR',
                    'error': f'ICR API error: {response.status_code}',
                    'response_text': response.text[:200]
                }

        except requests.exceptions.RequestException as e:
            logger.error(f"ICR API connection error: {e}")
            return {
                'verified': False, 
                'registry': 'ICR',
                'error': f'Connection error: {str(e)}'
            }
        except Exception as e:
            logger.error(f"ICR verification error: {e}")
            return {
                'verified': False, 
                'registry': 'ICR',
                'error': str(e)
            }

    def verify_with_vcs(self, project_data: Dict) -> Dict[str, Any]:
        """Mock VCS verification - API doesn't exist publicly"""
        project_id = project_data['project_id']
        
        # Real VCS project IDs for realistic simulation
        real_vcs_projects = {
            '674': {
                'name': 'Katingan Peatland Restoration and Conservation Project',
                'country': 'Indonesia',
                'methodology': 'VM0007',
                'status': 'active',
                'credits_available': 250000,
                'verification_body': 'SCS Global Services'
            },
            '1396': {
                'name': 'Kasigau Corridor REDD+ Project',
                'country': 'Kenya', 
                'methodology': 'VM0009',
                'status': 'active',
                'credits_available': 180000,
                'verification_body': 'Rainforest Alliance'
            },
            '2089': {
                'name': 'Brazil Nut Concessions in Madre de Dios',
                'country': 'Peru',
                'methodology': 'VM0007',
                'status': 'active',
                'credits_available': 95000,
                'verification_body': 'Control Union'
            }
        }

        if project_id in real_vcs_projects:
            project = real_vcs_projects[project_id]
            return {
                'verified': True,
                'registry': 'VCS',
                'methodology': project['methodology'],
                'status': project['status'],
                'credits_available': project['credits_available'],
                'verification_body': project['verification_body'],
                'last_audit_date': '2024-01-15',
                'project_url': f"https://registry.verra.org/app/projectDetail/VCS/{project_id}",
                'note': 'Simulated response - VCS API not publicly available'
            }
        else:
            return {
                'verified': False, 
                'registry': 'VCS',
                'error': 'Project not found in VCS registry',
                'note': 'Simulated response - VCS API not publicly available'
            }

    def verify_with_gold_standard(self, project_data: Dict) -> Dict[str, Any]:
        """Mock Gold Standard verification - API doesn't exist publicly"""
        project_id = project_data['project_id']
        
        # Real Gold Standard project IDs for realistic simulation
        real_gs_projects = {
            '1679': {
                'name': 'Improved Cookstoves in Kenya',
                'country': 'Kenya',
                'methodology': 'AMS-II.G',
                'status': 'active',
                'credits_available': 45000,
                'verification_body': 'SGS'
            },
            '2456': {
                'name': 'Solar Home Systems in Bangladesh',
                'country': 'Bangladesh',
                'methodology': 'AMS-I.A',
                'status': 'active', 
                'credits_available': 32000,
                'verification_body': 'TÜV SÜD'
            }
        }

        if project_id in real_gs_projects:
            project = real_gs_projects[project_id]
            return {
                'verified': True,
                'registry': 'Gold Standard',
                'methodology': project['methodology'],
                'status': project['status'],
                'credits_available': project['credits_available'],
                'verification_body': project['verification_body'],
                'co_benefits': ['Poverty Alleviation', 'Health', 'Gender Equality'],
                'last_audit_date': '2024-02-20',
                'project_url': f"https://registry.goldstandard.org/projects/details/{project_id}",
                'note': 'Simulated response - Gold Standard API not publicly available'
            }
        else:
            return {
                'verified': False, 
                'registry': 'Gold Standard',
                'error': 'Project not found in Gold Standard registry',
                'note': 'Simulated response - Gold Standard API not publicly available'
            }

    def verify_with_car(self, project_data: Dict) -> Dict[str, Any]:
        """Mock CAR verification - API doesn't exist publicly"""
        project_id = project_data['project_id']
        
        # Real CAR project examples
        real_car_projects = {
            'CAR1001': {
                'name': 'California Forest Carbon Project',
                'country': 'USA',
                'methodology': 'US Forest Protocol v4.0',
                'status': 'active',
                'credits_available': 75000,
                'verification_body': 'SCS Global Services'
            }
        }

        if project_id in real_car_projects:
            project = real_car_projects[project_id]
            return {
                'verified': True,
                'registry': 'CAR',
                'methodology': project['methodology'],
                'status': project['status'],
                'credits_available': project['credits_available'],
                'verification_body': project['verification_body'],
                'last_audit_date': '2024-03-10',
                'project_url': f"https://thereserve2.apx.com/myModule/rpt/myrpt.asp?r=111&project_id={project_id}",
                'note': 'Simulated response - CAR API not publicly available'
            }
        else:
            return {
                'verified': False, 
                'registry': 'CAR',
                'error': 'Project not found in CAR registry',
                'note': 'Simulated response - CAR API not publicly available'
            }

    def verify_with_acr(self, project_data: Dict) -> Dict[str, Any]:
        """Mock ACR verification - API doesn't exist publicly"""
        project_id = project_data['project_id']
        
        # Real ACR project examples
        real_acr_projects = {
            'ACR001': {
                'name': 'US Landfill Methane Project',
                'country': 'USA',
                'methodology': 'ACR Landfill Protocol v1.0',
                'status': 'active',
                'credits_available': 120000,
                'verification_body': 'Rainforest Alliance'
            }
        }

        if project_id in real_acr_projects:
            project = real_acr_projects[project_id]
            return {
                'verified': True,
                'registry': 'ACR',
                'methodology': project['methodology'],
                'status': project['status'],
                'credits_available': project['credits_available'],
                'verification_body': project['verification_body'],
                'last_audit_date': '2024-01-25',
                'project_url': f"https://acr2.apx.com/myModule/rpt/myrpt.asp?r=111&project_id={project_id}",
                'note': 'Simulated response - ACR API not publicly available'
            }
        else:
            return {
                'verified': False, 
                'registry': 'ACR',
                'error': 'Project not found in ACR registry',
                'note': 'Simulated response - ACR API not publicly available'
            }

    def get_methodology_template(self, methodology_type: str) -> Dict[str, Any]:
        """Get standardized calculation template"""
        templates = {
            'no_till': {
                'methodology': 'VCS VM0042',
                'emission_factor': 0.47,  # tCO2e/ha/year
                'uncertainty': 0.15,
                'required_data': ['field_area', 'soil_type', 'previous_practice'],
                'additionality_requirements': [
                    'practice_uncommon_in_region',
                    'financial_barrier_evidence',
                    'implementation_timeline'
                ]
            },
            'cover_crop': {
                'methodology': 'VCS VM0042',
                'emission_factor': 0.29,  # tCO2e/ha/year
                'uncertainty': 0.20,
                'required_data': ['crop_type', 'planting_date', 'termination_method'],
                'monitoring_requirements': ['annual_verification', 'biomass_sampling']
            },
            'reforestation': {
                'methodology': 'Gold Standard AFOLU',
                'emission_factor': 12.5,  # tCO2e/ha/year
                'uncertainty': 0.25,
                'required_data': ['tree_species', 'planting_density', 'survival_rate'],
                'monitoring_requirements': ['annual_measurement', 'biomass_assessment']
            },
            'composting': {
                'methodology': 'VCS VM0042',
                'emission_factor': 0.15,  # tCO2e/tonne
                'uncertainty': 0.30,
                'required_data': ['organic_waste_amount', 'composting_method'],
                'monitoring_requirements': ['weight_measurement', 'quality_testing']
            },
            'renewable_energy': {
                'methodology': 'Gold Standard Energy',
                'emission_factor': 0.85,  # tCO2e/MWh
                'uncertainty': 0.10,
                'required_data': ['energy_generation', 'grid_emission_factor'],
                'monitoring_requirements': ['energy_meter_readings', 'grid_connection_verification']
            },
            'methane_capture': {
                'methodology': 'VCS VM0006',
                'emission_factor': 25.0,  # tCO2e/tCH4
                'uncertainty': 0.20,
                'required_data': ['livestock_count', 'manure_management_system'],
                'monitoring_requirements': ['gas_flow_measurement', 'methane_concentration']
            }
        }
        return templates.get(methodology_type, {})

    def validate_project_credentials(self, project_id: str, registry: str) -> Dict[str, Any]:
        """Validate project credentials against specified registry"""
        registry_lower = registry.lower()
        
        if registry_lower == 'icr':
            return self.verify_with_icr({'project_id': project_id})
        elif registry_lower == 'vcs':
            return self.verify_with_vcs({'project_id': project_id})
        elif registry_lower == 'gold_standard':
            return self.verify_with_gold_standard({'project_id': project_id})
        elif registry_lower == 'car':
            return self.verify_with_car({'project_id': project_id})
        elif registry_lower == 'acr':
            return self.verify_with_acr({'project_id': project_id})
        else:
            return {'verified': False, 'error': f'Unsupported registry: {registry}'}

    def get_registry_project_url(self, project_id: str, registry: str) -> str:
        """Get direct URL to project in registry"""
        registry_urls = {
            'icr': f"{self.icr_base_url.replace('/api', '')}/projects/{project_id}",
            'vcs': f"https://registry.verra.org/app/projectDetail/VCS/{project_id}",
            'gold_standard': f"https://registry.goldstandard.org/projects/details/{project_id}",
            'car': f"https://thereserve2.apx.com/myModule/rpt/myrpt.asp?r=111&project_id={project_id}",
            'acr': f"https://acr2.apx.com/myModule/rpt/myrpt.asp?r=111&project_id={project_id}"
        }
        return registry_urls.get(registry.lower(), '#')

    def get_supported_registries(self) -> Dict[str, Dict[str, Any]]:
        """Get list of supported registries with their capabilities"""
        return {
            'ICR': {
                'name': 'International Carbon Registry',
                'has_api': True,
                'api_status': 'working',
                'environment': 'sandbox' if self.use_icr_sandbox else 'production',
                'supported_methodologies': ['ICR Standard', 'ISO 14064', 'Custom'],
                'description': 'ICROA endorsed registry with full API support'
            },
            'VCS': {
                'name': 'Verified Carbon Standard (Verra)',
                'has_api': False,
                'api_status': 'simulated',
                'supported_methodologies': ['VM0007', 'VM0009', 'VM0042', 'VM0047'],
                'description': 'World\'s largest voluntary carbon market registry (simulated)'
            },
            'Gold Standard': {
                'name': 'Gold Standard for the Global Goals',
                'has_api': False,
                'api_status': 'simulated',
                'supported_methodologies': ['AMS-II.G', 'AMS-I.A', 'AFOLU'],
                'description': 'Premium quality carbon credits with SDG co-benefits (simulated)'
            },
            'CAR': {
                'name': 'Climate Action Reserve',
                'has_api': False,
                'api_status': 'simulated',
                'supported_methodologies': ['US Forest Protocol', 'Landfill Protocol'],
                'description': 'North American carbon offset registry (simulated)'
            },
            'ACR': {
                'name': 'American Carbon Registry',
                'has_api': False,
                'api_status': 'simulated',
                'supported_methodologies': ['ACR Standard', 'Landfill Protocol'],
                'description': 'World\'s first private carbon offset registry (simulated)'
            }
        } 