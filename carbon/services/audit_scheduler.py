import random
import logging
from datetime import timedelta
from typing import List, Dict, Any
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from ..models import CarbonEntry

logger = logging.getLogger(__name__)

class AuditScheduler:
    """Automated audit scheduling and management"""

    def __init__(self):
        self.audit_percentage = getattr(settings, 'RANDOM_AUDIT_PERCENTAGE', 0.1)
        self.audit_notification_days = getattr(settings, 'AUDIT_NOTIFICATION_DAYS', 7)

    def schedule_audit(self, carbon_entry: CarbonEntry) -> Dict[str, Any]:
        """Schedule a single audit for a carbon entry"""
        from ..models import VerificationAudit
        
        try:
            audit = VerificationAudit.objects.create(
                carbon_entry=carbon_entry,
                audit_type='random',
                audit_date=timezone.now() + timedelta(days=self.audit_notification_days),
                auditor_name='Trazo Verification Team',
                result='pending'
            )

            # Update carbon entry status
            carbon_entry.audit_status = 'scheduled'
            carbon_entry.audit_scheduled_date = audit.audit_date
            carbon_entry.save()

            # Send notification
            self.send_audit_notification(carbon_entry)

            return {
                'success': True,
                'audit_id': audit.id,
                'audit_date': audit.audit_date
            }

        except Exception as e:
            logger.error(f"Error scheduling audit for carbon entry {carbon_entry.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def schedule_random_audits(self) -> Dict[str, Any]:
        """Schedule random audits for 10% of monthly offsets"""
        from ..models import VerificationAudit
        
        try:
            # Get offsets from last month
            last_month = timezone.now() - timedelta(days=30)
            recent_offsets = CarbonEntry.objects.filter(
                type='offset',
                created_at__gte=last_month,
                verification_level__in=['self_reported', 'community_verified']
            ).exclude(audit_status='passed')

            if not recent_offsets.exists():
                return {'count': 0, 'audit_ids': [], 'message': 'No eligible offsets for audit'}

            # Select percentage for random audit
            audit_count = max(1, int(len(recent_offsets) * self.audit_percentage))
            selected_for_audit = random.sample(list(recent_offsets), min(audit_count, len(recent_offsets)))

            audit_results = []
            for entry in selected_for_audit:
                audit_result = self.schedule_audit(entry)
                if audit_result['success']:
                    audit_results.append(audit_result['audit_id'])

            return {
                'count': len(audit_results),
                'audit_ids': audit_results,
                'message': f'Successfully scheduled {len(audit_results)} random audits'
            }

        except Exception as e:
            logger.error(f"Error scheduling random audits: {e}")
            return {
                'count': 0,
                'audit_ids': [],
                'error': str(e)
            }

    def send_audit_notification(self, carbon_entry: CarbonEntry) -> bool:
        """Send audit notification email to user"""
        try:
            subject = f'Carbon Offset Audit Required - {carbon_entry.amount} kg CO₂e'
            message = f"""
Dear {carbon_entry.created_by.first_name or 'Farmer'},

Your carbon offset entry requires verification audit:

Offset Details:
- Amount: {carbon_entry.amount} kg CO₂e
- Source: {carbon_entry.source.name if carbon_entry.source else 'Unknown'}
- Created: {carbon_entry.created_at.strftime('%B %d, %Y')}
- Audit Due Date: {carbon_entry.audit_scheduled_date.strftime('%B %d, %Y')}

Required Evidence:
- Photos or documentation of offset activity
- GPS coordinates if applicable
- Implementation timeline
- Proof of additionality (if applicable)

Please login to your Trazo dashboard to submit evidence before the due date.

Best regards,
Trazo Verification Team
            """

            from_email = getattr(settings, 'AUDIT_NOTIFICATION_FROM_EMAIL', 'audits@trazo.com')
            
            send_mail(
                subject,
                message,
                from_email,
                [carbon_entry.created_by.email],
                fail_silently=False
            )

            logger.info(f"Audit notification sent to {carbon_entry.created_by.email} for entry {carbon_entry.id}")
            return True

        except Exception as e:
            logger.error(f"Error sending audit notification for entry {carbon_entry.id}: {e}")
            return False

    def get_pending_audits(self) -> List[Dict[str, Any]]:
        """Get list of pending audits"""
        from ..models import VerificationAudit
        
        try:
            pending_audits = VerificationAudit.objects.filter(
                result='pending',
                audit_date__lte=timezone.now()
            ).select_related('carbon_entry', 'carbon_entry__created_by')

            audit_list = []
            for audit in pending_audits:
                audit_list.append({
                    'audit_id': audit.id,
                    'carbon_entry_id': audit.carbon_entry.id,
                    'amount': audit.carbon_entry.amount,
                    'user_email': audit.carbon_entry.created_by.email,
                    'audit_date': audit.audit_date,
                    'days_overdue': (timezone.now() - audit.audit_date).days
                })

            return audit_list

        except Exception as e:
            logger.error(f"Error getting pending audits: {e}")
            return []

    def complete_audit(self, audit_id: int, result: str, findings: Dict[str, Any], corrective_actions: str = '') -> Dict[str, Any]:
        """Complete an audit with results"""
        from ..models import VerificationAudit
        
        try:
            audit = VerificationAudit.objects.get(id=audit_id)
            audit.result = result
            audit.findings = findings
            audit.corrective_actions = corrective_actions
            audit.save()

            # Update carbon entry audit status
            carbon_entry = audit.carbon_entry
            carbon_entry.audit_status = result
            carbon_entry.save()

            # Send completion notification
            self.send_audit_completion_notification(audit)

            return {
                'success': True,
                'audit_id': audit_id,
                'result': result
            }

        except VerificationAudit.DoesNotExist:
            return {
                'success': False,
                'error': 'Audit not found'
            }
        except Exception as e:
            logger.error(f"Error completing audit {audit_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def send_audit_completion_notification(self, audit) -> bool:
        """Send audit completion notification to user"""
        try:
            result_message = "passed" if audit.result == "passed" else "requires attention"
            subject = f'Carbon Offset Audit Complete - {result_message.title()}'
            
            message = f"""
Dear {audit.carbon_entry.created_by.first_name or 'Farmer'},

Your carbon offset audit has been completed:

Offset Details:
- Amount: {audit.carbon_entry.amount} kg CO₂e
- Audit Result: {audit.result.title()}
- Audit Date: {audit.audit_date.strftime('%B %d, %Y')}

{f"Corrective Actions Required: {audit.corrective_actions}" if audit.corrective_actions else "No corrective actions required."}

Login to your Trazo dashboard to view detailed results.

Best regards,
Trazo Verification Team
            """

            from_email = getattr(settings, 'AUDIT_NOTIFICATION_FROM_EMAIL', 'audits@trazo.com')
            
            send_mail(
                subject,
                message,
                from_email,
                [audit.carbon_entry.created_by.email],
                fail_silently=False
            )

            return True

        except Exception as e:
            logger.error(f"Error sending audit completion notification for audit {audit.id}: {e}")
            return False 