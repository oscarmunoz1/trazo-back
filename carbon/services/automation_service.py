from django.utils import timezone
from datetime import timedelta
from carbon.models import AutomationRule, IoTDataPoint, CarbonEntry
from subscriptions.models import Subscription
from company.models import Company, Establishment
import logging
import random

logger = logging.getLogger(__name__)

class AutomationLevelService:
    """Service to enforce plan-based automation level restrictions"""
    
    def __init__(self):
        self.plan_automation_levels = {
            'Basic': 50,
            'Standard': 75,
            'Corporate': 85,
            'Enterprise': 85,  # Same as Corporate for automation level
        }
    
    def get_automation_level_for_establishment(self, establishment):
        """Get the automation level percentage for an establishment based on subscription plan"""
        try:
            subscription = establishment.company.subscription
            plan_name = subscription.plan.name
            
            # Get automation level from plan features
            automation_level = subscription.plan.features.get('iot_automation_level', 50)
            
            # Verify it matches our expected levels
            expected_level = self.plan_automation_levels.get(plan_name, 50)
            if automation_level != expected_level:
                logger.warning(f"Automation level mismatch for {plan_name}: expected {expected_level}, got {automation_level}")
                automation_level = expected_level
            
            return automation_level
            
        except (Subscription.DoesNotExist, AttributeError):
            # Default to Basic plan level
            return 50
    
    def should_auto_approve_event(self, data_point, base_confidence):
        """
        Determine if an event should be auto-approved based on:
        1. Base confidence score from data quality
        2. Subscription plan automation level 
        3. Random sampling to enforce the percentage limit
        """
        establishment = data_point.device.establishment
        automation_level = self.get_automation_level_for_establishment(establishment)
        
        # Calculate automation threshold based on plan
        # Higher confidence required for lower-tier plans
        if automation_level >= 85:  # Corporate/Enterprise
            min_confidence = 0.80
        elif automation_level >= 75:  # Standard
            min_confidence = 0.85
        else:  # Basic (50%)
            min_confidence = 0.90
        
        # First check: data quality must meet minimum confidence
        if base_confidence < min_confidence:
            return False
        
        # Second check: random sampling to enforce automation percentage
        # This ensures that even high-confidence events are sometimes held for manual review
        # to maintain the advertised automation level
        automation_chance = automation_level / 100.0
        random_factor = random.random()
        
        should_automate = random_factor < automation_chance
        
        logger.info(
            f"Automation decision for {establishment.name}: "
            f"level={automation_level}%, confidence={base_confidence:.2f}, "
            f"min_required={min_confidence:.2f}, random={random_factor:.2f}, "
            f"automate={should_automate}"
        )
        
        return should_automate
    
    def get_carbon_tracking_mode(self, establishment):
        """Get carbon tracking mode (manual/automated) based on subscription plan"""
        try:
            subscription = establishment.company.subscription
            carbon_tracking = subscription.plan.features.get('carbon_tracking', 'manual')
            return carbon_tracking
        except (Subscription.DoesNotExist, AttributeError):
            return 'manual'
    
    def should_require_manual_carbon_entry(self, establishment, entry_type='emission'):
        """
        Determine if carbon entries should require manual review based on plan
        """
        carbon_tracking_mode = self.get_carbon_tracking_mode(establishment)
        
        if carbon_tracking_mode == 'manual':
            # Basic plan - all entries require manual input/review
            return True
        else:
            # Standard/Corporate - automated carbon tracking allowed
            # But still may require review for certain complex entries
            complex_entry_types = ['offset', 'certification', 'verification']
            return entry_type in complex_entry_types
    
    def get_automation_stats_for_establishment(self, establishment, days=30):
        """Get automation statistics for an establishment over the specified period"""
        start_date = timezone.now() - timedelta(days=days)
        
        # Get all data points for this establishment in the time period
        total_data_points = IoTDataPoint.objects.filter(
            device__establishment=establishment,
            timestamp__gte=start_date
        ).count()
        
        # Get auto-processed data points
        auto_processed = IoTDataPoint.objects.filter(
            device__establishment=establishment,
            timestamp__gte=start_date,
            processed=True,
            carbon_entry__isnull=False  # Has associated carbon entry (auto-approved)
        ).count()
        
        # Get manually processed data points
        manual_processed = IoTDataPoint.objects.filter(
            device__establishment=establishment,
            timestamp__gte=start_date,
            processed=True,
            carbon_entry__isnull=True  # No carbon entry (manual review)
        ).count()
        
        # Calculate actual automation percentage
        if total_data_points > 0:
            actual_automation_rate = (auto_processed / total_data_points) * 100
        else:
            actual_automation_rate = 0
        
        # Get target automation level from plan
        target_automation_level = self.get_automation_level_for_establishment(establishment)
        carbon_tracking_mode = self.get_carbon_tracking_mode(establishment)
        
        return {
            'establishment_id': establishment.id,
            'establishment_name': establishment.name,
            'target_automation_level': target_automation_level,
            'actual_automation_rate': round(actual_automation_rate, 1),
            'carbon_tracking_mode': carbon_tracking_mode,
            'period_days': days,
            'total_data_points': total_data_points,
            'auto_processed': auto_processed,
            'manual_processed': manual_processed,
            'pending_review': total_data_points - auto_processed - manual_processed,
            'compliance_status': 'compliant' if abs(actual_automation_rate - target_automation_level) <= 10 else 'non_compliant'
        } 