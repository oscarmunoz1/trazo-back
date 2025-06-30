from typing import Dict, Any, Optional
from django.utils import timezone
from django.conf import settings
from ..models import (
    CarbonOffsetProject,
    CarbonOffsetPurchase,
    CarbonOffsetCertificate,
    CarbonAuditLog,
    CarbonEntry
)
from .blockchain import blockchain_service, BlockchainUnavailableError
import logging

logger = logging.getLogger(__name__)

class CarbonOffsetVerificationService:
    """Service for verifying carbon offset projects and purchases with blockchain integration"""

    def __init__(self):
        self.production_mode = getattr(settings, 'DEBUG', True) == False
        self.blockchain_required = self.production_mode or getattr(settings, 'FORCE_BLOCKCHAIN_VERIFICATION', False)

    def verify_project(self, project: CarbonOffsetProject) -> Dict[str, Any]:
        """
        Verify a carbon offset project's legitimacy and compliance
        
        Args:
            project: CarbonOffsetProject instance to verify
            
        Returns:
            Dictionary containing verification results
        """
        try:
            verification_results = {
                'project_id': project.id,
                'verification_date': timezone.now(),
                'status': 'pending',
                'checks': {}
            }
            
            # Check certification standards
            verification_results['checks']['certification'] = self._verify_certification(project)
            
            # Verify project documentation
            verification_results['checks']['documentation'] = self._verify_documentation(project)
            
            # Verify project capacity
            verification_results['checks']['capacity'] = self._verify_capacity(project)
            
            # Verify project location
            verification_results['checks']['location'] = self._verify_location(project)
            
            # BLOCKCHAIN VERIFICATION - Critical for production
            verification_results['checks']['blockchain'] = self._verify_blockchain_integration(project)
            
            # Determine overall status
            all_checks_passed = all(check['passed'] for check in verification_results['checks'].values())
            verification_results['status'] = 'verified' if all_checks_passed else 'failed'
            
            # Update project verification status
            project.verification_status = verification_results['status']
            project.last_verified_at = timezone.now()
            project.save()
            
            # Log verification
            CarbonAuditLog.objects.create(
                project=project,
                action='verify',
                details=f'Project verification completed with status: {verification_results["status"]}'
            )
            
            return verification_results
            
        except Exception as e:
            logger.error(f"Error verifying project {project.id}: {str(e)}")
            raise

    def verify_purchase(self, purchase: CarbonOffsetPurchase) -> Dict[str, Any]:
        """
        Verify a carbon offset purchase
        
        Args:
            purchase: CarbonOffsetPurchase instance to verify
            
        Returns:
            Dictionary containing verification results
        """
        try:
            verification_results = {
                'purchase_id': purchase.id,
                'verification_date': timezone.now(),
                'status': 'pending',
                'checks': {}
            }
            
            # Verify purchase amount
            verification_results['checks']['amount'] = self._verify_purchase_amount(purchase)
            
            # Verify payment
            verification_results['checks']['payment'] = self._verify_payment(purchase)
            
            # Verify certificate
            verification_results['checks']['certificate'] = self._verify_certificate(purchase)
            
            # BLOCKCHAIN VERIFICATION for purchase
            verification_results['checks']['blockchain'] = self._verify_purchase_blockchain(purchase)
            
            # Determine overall status
            all_checks_passed = all(check['passed'] for check in verification_results['checks'].values())
            verification_results['status'] = 'verified' if all_checks_passed else 'failed'
            
            # Update purchase verification status
            purchase.verification_status = verification_results['status']
            purchase.last_verified_at = timezone.now()
            purchase.save()
            
            # Log verification
            CarbonAuditLog.objects.create(
                user=purchase.user,
                action='verify',
                details=f'Purchase verification completed with status: {verification_results["status"]}'
            )
            
            return verification_results
            
        except Exception as e:
            logger.error(f"Error verifying purchase {purchase.id}: {str(e)}")
            raise

    def verify_carbon_entry(self, carbon_entry: CarbonEntry) -> Dict[str, Any]:
        """
        Verify a carbon entry (offset)
        
        Args:
            carbon_entry: CarbonEntry instance to verify
            
        Returns:
            Dictionary containing verification results
        """
        try:
            verification_results = {
                'entry_id': carbon_entry.id,
                'verification_date': timezone.now(),
                'status': 'pending',
                'checks': {}
            }
            
            # Verify entry amount
            verification_results['checks']['amount'] = self._verify_entry_amount(carbon_entry)
            
            # Verify entry completeness
            verification_results['checks']['completeness'] = self._verify_entry_completeness(carbon_entry)
            
            # Verify documentation
            verification_results['checks']['documentation'] = self._verify_entry_documentation(carbon_entry)
            
            # BLOCKCHAIN VERIFICATION for entry
            verification_results['checks']['blockchain'] = self._verify_entry_blockchain(carbon_entry)
            
            # Determine overall status
            all_checks_passed = all(check['passed'] for check in verification_results['checks'].values())
            verification_results['status'] = 'verified' if all_checks_passed else 'failed'
            
            # Update entry verification status
            carbon_entry.verification_status = verification_results['status']
            carbon_entry.save()
            
            # Log verification
            CarbonAuditLog.objects.create(
                carbon_entry=carbon_entry,
                user=carbon_entry.created_by,
                action='verify',
                details=f'Carbon entry verification completed with status: {verification_results["status"]}'
            )
            
            return verification_results
            
        except Exception as e:
            logger.error(f"Error verifying carbon entry {carbon_entry.id}: {str(e)}")
            raise

    def _verify_certification(self, project: CarbonOffsetProject) -> Dict[str, Any]:
        """Verify project certification standards"""
        try:
            # Check if certification is valid and not expired
            is_valid = (
                project.certification_standard and
                project.certification_date and
                project.certification_expiry and
                project.certification_expiry > timezone.now()
            )
            
            return {
                'passed': is_valid,
                'details': 'Certification is valid and not expired' if is_valid else 'Invalid or expired certification'
            }
        except Exception as e:
            logger.error(f"Error verifying certification: {str(e)}")
            return {'passed': False, 'details': str(e)}

    def _verify_documentation(self, project: CarbonOffsetProject) -> Dict[str, Any]:
        """Verify project documentation"""
        try:
            required_docs = ['project_plan', 'environmental_impact', 'monitoring_plan']
            missing_docs = [doc for doc in required_docs if not getattr(project, f'{doc}_document', None)]
            
            return {
                'passed': len(missing_docs) == 0,
                'details': 'All required documentation present' if not missing_docs else f'Missing documents: {", ".join(missing_docs)}'
            }
        except Exception as e:
            logger.error(f"Error verifying documentation: {str(e)}")
            return {'passed': False, 'details': str(e)}

    def _verify_capacity(self, project: CarbonOffsetProject) -> Dict[str, Any]:
        """Verify project capacity"""
        try:
            is_valid = (
                project.total_capacity > 0 and
                project.available_capacity >= 0 and
                project.available_capacity <= project.total_capacity
            )
            
            return {
                'passed': is_valid,
                'details': 'Capacity values are valid' if is_valid else 'Invalid capacity values'
            }
        except Exception as e:
            logger.error(f"Error verifying capacity: {str(e)}")
            return {'passed': False, 'details': str(e)}

    def _verify_location(self, project: CarbonOffsetProject) -> Dict[str, Any]:
        """Verify project location"""
        try:
            is_valid = (
                project.latitude is not None and
                project.longitude is not None and
                -90 <= project.latitude <= 90 and
                -180 <= project.longitude <= 180
            )
            
            return {
                'passed': is_valid,
                'details': 'Location coordinates are valid' if is_valid else 'Invalid location coordinates'
            }
        except Exception as e:
            logger.error(f"Error verifying location: {str(e)}")
            return {'passed': False, 'details': str(e)}

    def _verify_purchase_amount(self, purchase: CarbonOffsetPurchase) -> Dict[str, Any]:
        """Verify purchase amount"""
        try:
            is_valid = (
                purchase.amount > 0 and
                purchase.amount <= purchase.project.available_capacity
            )
            
            return {
                'passed': is_valid,
                'details': 'Purchase amount is valid' if is_valid else 'Invalid purchase amount'
            }
        except Exception as e:
            logger.error(f"Error verifying purchase amount: {str(e)}")
            return {'passed': False, 'details': str(e)}

    def _verify_payment(self, purchase: CarbonOffsetPurchase) -> Dict[str, Any]:
        """Verify payment status"""
        try:
            is_valid = purchase.status == 'completed'
            
            return {
                'passed': is_valid,
                'details': 'Payment is completed' if is_valid else 'Payment is not completed'
            }
        except Exception as e:
            logger.error(f"Error verifying payment: {str(e)}")
            return {'passed': False, 'details': str(e)}

    def _verify_certificate(self, purchase: CarbonOffsetPurchase) -> Dict[str, Any]:
        """Verify certificate"""
        try:
            certificate = CarbonOffsetCertificate.objects.filter(purchase=purchase).first()
            is_valid = (
                certificate is not None and
                certificate.certificate_number and
                certificate.verification_code
            )
            
            return {
                'passed': is_valid,
                'details': 'Certificate is valid' if is_valid else 'Invalid or missing certificate'
            }
        except Exception as e:
            logger.error(f"Error verifying certificate: {str(e)}")
            return {'passed': False, 'details': str(e)}

    def _verify_blockchain_integration(self, project: CarbonOffsetProject) -> Dict[str, Any]:
        """Verify project has blockchain verification"""
        try:
            # Check if blockchain verification is available and working
            if self.blockchain_required:
                try:
                    # Attempt to verify blockchain connectivity
                    blockchain_status = blockchain_service._is_blockchain_ready()
                    if not blockchain_status:
                        return {
                            'passed': False,
                            'details': 'Blockchain verification required but service unavailable'
                        }
                    
                    # Verify project has blockchain record
                    verification_result = blockchain_service.verify_carbon_record(project.id)
                    blockchain_verified = verification_result.get('blockchain_verified', False)
                    
                    return {
                        'passed': blockchain_verified,
                        'details': 'Project verified on blockchain' if blockchain_verified else 'Project not verified on blockchain',
                        'blockchain_data': verification_result
                    }
                except BlockchainUnavailableError:
                    return {
                        'passed': False,
                        'details': 'Blockchain verification required but unavailable'
                    }
            else:
                # Development mode - log but allow
                logger.warning(f"Blockchain verification skipped for project {project.id} (development mode)")
                return {
                    'passed': True,
                    'details': 'Blockchain verification skipped (development mode)',
                    'development_mode': True
                }
                
        except Exception as e:
            logger.error(f"Error in blockchain verification: {str(e)}")
            if self.blockchain_required:
                return {'passed': False, 'details': f'Blockchain verification failed: {str(e)}'}
            else:
                return {'passed': True, 'details': f'Blockchain verification error (allowed in dev): {str(e)}'}

    def _verify_purchase_blockchain(self, purchase: CarbonOffsetPurchase) -> Dict[str, Any]:
        """Verify purchase has blockchain verification"""
        try:
            # For purchases, verify the underlying project has blockchain verification
            return self._verify_blockchain_integration(purchase.project)
        except Exception as e:
            logger.error(f"Error in purchase blockchain verification: {str(e)}")
            return {'passed': False, 'details': str(e)}

    def _verify_entry_amount(self, carbon_entry: CarbonEntry) -> Dict[str, Any]:
        """Verify carbon entry amount"""
        try:
            is_valid = carbon_entry.amount > 0
            
            return {
                'passed': is_valid,
                'details': 'Entry amount is valid' if is_valid else 'Invalid entry amount'
            }
        except Exception as e:
            logger.error(f"Error verifying entry amount: {str(e)}")
            return {'passed': False, 'details': str(e)}

    def _verify_entry_completeness(self, carbon_entry: CarbonEntry) -> Dict[str, Any]:
        """Verify carbon entry completeness"""
        try:
            is_valid = (
                carbon_entry.source is not None and
                carbon_entry.amount is not None and
                carbon_entry.year is not None
            )
            
            return {
                'passed': is_valid,
                'details': 'Entry is complete' if is_valid else 'Entry is missing required data'
            }
        except Exception as e:
            logger.error(f"Error verifying entry completeness: {str(e)}")
            return {'passed': False, 'details': str(e)}

    def _verify_entry_documentation(self, carbon_entry: CarbonEntry) -> Dict[str, Any]:
        """Verify carbon entry documentation"""
        try:
            # For high-value offsets, require additional evidence
            requires_evidence = carbon_entry.amount >= 100
            has_evidence = bool(carbon_entry.additionality_evidence)
            
            if requires_evidence and not has_evidence:
                return {
                    'passed': False,
                    'details': 'High-value offsets require additionality evidence'
                }
            
            return {
                'passed': True,
                'details': 'Documentation requirements met'
            }
        except Exception as e:
            logger.error(f"Error verifying entry documentation: {str(e)}")
            return {'passed': False, 'details': str(e)}

    def _verify_entry_blockchain(self, carbon_entry: CarbonEntry) -> Dict[str, Any]:
        """Verify carbon entry blockchain verification"""
        try:
            # Check if blockchain verification is available and working
            if self.blockchain_required:
                try:
                    # Attempt to verify blockchain connectivity
                    blockchain_status = blockchain_service._is_blockchain_ready()
                    if not blockchain_status:
                        return {
                            'passed': False,
                            'details': 'Blockchain verification required but service unavailable'
                        }
                    
                    # Verify entry has blockchain record
                    verification_result = blockchain_service.verify_carbon_record(carbon_entry.id)
                    blockchain_verified = verification_result.get('blockchain_verified', False)
                    
                    return {
                        'passed': blockchain_verified,
                        'details': 'Entry verified on blockchain' if blockchain_verified else 'Entry not verified on blockchain',
                        'blockchain_data': verification_result
                    }
                except BlockchainUnavailableError:
                    return {
                        'passed': False,
                        'details': 'Blockchain verification required but unavailable'
                    }
            else:
                # Development mode - log but allow
                logger.warning(f"Blockchain verification skipped for carbon entry {carbon_entry.id} (development mode)")
                return {
                    'passed': True,
                    'details': 'Blockchain verification skipped (development mode)',
                    'development_mode': True
                }
                
        except Exception as e:
            logger.error(f"Error in entry blockchain verification: {str(e)}")
            if self.blockchain_required:
                return {'passed': False, 'details': f'Blockchain verification failed: {str(e)}'}
            else:
                return {'passed': True, 'details': f'Blockchain verification error (allowed in dev): {str(e)}'}

# Create a singleton instance
verification_service = CarbonOffsetVerificationService() 