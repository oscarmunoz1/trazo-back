from django.db import models
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from company.models import Company
from subscriptions.models import Subscription

class SupportTicket(models.Model):
    """Support ticket model with priority levels and SLA tracking"""
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'), 
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('waiting_customer', 'Waiting for Customer'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    CATEGORY_CHOICES = [
        ('billing', 'Billing & Subscriptions'),
        ('technical', 'Technical Support'),
        ('feature_request', 'Feature Request'),
        ('carbon_tracking', 'Carbon Tracking'),
        ('iot_devices', 'IoT Devices'),
        ('account', 'Account & Profile'),
        ('other', 'Other'),
    ]
    
    # Basic ticket information
    ticket_id = models.CharField(max_length=20, unique=True, db_index=True)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    
    # User and company information
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='support_tickets')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='support_tickets')
    
    # Assignment
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_tickets'
    )
    
    # SLA and response tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    # SLA targets (in hours)
    sla_response_hours = models.IntegerField(default=48)  # Calculated from subscription plan
    sla_resolution_hours = models.IntegerField(default=168)  # 7 days default
    
    # Tags and metadata
    tags = models.CharField(max_length=200, blank=True, help_text="Comma-separated tags")
    internal_notes = models.TextField(blank=True)
    customer_satisfaction_rating = models.IntegerField(null=True, blank=True, help_text="1-5 rating")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"#{self.ticket_id} - {self.subject}"
    
    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = self.generate_ticket_id()
        
        if not self.pk:  # New ticket
            self.set_sla_from_subscription()
            
        super().save(*args, **kwargs)
    
    def generate_ticket_id(self):
        """Generate unique ticket ID"""
        import random
        import string
        prefix = "TRZ"
        suffix = ''.join(random.choices(string.digits, k=6))
        return f"{prefix}-{suffix}"
    
    def set_sla_from_subscription(self):
        """Set SLA response time based on subscription plan"""
        try:
            subscription = self.company.subscription
            plan_features = subscription.plan.features
            
            # Get response time from plan features (in hours)
            response_time = plan_features.get('support_response_time', 48)
            self.sla_response_hours = response_time
            
            # Priority support gets faster response
            if plan_features.get('priority_support', False):
                self.priority = 'high'
                self.sla_response_hours = min(response_time, 12)  # Max 12h for priority
                
        except (Subscription.DoesNotExist, AttributeError):
            # Default SLA for users without subscription
            self.sla_response_hours = 48
            self.sla_resolution_hours = 168
    
    @property
    def sla_response_deadline(self):
        """Calculate SLA response deadline"""
        return self.created_at + timedelta(hours=self.sla_response_hours)
    
    @property 
    def sla_resolution_deadline(self):
        """Calculate SLA resolution deadline"""
        return self.created_at + timedelta(hours=self.sla_resolution_hours)
    
    @property
    def is_overdue_response(self):
        """Check if ticket is overdue for first response"""
        if self.first_response_at:
            return False
        return timezone.now() > self.sla_response_deadline
    
    @property
    def is_overdue_resolution(self):
        """Check if ticket is overdue for resolution"""
        if self.resolved_at:
            return False
        return timezone.now() > self.sla_resolution_deadline
    
    @property
    def response_time_hours(self):
        """Calculate actual response time in hours"""
        if not self.first_response_at:
            return None
        delta = self.first_response_at - self.created_at
        return delta.total_seconds() / 3600
    
    @property
    def resolution_time_hours(self):
        """Calculate actual resolution time in hours"""
        if not self.resolved_at:
            return None
        delta = self.resolved_at - self.created_at
        return delta.total_seconds() / 3600
    
    def mark_first_response(self):
        """Mark the first response time"""
        if not self.first_response_at:
            self.first_response_at = timezone.now()
            self.save(update_fields=['first_response_at'])
    
    def mark_resolved(self):
        """Mark ticket as resolved"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])
    
    def mark_closed(self):
        """Mark ticket as closed"""
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.save(update_fields=['status', 'closed_at'])


class SupportMessage(models.Model):
    """Messages within a support ticket thread"""
    
    MESSAGE_TYPES = [
        ('customer', 'Customer Message'),
        ('staff', 'Staff Response'),
        ('internal', 'Internal Note'),
        ('system', 'System Message'),
    ]
    
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='customer')
    content = models.TextField()
    is_internal = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message on {self.ticket.ticket_id} by {self.author.email}"
    
    def save(self, *args, **kwargs):
        is_new = not self.pk
        super().save(*args, **kwargs)
        
        # Mark first response if this is a staff message and no previous response
        if is_new and self.message_type == 'staff' and not self.ticket.first_response_at:
            self.ticket.mark_first_response()


class SupportAttachment(models.Model):
    """File attachments for support tickets"""
    
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='attachments')
    message = models.ForeignKey(SupportMessage, on_delete=models.CASCADE, null=True, blank=True)
    file = models.FileField(upload_to='support_attachments/%Y/%m/%d/')
    original_filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    content_type = models.CharField(max_length=100)
    
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Attachment: {self.original_filename}"


class SupportSLA(models.Model):
    """SLA tracking and reporting model"""
    
    # Monthly SLA metrics per plan
    plan_name = models.CharField(max_length=50)
    month = models.DateField()
    
    # Response time metrics
    total_tickets = models.IntegerField(default=0)
    met_response_sla = models.IntegerField(default=0)
    avg_response_time_hours = models.FloatField(default=0)
    max_response_time_hours = models.FloatField(default=0)
    
    # Resolution time metrics
    resolved_tickets = models.IntegerField(default=0)
    met_resolution_sla = models.IntegerField(default=0)
    avg_resolution_time_hours = models.FloatField(default=0)
    
    # Customer satisfaction
    satisfaction_ratings = models.IntegerField(default=0)
    avg_satisfaction_score = models.FloatField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['plan_name', 'month']
        ordering = ['-month']
    
    def __str__(self):
        return f"SLA {self.plan_name} - {self.month.strftime('%Y-%m')}"
    
    @property
    def response_sla_percentage(self):
        """Calculate response SLA percentage"""
        if self.total_tickets == 0:
            return 0
        return (self.met_response_sla / self.total_tickets) * 100
    
    @property
    def resolution_sla_percentage(self):
        """Calculate resolution SLA percentage"""
        if self.resolved_tickets == 0:
            return 0
        return (self.met_resolution_sla / self.resolved_tickets) * 100 