"""
Carbon Cost Intelligence Service - Simplified

Provides lightweight cost intelligence focused ONLY on carbon-related insights.
Avoids complex farm management features to stay focused on carbon transparency mission.
"""

from decimal import Decimal
from django.db.models import Sum, Avg, Q
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from carbon.models import CarbonEntry
from history.models import History  # Production is actually History model
from product.models import Parcel


class CarbonCostInsights:
    """Lightweight cost intelligence focused ONLY on carbon-related savings"""
    
    def __init__(self):
        self.carbon_credit_rate = Decimal('25.00')  # $25/ton average market rate
        
    def get_carbon_economics(self, production_id: int) -> Dict[str, Any]:
        """Get simple carbon economics for a production"""
        try:
            production = History.objects.get(id=production_id)
            
            # Simple carbon credit calculation
            carbon_potential = self.calculate_carbon_credit_potential(production)
            
            # Basic efficiency insights (only for carbon-heavy events)
            efficiency_tips = self.get_carbon_efficiency_tips(production)
            
            # Premium pricing eligibility
            premium_eligibility = self.check_premium_pricing_eligibility(production)
            
            return {
                'carbon_credit_potential': carbon_potential,
                'efficiency_tips': efficiency_tips,
                'premium_eligibility': premium_eligibility,
                'next_actions': self.get_next_carbon_actions(production),
                'generated_at': timezone.now().isoformat()
            }
            
        except History.DoesNotExist:
            return {'error': 'Production not found'}
        except Exception as e:
            return {'error': str(e)}
    
    def calculate_carbon_credit_potential(self, production: History) -> Dict[str, Any]:
        """Simple carbon credit revenue estimation"""
        try:
            # Get total carbon sequestered from production
            carbon_entries = CarbonEntry.objects.filter(
                production=production,
                entry_type='sequestration'
            )
            
            total_sequestered = carbon_entries.aggregate(
                total=Sum('co2_equivalent')
            )['total'] or Decimal('0')
            
            # Convert to tons (assuming co2_equivalent is in kg)
            tons_sequestered = total_sequestered / Decimal('1000')
            
            potential_revenue = tons_sequestered * self.carbon_credit_rate
            
            return {
                'tons_sequestered': float(tons_sequestered),
                'market_rate_per_ton': float(self.carbon_credit_rate),
                'potential_revenue': float(potential_revenue),
                'confidence': 'medium',
                'verification_needed': tons_sequestered > 0,
                'next_steps': [
                    'Complete carbon verification process',
                    'Register with carbon credit marketplace',
                    'Maintain detailed carbon tracking records'
                ] if tons_sequestered > 0 else [
                    'Continue carbon tracking to build credit potential',
                    'Focus on carbon sequestration activities'
                ]
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'tons_sequestered': 0,
                'potential_revenue': 0
            }
    
    def get_carbon_efficiency_tips(self, production: History) -> List[Dict[str, Any]]:
        """Get efficiency tips focused only on carbon-heavy activities"""
        tips = []
        
        try:
            # Analyze fuel consumption events from carbon entries
            fuel_entries = CarbonEntry.objects.filter(
                production=production,
                source__category__icontains='fuel'
            )
            
            if fuel_entries.exists():
                avg_fuel_per_event = fuel_entries.aggregate(
                    avg=Avg('amount')
                )['avg'] or 0
                
                if avg_fuel_per_event > 50:  # Threshold for high fuel use (kg CO2e)
                    tips.append({
                        'category': 'fuel_efficiency',
                        'title': 'Optimize Fuel Usage',
                        'description': f'Average fuel emissions are {avg_fuel_per_event:.1f} kg CO2e per operation. Consider precision agriculture techniques.',
                        'potential_savings': 'Reduce fuel costs by 15-25%',
                        'carbon_impact': 'Lower CO2 emissions from machinery',
                        'priority': 'high'
                    })
            
            # Analyze fertilizer usage
            fertilizer_entries = CarbonEntry.objects.filter(
                production=production,
                source__category__icontains='fertilizer'
            )
            
            if fertilizer_entries.exists():
                tips.append({
                    'category': 'fertilizer_efficiency',
                    'title': 'Optimize Fertilizer Application',
                    'description': 'Consider soil testing and precision application to reduce fertilizer use.',
                    'potential_savings': 'Reduce fertilizer costs by 10-20%',
                    'carbon_impact': 'Lower N2O emissions from fertilizer',
                    'priority': 'medium'
                })
            
            # Limit to max 2 tips to avoid overwhelming
            return tips[:2]
            
        except Exception as e:
            return [{
                'category': 'error',
                'title': 'Unable to analyze efficiency',
                'description': str(e)
            }]
    
    def check_premium_pricing_eligibility(self, production: History) -> Dict[str, Any]:
        """Check if production qualifies for premium sustainable pricing"""
        try:
            # Simple scoring based on carbon tracking completeness
            from history.models import WeatherEvent, ChemicalEvent, ProductionEvent, GeneralEvent, EquipmentEvent
            total_events = (WeatherEvent.objects.filter(history=production).count() + 
                          ChemicalEvent.objects.filter(history=production).count() +
                          ProductionEvent.objects.filter(history=production).count() +
                          GeneralEvent.objects.filter(history=production).count() +
                          EquipmentEvent.objects.filter(history=production).count())
            carbon_entries = CarbonEntry.objects.filter(production=production).count()
            
            # Basic eligibility criteria
            has_carbon_tracking = carbon_entries > 0
            has_regular_events = total_events >= 5
            has_sequestration = CarbonEntry.objects.filter(
                production=production,
                entry_type='sequestration'
            ).exists()
            
            score = 0
            if has_carbon_tracking:
                score += 40
            if has_regular_events:
                score += 30
            if has_sequestration:
                score += 30
            
            eligibility_level = 'none'
            if score >= 80:
                eligibility_level = 'premium'
            elif score >= 50:
                eligibility_level = 'sustainable'
            elif score >= 20:
                eligibility_level = 'basic'
            
            return {
                'eligible': score >= 20,
                'level': eligibility_level,
                'score': score,
                'criteria_met': {
                    'carbon_tracking': has_carbon_tracking,
                    'regular_monitoring': has_regular_events,
                    'carbon_sequestration': has_sequestration
                },
                'potential_premium': f"{5 + (score // 20)}%" if score >= 20 else "0%",
                'next_steps': self._get_premium_next_steps(score, has_carbon_tracking, has_regular_events, has_sequestration)
            }
            
        except Exception as e:
            return {
                'eligible': False,
                'error': str(e)
            }
    
    def _get_premium_next_steps(self, score: int, has_tracking: bool, has_events: bool, has_sequestration: bool) -> List[str]:
        """Get specific next steps to improve premium eligibility"""
        steps = []
        
        if not has_tracking:
            steps.append("Start recording carbon entries for all activities")
        if not has_events:
            steps.append("Log more production events (aim for 5+ events)")
        if not has_sequestration:
            steps.append("Implement carbon sequestration practices")
        if score < 80:
            steps.append("Maintain consistent carbon tracking for premium status")
            
        return steps[:2]  # Limit to 2 actionable steps
    
    def get_next_carbon_actions(self, production: History) -> List[Dict[str, str]]:
        """Get max 2 simple next actions focused on carbon improvement"""
        actions = []
        
        try:
            # Check recent activity
            recent_entries = CarbonEntry.objects.filter(
                production=production,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count()
            
            if recent_entries == 0:
                actions.append({
                    'action': 'Log Recent Activities',
                    'description': 'Record any farm activities from the past month',
                    'impact': 'Improves carbon tracking accuracy'
                })
            
            # Check for incomplete carbon tracking
            total_carbon_entries = CarbonEntry.objects.filter(production=production).count()
            
            if total_carbon_entries < 3:  # Minimum threshold for good tracking
                actions.append({
                    'action': 'Calculate Carbon Impact',
                    'description': 'Add more carbon tracking entries for better insights',
                    'impact': 'Complete carbon footprint tracking'
                })
            
            # If no specific actions, suggest general improvement
            if not actions:
                actions.append({
                    'action': 'Continue Carbon Tracking',
                    'description': 'Keep logging activities to build carbon credit potential',
                    'impact': 'Builds toward carbon credit eligibility'
                })
            
            return actions[:2]  # Max 2 actions
            
        except Exception as e:
            return [{
                'action': 'Review Carbon Data',
                'description': 'Check carbon tracking setup',
                'impact': 'Ensure accurate carbon calculations'
            }]
    
    def get_establishment_carbon_summary(self, establishment_id: int) -> Dict[str, Any]:
        """Get carbon cost summary for entire establishment"""
        try:
            from company.models import Establishment
            establishment = Establishment.objects.get(id=establishment_id)
            
            # Get all productions for this establishment
            productions = History.objects.filter(
                parcel__establishment=establishment
            )
            
            total_carbon_potential = Decimal('0')
            total_sequestered = Decimal('0')
            
            for production in productions:
                carbon_data = self.calculate_carbon_credit_potential(production)
                if 'potential_revenue' in carbon_data:
                    total_carbon_potential += Decimal(str(carbon_data['potential_revenue']))
                if 'tons_sequestered' in carbon_data:
                    total_sequestered += Decimal(str(carbon_data['tons_sequestered']))
            
            return {
                'establishment_name': establishment.name,
                'total_productions': productions.count(),
                'total_carbon_sequestered_tons': float(total_sequestered),
                'total_carbon_credit_potential': float(total_carbon_potential),
                'average_per_production': float(total_carbon_potential / productions.count()) if productions.count() > 0 else 0,
                'summary_date': timezone.now().isoformat()
            }
            
        except Exception as e:
            return {'error': str(e)} 