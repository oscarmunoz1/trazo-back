from django.db import models
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.conf import settings
from company.models import Company

class Plan(models.Model):
    """Subscription plan model"""
    INTERVAL_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    name = models.CharField(max_length=50)  # Basic, Standard, Corporate, Enterprise
    slug = models.SlugField(unique=True)    # basic, standard, corporate, enterprise
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES, default='monthly')
    features = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Plan")
        verbose_name_plural = _("Plans")
        
    def __str__(self):
        return f"{self.name} ({self.get_interval_display()})"
        
    def get_absolute_url(self):
        return reverse("plan-detail", kwargs={"slug": self.slug})

class Subscription(models.Model):
    """User subscription model"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('canceled', 'Canceled'),
        ('past_due', 'Past Due'),
        ('trialing', 'Trialing'),
        ('unpaid', 'Unpaid'),
        ('incomplete', 'Incomplete'),
    ]
    
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    current_period_start = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    cancel_at_period_end = models.BooleanField(default=False)
    
    # Usage tracking
    used_productions = models.IntegerField(default=0)
    used_storage_gb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    scan_count = models.IntegerField(default=0)
    
    # Trial information
    trial_end = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")
    
    def __str__(self):
        return f"{self.company.name} - {self.plan.name}"
        
    def is_active(self):
        return self.status in ['active', 'trialing']
        
    def is_trial(self):
        return self.status == 'trialing'

class AddOn(models.Model):
    """Add-on product model"""
    name = models.CharField(max_length=50)  # Extra Production, Extra Parcel, etc.
    slug = models.SlugField(unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _("Add-on")
        verbose_name_plural = _("Add-ons")
        
    def __str__(self):
        return self.name

class SubscriptionAddOn(models.Model):
    """Tracks add-ons purchased by a subscription"""
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='addons')
    addon = models.ForeignKey(AddOn, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    stripe_item_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Subscription Add-on")
        verbose_name_plural = _("Subscription Add-ons")
        
    def __str__(self):
        return f"{self.subscription.company.name} - {self.addon.name} x{self.quantity}"

class Invoice(models.Model):
    """Invoice model for tracking payments"""
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('open', 'Open'),
        ('uncollectible', 'Uncollectible'),
        ('void', 'Void'),
    ]
    
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='invoices')
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True)
    stripe_invoice_id = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    invoice_date = models.DateTimeField()
    due_date = models.DateTimeField(blank=True, null=True)
    invoice_pdf = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Invoice")
        verbose_name_plural = _("Invoices")
        
    def __str__(self):
        return f"Invoice {self.stripe_invoice_id} for {self.company.name}"

class PaymentMethod(models.Model):
    """Payment method model"""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='payment_methods')
    stripe_payment_method_id = models.CharField(max_length=100)
    card_brand = models.CharField(max_length=20)  # visa, mastercard, etc.
    last_4 = models.CharField(max_length=4)  # Last 4 digits of card
    exp_month = models.IntegerField()
    exp_year = models.IntegerField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _("Payment Method")
        verbose_name_plural = _("Payment Methods")
        
    def __str__(self):
        return f"{self.card_brand} **** **** **** {self.last_4}" 