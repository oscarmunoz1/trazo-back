from django.db import models
from company.models import Establishment
from history.models import History
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
from datetime import timedelta

# Create your models here.

class CarbonSource(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text='e.g., Citrus Fertilizer')
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=50, help_text="e.g. kg CO2e, liters, kWh")
    category = models.CharField(max_length=50, help_text='e.g., Fuel, Offset')
    default_emission_factor = models.FloatField(help_text='kg CO2e per unit, USDA-aligned', default=0.0)
    usda_verified = models.BooleanField(default=False, help_text='Whether this source is verified by USDA')
    # New fields for better verification tracking
    usda_factors_based = models.BooleanField(default=False, help_text='Whether calculations use USDA emission factors')
    verification_status = models.CharField(max_length=50, default='estimated', help_text='factors_verified, estimated, calculation_error')
    data_source = models.CharField(max_length=200, default='Unknown', help_text='Source of emission factors (e.g., USDA Agricultural Research Service)')
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['usda_verified']),
            models.Index(fields=['usda_factors_based']),
            models.Index(fields=['verification_status'])
        ]

    def __str__(self):
        return self.name

class CarbonOffsetAction(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=50, help_text="e.g. trees planted, tons CO2 offset")
    verification_required = models.BooleanField(default=False)
    verification_process = models.TextField(blank=True)
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
    iot_device_id = models.CharField(max_length=100, blank=True, help_text='ID of IoT device if automated entry')
    usda_verified = models.BooleanField(default=False)
    # New fields for better verification tracking
    usda_factors_based = models.BooleanField(default=False, help_text='Whether calculations use USDA emission factors')
    verification_status = models.CharField(max_length=50, default='estimated', help_text='factors_verified, estimated, calculation_error')
    data_source = models.CharField(max_length=200, default='Unknown', help_text='Source of emission factors (e.g., USDA Agricultural Research Service)')
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
            models.Index(fields=['usda_verified']),
            models.Index(fields=['usda_factors_based']),
            models.Index(fields=['verification_status'])
        ]

    def __str__(self):
        return f"{self.type.capitalize()} - {self.amount} ({self.timestamp})"

    @classmethod
    def calculate_carbon_score(cls, total_emissions, total_offsets, industry_benchmark=None):
        """
        Calculate a carbon score on a scale of 1-100.
        100 is the best (carbon negative), 50 is neutral, <50 is carbon positive.
        
        Args:
            total_emissions: Total emissions in kg CO2e
            total_offsets: Total offsets in kg CO2e
            industry_benchmark: Industry average emissions (optional)
            
        Returns:
            int: Carbon score from 1-100
        """
        # If no emissions or offsets, return neutral score
        if total_emissions == 0 and total_offsets == 0:
            return 50
            
        net_carbon = total_emissions - total_offsets
        
        # If carbon negative (more offsets than emissions)
        if net_carbon <= 0:
            # Scale from 50 (neutral) to 100 (highly negative)
            # The more negative, the higher the score
            if total_emissions == 0:
                return 100  # Perfect score if no emissions but has offsets
            
            # Calculate how much more offsets than emissions (as percentage)
            offset_ratio = abs(net_carbon) / total_emissions
            
            # Cap at 100% (or 2x emissions) for max score
            offset_ratio = min(offset_ratio, 1.0)
            
            # Scale from 50 to 100
            return int(50 + (offset_ratio * 50))
        
        # If carbon positive (more emissions than offsets)
        else:
            # If we have an industry benchmark to compare against
            if industry_benchmark and industry_benchmark > 0:
                # If better than industry average
                if net_carbon < industry_benchmark:
                    ratio = net_carbon / industry_benchmark
                    # Scale from 25 to 50 (50 being carbon neutral)
                    return int(50 - (ratio * 25))
                # If worse than industry average
                else:
                    ratio = min(net_carbon / industry_benchmark, 2.0)  # Cap at 2x industry average
                    # Scale from 1 to 25
                    return max(1, int(25 - (ratio - 1) * 24))
            
            # Without industry benchmark, use a simple ratio
            else:
                # Calculate ratio of offsets to emissions
                offset_ratio = total_offsets / total_emissions if total_emissions > 0 else 0
                # Scale from 1 to 50 (50 being carbon neutral)
                return int(offset_ratio * 50)

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
    document = models.FileField(upload_to='carbon_reports/', null=True, blank=True, help_text='Report document file')
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
            models.Index(fields=['carbon_score'])
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
    description = models.TextField(blank=True)
    criteria = models.JSONField(default=dict, help_text='Criteria for badge award, e.g., net_footprint < 0')
    icon = models.FileField(upload_to='badges/', null=True, blank=True)
    minimum_score = models.IntegerField(default=0, help_text='Minimum carbon score to automatically award this badge')
    is_automatic = models.BooleanField(default=False, help_text='Whether to automatically award this badge based on score')
    establishments = models.ManyToManyField('company.Establishment', related_name='badges', blank=True)
    productions = models.ManyToManyField('history.History', related_name='badges', blank=True)
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

# IoT Device Management Models

class IoTDevice(models.Model):
    """Model for tracking IoT devices connected to establishments."""
    
    DEVICE_TYPES = [
        ('fuel_sensor', 'Fuel Consumption Sensor'),
        ('weather_station', 'Weather Station'),
        ('soil_moisture', 'Soil Moisture Sensor'),
        ('irrigation', 'Irrigation Controller'),
        ('equipment_monitor', 'Equipment Monitor'),
        ('gps_tracker', 'GPS Tracker'),
    ]
    
    STATUS_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('maintenance', 'Under Maintenance'),
        ('error', 'Error State'),
    ]
    
    device_id = models.CharField(max_length=100, unique=True, help_text="Unique device identifier")
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES)
    establishment = models.ForeignKey('company.Establishment', on_delete=models.CASCADE, related_name='iot_devices')
    name = models.CharField(max_length=200, help_text="Human-readable device name")
    manufacturer = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    
    # Status and monitoring
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    last_seen = models.DateTimeField(null=True, blank=True)
    battery_level = models.IntegerField(null=True, blank=True, help_text="Battery percentage (0-100)")
    signal_strength = models.CharField(max_length=20, blank=True, help_text="Signal strength indicator")
    
    # Location and configuration
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    configuration = models.JSONField(default=dict, help_text="Device-specific configuration")
    
    # John Deere API Integration
    john_deere_machine_id = models.CharField(max_length=100, null=True, blank=True, help_text="John Deere machine ID for API integration")
    last_api_sync = models.DateTimeField(null=True, blank=True, help_text="Last successful API synchronization")
    api_connection_status = models.CharField(max_length=20, default='disconnected', choices=[
        ('connected', 'Connected'),
        ('disconnected', 'Disconnected'),
        ('error', 'Connection Error'),
        ('pending', 'Connection Pending'),
    ], help_text="Status of API connection")
    api_error_message = models.TextField(blank=True, help_text="Last API error message if any")
    
    # Metadata
    installed_date = models.DateTimeField(auto_now_add=True)
    last_maintenance = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Data tracking
    total_data_points = models.IntegerField(default=0)
    last_data_received = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'carbon_iot_device'
        ordering = ['establishment', 'device_type', 'name']
        
    def __str__(self):
        return f"{self.name} ({self.device_id}) - {self.establishment.name}"
    
    def update_status(self, status='online'):
        """Update device status and last seen timestamp."""
        self.status = status
        self.last_seen = timezone.now()
        if status == 'online':
            self.last_data_received = timezone.now()
        self.save(update_fields=['status', 'last_seen', 'last_data_received'])
    
    def increment_data_points(self):
        """Increment the total data points counter."""
        self.total_data_points += 1
        self.last_data_received = timezone.now()
        self.save(update_fields=['total_data_points', 'last_data_received'])
    
    @property
    def is_online(self):
        """Check if device is considered online (data received within last hour)."""
        if not self.last_seen:
            return False
        return timezone.now() - self.last_seen < timedelta(hours=1)
    
    @property
    def needs_maintenance(self):
        """Check if device needs maintenance based on battery or last maintenance date."""
        if self.battery_level and self.battery_level < 20:
            return True
        if self.last_maintenance:
            return timezone.now() - self.last_maintenance > timedelta(days=90)
        return timezone.now() - self.installed_date > timedelta(days=90)


class IoTDataPoint(models.Model):
    """Model for storing raw IoT data points."""
    
    device = models.ForeignKey(IoTDevice, on_delete=models.CASCADE, related_name='data_points')
    timestamp = models.DateTimeField()
    data = models.JSONField(help_text="Raw sensor data")
    processed = models.BooleanField(default=False, help_text="Whether this data has been processed into carbon entries")
    
    # Optional carbon entry link if this data point created a carbon entry
    carbon_entry = models.ForeignKey(CarbonEntry, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Data quality indicators
    quality_score = models.FloatField(default=1.0, help_text="Data quality score (0.0-1.0)")
    anomaly_detected = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'carbon_iot_data_point'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['device', '-timestamp']),
            models.Index(fields=['processed', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.device.device_id} - {self.timestamp}"
    
    def mark_processed(self, carbon_entry=None):
        """Mark this data point as processed."""
        self.processed = True
        if carbon_entry:
            self.carbon_entry = carbon_entry
        self.save(update_fields=['processed', 'carbon_entry'])


class AutomationRule(models.Model):
    """Model for defining automation rules based on IoT data."""
    
    TRIGGER_TYPES = [
        ('threshold', 'Threshold Trigger'),
        ('pattern', 'Pattern Recognition'),
        ('schedule', 'Scheduled Trigger'),
        ('weather', 'Weather Condition'),
        ('combination', 'Multiple Conditions'),
    ]
    
    ACTION_TYPES = [
        ('create_event', 'Create Carbon Event'),
        ('send_alert', 'Send Alert'),
        ('update_status', 'Update Status'),
        ('trigger_webhook', 'Trigger Webhook'),
        ('generate_report', 'Generate Report'),
    ]
    
    name = models.CharField(max_length=200)
    establishment = models.ForeignKey('company.Establishment', on_delete=models.CASCADE, related_name='automation_rules')
    device_type = models.CharField(max_length=20, choices=IoTDevice.DEVICE_TYPES, blank=True, help_text="Apply to specific device type")
    
    # Rule configuration
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPES)
    trigger_config = models.JSONField(help_text="Trigger configuration (thresholds, patterns, etc.)")
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    action_config = models.JSONField(help_text="Action configuration")
    
    # Rule status
    is_active = models.BooleanField(default=True)
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('users.User', on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'carbon_automation_rule'
        ordering = ['establishment', 'name']
    
    def __str__(self):
        return f"{self.name} - {self.establishment.name}"
    
    def evaluate_trigger(self, data_point):
        """Evaluate if this rule should trigger based on a data point."""
        if not self.is_active:
            return False
        
        # Implementation would depend on trigger_type and trigger_config
        # This is a simplified example
        if self.trigger_type == 'threshold':
            field = self.trigger_config.get('field')
            threshold = self.trigger_config.get('threshold')
            operator = self.trigger_config.get('operator', 'gt')
            
            if field in data_point.data:
                value = data_point.data[field]
                if operator == 'gt' and value > threshold:
                    return True
                elif operator == 'lt' and value < threshold:
                    return True
                elif operator == 'eq' and value == threshold:
                    return True
        
        return False
    
    def execute_action(self, data_point):
        """Execute the action defined by this rule."""
        if self.action_type == 'create_event':
            # Create a carbon entry based on the action config
            event_config = self.action_config
            CarbonEntry.objects.create(
                establishment=self.establishment,
                type=event_config.get('type', 'emission'),
                source=event_config.get('source', f'Auto: {self.name}'),
                amount=event_config.get('amount', 0),
                year=timezone.now().year,
                description=f'Auto-generated from rule: {self.name}',
                created_by=self.created_by
            )
        
        # Update trigger statistics
        self.last_triggered = timezone.now()
        self.trigger_count += 1
        self.save(update_fields=['last_triggered', 'trigger_count'])
