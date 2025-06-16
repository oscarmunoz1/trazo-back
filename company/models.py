from django.db import models
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.conf import settings
from django.utils import timezone


class Company(models.Model):
    name = models.CharField(max_length=30)
    tradename = models.CharField(max_length=30, blank=True, null=True)
    address = models.CharField(max_length=30)
    city = models.CharField(max_length=30)
    state = models.CharField(max_length=30)
    country = models.CharField(max_length=30, blank=True, null=True)
    fiscal_id = models.CharField(max_length=30, help_text="RUT", blank=True, null=True)
    logo = models.ImageField(upload_to="company_logos", blank=True)
    description = models.TextField(blank=True, null=True)
    invitation_code = models.CharField(max_length=30, blank=True, null=True)
    contact_email = models.EmailField(max_length=254, blank=True, null=True)
    contact_phone = models.CharField(max_length=30, blank=True, null=True)
    website = models.URLField(max_length=200, blank=True, null=True)
    facebook = models.URLField(max_length=200, blank=True, null=True)
    instagram = models.URLField(max_length=200, blank=True, null=True)
    certifications = models.TextField(blank=True, null=True)
    
    # Additional business fields
    zip_code = models.CharField(max_length=20, blank=True, null=True, help_text="Postal/ZIP code")
    employee_count = models.PositiveIntegerField(blank=True, null=True, help_text="Number of employees")
    industry = models.CharField(max_length=100, blank=True, null=True, help_text="Primary agricultural industry")
    is_active = models.BooleanField(default=True, help_text="Whether the company is active")
    
    # Sustainability and carbon tracking metadata
    sustainability_metadata = models.JSONField(
        blank=True, 
        null=True, 
        help_text="JSON data containing crop selection, sustainability goals, and carbon benchmarks"
    )
    
    # Blockchain subscription status
    blockchain_subscription_status = models.BooleanField(
        default=False, 
        help_text="Whether company has active blockchain verification subscription"
    )

    class Meta:
        verbose_name = _("Company")
        verbose_name_plural = _("Companies")

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("company-detail", kwargs={"id": self.id})

    # Subscription-related methods
    @property
    def subscription_plan(self):
        """Get the current subscription plan for this company"""
        try:
            if hasattr(self, 'subscription') and self.subscription.status in ['active', 'trialing']:
                return self.subscription.plan
            return None
        except:
            return None
    
    def get_feature_limit(self, feature_name, default=0):
        """Get limit for a specific feature from subscription plan"""
        if not self.subscription_plan:
            return default
        
        features = self.subscription_plan.features
        return features.get(feature_name, default)
    
    def has_feature(self, feature_name):
        """Check if company has access to a specific feature"""
        if not self.subscription_plan:
            return False
        
        features = self.subscription_plan.features
        return features.get(feature_name, False)
    
    def can_create_establishment(self):
        """Check if company can create more establishments"""
        current_count = self.establishment_set.count()
        max_allowed = self.get_feature_limit('max_establishments', 0)
        return current_count < max_allowed
    
    def can_create_parcel(self, establishment=None):
        """Check if company can create more parcels"""
        plan = self.subscription_plan
        if not plan:
            print(f"Company {self.id} has no subscription plan")
            return False
        
        features = plan.features
        print(f"Company {self.id} subscription features: {features}")
        
        # For Corporate plan with parcels per establishment limit
        if features.get('max_parcels_per_establishment', 0) > 0 and establishment:
            current_count = establishment.parcel_set.count()
            max_allowed = features.get('max_parcels_per_establishment', 0)
            print(f"Checking parcels per establishment: current={current_count}, max={max_allowed}")
            return current_count < max_allowed
        
        # For Basic/Standard plans with total parcel limit
        if features.get('max_parcels', 0) > 0:
            total_parcels = sum(est.parcel_set.count() for est in self.establishment_set.all())
            max_allowed = features.get('max_parcels', 0)
            # Add purchased add-ons
            if hasattr(self, 'subscription'):
                extra_parcels = sum(
                    addon.quantity 
                    for addon in self.subscription.addons.filter(addon__slug='extra-parcel')
                )
                max_allowed += extra_parcels
            print(f"Checking total parcels: current={total_parcels}, max={max_allowed}")
            return total_parcels < max_allowed
        
        print(f"No parcel limit found in features")
        return False
    
    def can_create_production(self):
        """Check if company can create more productions this year"""
        if not self.subscription_plan:
            return False
        
        # Calculate current year's productions
        start_of_year = timezone.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        productions_this_year = 0
        
        # Count productions created this year across all establishments and parcels
        for establishment in self.establishment_set.all():
            for parcel in establishment.parcel_set.all():
                # Adjust this query based on your actual production model
                productions_this_year += parcel.production_set.filter(
                    created_at__gte=start_of_year
                ).count()
        
        # Get base limit from plan
        max_productions = self.get_feature_limit('max_productions_per_year', 0)
        
        # Add purchased add-ons
        if hasattr(self, 'subscription'):
            extra_productions = sum(
                addon.quantity 
                for addon in self.subscription.addons.filter(addon__slug='extra-production')
            )
            max_productions += extra_productions
        
        return productions_this_year < max_productions
    
    def get_remaining_scan_quota(self):
        """Get remaining scan quota for the current month"""
        if not self.subscription_plan:
            return 0
        
        base_quota = self.get_feature_limit('monthly_scan_limit', 5000)
        
        # Get current month's usage
        if hasattr(self, 'subscription'):
            current_usage = self.subscription.scan_count
            return max(0, base_quota - current_usage)
        
        return base_quota
    
    def get_storage_limit_gb(self):
        """Get storage limit in GB"""
        if not self.subscription_plan:
            return 0
        
        base_limit = self.get_feature_limit('storage_limit_gb', 10)
        
        # Add purchased storage add-ons
        if hasattr(self, 'subscription'):
            extra_storage = sum(
                addon.quantity 
                for addon in self.subscription.addons.filter(addon__slug='extra-storage')
            )
            base_limit += extra_storage
        
        return base_limit


class Establishment(models.Model):
    name = models.CharField(max_length=30)
    address = models.CharField(max_length=30)
    city = models.CharField(max_length=30, blank=True, null=True)
    zone = models.CharField(max_length=30, blank=True, null=True)
    state = models.CharField(max_length=30)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    album = models.ForeignKey(
        "common.Gallery", on_delete=models.CASCADE, blank=True, null=True
    )
    description = models.TextField(blank=True, null=True)
    country = models.CharField(max_length=30, blank=True, null=True)
    type = models.CharField(max_length=30, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    contact_person = models.CharField(max_length=60, blank=True, null=True)
    contact_phone = models.CharField(max_length=30, blank=True, null=True)
    contact_email = models.EmailField(max_length=254, blank=True, null=True)
    facebook = models.URLField(max_length=200, blank=True, null=True)
    instagram = models.URLField(max_length=200, blank=True, null=True)
    certifications = models.TextField(blank=True, null=True)
    about = models.TextField(blank=True, null=True)
    main_activities = models.TextField(blank=True, null=True)
    location_highlights = models.TextField(blank=True, null=True)
    custom_message = models.TextField(blank=True, null=True)

    # New valuable fields
    email = models.EmailField(max_length=254, blank=True, null=True, help_text="Main establishment email")
    phone = models.CharField(max_length=30, blank=True, null=True, help_text="Main establishment phone")
    zip_code = models.CharField(max_length=20, blank=True, null=True, help_text="Postal/ZIP code")
    is_active = models.BooleanField(default=True, help_text="Whether the establishment is active")
    crops_grown = models.JSONField(default=list, blank=True, help_text="List of crops grown at this establishment")
    sustainability_practices = models.JSONField(default=list, blank=True, help_text="List of sustainability practices")
    employee_count = models.PositiveIntegerField(blank=True, null=True, help_text="Number of employees")
    total_acreage = models.FloatField(blank=True, null=True, help_text="Total land area in acres")
    year_established = models.PositiveIntegerField(blank=True, null=True, help_text="Year the establishment was founded")
    establishment_type = models.CharField(max_length=50, blank=True, null=True, help_text="Type of agricultural operation")
    farming_method = models.CharField(max_length=50, blank=True, null=True, help_text="Primary farming approach")

    class Meta:
        verbose_name = _("Establishment")
        verbose_name_plural = _("Establishments")

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("establishment-detail", kwargs={"id": self.id})

    def get_location(self) -> str:
        return f"{self.city if self.city is not None else '-'}, {self.country if self.country is not None else '-'}"
