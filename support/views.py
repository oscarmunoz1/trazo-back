from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q, Avg, Count
from django.shortcuts import get_object_or_404
from datetime import timedelta
from .models import SupportTicket, SupportMessage, SupportAttachment, SupportSLA
from .serializers import (
    SupportTicketSerializer, 
    SupportMessageSerializer, 
    SupportAttachmentSerializer,
    SupportTicketCreateSerializer
)
from company.models import Company
import logging

logger = logging.getLogger(__name__)

class SupportTicketViewSet(viewsets.ModelViewSet):
    """Support ticket management with priority queue and SLA tracking"""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SupportTicketCreateSerializer
        return SupportTicketSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # Support staff can see all tickets
        if user.is_staff:
            return SupportTicket.objects.all().select_related('user', 'company', 'assigned_to')
        
        # Regular users can only see their company's tickets
        user_companies = user.companies.all()
        return SupportTicket.objects.filter(
            company__in=user_companies
        ).select_related('user', 'company', 'assigned_to')
    
    def perform_create(self, serializer):
        """Create ticket with automatic priority and SLA assignment"""
        user = self.request.user
        
        # Get user's active company
        company = user.get_active_company()
        if not company:
            company = user.companies.first()
        
        if not company:
            raise ValueError("User must be associated with a company to create support tickets")
        
        # Create ticket
        ticket = serializer.save(user=user, company=company)
        
        # Log ticket creation
        logger.info(f"Support ticket created: {ticket.ticket_id} by {user.email}")
        
        # Send notification (implement as needed)
        # self.send_ticket_notification(ticket)
    
    @action(detail=False, methods=['get'])
    def priority_queue(self, request):
        """Get tickets ordered by priority for support staff"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Access denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Priority order: urgent > high > normal > low
        # Within each priority: oldest first, overdue first
        tickets = SupportTicket.objects.filter(
            status__in=['open', 'in_progress']
        ).extra(
            select={
                'priority_order': """
                    CASE priority 
                        WHEN 'urgent' THEN 1 
                        WHEN 'high' THEN 2 
                        WHEN 'normal' THEN 3 
                        WHEN 'low' THEN 4 
                    END
                """,
                'is_overdue': """
                    CASE 
                        WHEN first_response_at IS NULL AND NOW() > DATE_ADD(created_at, INTERVAL sla_response_hours HOUR) THEN 1
                        ELSE 0
                    END
                """
            }
        ).order_by('-is_overdue', 'priority_order', 'created_at')[:50]
        
        serializer = self.get_serializer(tickets, many=True)
        
        # Add queue statistics
        queue_stats = {
            'total_open': SupportTicket.objects.filter(status='open').count(),
            'overdue_response': SupportTicket.objects.filter(
                first_response_at__isnull=True,
                created_at__lt=timezone.now() - timedelta(hours=24)
            ).count(),
            'high_priority': SupportTicket.objects.filter(
                status__in=['open', 'in_progress'],
                priority__in=['urgent', 'high']
            ).count(),
        }
        
        return Response({
            'queue_stats': queue_stats,
            'tickets': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign ticket to support staff"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Access denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        ticket = self.get_object()
        assignee_id = request.data.get('assignee_id')
        
        if assignee_id:
            try:
                from users.models import User
                assignee = User.objects.get(id=assignee_id, is_staff=True)
                ticket.assigned_to = assignee
            except User.DoesNotExist:
                return Response(
                    {'error': 'Invalid assignee'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            ticket.assigned_to = request.user
        
        ticket.status = 'in_progress'
        ticket.save(update_fields=['assigned_to', 'status'])
        
        # Create system message
        SupportMessage.objects.create(
            ticket=ticket,
            author=request.user,
            message_type='system',
            content=f"Ticket assigned to {ticket.assigned_to.get_full_name()}",
            is_internal=True
        )
        
        return Response({'status': 'assigned'})
    
    @action(detail=True, methods=['post'])
    def add_message(self, request, pk=None):
        """Add message to ticket"""
        ticket = self.get_object()
        content = request.data.get('content')
        is_internal = request.data.get('is_internal', False)
        
        if not content:
            return Response(
                {'error': 'Message content is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine message type
        message_type = 'customer'
        if request.user.is_staff:
            message_type = 'internal' if is_internal else 'staff'
        
        message = SupportMessage.objects.create(
            ticket=ticket,
            author=request.user,
            message_type=message_type,
            content=content,
            is_internal=is_internal
        )
        
        # Update ticket status if needed
        if message_type == 'customer' and ticket.status == 'waiting_customer':
            ticket.status = 'in_progress'
            ticket.save(update_fields=['status'])
        
        serializer = SupportMessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Mark ticket as resolved"""
        ticket = self.get_object()
        resolution_note = request.data.get('resolution_note', '')
        
        ticket.mark_resolved()
        
        # Add resolution message
        if resolution_note:
            SupportMessage.objects.create(
                ticket=ticket,
                author=request.user,
                message_type='staff',
                content=f"Resolution: {resolution_note}"
            )
        
        return Response({'status': 'resolved'})
    
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close ticket and collect satisfaction rating"""
        ticket = self.get_object()
        satisfaction_rating = request.data.get('satisfaction_rating')
        
        if satisfaction_rating:
            try:
                rating = int(satisfaction_rating)
                if 1 <= rating <= 5:
                    ticket.customer_satisfaction_rating = rating
            except (ValueError, TypeError):
                pass
        
        ticket.mark_closed()
        
        return Response({'status': 'closed'})
    
    @action(detail=False, methods=['get'])
    def sla_metrics(self, request):
        """Get SLA performance metrics"""
        if not request.user.is_staff:
            return Response(
                {'error': 'Access denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Current month metrics
        current_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        metrics = {}
        
        # Get metrics by plan
        from subscriptions.models import Plan
        for plan in Plan.objects.filter(is_active=True).distinct('name'):
            plan_tickets = SupportTicket.objects.filter(
                created_at__gte=current_month,
                company__subscription__plan__name=plan.name
            )
            
            total_tickets = plan_tickets.count()
            if total_tickets == 0:
                continue
            
            # Response time metrics
            responded_tickets = plan_tickets.filter(first_response_at__isnull=False)
            met_response_sla = 0
            response_times = []
            
            for ticket in responded_tickets:
                response_time = ticket.response_time_hours
                if response_time:
                    response_times.append(response_time)
                    if response_time <= ticket.sla_response_hours:
                        met_response_sla += 1
            
            # Resolution metrics
            resolved_tickets = plan_tickets.filter(resolved_at__isnull=False)
            met_resolution_sla = 0
            resolution_times = []
            
            for ticket in resolved_tickets:
                resolution_time = ticket.resolution_time_hours
                if resolution_time:
                    resolution_times.append(resolution_time)
                    if resolution_time <= ticket.sla_resolution_hours:
                        met_resolution_sla += 1
            
            # Satisfaction metrics
            satisfaction_ratings = plan_tickets.filter(
                customer_satisfaction_rating__isnull=False
            ).values_list('customer_satisfaction_rating', flat=True)
            
            metrics[plan.name] = {
                'total_tickets': total_tickets,
                'response_sla_met': met_response_sla,
                'response_sla_percentage': (met_response_sla / max(responded_tickets.count(), 1)) * 100,
                'avg_response_time_hours': sum(response_times) / len(response_times) if response_times else 0,
                'resolution_sla_met': met_resolution_sla,
                'resolution_sla_percentage': (met_resolution_sla / max(resolved_tickets.count(), 1)) * 100,
                'avg_resolution_time_hours': sum(resolution_times) / len(resolution_times) if resolution_times else 0,
                'avg_satisfaction': sum(satisfaction_ratings) / len(satisfaction_ratings) if satisfaction_ratings else 0,
                'satisfaction_count': len(satisfaction_ratings)
            }
        
        return Response({
            'month': current_month.strftime('%Y-%m'),
            'metrics_by_plan': metrics
        })


class SupportMessageViewSet(viewsets.ReadOnlyModelViewSet):
    """Support message management"""
    
    serializer_class = SupportMessageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        ticket_id = self.request.query_params.get('ticket_id')
        
        queryset = SupportMessage.objects.select_related('ticket', 'author')
        
        if ticket_id:
            queryset = queryset.filter(ticket_id=ticket_id)
        
        # Filter based on user permissions
        if not user.is_staff:
            # Regular users can't see internal messages
            queryset = queryset.filter(is_internal=False)
            # And only messages for their company's tickets
            user_companies = user.companies.all()
            queryset = queryset.filter(ticket__company__in=user_companies)
        
        return queryset.order_by('created_at')


class SupportAttachmentViewSet(viewsets.ModelViewSet):
    """Support attachment management"""
    
    serializer_class = SupportAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        queryset = SupportAttachment.objects.select_related('ticket', 'uploaded_by')
        
        if not user.is_staff:
            # Regular users can only see attachments for their company's tickets
            user_companies = user.companies.all()
            queryset = queryset.filter(ticket__company__in=user_companies)
        
        return queryset
    
    def perform_create(self, serializer):
        """Handle file upload with validation"""
        file = self.request.FILES.get('file')
        if file:
            # Validate file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValueError("File size cannot exceed 10MB")
            
            serializer.save(
                uploaded_by=self.request.user,
                original_filename=file.name,
                file_size=file.size,
                content_type=file.content_type
            )
        else:
            raise ValueError("No file provided") 