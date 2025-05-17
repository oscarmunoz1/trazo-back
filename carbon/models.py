from django.db import models
from company.models import Establishment
from history.models import History
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

# Create your models here.

class CarbonSource(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text='e.g., Citrus Fertilizer')
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=50, help_text="e.g. kg CO2e, liters, kWh")
    category = models.CharField(max_length=50, help_text='e.g., Fuel, Offset')
    default_emission_factor = models.FloatField(help_text='kg CO2e per unit, USDA-aligned', default=0.0)
    usda_verified = models.BooleanField(default=False, help_text='Whether this source is verified by USDA')
    cost_per_unit = models.FloatField(default=0.0, help_text='Cost per unit for ROI calculations')
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['usda_verified'])
        ]

    def __str__(self):
        return self.name

class CarbonOffsetAction(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=50, help_text="e.g. trees planted, tons CO2 offset")
    verification_required = models.BooleanField(default=False)
    verification_process = models.TextField(blank=True)
    cost_per_unit = models.FloatField(default=0.0, help_text='Cost per unit for ROI calculations')
    usda_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class CarbonEntry(models.Model):
    TYPE_CHOICES = (
        ('emission', 'Emission'),
        ('offset', 'Offset'),
    )
    establishment = models.ForeignKey('company.Establishment', on_delete=models.CASCADE, null=True, blank=True)
    production = models.ForeignKey('history.History', on_delete=models.CASCADE, null=True, blank=True)
    created_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    source = models.ForeignKey('CarbonSource', on_delete=models.SET_NULL, null=True)
    amount = models.FloatField(help_text='Amount in kg CO2e')
    co2e_amount = models.FloatField(default=0.0, help_text='Amount in CO2 equivalent')
    year = models.IntegerField()
    timestamp = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True)
    cost = models.FloatField(default=0.0, help_text='Associated cost for ROI calculations')
    iot_device_id = models.CharField(max_length=100, blank=True, help_text='ID of IoT device if automated entry')
    usda_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(establishment__isnull=False) | models.Q(production__isnull=False),
                name='either_establishment_or_production_set'
            )
        ]
        indexes = [
            models.Index(fields=['establishment']),
            models.Index(fields=['production']),
            models.Index(fields=['year']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['iot_device_id']),
            models.Index(fields=['usda_verified'])
        ]

    def __str__(self):
        return f"{self.type.capitalize()} - {self.amount} ({self.timestamp})"

class CarbonCertification(models.Model):
    establishment = models.ForeignKey('company.Establishment', on_delete=models.CASCADE, null=True, blank=True)
    production = models.ForeignKey('history.History', on_delete=models.CASCADE, null=True, blank=True)
    certifier = models.CharField(max_length=100, help_text='e.g., USDA Organic', default='Unknown')
    certificate_id = models.CharField(max_length=50, unique=True, default='TEMP_ID')
    issue_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(null=True, blank=True)
    document = models.FileField(upload_to='certifications/', null=True, blank=True)
    is_usda_soe_verified = models.BooleanField(default=False)
    verification_date = models.DateField(null=True, blank=True)
    verification_details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(establishment__isnull=False) | models.Q(production__isnull=False),
                name='either_establishment_or_production_set_certification'
            )
        ]
        indexes = [
            models.Index(fields=['is_usda_soe_verified']),
            models.Index(fields=['verification_date'])
        ]

    def __str__(self):
        return f'{self.certificate_id} ({self.establishment.name if self.establishment else "N/A"})'

class CarbonBenchmark(models.Model):
    industry = models.CharField(max_length=100)
    year = models.PositiveIntegerField()
    average_emissions = models.FloatField()
    min_emissions = models.FloatField(default=0.0)
    max_emissions = models.FloatField(default=0.0)
    company_count = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=50)
    source = models.CharField(max_length=200)
    last_updated = models.DateField(auto_now=True)
    usda_verified = models.BooleanField(default=False)
    crop_type = models.CharField(max_length=100, blank=True, help_text='Specific crop type if applicable')
    region = models.CharField(max_length=100, blank=True, help_text='Geographic region if applicable')
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('industry', 'year', 'crop_type', 'region')
        indexes = [
            models.Index(fields=['crop_type']),
            models.Index(fields=['region']),
            models.Index(fields=['usda_verified'])
        ]

    def __str__(self):
        return f'Benchmark {self.industry} - {self.year}'

class CarbonReport(models.Model):
    establishment = models.ForeignKey('company.Establishment', on_delete=models.CASCADE, null=True, blank=True)
    production = models.ForeignKey('history.History', on_delete=models.CASCADE, null=True, blank=True)
    period_start = models.DateField(default='2023-01-01')
    period_end = models.DateField(default='2023-12-31')
    total_emissions = models.FloatField(default=0.0)
    total_offsets = models.FloatField(default=0.0)
    net_footprint = models.FloatField(default=0.0)
    carbon_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Score from 1 to 100'
    )
    generated_at = models.DateTimeField(default=timezone.now)
    usda_verified = models.BooleanField(default=False)
    cost_savings = models.FloatField(default=0.0, help_text='Cost savings achieved')
    recommendations = models.JSONField(default=list, help_text='List of cost-saving recommendations')
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(establishment__isnull=False) | models.Q(production__isnull=False),
                name='either_establishment_or_production_set_report'
            )
        ]
        indexes = [
            models.Index(fields=['usda_verified']),
            models.Index(fields=['carbon_score']),
            models.Index(fields=['cost_savings'])
        ]

    def __str__(self):
        return f'{self.establishment.name if self.establishment else "N/A"} - {self.period_start} to {self.period_end}'

class CarbonAuditLog(models.Model):
    carbon_entry = models.ForeignKey(CarbonEntry, on_delete=models.CASCADE, related_name='audit_logs', null=True, blank=True)
    certification = models.ForeignKey(CarbonCertification, on_delete=models.CASCADE, related_name='audit_logs', null=True, blank=True)
    report = models.ForeignKey(CarbonReport, on_delete=models.CASCADE, related_name='audit_logs', null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=50, choices=[
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('verify', 'Verify')
    ])
    timestamp = models.DateTimeField(auto_now=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['action']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['ip_address'])
        ]

    def __str__(self):
        return f'{self.action} by {self.user} at {self.timestamp}'

class SustainabilityBadge(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text='e.g., Gold Tier')
    criteria = models.JSONField(default=dict, help_text='Criteria for badge award, e.g., net_footprint < 0')
    icon = models.FileField(upload_to='badges/', null=True, blank=True)
    description = models.TextField(blank=True)
    usda_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['usda_verified'])
        ]

    def __str__(self):
        return self.name

class MicroOffset(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    production = models.ForeignKey('history.History', on_delete=models.CASCADE)
    amount = models.FloatField(validators=[MinValueValidator(0.05), MaxValueValidator(0.10)])
    provider = models.CharField(max_length=50, default='wren')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at'])
        ]

    def __str__(self):
        return f'Offset {self.amount} by {self.user} for {self.production}'

class GreenPoints(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    points = models.IntegerField(default=0)
    last_scan = models.DateTimeField(null=True, blank=True)
    achievements = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['points']),
            models.Index(fields=['last_scan'])
        ]

    def __str__(self):
        return f'{self.user} - {self.points} points'

class CarbonOffsetProject(models.Model):
    """Model for carbon offset projects available in the marketplace"""
    name = models.CharField(max_length=255)
    description = models.TextField()
    project_type = models.CharField(max_length=100)
    certification_standard = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    price_per_ton = models.DecimalField(max_digits=10, decimal_places=2)
    available_capacity = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class CarbonOffsetPurchase(models.Model):
    """Model for tracking carbon offset purchases"""
    project = models.ForeignKey(CarbonOffsetProject, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_ton = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='pending')
    is_verified = models.BooleanField(default=False)
    certificate_file = models.FileField(upload_to='certificates/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    certificate_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    def __str__(self):
        return f"{self.user.username} - {self.project.name} - {self.amount} tons"

    def save(self, *args, **kwargs):
        if not self.total_price:
            self.total_price = self.amount * self.price_per_ton
        super().save(*args, **kwargs)

class CarbonOffsetCertificate(models.Model):
    """Model for carbon offset certificates"""
    purchase = models.OneToOneField(CarbonOffsetPurchase, on_delete=models.CASCADE)
    certificate_number = models.CharField(max_length=100, unique=True)
    verification_code = models.CharField(max_length=100, unique=True)
    certificate_url = models.URLField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.certificate_number
