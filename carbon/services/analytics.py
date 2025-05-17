from django.db.models import Sum, Avg, Count, F, Q
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone
from datetime import timedelta
from ..models import CarbonOffsetPurchase, CarbonOffsetProject, CarbonAuditLog

class CarbonOffsetAnalytics:
    """Service for analyzing carbon offset data and generating insights."""

    def get_user_analytics(self, user, time_period='year'):
        """
        Get analytics for a specific user's carbon offset activities.
        
        Args:
            user: User instance
            time_period: 'month', 'year', or 'all'
            
        Returns:
            dict: Analytics data
        """
        # Base queryset
        purchases = CarbonOffsetPurchase.objects.filter(buyer=user)
        
        # Apply time filter
        if time_period == 'month':
            start_date = timezone.now() - timedelta(days=30)
        elif time_period == 'year':
            start_date = timezone.now() - timedelta(days=365)
        else:
            start_date = None
            
        if start_date:
            purchases = purchases.filter(created_at__gte=start_date)

        # Calculate metrics
        total_offsets = purchases.aggregate(total=Sum('amount'))['total'] or 0
        total_spent = purchases.aggregate(total=Sum(F('amount') * F('price_per_ton')))['total'] or 0
        avg_price = purchases.aggregate(avg=Avg('price_per_ton'))['avg'] or 0
        project_count = purchases.values('project').distinct().count()

        # Get monthly trends
        monthly_trends = purchases.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total_offsets=Sum('amount'),
            total_spent=Sum(F('amount') * F('price_per_ton'))
        ).order_by('month')

        # Get project type distribution
        project_distribution = purchases.values(
            'project__project_type'
        ).annotate(
            total_offsets=Sum('amount'),
            count=Count('id')
        ).order_by('-total_offsets')

        # Get certification standard distribution
        certification_distribution = purchases.values(
            'project__certification_standard'
        ).annotate(
            total_offsets=Sum('amount'),
            count=Count('id')
        ).order_by('-total_offsets')

        # Calculate impact metrics
        impact_metrics = {
            'trees_equivalent': total_offsets * 0.5,  # Assuming 0.5 tons per tree per year
            'cars_equivalent': total_offsets * 0.4,   # Assuming 0.4 tons per car per year
            'homes_equivalent': total_offsets * 0.3   # Assuming 0.3 tons per home per year
        }

        # Get recent activity
        recent_activity = CarbonAuditLog.objects.filter(
            Q(carbon_offset_purchase__in=purchases) |
            Q(carbon_offset_project__in=purchases.values('project'))
        ).order_by('-timestamp')[:10]

        return {
            'total_offsets': total_offsets,
            'total_spent': total_spent,
            'avg_price_per_ton': avg_price,
            'project_count': project_count,
            'monthly_trends': list(monthly_trends),
            'project_distribution': list(project_distribution),
            'certification_distribution': list(certification_distribution),
            'impact_metrics': impact_metrics,
            'recent_activity': [
                {
                    'timestamp': activity.timestamp,
                    'action': activity.action,
                    'details': activity.details
                }
                for activity in recent_activity
            ]
        }

    def get_project_analytics(self, project):
        """
        Get analytics for a specific carbon offset project.
        
        Args:
            project: CarbonOffsetProject instance
            
        Returns:
            dict: Project analytics data
        """
        purchases = CarbonOffsetPurchase.objects.filter(project=project)
        
        # Calculate metrics
        total_offsets = purchases.aggregate(total=Sum('amount'))['total'] or 0
        total_revenue = purchases.aggregate(total=Sum(F('amount') * F('price_per_ton')))['total'] or 0
        buyer_count = purchases.values('buyer').distinct().count()
        
        # Get monthly trends
        monthly_trends = purchases.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total_offsets=Sum('amount'),
            total_revenue=Sum(F('amount') * F('price_per_ton'))
        ).order_by('month')

        # Get buyer distribution
        buyer_distribution = purchases.values(
            'buyer__company__name'
        ).annotate(
            total_offsets=Sum('amount'),
            count=Count('id')
        ).order_by('-total_offsets')

        # Calculate verification metrics
        verification_metrics = {
            'total_verified': purchases.filter(verification_status='verified').count(),
            'total_pending': purchases.filter(verification_status='pending').count(),
            'total_failed': purchases.filter(verification_status='failed').count()
        }

        return {
            'total_offsets': total_offsets,
            'total_revenue': total_revenue,
            'buyer_count': buyer_count,
            'monthly_trends': list(monthly_trends),
            'buyer_distribution': list(buyer_distribution),
            'verification_metrics': verification_metrics
        }

    def get_global_analytics(self):
        """
        Get global analytics for all carbon offset activities.
        
        Returns:
            dict: Global analytics data
        """
        purchases = CarbonOffsetPurchase.objects.all()
        projects = CarbonOffsetProject.objects.all()
        
        # Calculate global metrics
        total_offsets = purchases.aggregate(total=Sum('amount'))['total'] or 0
        total_revenue = purchases.aggregate(total=Sum(F('amount') * F('price_per_ton')))['total'] or 0
        total_projects = projects.count()
        total_buyers = purchases.values('buyer').distinct().count()
        
        # Get yearly trends
        yearly_trends = purchases.annotate(
            year=TruncYear('created_at')
        ).values('year').annotate(
            total_offsets=Sum('amount'),
            total_revenue=Sum(F('amount') * F('price_per_ton'))
        ).order_by('year')

        # Get project type distribution
        project_distribution = projects.values(
            'project_type'
        ).annotate(
            count=Count('id'),
            total_capacity=Sum('total_capacity'),
            available_capacity=Sum('available_capacity')
        ).order_by('-count')

        # Get certification standard distribution
        certification_distribution = projects.values(
            'certification_standard'
        ).annotate(
            count=Count('id'),
            total_capacity=Sum('total_capacity')
        ).order_by('-count')

        return {
            'total_offsets': total_offsets,
            'total_revenue': total_revenue,
            'total_projects': total_projects,
            'total_buyers': total_buyers,
            'yearly_trends': list(yearly_trends),
            'project_distribution': list(project_distribution),
            'certification_distribution': list(certification_distribution)
        }

# Create singleton instance
analytics = CarbonOffsetAnalytics() 