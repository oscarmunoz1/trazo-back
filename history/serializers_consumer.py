"""
Consumer-specific serializers for API responses
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import History, HistoryScan
from .models_consumer import (
    UserFavorite, 
    UserImpactSummary, 
    UserProductComparison,
    UserShoppingGoal,
    UserShoppingInsight,
    UserLocalRecommendation
)
from carbon.models import CarbonEntry
from company.models import Establishment
from backend.constants import get_carbon_score_from_co2e

User = get_user_model()


class UserFavoriteSerializer(serializers.ModelSerializer):
    """Serialize user favorites with product details"""
    product_name = serializers.CharField(source='production.product', read_only=True)
    farm_name = serializers.CharField(source='production.parcel.establishment.name', read_only=True)
    location = serializers.SerializerMethodField()
    carbon_score = serializers.SerializerMethodField()
    carbon_footprint = serializers.SerializerMethodField()
    production_id = serializers.IntegerField(source='production.id', read_only=True)
    
    class Meta:
        model = UserFavorite
        fields = [
            'id', 'production_id', 'product_name', 'farm_name', 
            'location', 'carbon_score', 'carbon_footprint', 'created_at'
        ]
    
    def get_location(self, obj):
        if obj.production.parcel and obj.production.parcel.establishment:
            establishment = obj.production.parcel.establishment
            return f"{establishment.city}, {establishment.state}" if establishment.city and establishment.state else "Location unavailable"
        return "Location unavailable"
    
    def get_carbon_score(self, obj):
        """Calculate carbon score (A+ to F scale)"""
        # Get latest carbon entry for this production
        carbon_entry = CarbonEntry.objects.filter(
            production=obj.production
        ).order_by('-created_at').first()
        
        if carbon_entry:
            # Use co2e_amount if available and non-zero, otherwise fall back to amount
            co2e = carbon_entry.co2e_amount if carbon_entry.co2e_amount and carbon_entry.co2e_amount > 0 else carbon_entry.amount
            if co2e and co2e > 0:
                co2e = float(co2e)
                return get_carbon_score_from_co2e(co2e)
        return "Not Available"
    
    def get_carbon_footprint(self, obj):
        """Get formatted carbon footprint"""
        carbon_entry = CarbonEntry.objects.filter(
            production=obj.production
        ).order_by('-created_at').first()
        
        if carbon_entry:
            # Use co2e_amount if available and non-zero, otherwise fall back to amount
            co2e = carbon_entry.co2e_amount if carbon_entry.co2e_amount and carbon_entry.co2e_amount > 0 else carbon_entry.amount
            if co2e and co2e > 0:
                co2e = float(co2e)
                return f"{co2e:.2f} kg CO₂e/kg"
        return "Data unavailable"


class UserImpactSummarySerializer(serializers.ModelSerializer):
    """Serialize user impact summary for dashboard"""
    
    class Meta:
        model = UserImpactSummary
        fields = [
            'total_scans', 'total_reviews', 'total_carbon_offset_kg',
            'miles_driving_offset', 'trees_equivalent', 'sustainable_farms_found',
            'local_farms_found', 'better_choices_made', 'achievements_earned',
            'current_level', 'points_earned', 'first_scan_date', 'last_scan_date'
        ]


class EnhancedHistoryScanSerializer(serializers.ModelSerializer):
    """Enhanced serializer for shopping history with rich data"""
    product_name = serializers.CharField(source='history.product', read_only=True)
    farm_name = serializers.CharField(source='history.parcel.establishment.name', read_only=True)
    location = serializers.SerializerMethodField()
    carbon_score = serializers.SerializerMethodField()
    carbon_footprint = serializers.SerializerMethodField()
    carbon_saved = serializers.SerializerMethodField()
    sustainability_practices = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    
    class Meta:
        model = HistoryScan
        fields = [
            'id', 'product_name', 'farm_name', 'location', 'carbon_score',
            'carbon_footprint', 'carbon_saved', 'sustainability_practices',
            'is_verified', 'is_favorite', 'date', 'comment'
        ]
    
    def get_location(self, obj):
        if obj.history.parcel and obj.history.parcel.establishment:
            establishment = obj.history.parcel.establishment
            return f"{establishment.city}, {establishment.state}" if establishment.city and establishment.state else "Location unavailable"
        return "Location unavailable"
    
    def get_carbon_score(self, obj):
        """Calculate carbon score grade"""
        carbon_entry = CarbonEntry.objects.filter(
            production=obj.history
        ).order_by('-created_at').first()
        
        if carbon_entry:
            # Use co2e_amount if available and non-zero, otherwise fall back to amount
            co2e = carbon_entry.co2e_amount if carbon_entry.co2e_amount and carbon_entry.co2e_amount > 0 else carbon_entry.amount
            if co2e and co2e > 0:
                co2e = float(co2e)
                return get_carbon_score_from_co2e(co2e)
        return "Not Available"
    
    def get_carbon_footprint(self, obj):
        """Get formatted carbon footprint"""
        carbon_entry = CarbonEntry.objects.filter(
            production=obj.history
        ).order_by('-created_at').first()
        
        if carbon_entry:
            # Use co2e_amount if available and non-zero, otherwise fall back to amount
            co2e = carbon_entry.co2e_amount if carbon_entry.co2e_amount and carbon_entry.co2e_amount > 0 else carbon_entry.amount
            if co2e and co2e > 0:
                co2e = float(co2e)
                return f"{co2e:.2f} kg CO₂e/kg"
        return "Data unavailable"
    
    def get_carbon_saved(self, obj):
        """Show carbon footprint tracking instead of fake savings"""
        carbon_entry = CarbonEntry.objects.filter(
            production=obj.history
        ).order_by('-created_at').first()
        
        if carbon_entry:
            # Use co2e_amount if available and non-zero, otherwise fall back to amount
            co2e = carbon_entry.co2e_amount if carbon_entry.co2e_amount and carbon_entry.co2e_amount > 0 else carbon_entry.amount
            if co2e and co2e > 0:
                co2e = float(co2e)
                # For MVP: Show the actual footprint being tracked rather than fake "savings"
                return f"{co2e:.1f} kg CO₂e tracked"
        return "Carbon data pending"
    
    def get_sustainability_practices(self, obj):
        """Get real sustainability practices from actual data"""
        practices = []
        
        # Check for organic certification from parcel data
        if obj.history.parcel and obj.history.parcel.certified:
            practices.append("Certified sustainable")
        
        # Check for carbon verification from carbon entries
        carbon_entry = CarbonEntry.objects.filter(
            production=obj.history
        ).order_by('-created_at').first()
        
        if carbon_entry and carbon_entry.usda_verified:
            practices.append("Carbon verified")
        
        # Check if establishment has sustainability certifications
        if obj.history.parcel and obj.history.parcel.establishment:
            establishment = obj.history.parcel.establishment
            # Add more specific checks based on actual establishment data
            if hasattr(establishment, 'certifications') and establishment.certifications:
                practices.append("Farm certified")
        
        # Only return actual verified practices, not mock data
        return practices[:3] if practices else []
    
    def get_is_verified(self, obj):
        """Check if production has verification"""
        return bool(obj.history.parcel and obj.history.parcel.certified)
    
    def get_is_favorite(self, obj):
        """Check if user has favorited this product"""
        user = self.context.get('request').user if self.context.get('request') else None
        if user and user.is_authenticated:
            return UserFavorite.objects.filter(
                user=user, 
                production=obj.history
            ).exists()
        return False


class ProductComparisonSerializer(serializers.Serializer):
    """Serializer for product comparison data"""
    products = serializers.ListField(
        child=serializers.IntegerField(),
        max_length=5,
        min_length=2
    )
    
    def validate_products(self, value):
        """Validate that all products exist"""
        existing_products = History.objects.filter(id__in=value).count()
        if existing_products != len(value):
            raise serializers.ValidationError("One or more products not found")
        return value


class ProductComparisonResultSerializer(serializers.Serializer):
    """Serializer for comparison results"""
    id = serializers.IntegerField()
    name = serializers.CharField()
    farm = serializers.CharField()
    location = serializers.CharField()
    carbon_score = serializers.CharField()
    carbon_footprint = serializers.CharField()
    farming_method = serializers.CharField()
    certifications = serializers.ListField()
    # Removed: price, distance, sustainability_rating (no real data available)


class UserShoppingGoalSerializer(serializers.ModelSerializer):
    """Serialize user shopping goals"""
    progress_percentage = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = UserShoppingGoal
        fields = [
            'id', 'goal_type', 'title', 'description', 'target_value',
            'current_value', 'unit', 'start_date', 'target_date',
            'status', 'progress_percentage', 'is_completed', 'days_remaining'
        ]
    
    def get_days_remaining(self, obj):
        """Calculate days remaining to target date"""
        from django.utils import timezone
        today = timezone.now().date()
        if obj.target_date > today:
            return (obj.target_date - today).days
        return 0


class UserShoppingInsightSerializer(serializers.ModelSerializer):
    """Serialize user shopping insights"""
    
    class Meta:
        model = UserShoppingInsight
        fields = [
            'id', 'insight_type', 'title', 'description', 'data',
            'is_read', 'created_at', 'expires_at'
        ]


class UserLocalRecommendationSerializer(serializers.ModelSerializer):
    """Serialize local recommendations"""
    establishment_name = serializers.CharField(source='establishment.name', read_only=True)
    establishment_address = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UserLocalRecommendation
        fields = [
            'id', 'establishment_name', 'establishment_address', 'distance_miles',
            'carbon_score', 'recommendation_score', 'product_count', 'is_favorited'
        ]
    
    def get_establishment_address(self, obj):
        """Get establishment address"""
        if obj.establishment.parcel_set.exists():
            parcel = obj.establishment.parcel_set.first()
            return f"{parcel.city}, {parcel.state}" if parcel.city and parcel.state else "Address unavailable"
        return "Address unavailable"
    
    def get_product_count(self, obj):
        """Get number of recommended products"""
        return obj.recommended_products.count()