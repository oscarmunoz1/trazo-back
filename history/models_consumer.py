"""
Consumer-specific models for enhanced user experience
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from backend.constants import calculate_miles_equivalent, calculate_trees_equivalent

User = get_user_model()


class UserFavorite(models.Model):
    """Track user's favorite products/establishments"""
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='favorites'
    )
    production = models.ForeignKey(
        'history.History', 
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'production')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.production.product}"


class UserImpactSummary(models.Model):
    """Aggregate user impact metrics for dashboard"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='impact_summary'
    )
    
    # Core Impact Metrics
    total_scans = models.IntegerField(default=0)
    total_reviews = models.IntegerField(default=0)
    total_carbon_offset_kg = models.FloatField(default=0.0)  # kg CO2e saved
    total_money_saved_usd = models.FloatField(default=0.0)  # USD saved through better choices
    
    # US-Friendly Metrics
    miles_driving_offset = models.FloatField(default=0.0)  # Miles of driving offset
    trees_equivalent = models.FloatField(default=0.0)  # Trees planted equivalent
    
    # Engagement Metrics
    sustainable_farms_found = models.IntegerField(default=0)
    local_farms_found = models.IntegerField(default=0)
    better_choices_made = models.IntegerField(default=0)
    
    # Achievement Tracking
    achievements_earned = models.JSONField(default=list)
    current_level = models.IntegerField(default=1)
    points_earned = models.IntegerField(default=0)
    
    # Tracking
    first_scan_date = models.DateTimeField(null=True, blank=True)
    last_scan_date = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def calculate_us_friendly_metrics(self):
        """Convert carbon awareness data to US consumer-friendly units"""
        # For MVP: Show carbon footprint awareness instead of fake "offset"
        # The total_carbon_offset_kg now represents total carbon tracked, not "saved"
        
        if self.total_carbon_offset_kg > 0:
            # Convert to miles equivalent using EPA standards for context (not as "offset" but as awareness)
            # This shows the equivalent driving impact of the carbon they're tracking
            self.miles_driving_offset = round(calculate_miles_equivalent(self.total_carbon_offset_kg), 1)
            
            # Trees equivalent for carbon absorption context using EPA standards
            self.trees_equivalent = round(calculate_trees_equivalent(self.total_carbon_offset_kg), 1)
        else:
            self.miles_driving_offset = 0
            self.trees_equivalent = 0
        
    def add_scan_impact(self, carbon_saved_kg, is_better_choice=True, is_local=False):
        """Add impact from a new scan"""
        self.total_scans += 1
        self.total_carbon_offset_kg += carbon_saved_kg
        
        if is_better_choice:
            self.better_choices_made += 1
            
        if is_local:
            self.local_farms_found += 1
            
        self.last_scan_date = timezone.now()
        if not self.first_scan_date:
            self.first_scan_date = timezone.now()
            
        self.calculate_us_friendly_metrics()
        self.save()
    
    def __str__(self):
        return f"{self.user.email} - {self.total_scans} scans, {self.miles_driving_offset} miles offset"


class UserProductComparison(models.Model):
    """Store product comparison sessions for analytics"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comparisons'
    )
    comparison_name = models.CharField(max_length=200, blank=True)
    products = models.ManyToManyField(
        'history.History',
        related_name='compared_in'
    )
    comparison_data = models.JSONField(default=dict)  # Store comparison results
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - Comparison {self.id} ({self.products.count()} products)"


class UserShoppingGoal(models.Model):
    """User-defined sustainability goals"""
    GOAL_TYPES = [
        ('carbon_reduction', 'Reduce Carbon Footprint'),
        ('local_shopping', 'Shop Local'),
        ('sustainable_farms', 'Support Sustainable Farms'),
        ('scan_products', 'Scan Products'),
        ('money_savings', 'Save Money'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shopping_goals'
    )
    goal_type = models.CharField(max_length=50, choices=GOAL_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Goal Metrics
    target_value = models.FloatField()
    current_value = models.FloatField(default=0.0)
    unit = models.CharField(max_length=50)  # 'kg CO2e', 'products', 'farms', etc.
    
    # Timeline
    start_date = models.DateField(default=timezone.now)
    target_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def progress_percentage(self):
        """Calculate goal completion percentage"""
        if self.target_value == 0:
            return 0
        return min(100, (self.current_value / self.target_value) * 100)
    
    @property
    def is_completed(self):
        """Check if goal is completed"""
        return self.current_value >= self.target_value
    
    def update_progress(self, new_value):
        """Update goal progress"""
        self.current_value = new_value
        if self.is_completed and self.status == 'active':
            self.status = 'completed'
            self.completed_date = timezone.now().date()
        self.save()
    
    def __str__(self):
        return f"{self.user.email} - {self.title} ({self.progress_percentage:.1f}%)"


class UserShoppingInsight(models.Model):
    """Personal shopping insights and recommendations"""
    INSIGHT_TYPES = [
        ('trend', 'Shopping Trend'),
        ('recommendation', 'Product Recommendation'),
        ('achievement', 'Achievement Unlock'),
        ('tip', 'Sustainability Tip'),
        ('milestone', 'Milestone Reached'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shopping_insights'
    )
    insight_type = models.CharField(max_length=50, choices=INSIGHT_TYPES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    data = models.JSONField(default=dict)  # Additional insight data
    
    # Engagement
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"


class UserLocalRecommendation(models.Model):
    """Recommendations for local sustainable products/farms"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='local_recommendations'
    )
    establishment = models.ForeignKey(
        'company.Establishment',
        on_delete=models.CASCADE,
        related_name='recommended_to'
    )
    recommended_products = models.ManyToManyField(
        'history.History',
        related_name='recommended_to_users',
        blank=True
    )
    
    # Recommendation Metrics
    distance_miles = models.FloatField()
    carbon_score = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    recommendation_score = models.FloatField()  # Algorithm-generated score
    
    # User Interaction
    is_viewed = models.BooleanField(default=False)
    is_favorited = models.BooleanField(default=False)
    view_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'establishment')
        ordering = ['-recommendation_score']
    
    def __str__(self):
        return f"{self.user.email} - {self.establishment.name} ({self.distance_miles} miles)"