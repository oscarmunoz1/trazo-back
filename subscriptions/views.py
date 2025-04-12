from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet
import stripe
import json
from .models import Plan, Subscription, AddOn, SubscriptionAddOn, Invoice, PaymentMethod
from .serializers import (
    PlanSerializer, SubscriptionSerializer, AddOnSerializer,
    SubscriptionAddOnSerializer, InvoiceSerializer, PaymentMethodSerializer
)
from company.models import Company
from company.serializers import RetrieveCompanySerializer

stripe.api_key = settings.STRIPE_SECRET_KEY

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for listing subscription plans"""
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        interval = self.request.query_params.get('interval')
        if interval:
            queryset = queryset.filter(interval=interval)
        return queryset

class AddOnViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for listing available add-ons"""
    queryset = AddOn.objects.filter(is_active=True)
    serializer_class = AddOnSerializer
    permission_classes = [permissions.IsAuthenticated]

class SubscriptionViewSet(viewsets.ModelViewSet):
    """API endpoint for managing subscriptions"""
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Subscription.objects.all()
        return Subscription.objects.filter(company__in=user.companies.all())
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel subscription at the end of billing period"""
        subscription = self.get_object()
        
        try:
            if subscription.stripe_subscription_id:
                stripe_subscription = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
            
            subscription.cancel_at_period_end = True
            subscription.save()
            
            return Response({
                'status': 'subscription will be canceled at the end of the billing period',
                'end_date': subscription.current_period_end
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        """Reactivate a subscription that was scheduled for cancellation"""
        subscription = self.get_object()
        
        try:
            if subscription.stripe_subscription_id:
                stripe_subscription = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=False
                )
            
            subscription.cancel_at_period_end = False
            subscription.save()
            
            return Response({'status': 'subscription reactivated'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def change_plan(self, request, pk=None):
        """Change subscription plan"""
        subscription = self.get_object()
        plan_id = request.data.get('plan_id')
        
        try:
            plan = Plan.objects.get(id=plan_id, is_active=True)
            
            if subscription.stripe_subscription_id:
                # Update the subscription in Stripe
                stripe_subscription = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    items=[{
                        'id': stripe.Subscription.retrieve(subscription.stripe_subscription_id)['items']['data'][0]['id'],
                        'price': plan.stripe_price_id,
                    }],
                    proration_behavior='always_invoice'
                )
            
            # Update the subscription in our database
            subscription.plan = plan
            subscription.save()
            
            return Response({
                'status': 'plan changed successfully',
                'subscription': SubscriptionSerializer(subscription).data
            })
        except Plan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_addon(self, request, pk=None):
        """Add an add-on to the subscription"""
        subscription = self.get_object()
        addon_id = request.data.get('addon_id')
        quantity = int(request.data.get('quantity', 1))
        
        try:
            addon = AddOn.objects.get(id=addon_id, is_active=True)
            
            with transaction.atomic():
                # Check if add-on already exists for this subscription
                existing_addon = SubscriptionAddOn.objects.filter(
                    subscription=subscription,
                    addon=addon
                ).first()
                
                if existing_addon:
                    # Update quantity
                    existing_addon.quantity += quantity
                    existing_addon.save()
                    addon_item = existing_addon
                else:
                    # Create new subscription add-on
                    addon_item = SubscriptionAddOn.objects.create(
                        subscription=subscription,
                        addon=addon,
                        quantity=quantity
                    )
                
                if subscription.stripe_subscription_id and addon.stripe_price_id:
                    # Add the add-on in Stripe
                    stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                    
                    # Check if this add-on is already in the subscription
                    existing_item = None
                    for item in stripe_sub['items']['data']:
                        if item['price']['id'] == addon.stripe_price_id:
                            existing_item = item
                            break
                    
                    if existing_item:
                        # Update existing item
                        stripe.SubscriptionItem.modify(
                            existing_item['id'],
                            quantity=existing_item['quantity'] + quantity
                        )
                        addon_item.stripe_item_id = existing_item['id']
                    else:
                        # Add new item
                        item = stripe.SubscriptionItem.create(
                            subscription=subscription.stripe_subscription_id,
                            price=addon.stripe_price_id,
                            quantity=quantity
                        )
                        addon_item.stripe_item_id = item['id']
                    
                    addon_item.save()
            
            return Response({
                'status': 'add-on added successfully',
                'addon': SubscriptionAddOnSerializer(addon_item).data
            })
        except AddOn.DoesNotExist:
            return Response({'error': 'Add-on not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for listing invoices"""
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Invoice.objects.all().order_by('-invoice_date')
        return Invoice.objects.filter(company__in=user.companies.all()).order_by('-invoice_date')

class PaymentMethodViewSet(viewsets.ModelViewSet):
    """API endpoint for managing payment methods"""
    serializer_class = PaymentMethodSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return PaymentMethod.objects.all()
        return PaymentMethod.objects.filter(company__in=user.companies.all())
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        payment_method = self.get_object()
        company = payment_method.company
        
        # Set all other payment methods as non-default
        company.payment_methods.update(is_default=False)
        
        # Set this payment method as default
        payment_method.is_default = True
        payment_method.save()
        
        # Update default payment method in Stripe if customer exists
        try:
            if hasattr(company, 'subscription') and company.subscription.stripe_customer_id:
                stripe.Customer.modify(
                    company.subscription.stripe_customer_id,
                    invoice_settings={
                        'default_payment_method': payment_method.stripe_payment_method_id
                    }
                )
        except Exception as e:
            # Log the error but don't fail the request
            print(f"Error updating Stripe default payment method: {str(e)}")
        
        return Response({'status': 'default payment method set'})

# Create a dedicated ViewSet for checkout operations
class CheckoutViewSet(ViewSet):
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def create_session(self, request):
        """Create a new Stripe checkout session"""
        data = request.data
        plan_id = data.get('plan_id')
        company_id = data.get('company_id')
        interval = data.get('interval', 'monthly')
        new_company = data.get('new_company', False)
        trial_days = data.get('trial_days', 0)
        
        try:
            plan = Plan.objects.get(id=plan_id, interval=interval, is_active=True)
            company = Company.objects.get(id=company_id)
            
            # Verify user has permission to manage this company
            if not request.user.is_staff and company not in request.user.companies.all():
                return Response(
                    {'error': 'You do not have permission to manage this company'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Create or get Stripe customer
            customer_id = None
            if hasattr(company, 'subscription') and company.subscription.stripe_customer_id:
                customer_id = company.subscription.stripe_customer_id
            else:
                # Create a new customer
                customer = stripe.Customer.create(
                    email=request.user.email,
                    name=company.name,
                    metadata={
                        'company_id': company.id
                    }
                )
                customer_id = customer['id']
            
            # Set up trial parameters if requested
            subscription_data = {}
            if trial_days > 0:
                subscription_data['trial_period_days'] = trial_days
            
            # Determine success and cancel URLs based on whether this is a new company
            success_url = f"{settings.FRONTEND_URL}/admin/dashboard/stripe/success?success=true&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{settings.FRONTEND_URL}/pricing?canceled=true"
            
            if new_company:
                # If this is a new company, include redirect to establishment creation after successful subscription
                success_url += f"&new_company=true&company_id={str(company.id)}"
                cancel_url += f"&company_id={str(company.id)}&new_company=true"
            else:
                # Always include company_id for consistent handling
                success_url += f"&company_id={str(company.id)}"
            
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': plan.stripe_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                subscription_data=subscription_data,  # Include trial parameters
                metadata={
                    'company_id': company.id,
                    'plan_id': plan.id,
                    'interval': interval,
                    'new_company': str(new_company).lower(),
                    'trial_days': str(trial_days)
                }
            )
            
            return Response({
                'sessionId': checkout_session['id']
            })
        except Plan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def complete_checkout(self, request):
        """Complete the checkout after a successful payment"""
        session_id = request.data.get('session_id')
        company_id = request.data.get('company_id')
        
        if not session_id or not company_id:
            return Response({'success': False, 'error': 'Missing required parameters'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Retrieve checkout session from Stripe
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Verify this is a valid checkout session
            if session.get('payment_status') != 'paid':
                return Response({'success': False, 'error': 'Payment not completed'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get subscription ID from session
            subscription_id = session.get('subscription')
            if not subscription_id:
                return Response({'success': False, 'error': 'No subscription found'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get subscription details
            stripe_sub = stripe.Subscription.retrieve(subscription_id)
            
            # Get company
            company = Company.objects.get(id=company_id)
            
            # Get plan from price ID
            price_id = stripe_sub['items']['data'][0]['price']['id']
            plan = Plan.objects.get(stripe_price_id=price_id)
            
            # Create or update subscription record
            subscription, created = Subscription.objects.update_or_create(
                company=company,
                defaults={
                    'plan': plan,
                    'stripe_subscription_id': subscription_id,
                    'stripe_customer_id': session.get('customer'),
                    'status': stripe_sub['status'],
                    'current_period_start': timezone.datetime.fromtimestamp(stripe_sub['current_period_start']),
                    'current_period_end': timezone.datetime.fromtimestamp(stripe_sub['current_period_end']),
                    'cancel_at_period_end': stripe_sub['cancel_at_period_end'],
                    'trial_end': timezone.datetime.fromtimestamp(stripe_sub['trial_end']) if stripe_sub.get('trial_end') else None
                }
            )
            
            # After creating the subscription, also return updated company data
            company_data = RetrieveCompanySerializer(company).data
            
            return Response({
                'success': True, 
                'subscription_id': subscription.id,
                'company': company_data  # Include the company data with subscription info
            })
            
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Stripe webhook handler
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)
    
    # Handle the event
    event_type = event['type']
    data = event['data']['object']
    
    print(f"Received webhook event: {event_type}")
    
    if event_type == 'checkout.session.completed':
        handle_checkout_session_completed(data)
    elif event_type == 'invoice.payment_succeeded':
        handle_invoice_payment_succeeded(data)
    elif event_type == 'invoice.payment_failed':
        handle_invoice_payment_failed(data)
    elif event_type == 'customer.subscription.updated':
        handle_subscription_updated(data)
    elif event_type == 'customer.subscription.deleted':
        handle_customer_subscription_deleted(data)
    elif event_type == 'payment_method.attached':
        handle_payment_method_attached(data)
    elif event_type == 'customer.subscription.created':
        subscription_data = data
        
        # If subscription is in trial, send trial started email
        if subscription_data['status'] == 'trialing' and subscription_data.get('trial_end'):
            try:
                company_id = subscription_data['metadata'].get('company_id')
                if company_id:
                    company = Company.objects.get(id=company_id)
                    
                    # Get the admin user
                    admin_user = company.company_admins.first()
                    if admin_user:
                        from subscriptions.utils import send_trial_started_email
                        
                        trial_end = timezone.datetime.fromtimestamp(subscription_data['trial_end'])
                        plan = Plan.objects.get(stripe_price_id=subscription_data['items']['data'][0]['price']['id'])
                        
                        send_trial_started_email(
                            admin_user.email,
                            admin_user.first_name,
                            company.name,
                            plan.name,
                            trial_end
                        )
            except Exception as e:
                print(f"Error sending trial started email: {str(e)}")
            
        # Handle subscription created normally
        handle_subscription_created(subscription_data)
    
    return HttpResponse(status=200)

def handle_checkout_session_completed(session):
    """Process completed checkout session"""
    try:
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')
        company_id = session.get('metadata', {}).get('company_id')
        plan_id = session.get('metadata', {}).get('plan_id')
        
        if not customer_id or not subscription_id or not company_id or not plan_id:
            print("Missing required data in checkout session")
            return
        
        company = Company.objects.get(id=company_id)
        plan = Plan.objects.get(id=plan_id)
        
        # Retrieve subscription details from Stripe
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        
        with transaction.atomic():
            # Create or update subscription
            subscription, created = Subscription.objects.update_or_create(
                company=company,
                defaults={
                    'plan': plan,
                    'stripe_subscription_id': subscription_id,
                    'stripe_customer_id': customer_id,
                    'status': stripe_sub['status'],
                    'current_period_start': timezone.datetime.fromtimestamp(stripe_sub['current_period_start']),
                    'current_period_end': timezone.datetime.fromtimestamp(stripe_sub['current_period_end']),
                    'cancel_at_period_end': stripe_sub['cancel_at_period_end'],
                    'trial_end': timezone.datetime.fromtimestamp(stripe_sub['trial_end']) if stripe_sub.get('trial_end') else None
                }
            )
    except Exception as e:
        print(f"Error processing checkout session: {str(e)}")

def handle_invoice_payment_succeeded(invoice):
    """Process successful invoice payment"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return
        
        # Get subscription from our database
        subscription = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
        if not subscription:
            return
        
        # Create or update invoice record
        Invoice.objects.update_or_create(
            stripe_invoice_id=invoice['id'],
            defaults={
                'company': subscription.company,
                'subscription': subscription,
                'amount': invoice['amount_paid'] / 100,  # Convert from cents
                'status': 'paid',
                'invoice_date': timezone.datetime.fromtimestamp(invoice['created']),
                'due_date': timezone.datetime.fromtimestamp(invoice['due_date']) if invoice.get('due_date') else None,
                'invoice_pdf': invoice.get('invoice_pdf')
            }
        )
        
        # Update subscription status if needed
        if subscription.status != 'active' and invoice['paid']:
            subscription.status = 'active'
            subscription.save()
            
    except Exception as e:
        print(f"Error processing invoice payment: {str(e)}")

def handle_invoice_payment_failed(invoice):
    """Process failed invoice payment"""
    try:
        subscription_id = invoice.get('subscription')
        if not subscription_id:
            return
        
        # Get subscription from our database
        subscription = Subscription.objects.filter(stripe_subscription_id=subscription_id).first()
        if not subscription:
            return
        
        # Create or update invoice record
        Invoice.objects.update_or_create(
            stripe_invoice_id=invoice['id'],
            defaults={
                'company': subscription.company,
                'subscription': subscription,
                'amount': invoice['amount_due'] / 100,  # Convert from cents
                'status': 'uncollectible' if invoice.get('uncollectible') else 'open',
                'invoice_date': timezone.datetime.fromtimestamp(invoice['created']),
                'due_date': timezone.datetime.fromtimestamp(invoice['due_date']) if invoice.get('due_date') else None,
                'invoice_pdf': invoice.get('invoice_pdf')
            }
        )
        
        # Update subscription status
        if subscription.status == 'active':
            subscription.status = 'past_due'
            subscription.save()
            
    except Exception as e:
        print(f"Error processing invoice payment failure: {str(e)}")

def handle_subscription_updated(subscription_data):
    """Process subscription update"""
    try:
        subscription = Subscription.objects.filter(
            stripe_subscription_id=subscription_data['id']
        ).first()
        
        if not subscription:
            return
        
        # Update subscription details
        subscription.status = subscription_data['status']
        subscription.current_period_start = timezone.datetime.fromtimestamp(subscription_data['current_period_start'])
        subscription.current_period_end = timezone.datetime.fromtimestamp(subscription_data['current_period_end'])
        subscription.cancel_at_period_end = subscription_data['cancel_at_period_end']
        
        if subscription_data.get('trial_end'):
            subscription.trial_end = timezone.datetime.fromtimestamp(subscription_data['trial_end'])
        
        subscription.save()
        
    except Exception as e:
        print(f"Error updating subscription: {str(e)}")

def handle_customer_subscription_deleted(subscription_data):
    """Process subscription cancellation"""
    try:
        subscription = Subscription.objects.filter(
            stripe_subscription_id=subscription_data['id']
        ).first()
        
        if not subscription:
            return
        
        # Update subscription status
        subscription.status = 'canceled'
        subscription.save()
        
        # Send cancellation email
        try:
            company = subscription.company
            admin_user = company.company_admins.first()
            if admin_user:
                # Import email utility function
                from subscriptions.utils import send_subscription_canceled_email
                send_subscription_canceled_email(
                    admin_user.email, 
                    admin_user.first_name, 
                    company.name
                )
        except Exception as e:
            print(f"Error sending cancellation email: {str(e)}")
        
    except Exception as e:
        print(f"Error handling subscription deletion: {str(e)}")

def handle_payment_method_attached(payment_method_data):
    """Process payment method attachment"""
    try:
        customer_id = payment_method_data.get('customer')
        if not customer_id:
            return
        
        # Find the subscription with this customer ID
        subscription = Subscription.objects.filter(stripe_customer_id=customer_id).first()
        if not subscription:
            return
        
        company = subscription.company
        
        # Get card details
        card = payment_method_data.get('card', {})
        if not card:
            return
        
        # Create payment method record
        is_first = company.payment_methods.count() == 0
        
        payment_method = PaymentMethod.objects.create(
            company=company,
            stripe_payment_method_id=payment_method_data['id'],
            card_brand=card.get('brand', '').lower(),
            last_4=card.get('last4', ''),
            exp_month=card.get('exp_month', 0),
            exp_year=card.get('exp_year', 0),
            is_default=is_first  # Set as default if it's the first payment method
        )
        
        # If this is the first payment method, set it as default in Stripe
        if is_first:
            stripe.Customer.modify(
                customer_id,
                invoice_settings={
                    'default_payment_method': payment_method_data['id']
                }
            )
        
    except Exception as e:
        print(f"Error handling payment method: {str(e)}")

def handle_subscription_created(subscription_data):
    """Process newly created subscription"""
    try:
        # Get company_id from metadata
        company_id = subscription_data.get('metadata', {}).get('company_id')
        if not company_id:
            # Try to get it from the customer's metadata
            customer_id = subscription_data.get('customer')
            if customer_id:
                customer = stripe.Customer.retrieve(customer_id)
                company_id = customer.get('metadata', {}).get('company_id')
        
        if not company_id:
            print("Cannot find company_id in subscription metadata")
            return
        
        company = Company.objects.get(id=company_id)
        
        # Get plan from Stripe price ID
        price_id = subscription_data['items']['data'][0]['price']['id']
        plan = Plan.objects.get(stripe_price_id=price_id)
        
        # Create or update subscription
        subscription, created = Subscription.objects.update_or_create(
            company=company,
            defaults={
                'plan': plan,
                'stripe_subscription_id': subscription_data['id'],
                'stripe_customer_id': subscription_data['customer'],
                'status': subscription_data['status'],
                'current_period_start': timezone.datetime.fromtimestamp(subscription_data['current_period_start']),
                'current_period_end': timezone.datetime.fromtimestamp(subscription_data['current_period_end']),
                'cancel_at_period_end': subscription_data['cancel_at_period_end'],
                'trial_end': timezone.datetime.fromtimestamp(subscription_data['trial_end']) if subscription_data.get('trial_end') else None
            }
        )
        
        print(f"Subscription {'created' if created else 'updated'} for company {company.name}")
        
    except Exception as e:
        print(f"Error handling subscription creation: {str(e)}")