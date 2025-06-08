from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import SupportTicket, SupportMessage, SupportAttachment, SupportSLA

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_id', 'subject', 'user_email', 'company_name', 'priority', 
        'status', 'assigned_to', 'sla_status', 'created_at'
    ]
    list_filter = [
        'priority', 'status', 'category', 'created_at', 
        'company__subscription__plan__name'
    ]
    search_fields = [
        'ticket_id', 'subject', 'user__email', 'company__name', 'description'
    ]
    readonly_fields = [
        'ticket_id', 'user', 'company', 'created_at', 'updated_at',
        'first_response_at', 'resolved_at', 'closed_at',
        'sla_response_hours', 'sla_resolution_hours',
        'sla_response_deadline', 'sla_resolution_deadline',
        'response_time_hours', 'resolution_time_hours'
    ]
    raw_id_fields = ['user', 'company', 'assigned_to']
    
    fieldsets = (
        ('Ticket Information', {
            'fields': ('ticket_id', 'subject', 'description', 'category')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'assigned_to')
        }),
        ('User & Company', {
            'fields': ('user', 'company')
        }),
        ('SLA Tracking', {
            'fields': (
                'sla_response_hours', 'sla_resolution_hours',
                'sla_response_deadline', 'sla_resolution_deadline',
                'first_response_at', 'resolved_at', 'closed_at',
                'response_time_hours', 'resolution_time_hours'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('tags', 'internal_notes', 'customer_satisfaction_rating'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User Email'
    
    def company_name(self, obj):
        return obj.company.name
    company_name.short_description = 'Company'
    
    def sla_status(self, obj):
        """Show SLA status with color coding"""
        if obj.is_overdue_response:
            return format_html(
                '<span style="color: red; font-weight: bold;">OVERDUE RESPONSE</span>'
            )
        elif obj.is_overdue_resolution:
            return format_html(
                '<span style="color: orange; font-weight: bold;">OVERDUE RESOLUTION</span>'
            )
        elif obj.status in ['resolved', 'closed']:
            return format_html(
                '<span style="color: green;">ON TIME</span>'
            )
        else:
            time_left = obj.sla_response_deadline - timezone.now()
            hours_left = int(time_left.total_seconds() / 3600)
            if hours_left < 2:
                return format_html(
                    '<span style="color: orange;">{}h LEFT</span>', hours_left
                )
            else:
                return format_html(
                    '<span style="color: blue;">{}h LEFT</span>', hours_left
                )
    sla_status.short_description = 'SLA Status'
    
    actions = ['assign_to_me', 'mark_high_priority', 'mark_resolved']
    
    def assign_to_me(self, request, queryset):
        """Assign selected tickets to current user"""
        queryset.update(assigned_to=request.user, status='in_progress')
        self.message_user(
            request, 
            f"Assigned {queryset.count()} tickets to {request.user.get_full_name()}"
        )
    assign_to_me.short_description = "Assign selected tickets to me"
    
    def mark_high_priority(self, request, queryset):
        """Mark selected tickets as high priority"""
        queryset.update(priority='high')
        self.message_user(request, f"Marked {queryset.count()} tickets as high priority")
    mark_high_priority.short_description = "Mark as high priority"
    
    def mark_resolved(self, request, queryset):
        """Mark selected tickets as resolved"""
        for ticket in queryset:
            ticket.mark_resolved()
        self.message_user(request, f"Resolved {queryset.count()} tickets")
    mark_resolved.short_description = "Mark as resolved"


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ['ticket_id', 'author_name', 'message_type', 'is_internal', 'created_at']
    list_filter = ['message_type', 'is_internal', 'created_at']
    search_fields = ['ticket__ticket_id', 'author__email', 'content']
    readonly_fields = ['author', 'created_at', 'updated_at']
    raw_id_fields = ['ticket', 'author']
    
    def ticket_id(self, obj):
        return obj.ticket.ticket_id
    ticket_id.short_description = 'Ticket ID'
    
    def author_name(self, obj):
        return obj.author.get_full_name()
    author_name.short_description = 'Author'


@admin.register(SupportAttachment)
class SupportAttachmentAdmin(admin.ModelAdmin):
    list_display = [
        'ticket_id', 'original_filename', 'file_size_mb', 
        'content_type', 'uploaded_by_name', 'uploaded_at'
    ]
    list_filter = ['content_type', 'uploaded_at']
    search_fields = ['ticket__ticket_id', 'original_filename', 'uploaded_by__email']
    readonly_fields = ['uploaded_by', 'uploaded_at', 'file_size', 'content_type']
    raw_id_fields = ['ticket', 'message', 'uploaded_by']
    
    def ticket_id(self, obj):
        return obj.ticket.ticket_id
    ticket_id.short_description = 'Ticket ID'
    
    def uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name()
    uploaded_by_name.short_description = 'Uploaded By'
    
    def file_size_mb(self, obj):
        return f"{obj.file_size / (1024*1024):.2f} MB"
    file_size_mb.short_description = 'File Size'


@admin.register(SupportSLA)
class SupportSLAAdmin(admin.ModelAdmin):
    list_display = [
        'plan_name', 'month', 'total_tickets', 'response_sla_percentage_display',
        'resolution_sla_percentage_display', 'avg_satisfaction_score'
    ]
    list_filter = ['plan_name', 'month']
    readonly_fields = [
        'response_sla_percentage', 'resolution_sla_percentage',
        'created_at', 'updated_at'
    ]
    
    def response_sla_percentage_display(self, obj):
        percentage = obj.response_sla_percentage
        if percentage >= 95:
            color = 'green'
        elif percentage >= 85:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, percentage
        )
    response_sla_percentage_display.short_description = 'Response SLA'
    
    def resolution_sla_percentage_display(self, obj):
        percentage = obj.resolution_sla_percentage
        if percentage >= 90:
            color = 'green'
        elif percentage >= 80:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, percentage
        )
    resolution_sla_percentage_display.short_description = 'Resolution SLA' 