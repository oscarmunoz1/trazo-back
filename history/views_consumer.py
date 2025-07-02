"""
Consumer-specific API ViewSets for dynamic dashboard data
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Count, Avg, Sum, Q, F, Min, Max
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal

from .models import History, HistoryScan
from .models_consumer import (
    UserFavorite, 
    UserImpactSummary, 
    UserProductComparison,
    UserShoppingGoal,
    UserShoppingInsight,
    UserLocalRecommendation
)
from .serializers_consumer import (
    UserFavoriteSerializer,
    UserImpactSummarySerializer,
    EnhancedHistoryScanSerializer,
    ProductComparisonSerializer,
    ProductComparisonResultSerializer,
    UserShoppingGoalSerializer,
    UserShoppingInsightSerializer,
    UserLocalRecommendationSerializer
)
from carbon.models import CarbonEntry
from company.models import Establishment
from backend.constants import get_carbon_score_from_co2e, EngagementMilestones

User = get_user_model()


class ConsumerDashboardViewSet(viewsets.ViewSet):
    """
    Main consumer dashboard API providing aggregated data for all consumer features
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def impact_dashboard(self, request):
        """Get comprehensive impact dashboard data"""
        user = request.user
        
        # Get or create user impact summary
        impact_summary, created = UserImpactSummary.objects.get_or_create(
            user=user,
            defaults={
                'total_scans': 0,
                'total_reviews': 0,
                'total_carbon_offset_kg': 0.0,
                'sustainable_farms_found': 0,
                'local_farms_found': 0,
                'better_choices_made': 0,
            }
        )
        
        # Update impact summary with latest data if needed
        if created or impact_summary.last_updated < timezone.now() - timedelta(hours=1):
            self._update_impact_summary(user, impact_summary)
        
        # Get recent scans for timeline
        recent_scans = HistoryScan.objects.filter(
            user=user
        ).select_related('history', 'history__parcel__establishment').order_by('-date')[:3]
        
        # Prepare response data
        dashboard_data = {
            'impact_metrics': UserImpactSummarySerializer(impact_summary).data,
            'recent_scans': EnhancedHistoryScanSerializer(
                recent_scans, 
                many=True, 
                context={'request': request}
            ).data,
            'quick_stats': {
                'better_choices': impact_summary.better_choices_made,
                'local_farms': impact_summary.local_farms_found,
                'favorite_count': UserFavorite.objects.filter(user=user).count(),
            },
            'recommendations': self._get_retailer_recommendations(),
            'achievements': self._get_recent_achievements(user),
        }
        
        return Response(dashboard_data)
    
    @action(detail=False, methods=['get'])
    def shopping_history(self, request):
        """Get enhanced shopping history with filtering"""
        user = request.user
        
        # Get query parameters for filtering
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        carbon_score = request.query_params.get('carbon_score')  # A+, A, B, etc.
        is_favorite = request.query_params.get('is_favorite', '').lower() == 'true'
        
        # Base queryset
        queryset = HistoryScan.objects.filter(
            user=user
        ).select_related('history', 'history__parcel__establishment').order_by('-date')
        
        # Apply date filters
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(date__gte=date_from)
            except ValueError:
                pass
                
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(date__lte=date_to)
            except ValueError:
                pass
        
        # Apply favorite filter
        if is_favorite:
            favorite_production_ids = UserFavorite.objects.filter(
                user=user
            ).values_list('production_id', flat=True)
            queryset = queryset.filter(history_id__in=favorite_production_ids)
        
        # Pagination
        page_size = int(request.query_params.get('page_size', 20))
        page = int(request.query_params.get('page', 1))
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_scans = queryset[start:end]
        total_count = queryset.count()
        
        # Summary statistics
        summary_stats = {
            'total_scans': queryset.count(),
            'date_range': {
                'earliest': queryset.aggregate(earliest=Min('date'))['earliest'],
                'latest': queryset.aggregate(latest=Max('date'))['latest'],
            },
            'farms_scanned': queryset.values('history__parcel__establishment').distinct().count(),
        }
        
        return Response({
            'scans': EnhancedHistoryScanSerializer(
                paginated_scans, 
                many=True, 
                context={'request': request}
            ).data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size,
            },
            'summary': summary_stats,
        })
    
    @action(detail=False, methods=['post'])
    def compare_products(self, request):
        """Compare multiple products side-by-side"""
        serializer = ProductComparisonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_ids = serializer.validated_data['products']
        
        # Get products with carbon data
        products = History.objects.filter(
            id__in=product_ids
        ).select_related('parcel__establishment').prefetch_related('carbonentry_set')
        
        comparison_results = []
        
        for product in products:
            # Get latest carbon entry
            carbon_entry = product.carbonentry_set.order_by('-created_at').first()
            
            # Distance removed - no real location data available
            # Will implement when user location and establishment coordinates are available
            
            # Get establishment location
            location = "Location unavailable"
            if product.parcel and product.parcel.establishment:
                establishment = product.parcel.establishment
                if establishment.city and establishment.state:
                    location = f"{establishment.city}, {establishment.state}"
            
            # Calculate carbon score using same logic as serializers
            carbon_score = "Not Available"
            carbon_footprint = "Data unavailable"
            
            if carbon_entry:
                # Use co2e_amount if available and non-zero, otherwise fall back to amount
                co2e = carbon_entry.co2e_amount if carbon_entry.co2e_amount and carbon_entry.co2e_amount > 0 else carbon_entry.amount
                if co2e and co2e > 0:
                    co2e = float(co2e)
                    carbon_footprint = f"{co2e:.2f} kg CO₂e/kg"
                    carbon_score = get_carbon_score_from_co2e(co2e)
            
            # Get certifications
            certifications = []
            if product.parcel and product.parcel.certified:
                certifications.append("USDA Organic")
            if carbon_entry and carbon_entry.usda_verified:
                certifications.append("USDA Verified")
            
            comparison_results.append({
                'id': product.id,
                'name': product.product or "Unknown Product",
                'farm': product.parcel.establishment.name if product.parcel and product.parcel.establishment else "Unknown Farm",
                'location': location,
                'carbon_score': carbon_score,
                'carbon_footprint': carbon_footprint,
                # Price field removed - no pricing data available in database
                # Distance field removed - no location calculation available
                'farming_method': "Organic" if product.parcel and product.parcel.certified else "Conventional",
                # Sustainability rating removed - would need real sustainability metrics calculation
                'certifications': certifications,
            })
        
        # Save comparison for analytics
        if request.user.is_authenticated:
            comparison = UserProductComparison.objects.create(
                user=request.user,
                comparison_data={
                    'product_ids': product_ids,
                    'results': comparison_results,
                    'timestamp': timezone.now().isoformat(),
                }
            )
            comparison.products.set(products)
        
        # Calculate comparison summary with only real data
        valid_scores = [result['carbon_score'] for result in comparison_results if result['carbon_score'] != "Not Available"]
        
        return Response({
            'comparison_id': comparison.id if request.user.is_authenticated else None,
            'products': comparison_results,
            'comparison_summary': {
                'best_carbon_score': min(valid_scores) if valid_scores else "Not Available",
                'total_products': len(comparison_results),
                'verified_products': len([r for r in comparison_results if 'USDA Verified' in r.get('certifications', [])]),
            }
        })
    
    def _update_impact_summary(self, user, impact_summary):
        """Update user impact summary with latest data"""
        # Count scans
        total_scans = HistoryScan.objects.filter(user=user).count()
        
        # Count reviews  
        from reviews.models import Review
        total_reviews = Review.objects.filter(user=user).count()
        
        # Calculate real carbon offset based on actual carbon entries
        from carbon.models import CarbonEntry
        
        total_carbon_offset = 0
        for scan in HistoryScan.objects.filter(user=user).select_related('history'):
            if scan.history:
                try:
                    # Use the same logic as the serializer fix
                    carbon_entry = CarbonEntry.objects.filter(production=scan.history).order_by('-created_at').first()
                    if carbon_entry:
                        # Use co2e_amount if available and non-zero, otherwise fall back to amount
                        co2e = carbon_entry.co2e_amount if carbon_entry.co2e_amount and carbon_entry.co2e_amount > 0 else carbon_entry.amount
                        if co2e and co2e > 0:
                            total_carbon_offset += float(co2e)
                except Exception as e:
                    continue
        
        # Convert to awareness metric rather than false "savings"
        carbon_offset = total_carbon_offset
        
        # Count unique establishments (use parcel__establishment relationship)
        sustainable_farms = HistoryScan.objects.filter(
            user=user,
            history__parcel__certified=True  # Use parcel certified field instead
        ).values('history__parcel__establishment').distinct().count()
        
        # Count local farms based on real data (disable for now until location logic is implemented)
        # For MVP: only count farms with verified local indicators or disable this metric
        local_farms = 0  # Will implement proper location-based calculation later
        
        # Count better choices based on real data
        # For MVP: Count scans where user chose certified/sustainable options
        better_choices = HistoryScan.objects.filter(
            user=user,
            history__parcel__certified=True
        ).count()
        
        # If no certified data available, count scans with verified carbon entries
        if better_choices == 0:
            better_choices = HistoryScan.objects.filter(
                user=user,
                history__carbonentry__usda_verified=True
            ).count()
        
        # Update impact summary
        impact_summary.total_scans = total_scans
        impact_summary.total_reviews = total_reviews
        impact_summary.total_carbon_offset_kg = carbon_offset
        impact_summary.sustainable_farms_found = sustainable_farms
        impact_summary.local_farms_found = local_farms
        impact_summary.better_choices_made = better_choices
        
        # Calculate US-friendly metrics
        impact_summary.calculate_us_friendly_metrics()
        
        # Update timestamps
        first_scan = HistoryScan.objects.filter(user=user).order_by('date').first()
        last_scan = HistoryScan.objects.filter(user=user).order_by('-date').first()
        
        if first_scan:
            impact_summary.first_scan_date = first_scan.date
        if last_scan:
            impact_summary.last_scan_date = last_scan.date
            
        impact_summary.save()
    
    def _get_retailer_recommendations(self):
        """Get retailer recommendations based on user's actual scan history"""
        # For MVP: Disable hardcoded recommendations
        # Future: Generate recommendations based on user's scanned establishments
        return []
    
    def _get_recent_achievements(self, user):
        """Get recent achievements for the user"""
        achievements = []
        
        # Check for scan milestones using configurable thresholds
        scan_count = HistoryScan.objects.filter(user=user).count()
        milestones = EngagementMilestones.SCAN_MILESTONES
        
        if scan_count >= milestones['EXPLORER'] and scan_count < milestones['EXPLORER'] + 5:
            achievements.append({
                'title': 'Scan Explorer',
                'description': f'Scanned {milestones["EXPLORER"]} products!',
                'icon': 'scan',
                'earned_date': timezone.now().date(),
            })
        
        if scan_count >= milestones['COMMITTED'] and scan_count < milestones['COMMITTED'] + 5:
            achievements.append({
                'title': 'Sustainability Detective',
                'description': f'Scanned {milestones["COMMITTED"]} products!',
                'icon': 'detective',
                'earned_date': timezone.now().date(),
            })
        
        return achievements


class UserFavoriteViewSet(viewsets.ModelViewSet):
    """Manage user favorites"""
    serializer_class = UserFavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return UserFavorite.objects.filter(
            user=self.request.user
        ).select_related('production', 'production__parcel__establishment')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def toggle_favorite(self, request):
        """Toggle favorite status for a product"""
        production_id = request.data.get('production_id')
        
        if not production_id:
            return Response(
                {'error': 'production_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            production = History.objects.get(id=production_id)
        except History.DoesNotExist:
            return Response(
                {'error': 'Product not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        favorite, created = UserFavorite.objects.get_or_create(
            user=request.user,
            production=production
        )
        
        if not created:
            favorite.delete()
            return Response({'is_favorite': False, 'message': 'Removed from favorites'})
        else:
            return Response({'is_favorite': True, 'message': 'Added to favorites'})


class UserShoppingGoalViewSet(viewsets.ModelViewSet):
    """Manage user shopping goals"""
    serializer_class = UserShoppingGoalSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return UserShoppingGoal.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)