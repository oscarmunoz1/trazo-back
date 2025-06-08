from rest_framework import serializers
from .models import SupportTicket, SupportMessage, SupportAttachment, SupportSLA
from users.models import User

class SupportTicketSerializer(serializers.ModelSerializer):
    """Comprehensive support ticket serializer"""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    
    # SLA information
    sla_response_deadline = serializers.DateTimeField(read_only=True)
    sla_resolution_deadline = serializers.DateTimeField(read_only=True)
    is_overdue_response = serializers.BooleanField(read_only=True)
    is_overdue_resolution = serializers.BooleanField(read_only=True)
    response_time_hours = serializers.FloatField(read_only=True)
    resolution_time_hours = serializers.FloatField(read_only=True)
    
    # Message count
    message_count = serializers.SerializerMethodField()
    
    # Subscription plan info
    subscription_plan = serializers.SerializerMethodField()
    
    class Meta:
        model = SupportTicket
        fields = [
            'id', 'ticket_id', 'subject', 'description', 'category', 'priority', 'status',
            'user', 'user_name', 'user_email', 'company', 'company_name',
            'assigned_to', 'assigned_to_name', 'created_at', 'updated_at',
            'first_response_at', 'resolved_at', 'closed_at',
            'sla_response_hours', 'sla_resolution_hours',
            'sla_response_deadline', 'sla_resolution_deadline',
            'is_overdue_response', 'is_overdue_resolution',
            'response_time_hours', 'resolution_time_hours',
            'tags', 'internal_notes', 'customer_satisfaction_rating',
            'message_count', 'subscription_plan'
        ]
        read_only_fields = [
            'ticket_id', 'user', 'company', 'first_response_at', 'resolved_at', 'closed_at',
            'sla_response_hours', 'sla_resolution_hours'
        ]
    
    def get_message_count(self, obj):
        """Get count of messages in this ticket"""
        return obj.messages.count()
    
    def get_subscription_plan(self, obj):
        """Get subscription plan information"""
        try:
            subscription = obj.company.subscription
            return {
                'name': subscription.plan.name,
                'priority_support': subscription.plan.features.get('priority_support', False),
                'response_time_hours': subscription.plan.features.get('support_response_time', 48)
            }
        except:
            return None


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating support tickets"""
    
    class Meta:
        model = SupportTicket
        fields = ['subject', 'description', 'category', 'priority']
        
    def validate_priority(self, value):
        """Validate priority - regular users can't set urgent priority"""
        request = self.context.get('request')
        if value == 'urgent' and request and not request.user.is_staff:
            raise serializers.ValidationError(
                "Only support staff can create urgent priority tickets"
            )
        return value


class SupportMessageSerializer(serializers.ModelSerializer):
    """Support message serializer"""
    
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    author_email = serializers.CharField(source='author.email', read_only=True)
    is_staff_message = serializers.BooleanField(source='author.is_staff', read_only=True)
    
    class Meta:
        model = SupportMessage
        fields = [
            'id', 'ticket', 'author', 'author_name', 'author_email', 'is_staff_message',
            'message_type', 'content', 'is_internal', 'created_at', 'updated_at'
        ]
        read_only_fields = ['author', 'message_type']


class SupportAttachmentSerializer(serializers.ModelSerializer):
    """Support attachment serializer"""
    
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = SupportAttachment
        fields = [
            'id', 'ticket', 'message', 'file', 'file_url', 'original_filename',
            'file_size', 'content_type', 'uploaded_by', 'uploaded_by_name', 'uploaded_at'
        ]
        read_only_fields = ['uploaded_by', 'file_size', 'content_type', 'original_filename']
    
    def get_file_url(self, obj):
        """Get file download URL"""
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class SupportSLASerializer(serializers.ModelSerializer):
    """SLA metrics serializer"""
    
    response_sla_percentage = serializers.FloatField(read_only=True)
    resolution_sla_percentage = serializers.FloatField(read_only=True)
    
    class Meta:
        model = SupportSLA
        fields = [
            'id', 'plan_name', 'month', 'total_tickets', 'met_response_sla',
            'avg_response_time_hours', 'max_response_time_hours',
            'resolved_tickets', 'met_resolution_sla', 'avg_resolution_time_hours',
            'satisfaction_ratings', 'avg_satisfaction_score',
            'response_sla_percentage', 'resolution_sla_percentage',
            'created_at', 'updated_at'
        ] 