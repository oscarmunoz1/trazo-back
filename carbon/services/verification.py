from typing import Dict, Any, Optional
from django.utils import timezone
from ..models import (
    CarbonOffsetProject,
    CarbonOffsetPurchase,
    CarbonOffsetCertificate,
    CarbonAuditLog
)
import logging

logger = logging.getLogger(__name__)

class CarbonOffsetVerificationService:
    """Service for verifying carbon offset projects and purchases"""

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
            
            # Determine overall status
            all_checks_passed = all(check['passed'] for check in verification_results['checks'].values())
            verification_results['status'] = 'verified' if all_checks_passed else 'failed'
            
            # Update purchase verification status
            purchase.verification_status = verification_results['status']
            purchase.last_verified_at = timezone.now()
            purchase.save()
            
            # Log verification
            CarbonAuditLog.objects.create(
                purchase=purchase,
                action='verify',
                details=f'Purchase verification completed with status: {verification_results["status"]}'
            )
            
            return verification_results
            
        except Exception as e:
            logger.error(f"Error verifying purchase {purchase.id}: {str(e)}")
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

# Create a singleton instance
verification_service = CarbonOffsetVerificationService() 