from typing import Dict, Any, Optional
import random
import logging
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum, Count, Q
from datetime import timedelta, datetime
from decimal import Decimal
from ..models import CarbonEntry
from .registry_integration import RegistryIntegrationService

logger = logging.getLogger(__name__)

class VerificationService:
    """
    Industry-standard carbon offset verification service with comprehensive anti-gaming mechanisms.
    
    Based on leading platforms like Indigo Ag, Agoro Carbon Alliance, and Verra standards.
    Implements conservative crediting, buffer pools, and additionality testing.
    """

    # Industry-standard limits based on research
    MONTHLY_SELF_REPORTED_LIMIT = 500  # kg CO2e per month
    ANNUAL_SELF_REPORTED_LIMIT = 5000  # kg CO2e per year
    SINGLE_ENTRY_VERIFICATION_THRESHOLD = 100  # kg CO2e
    RAPID_SUBMISSION_THRESHOLD = 5  # entries per day
    UNREALISTIC_OFFSET_RATIO = 2.0  # offset-to-emission ratio threshold
    
    # Buffer pool percentages (following Indigo Ag and Agoro practices)
    BUFFER_POOLS = {
        'self_reported': 0.20,      # 20% buffer for self-reported
        'community_verified': 0.15,  # 15% buffer for community verified
        'certified_project': 0.10,   # 10% buffer for certified projects
    }
    
    # Trust scores (conservative approach)
    TRUST_SCORES = {
        'self_reported': 0.5,        # 50% trust for self-reported
        'community_verified': 0.75,  # 75% trust for community verified
        'certified_project': 1.0,    # 100% trust for certified projects
    }

    def __init__(self):
        self.registry_service = RegistryIntegrationService()

    def verify_offset_entry(self, carbon_entry) -> Dict[str, Any]:
        """
        Main verification method implementing industry-standard anti-gaming mechanisms.
        
        Returns verification result with anti-gaming flags, requirements, and recommendations.
        """
        logger.info(f"🔍 Starting verification for carbon entry {carbon_entry.id}")
        logger.info(f"   Entry details: {carbon_entry.amount} kg CO₂e, level: {carbon_entry.verification_level}")
        
        result = {
            'approved': False,
            'anti_gaming_flags': [],
            'requirements': [],
            'audit_required': False,
            'trust_score': self.TRUST_SCORES.get(carbon_entry.verification_level, 0.5),
            'buffer_pool_deduction': self.BUFFER_POOLS.get(carbon_entry.verification_level, 0.20),
            'recommendations': [],
            'additionality_assessment': {},
            'permanence_risk': 'medium',
            'verification_tier': self._determine_verification_tier(carbon_entry),
            'third_party_verification': {},
            'registry_validation': {}
        }

        # 1. THIRD-PARTY REGISTRY VERIFICATION (for certified projects)
        if carbon_entry.verification_level == 'certified_project' and carbon_entry.registry_verification_id:
            logger.info(f"🏛️ Attempting third-party registry verification for entry {carbon_entry.id}")
            logger.info(f"   Registry ID: {carbon_entry.registry_verification_id}")
            
            registry_result = self._verify_with_third_party_registry(carbon_entry)
            result['registry_validation'] = registry_result
            
            logger.info(f"📋 Registry verification result: {registry_result}")
            
            if not registry_result['verified']:
                logger.warning(f"❌ Registry verification FAILED for entry {carbon_entry.id}")
                logger.warning(f"   Reason: {registry_result.get('error', 'Unknown error')}")
                result['anti_gaming_flags'].append('registry_verification_failed')
                result['requirements'].append('Registry verification ID not found or invalid')
                result['approved'] = False
                logger.info(f"🚫 Entry {carbon_entry.id} REJECTED due to registry verification failure")
                return result
            else:
                logger.info(f"✅ Registry verification PASSED for entry {carbon_entry.id}")
                logger.info(f"   Registry: {registry_result.get('registry', 'Unknown')}")
                logger.info(f"   Project URL: {registry_result.get('project_url', 'N/A')}")
            
            # Update carbon entry with registry data
            carbon_entry.third_party_verification_url = registry_result.get('project_url', '')
            carbon_entry.save()
        elif carbon_entry.verification_level == 'certified_project':
            logger.warning(f"⚠️ Entry {carbon_entry.id} marked as certified_project but missing registry_verification_id")
        else:
            logger.info(f"ℹ️ Entry {carbon_entry.id} verification level '{carbon_entry.verification_level}' - skipping third-party verification")

        # 2. ADDITIONALITY TESTING (following Oxford/Berkeley research)
        logger.info(f"🧪 Running additionality assessment for entry {carbon_entry.id}")
        additionality_result = self._assess_additionality(carbon_entry)
        result['additionality_assessment'] = additionality_result
        
        if not additionality_result['passes_test']:
            logger.warning(f"⚠️ Additionality test failed for entry {carbon_entry.id}")
            logger.warning(f"   Violations: {additionality_result['violations']}")
            result['anti_gaming_flags'].extend(additionality_result['violations'])
            result['requirements'].extend(additionality_result['requirements'])

        # 3. CUMULATIVE LIMITS ENFORCEMENT
        logger.info(f"📊 Checking cumulative limits for entry {carbon_entry.id}")
        cumulative_check = self._check_cumulative_limits(carbon_entry)
        if cumulative_check['violations']:
            logger.warning(f"⚠️ Cumulative limits exceeded for entry {carbon_entry.id}")
            logger.warning(f"   Violations: {cumulative_check['violations']}")
            result['anti_gaming_flags'].extend(cumulative_check['violations'])
            result['requirements'].extend(cumulative_check['requirements'])

        # 4. RAPID SUBMISSION PATTERN DETECTION
        logger.info(f"⏱️ Analyzing submission patterns for entry {carbon_entry.id}")
        submission_pattern = self._analyze_submission_patterns(carbon_entry)
        if submission_pattern['suspicious']:
            logger.warning(f"⚠️ Suspicious submission pattern detected for entry {carbon_entry.id}")
            logger.warning(f"   Flags: {submission_pattern['flags']}")
            result['anti_gaming_flags'].extend(submission_pattern['flags'])
            result['requirements'].extend(submission_pattern['requirements'])

        # 5. UNREALISTIC OFFSET RATIO DETECTION
        logger.info(f"⚖️ Checking offset-to-emission ratio for entry {carbon_entry.id}")
        offset_ratio_check = self._check_offset_emission_ratio(carbon_entry)
        if offset_ratio_check['unrealistic']:
            logger.warning(f"⚠️ Unrealistic offset ratio detected for entry {carbon_entry.id}")
            logger.warning(f"   Flags: {offset_ratio_check['flags']}")
            result['anti_gaming_flags'].extend(offset_ratio_check['flags'])
            result['requirements'].extend(offset_ratio_check['requirements'])

        # 6. ACREAGE CAPACITY VALIDATION
        logger.info(f"🌾 Validating acreage capacity for entry {carbon_entry.id}")
        acreage_check = self._validate_acreage_capacity(carbon_entry)
        if acreage_check['exceeds_capacity']:
            logger.warning(f"⚠️ Acreage capacity exceeded for entry {carbon_entry.id}")
            logger.warning(f"   Flags: {acreage_check['flags']}")
            result['anti_gaming_flags'].extend(acreage_check['flags'])
            result['requirements'].extend(acreage_check['requirements'])

        # 7. EVIDENCE REQUIREMENTS VALIDATION
        logger.info(f"📎 Validating evidence requirements for entry {carbon_entry.id}")
        evidence_check = self._validate_evidence_requirements(carbon_entry)
        result['evidence_complete'] = evidence_check['complete']
        if not evidence_check['complete']:
            logger.info(f"📋 Evidence incomplete for entry {carbon_entry.id}: {evidence_check['missing']}")
            result['requirements'].extend(evidence_check['missing'])

        # 8. CONSERVATIVE BASELINE VALIDATION
        logger.info(f"📈 Validating conservative baseline for entry {carbon_entry.id}")
        baseline_check = self._validate_conservative_baseline(carbon_entry)
        if baseline_check['requires_adjustment']:
            logger.warning(f"⚠️ Baseline too optimistic for entry {carbon_entry.id}")
            result['anti_gaming_flags'].append('baseline_too_optimistic')
            result['requirements'].extend(baseline_check['requirements'])

        # 9. METHODOLOGY TEMPLATE VALIDATION
        logger.info(f"📋 Validating methodology template for entry {carbon_entry.id}")
        methodology_check = self._validate_methodology_template(carbon_entry)
        result['methodology_validation'] = methodology_check
        if not methodology_check['valid']:
            logger.info(f"📄 Methodology validation issues for entry {carbon_entry.id}: {methodology_check['requirements']}")
            result['requirements'].extend(methodology_check['requirements'])

        # 10. DETERMINE AUDIT REQUIREMENTS
        logger.info(f"🔍 Determining audit requirements for entry {carbon_entry.id}")
        result['audit_required'] = self._requires_audit(carbon_entry, result)

        # 11. FINAL APPROVAL DECISION
        high_risk_flags = [
            'high_cumulative_threshold_exceeded',
            'rapid_submission_pattern',
            'unrealistic_offset_ratio',
            'exceeds_acreage_capacity',
            'fails_additionality_test',
            'baseline_too_optimistic',
            'registry_verification_failed'
        ]
        
        # Check if any high-risk flags are present
        high_risk_violations = [flag for flag in result['anti_gaming_flags'] if flag in high_risk_flags]
        result['approved'] = len(high_risk_violations) == 0
        
        if high_risk_violations:
            logger.warning(f"❌ Entry {carbon_entry.id} REJECTED due to high-risk violations: {high_risk_violations}")
        else:
            logger.info(f"✅ Entry {carbon_entry.id} APPROVED (no high-risk violations found)")
        
        # 12. GENERATE RECOMMENDATIONS
        result['recommendations'] = self._generate_recommendations(carbon_entry, result)

        # Final logging summary
        logger.info(f"🎯 Verification complete for entry {carbon_entry.id}")
        logger.info(f"   Final status: {'APPROVED' if result['approved'] else 'REJECTED'}")
        logger.info(f"   Trust score: {result['trust_score']}")
        logger.info(f"   Anti-gaming flags: {result['anti_gaming_flags']}")
        logger.info(f"   Audit required: {result['audit_required']}")
        
        return result

    def _verify_with_third_party_registry(self, carbon_entry) -> Dict[str, Any]:
        """
        Verify offset entry against third-party registries (ICR real API + VCS/Gold Standard/etc. simulated)
        """
        try:
            registry_id = carbon_entry.registry_verification_id
            logger.info(f"🏛️ Starting third-party registry verification")
            logger.info(f"   Entry ID: {carbon_entry.id}")
            logger.info(f"   Registry ID: {registry_id}")
            
            # Try ICR first (real API)
            logger.info(f"🔍 Attempting ICR verification for registry ID: {registry_id}")
            icr_result = self.registry_service.verify_with_icr({'project_id': registry_id})
            logger.info(f"📋 ICR verification result: {icr_result}")
            
            if icr_result['verified']:
                logger.info(f"✅ ICR verification SUCCESSFUL for registry ID: {registry_id}")
                project_url = self.registry_service.get_registry_project_url(registry_id, 'icr')
                logger.info(f"   Project URL: {project_url}")
                
                return {
                    'verified': True,
                    'registry': 'ICR',
                    'project_url': project_url,
                    'verification_body': icr_result.get('verification_body', 'ICR Verification Body'),
                    'methodology': icr_result.get('methodology', 'ICR Standard'),
                    'status': icr_result.get('status', 'active'),
                    'credits_available': icr_result.get('credits_available', 0),
                    'last_audit_date': icr_result.get('last_audit_date'),
                    'api_verified': True  # Mark as real API verification
                }
            else:
                logger.warning(f"❌ ICR verification failed for registry ID: {registry_id}")
                logger.warning(f"   ICR error: {icr_result.get('error', 'Unknown error')}")

            # Try VCS (simulated)
            logger.info(f"🔍 Attempting VCS verification for registry ID: {registry_id}")
            vcs_result = self.registry_service.verify_with_vcs({'project_id': registry_id})
            logger.info(f"📋 VCS verification result: {vcs_result}")
            
            if vcs_result['verified']:
                logger.info(f"✅ VCS verification SUCCESSFUL for registry ID: {registry_id}")
                project_url = self.registry_service.get_registry_project_url(registry_id, 'vcs')
                logger.info(f"   Project URL: {project_url}")
                
                return {
                    'verified': True,
                    'registry': 'VCS',
                    'project_url': project_url,
                    'verification_body': vcs_result.get('verification_body', 'Verra'),
                    'methodology': vcs_result.get('methodology', 'VM0042'),
                    'status': vcs_result.get('status', 'active'),
                    'credits_available': vcs_result.get('credits_available', 0),
                    'last_audit_date': vcs_result.get('last_audit_date'),
                    'api_verified': False  # Mark as simulated
                }
            else:
                logger.warning(f"❌ VCS verification failed for registry ID: {registry_id}")
                logger.warning(f"   VCS error: {vcs_result.get('error', 'Unknown error')}")
            
            # Try Gold Standard (simulated)
            logger.info(f"🔍 Attempting Gold Standard verification for registry ID: {registry_id}")
            gs_result = self.registry_service.verify_with_gold_standard({'project_id': registry_id})
            logger.info(f"📋 Gold Standard verification result: {gs_result}")
            
            if gs_result['verified']:
                logger.info(f"✅ Gold Standard verification SUCCESSFUL for registry ID: {registry_id}")
                project_url = self.registry_service.get_registry_project_url(registry_id, 'gold_standard')
                logger.info(f"   Project URL: {project_url}")
                
                return {
                    'verified': True,
                    'registry': 'Gold Standard',
                    'project_url': project_url,
                    'verification_body': gs_result.get('verification_body', 'Gold Standard Foundation'),
                    'methodology': gs_result.get('methodology'),
                    'status': gs_result.get('status', 'active'),
                    'credits_available': gs_result.get('credits_available', 0),
                    'co_benefits': gs_result.get('co_benefits', []),
                    'api_verified': False  # Mark as simulated
                }
            else:
                logger.warning(f"❌ Gold Standard verification failed for registry ID: {registry_id}")
                logger.warning(f"   Gold Standard error: {gs_result.get('error', 'Unknown error')}")
            
            # Try other registries (CAR, ACR) - simulated
            for registry in ['car', 'acr']:
                logger.info(f"🔍 Attempting {registry.upper()} verification for registry ID: {registry_id}")
                registry_result = self.registry_service.validate_project_credentials(registry_id, registry)
                logger.info(f"📋 {registry.upper()} verification result: {registry_result}")
                
                if registry_result['verified']:
                    logger.info(f"✅ {registry.upper()} verification SUCCESSFUL for registry ID: {registry_id}")
                    project_url = self.registry_service.get_registry_project_url(registry_id, registry)
                    logger.info(f"   Project URL: {project_url}")
                    
                    return {
                        'verified': True,
                        'registry': registry.upper(),
                        'project_url': project_url,
                        'verification_body': f'{registry.upper()} Registry',
                        'status': 'active',
                        'api_verified': False  # Mark as simulated
                    }
                else:
                    logger.warning(f"❌ {registry.upper()} verification failed for registry ID: {registry_id}")
                    logger.warning(f"   {registry.upper()} error: {registry_result.get('error', 'Unknown error')}")
            
            # All registries failed
            error_msg = f'Registry verification ID {registry_id} not found in any supported registries (ICR, VCS, Gold Standard, CAR, ACR)'
            logger.error(f"🚫 ALL REGISTRIES FAILED for registry ID: {registry_id}")
            logger.error(f"   Final error: {error_msg}")
            
            return {
                'verified': False,
                'error': error_msg,
                'supported_registries': ['ICR', 'VCS', 'Gold Standard', 'CAR', 'ACR']
            }
            
        except Exception as e:
            error_msg = f'Registry verification failed: {str(e)}'
            logger.error(f"💥 EXCEPTION during third-party registry verification: {e}")
            logger.error(f"   Entry ID: {carbon_entry.id}")
            logger.error(f"   Registry ID: {getattr(carbon_entry, 'registry_verification_id', 'N/A')}")
            
            return {
                'verified': False,
                'error': error_msg
            }

    def _validate_methodology_template(self, carbon_entry) -> Dict[str, Any]:
        """
        Validate that the carbon entry follows appropriate methodology templates
        """
        try:
            # Get methodology template based on source
            source_name = carbon_entry.source.name.lower() if carbon_entry.source else ''
            methodology_template = self.registry_service.get_methodology_template(source_name)
            
            if not methodology_template:
                return {
                    'valid': True,  # Allow if no specific template found
                    'template': None,
                    'requirements': []
                }
            
            result = {
                'valid': True,
                'template': methodology_template,
                'requirements': [],
                'missing_data': []
            }
            
            # Check required data fields
            required_data = methodology_template.get('required_data', [])
            baseline_data = carbon_entry.baseline_data or {}
            
            for field in required_data:
                if field not in baseline_data or not baseline_data[field]:
                    result['missing_data'].append(field)
                    result['requirements'].append(f'Missing required data: {field}')
            
            # Check if amount is reasonable based on emission factor
            emission_factor = methodology_template.get('emission_factor', 0)
            if emission_factor > 0:
                # Estimate reasonable range (±50% of calculated amount)
                estimated_amount = emission_factor * baseline_data.get('field_area', 1)
                if carbon_entry.amount > estimated_amount * 1.5:
                    result['requirements'].append(f'Claimed amount ({carbon_entry.amount} kg CO₂e) exceeds reasonable estimate based on methodology ({estimated_amount:.1f} kg CO₂e)')
            
            # Check additionality requirements for high-value offsets
            if carbon_entry.amount >= 100:
                additionality_reqs = methodology_template.get('additionality_requirements', [])
                for req in additionality_reqs:
                    if req not in carbon_entry.additionality_evidence:
                        result['requirements'].append(f'Additionality requirement not addressed: {req}')
            
            result['valid'] = len(result['requirements']) == 0
            
            return result
            
        except Exception as e:
            logger.error(f"Methodology template validation error: {e}")
            return {
                'valid': True,  # Default to valid if validation fails
                'error': str(e)
            }

    def _assess_additionality(self, carbon_entry) -> Dict[str, Any]:
        """
        Comprehensive additionality testing following Verra VM0042 and research standards.
        
        Tests:
        1. Financial additionality - carbon revenue as decisive factor
        2. Barrier analysis - implementation obstacles
        3. Common practice assessment - regional baselines
        """
        result = {
            'passes_test': True,
            'violations': [],
            'requirements': [],
            'financial_analysis': {},
            'barrier_analysis': {},
            'common_practice': {}
        }

        # Financial additionality test
        if carbon_entry.verification_level == 'self_reported' and carbon_entry.amount > 50:
            if not carbon_entry.additionality_evidence:
                result['violations'].append('missing_financial_additionality_evidence')
                result['requirements'].append('Provide financial analysis showing carbon revenue as decisive investment factor')
                result['passes_test'] = False

        # Common practice assessment
        establishment = carbon_entry.establishment
        if establishment:
            # Check if practice is already common (>30% adoption) in region
            similar_offsets = CarbonEntry.objects.filter(
                establishment__state=establishment.state,
                type='offset',
                description__icontains=carbon_entry.description[:20] if carbon_entry.description else ''
            ).count()
            
            total_establishments_in_region = establishment.__class__.objects.filter(
                state=establishment.state
            ).count()
            
            if total_establishments_in_region > 0:
                adoption_rate = similar_offsets / total_establishments_in_region
                result['common_practice']['adoption_rate'] = adoption_rate
                
                if adoption_rate > 0.30:  # >30% adoption = common practice
                    result['violations'].append('fails_common_practice_test')
                    result['requirements'].append('Practice appears to be common practice (>30% regional adoption). Provide evidence of additional barriers or enhanced implementation.')
                    result['passes_test'] = False

        # Barrier analysis for larger offsets
        if carbon_entry.amount > 100:
            if not carbon_entry.baseline_data:
                result['violations'].append('missing_barrier_analysis')
                result['requirements'].append('Provide barrier analysis identifying specific implementation obstacles overcome')
                result['passes_test'] = False

        return result

    def _check_cumulative_limits(self, carbon_entry) -> Dict[str, Any]:
        """Check cumulative offset limits to prevent gaming through many small entries."""
        result = {'violations': [], 'requirements': []}
        
        if carbon_entry.verification_level != 'certified_project':
            establishment = carbon_entry.establishment
            user = carbon_entry.created_by
            
            # Monthly limit check
            month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_total = CarbonEntry.objects.filter(
                Q(establishment=establishment) | Q(created_by=user),
                type='offset',
                verification_level__in=['self_reported', 'community_verified'],
                created_at__gte=month_start
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            if monthly_total + carbon_entry.amount > self.MONTHLY_SELF_REPORTED_LIMIT:
                result['violations'].append('monthly_limit_exceeded')
                result['requirements'].append(f'Monthly limit of {self.MONTHLY_SELF_REPORTED_LIMIT} kg CO2e exceeded. Use certified projects for larger offsets.')
            
            # Annual limit check
            year_start = timezone.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            annual_total = CarbonEntry.objects.filter(
                Q(establishment=establishment) | Q(created_by=user),
                type='offset',
                verification_level__in=['self_reported', 'community_verified'],
                created_at__gte=year_start
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            if annual_total + carbon_entry.amount > self.ANNUAL_SELF_REPORTED_LIMIT:
                result['violations'].append('high_cumulative_threshold_exceeded')
                result['requirements'].append(f'Annual limit of {self.ANNUAL_SELF_REPORTED_LIMIT} kg CO2e exceeded. Upgrade to certified projects.')

        return result

    def _analyze_submission_patterns(self, carbon_entry) -> Dict[str, Any]:
        """Detect rapid submission patterns that may indicate gaming."""
        result = {'suspicious': False, 'flags': [], 'requirements': []}
        
        # Check submissions in last 24 hours
        day_ago = timezone.now() - timedelta(days=1)
        recent_submissions = CarbonEntry.objects.filter(
            created_by=carbon_entry.created_by,
            type='offset',
            created_at__gte=day_ago
        ).count()
        
        if recent_submissions >= self.RAPID_SUBMISSION_THRESHOLD:
            result['suspicious'] = True
            result['flags'].append('rapid_submission_pattern')
            result['requirements'].append(f'More than {self.RAPID_SUBMISSION_THRESHOLD} offset entries in 24 hours. Please consolidate entries or upgrade verification level.')

        # Check for identical entries (copy-paste behavior)
        similar_entries = CarbonEntry.objects.filter(
            created_by=carbon_entry.created_by,
            type='offset',
            amount=carbon_entry.amount,
            description=carbon_entry.description,
            created_at__gte=day_ago
        ).count()
        
        if similar_entries > 1:
            result['suspicious'] = True
            result['flags'].append('duplicate_entries_pattern')
            result['requirements'].append('Multiple identical entries detected. Please provide unique documentation for each offset activity.')

        return result

    def _check_offset_emission_ratio(self, carbon_entry) -> Dict[str, Any]:
        """Check if offset-to-emission ratio is realistic."""
        result = {'unrealistic': False, 'flags': [], 'requirements': []}
        
        establishment = carbon_entry.establishment
        if establishment:
            # Get total emissions for this establishment
            total_emissions = CarbonEntry.objects.filter(
                establishment=establishment,
                type='emission'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Get total offsets (including this one)
            total_offsets = CarbonEntry.objects.filter(
                establishment=establishment,
                type='offset'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            total_offsets += carbon_entry.amount
            
            if total_emissions > 0:
                offset_ratio = total_offsets / total_emissions
                
                if offset_ratio > self.UNREALISTIC_OFFSET_RATIO:
                    result['unrealistic'] = True
                    result['flags'].append('unrealistic_offset_ratio')
                    result['requirements'].append(f'Offset-to-emission ratio ({offset_ratio:.1f}:1) exceeds realistic threshold. Provide additional verification or use certified projects.')

        return result

    def _validate_acreage_capacity(self, carbon_entry) -> Dict[str, Any]:
        """Validate that offset claims don't exceed farm acreage capacity."""
        result = {'exceeds_capacity': False, 'flags': [], 'requirements': []}
        
        establishment = carbon_entry.establishment
        if establishment and hasattr(establishment, 'total_area'):
            # Estimate maximum offset potential per hectare (conservative)
            max_offset_per_hectare = 5000  # kg CO2e/ha/year (very conservative)
            
            if establishment.total_area:
                max_annual_capacity = establishment.total_area * max_offset_per_hectare
                
                # Check annual offsets for this establishment
                year_start = timezone.now().replace(month=1, day=1)
                annual_offsets = CarbonEntry.objects.filter(
                    establishment=establishment,
                    type='offset',
                    created_at__gte=year_start
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                annual_offsets += carbon_entry.amount
                
                if annual_offsets > max_annual_capacity:
                    result['exceeds_capacity'] = True
                    result['flags'].append('exceeds_acreage_capacity')
                    result['requirements'].append(f'Annual offset claims ({annual_offsets:.0f} kg CO2e) exceed estimated farm capacity ({max_annual_capacity:.0f} kg CO2e). Provide detailed acreage-based calculations.')

        return result

    def _validate_evidence_requirements(self, carbon_entry) -> Dict[str, Any]:
        """Validate evidence requirements based on verification level and amount."""
        result = {'complete': True, 'missing': []}
        
        # Evidence requirements based on amount and verification level
        if carbon_entry.verification_level == 'self_reported':
            if carbon_entry.amount > 25:  # Stricter than before
                if not carbon_entry.evidence_photos:
                    result['complete'] = False
                    result['missing'].append('Photo evidence required for self-reported offsets >25 kg CO2e')
                
                if not carbon_entry.description or len(carbon_entry.description) < 50:
                    result['complete'] = False
                    result['missing'].append('Detailed description (min 50 characters) required')
            
            if carbon_entry.amount > 100:
                if not carbon_entry.additionality_evidence:
                    result['complete'] = False
                    result['missing'].append('Additionality evidence required for offsets >100 kg CO2e')
                
                if not carbon_entry.baseline_data:
                    result['complete'] = False
                    result['missing'].append('Baseline data required for large offset claims')

        elif carbon_entry.verification_level == 'community_verified':
            if carbon_entry.attestation_count < 2:
                result['complete'] = False
                result['missing'].append('Minimum 2 community attestations required')

        return result

    def _validate_conservative_baseline(self, carbon_entry) -> Dict[str, Any]:
        """Validate that baseline assumptions are conservative (following Verra standards)."""
        result = {'requires_adjustment': False, 'requirements': []}
        
        # For self-reported offsets, apply conservative baseline checks
        if carbon_entry.verification_level == 'self_reported' and carbon_entry.amount > 50:
            # Check if baseline data exists and is conservative
            if carbon_entry.baseline_data:
                # Simple heuristic: if claimed offset is >50% above typical for practice type
                # This would normally integrate with USDA benchmarks
                typical_offset_for_practice = 100  # kg CO2e (placeholder)
                
                if carbon_entry.amount > typical_offset_for_practice * 1.5:
                    result['requires_adjustment'] = True
                    result['requirements'].append('Offset claim appears optimistic compared to typical practice. Provide detailed methodology or use certified project.')

        return result

    def _requires_audit(self, carbon_entry, verification_result) -> bool:
        """Determine if entry requires audit based on risk factors."""
        audit_triggers = [
            carbon_entry.amount > 200,  # Large offsets
            len(verification_result['anti_gaming_flags']) > 2,  # Multiple flags
            carbon_entry.verification_level == 'self_reported' and carbon_entry.amount > 100,
            verification_result['additionality_assessment'].get('adoption_rate', 0) > 0.25  # Common practice risk
        ]
        
        return any(audit_triggers)

    def _determine_verification_tier(self, carbon_entry) -> str:
        """Determine verification tier following registry standards."""
        if carbon_entry.verification_level == 'certified_project':
            return 'tier_3_certified'
        elif carbon_entry.verification_level == 'community_verified':
            return 'tier_2_community'
        else:
            return 'tier_1_self_reported'

    def _generate_recommendations(self, carbon_entry, verification_result) -> list:
        """Generate actionable recommendations for farmers."""
        recommendations = []
        
        if verification_result['anti_gaming_flags']:
            recommendations.append("Consider upgrading to certified offset projects for larger carbon claims")
            recommendations.append("Consolidate multiple small activities into comprehensive sustainability plans")
        
        if not verification_result['evidence_complete']:
            recommendations.append("Add photo documentation and detailed practice descriptions")
            recommendations.append("Consider community verification to increase trust score")
        
        if verification_result['audit_required']:
            recommendations.append("Large offset claims will be scheduled for third-party audit")
            recommendations.append("Prepare detailed documentation including financial analysis and practice timeline")
        
        # Always recommend certified projects for scale
        if carbon_entry.amount > 100:
            recommendations.append("For offset claims >100 kg CO2e, certified projects provide 100% credit vs 50% for self-reported")
        
        return recommendations

    def calculate_effective_amount(self, carbon_entry) -> float:
        """
        Calculate effective amount with industry-standard deductions.
        
        Applies trust score and buffer pool deductions following
        Indigo Ag and Agoro Carbon Alliance practices.
        """
        trust_score = self.TRUST_SCORES.get(carbon_entry.verification_level, 0.5)
        buffer_deduction = self.BUFFER_POOLS.get(carbon_entry.verification_level, 0.20)
        
        # Apply trust score first, then buffer pool deduction
        effective_amount = carbon_entry.amount * trust_score
        effective_amount = effective_amount * (1 - buffer_deduction)
        
        return effective_amount

    def apply_verification_results(self, carbon_entry, verification_result) -> None:
        """
        Apply verification results to carbon entry, including effective amount calculation.
        This centralizes all verification logic to prevent inconsistencies.
        """
        # Mark as processed to prevent CarbonEntry.save() from overriding
        carbon_entry._verification_processed = True
        
        # Set trust score from verification
        carbon_entry.trust_score = verification_result['trust_score']
        
        # Calculate effective amount using centralized method
        carbon_entry.effective_amount = self.calculate_effective_amount(carbon_entry)
        
        # Update audit status based on verification
        if verification_result['audit_required']:
            carbon_entry.audit_status = 'scheduled'
        elif verification_result['approved']:
            carbon_entry.audit_status = 'passed'
        else:
            carbon_entry.audit_status = 'failed'
        
        # Update verification status based on approval
        if verification_result['approved']:
            carbon_entry.verification_status = 'verified'
        else:
            carbon_entry.verification_status = 'rejected'
        
        # Update evidence and documentation flags
        carbon_entry.evidence_requirements_met = verification_result.get('evidence_complete', False)
        carbon_entry.documentation_complete = verification_result.get('evidence_complete', False)
        
        # Save with verification processing flag
        carbon_entry.save()
        
        logger.info(f"✅ Applied verification results to entry {carbon_entry.id}")
        logger.info(f"   verification_status: {carbon_entry.verification_status}")
        logger.info(f"   audit_status: {carbon_entry.audit_status}")
        logger.info(f"   trust_score: {carbon_entry.trust_score}")
        logger.info(f"   effective_amount: {carbon_entry.effective_amount}") 