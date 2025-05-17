from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.core.cache import cache
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
import logging

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)

class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for listing subscription plans"""
    queryset = Plan.objects.filter(is_active=True)
    serializer_class = PlanSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        interval = self.request.query_params.get('interval')
        
        logger.info(f"Getting plans with interval: {interval}")
        logger.info(f"Initial queryset count: {queryset.count()}")
        
        # Create cache key based on interval
        cache_key = f"plans_{interval}" if interval else "plans_all"
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            logger.info(f"Using cached plan data for {cache_key}")
            return cached_data
        
        # Filter by interval if provided
        if interval:
            queryset = queryset.filter(interval=interval)
            logger.info(f"Filtered queryset count: {queryset.count()}")
        
        # Cache the queryset for 1 hour (3600 seconds)
        cache.set(cache_key, queryset, 3600)
        logger.info(f"Cached plan data for {cache_key}")
        
        return queryset

class AddOnViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for listing available add-ons"""
    queryset = AddOn.objects.filter(is_active=True)
    serializer_class = AddOnSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Create cache key for add-ons
        cache_key = "addons_active"
        cached_data = cache.get(cache_key)
        
        if cached_data is not None:
            logger.info("Using cached add-on data")
            return cached_data
        
        queryset = AddOn.objects.filter(is_active=True)
        
        # Cache the queryset for 1 hour (3600 seconds)
        cache.set(cache_key, queryset, 3600)
        logger.info("Cached add-on data")
        
        return queryset

class SubscriptionViewSet(viewsets.ModelViewSet):
    """API endpoint for managing subscriptions"""
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Subscription.objects.all()
        return Subscription.objects.filter(company__in=user.companies.all())
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Return all billing data in a single request"""
        try:
            user = request.user
            companies = user.companies.all()
            
            # Get subscription - typically just one per user/company
            subscriptions = self.get_queryset()
            subscription = subscriptions.first() if subscriptions.exists() else None
            
            # Get available add-ons
            addons = AddOn.objects.filter(is_active=True)
            
            # Get payment methods for user's companies
            payment_methods = PaymentMethod.objects.filter(company__in=companies)
            
            # Get invoices for user's companies
            invoices = Invoice.objects.filter(company__in=companies).order_by('-invoice_date')
            
            # Return all data in one response
            response_data = {
                'subscription': SubscriptionSerializer(subscription).data if subscription else None,
                'addons': AddOnSerializer(addons, many=True).data,
                'paymentMethods': PaymentMethodSerializer(payment_methods, many=True).data,
                'invoices': InvoiceSerializer(invoices, many=True).data
            }
            
            return Response(response_data)
        except Exception as e:
            logger.error(f"Error in dashboard endpoint: {str(e)}")
            return Response(
                {'error': f'Error fetching dashboard data: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
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
        """Add an add-on to the subscription with Stripe checkout"""
        subscription = self.get_object()
        addon_id = request.data.get('addon_id')
        quantity = int(request.data.get('quantity', 1))
        return_url = request.data.get('return_url', None)
        
        # Better validation
        if not addon_id:
            return Response({'error': 'addon_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if quantity <= 0:
            return Response({'error': 'quantity must be greater than 0'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Add request logging for debugging
        logger.info(f"Creating checkout session for addon {addon_id} with quantity {quantity} to subscription {subscription.id}")
        
        try:
            addon = AddOn.objects.get(id=addon_id, is_active=True)
            
            # Get the frontend URL from settings or use a default
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            
            # Create a Stripe checkout session for the add-on
            success_url_params = "success=true&from_addon=true"
            
            # If return_url is provided, add it to the success URL
            if return_url:
                success_url_params += f"&return_url={return_url}"
                
            success_url = f"{frontend_url}/admin/dashboard/stripe-success?{success_url_params}"
            cancel_url = f"{frontend_url}/admin/dashboard/billing"
            
            # Create the checkout session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': addon.stripe_price_id,
                    'quantity': quantity,
                }],
                mode='payment',
                customer=subscription.stripe_customer_id,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'company_id': str(subscription.company.id),
                    'subscription_id': str(subscription.id),
                    'addon_id': str(addon.id),
                    'quantity': str(quantity),
                    'addon_type': addon.slug,
                    'is_addon_purchase': 'true',
                    'return_url': return_url
                }
            )
            
            # Return the session URL
            logger.info(f"Created checkout session: {checkout_session.id}")
            return Response({
                'url': checkout_session.url,
                'session_id': checkout_session.id
            })
            
        except AddOn.DoesNotExist:
            logger.error(f"Addon not found: {addon_id}")
            return Response({'error': 'Add-on not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error creating checkout session for add-on: {str(e)}")
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
        mode = data.get('mode', 'subscription')  # Default to subscription mode
        
        # Add-on parameters
        addon_type = data.get('addon_type')
        quantity = int(data.get('quantity', 1))
        success_url = data.get('successUrl')
        cancel_url = data.get('cancelUrl')
        
        try:
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
            
            # Special mode for setting up a payment method without a charge
            if mode == 'setup':
                # Determine success and cancel URLs
                success_url_final = success_url or f"{settings.FRONTEND_URL}/admin/dashboard/account/billing?success=true"
                cancel_url_final = cancel_url or f"{settings.FRONTEND_URL}/admin/dashboard/account/billing?canceled=true"
                
                # Create checkout session for payment method setup
                checkout_session = stripe.checkout.Session.create(
                    customer=customer_id,
                    payment_method_types=['card'],
                    mode='setup',
                    success_url=success_url_final,
                    cancel_url=cancel_url_final,
                    metadata={
                        'company_id': company.id,
                        'setup_type': 'payment_method'
                    }
                )
                
                return Response({
                    'url': checkout_session.url
                })
            
            # For add-on purchases, we use a different flow
            if addon_type:
                # Make sure the company has an active subscription
                if not hasattr(company, 'subscription') or not company.subscription.stripe_subscription_id:
                    return Response(
                        {'error': 'Company must have an active subscription to purchase add-ons'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Get the add-on
                addon_slug_map = {
                    'extraProduction': 'extra-production',
                    'extraParcel': 'extra-parcel',
                    'extraStorage': 'extra-storage'
                }
                
                try:
                    addon = AddOn.objects.get(slug=addon_slug_map[addon_type], is_active=True)
                except AddOn.DoesNotExist:
                    return Response({'error': 'Add-on not found'}, status=status.HTTP_404_NOT_FOUND)
                
                # Determine success and cancel URLs
                success_url_params = f"success=true&session_id={{CHECKOUT_SESSION_ID}}&company_id={str(company.id)}&addon=true"
                
                # Add return_url parameter if provided
                if success_url:
                    success_url_params += f"&return_url={success_url}"
                
                success_url_final = success_url or f"{settings.FRONTEND_URL}/admin/dashboard/stripe-success?{success_url_params}"
                cancel_url_final = cancel_url or f"{settings.FRONTEND_URL}/admin/dashboard/plan-usage?canceled=true"
                
                # Create checkout session for add-on
                checkout_session = stripe.checkout.Session.create(
                    customer=customer_id,
                    payment_method_types=['card'],
                    line_items=[{
                        'price': addon.stripe_price_id,
                        'quantity': quantity,
                    }],
                    mode='payment',  # Use one-time payment for add-ons
                    success_url=success_url_final,
                    cancel_url=cancel_url_final,
                    metadata={
                        'company_id': company.id,
                        'addon_id': addon.id,
                        'quantity': quantity,
                        'addon_type': addon_type,
                        'return_url': success_url
                    }
                )
                
                return Response({
                    'url': checkout_session.url
                })
            
            # Regular subscription flow
            plan = Plan.objects.get(id=plan_id, interval=interval, is_active=True)
            
            # Set up trial parameters if requested
            subscription_data = {}
            if trial_days > 0:
                subscription_data['trial_period_days'] = trial_days
            
            # Determine success and cancel URLs based on whether this is a new company
            success_url = f"{settings.FRONTEND_URL}/admin/dashboard/stripe-success?success=true&session_id={{CHECKOUT_SESSION_ID}}"
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
    def create_customer_portal_session(self, request):
        """Create a Stripe Customer Portal session for managing payment methods and billing"""
        data = request.data
        company_id = data.get('company_id')
        return_url = data.get('return_url', f"{settings.FRONTEND_URL}/admin/dashboard/account/billing")
        
        try:
            company = Company.objects.get(id=company_id)
            
            # Verify user has permission to manage this company
            if not request.user.is_staff and company not in request.user.companies.all():
                return Response(
                    {'error': 'You do not have permission to manage this company'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Check if company has a Stripe customer
            if not hasattr(company, 'subscription') or not company.subscription.stripe_customer_id:
                return Response(
                    {'error': 'Company does not have a Stripe customer account'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            customer_id = company.subscription.stripe_customer_id
            
            # Create a portal session
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
                flow_data={
                    'type': 'payment_method_update',
                }
            )
            
            # Return the URL to redirect the user to
            return Response({
                'url': portal_session.url
            })
            
        except Company.DoesNotExist:
            return Response({'error': 'Company not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error creating customer portal session: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def complete_checkout(self, request):
        """Complete the checkout after a successful payment"""
        session_id = request.data.get('session_id')
        company_id = request.data.get('company_id')
        
        # Log the request data for debugging
        logger.info(f"Complete checkout called with: session_id={session_id}, company_id={company_id}")
        
        if not session_id or not company_id:
            return Response({'success': False, 'error': 'Missing required parameters'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Retrieve checkout session from Stripe
            try:
                session = stripe.checkout.Session.retrieve(session_id)
                logger.info(f"Retrieved Stripe session: {session_id}")
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error retrieving session: {str(e)}")
                return Response({'success': False, 'error': f'Stripe error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify this is a valid checkout session
            if session.get('payment_status') != 'paid':
                logger.warning(f"Payment not completed for session {session_id}, status: {session.get('payment_status')}")
                return Response({'success': False, 'error': f"Payment not completed, status: {session.get('payment_status')}"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get subscription ID from session
            subscription_id = session.get('subscription')
            if not subscription_id:
                logger.warning(f"No subscription found in session {session_id}")
                return Response({'success': False, 'error': 'No subscription found in this session'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get subscription details
            try:
                stripe_sub = stripe.Subscription.retrieve(subscription_id)
                logger.info(f"Retrieved Stripe subscription: {subscription_id}")
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error retrieving subscription: {str(e)}")
                return Response({'success': False, 'error': f'Error retrieving subscription: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get company
            try:
                company = Company.objects.get(id=company_id)
            except Company.DoesNotExist:
                logger.error(f"Company with ID {company_id} not found")
                return Response({'success': False, 'error': f'Company with ID {company_id} not found'}, status=status.HTTP_404_NOT_FOUND)
            
            # Get plan from price ID
            price_id = stripe_sub['items']['data'][0]['price']['id']
            try:
                plan = Plan.objects.get(stripe_price_id=price_id)
            except Plan.DoesNotExist:
                logger.error(f"Plan with stripe_price_id {price_id} not found")
                return Response({'success': False, 'error': f'Plan with price ID {price_id} not found'}, status=status.HTTP_404_NOT_FOUND)
            
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
            
            # After creating the subscription, try to return updated company data
            try:
                # Try with full context
                company_data = RetrieveCompanySerializer(company, context={'request': request}).data
            except Exception as serializer_error:
                # If that fails, create a minimal data structure with just the essential subscription info
                logger.warning(f"Error serializing company with request context: {serializer_error}")
                company_data = {
                    'id': company.id,
                    'name': company.name,
                    'has_subscription': True,
                    'subscription': {
                        'id': subscription.id,
                        'status': subscription.status,
                        'current_period_end': subscription.current_period_end,
                        'stripe_subscription_id': subscription.stripe_subscription_id
                    },
                    'subscription_plan': {
                        'id': plan.id,
                        'name': plan.name,
                        'interval': plan.interval,
                        'features': plan.features
                    }
                }
            
            logger.info(f"Successfully completed checkout for session {session_id}, subscription {subscription.id}")
            return Response({
                'success': True, 
                'subscription_id': subscription.id,
                'company': company_data  # Include the company data with subscription info
            })
            
        except Exception as e:
            logger.error(f"Unexpected error completing checkout: {str(e)}", exc_info=True)
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Stripe webhook handler
@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    print(f"Received webhook payload: {payload}")
    print(f"Received webhook signature header: {sig_header}")
    
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
        # Check if this is a payment method setup session
        if data.get('mode') == 'setup' and data.get('metadata', {}).get('setup_type') == 'payment_method':
            # Payment method setup will be handled via the setup_intent.succeeded event
            print("Checkout session completed for payment method setup")
        # Check if this is an add-on purchase
        elif data.get('metadata', {}).get('is_addon_purchase') == 'true':
            handle_addon_purchase_completed(data)
        elif data.get('mode') == 'payment' and data.get('metadata', {}).get('addon_id'):
            handle_addon_purchase_completed(data)
        else:
            handle_checkout_session_completed(data)
    elif event_type == 'setup_intent.succeeded':
        # Handle successful setup of payment method
        handle_setup_intent_succeeded(data)
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

def handle_addon_purchase_completed(session):
    """Process completed add-on purchase"""
    try:
        metadata = session.get('metadata', {})
        
        # Extract data from session metadata
        company_id = metadata.get('company_id')
        subscription_id = metadata.get('subscription_id')
        addon_id = metadata.get('addon_id')
        quantity = int(metadata.get('quantity', 1))
        addon_type = metadata.get('addon_type')
        return_url = metadata.get('return_url', None)
        
        # Log the addon purchase data
        logger.info(f"Processing add-on purchase: company={company_id}, addon={addon_id}, quantity={quantity}, type={addon_type}")
        
        if not company_id or not addon_id:
            logger.error("Missing required data in add-on purchase metadata")
            return
        
        company = Company.objects.get(id=company_id)
        addon = AddOn.objects.get(id=addon_id)
        
        # Find the subscription - either by ID in metadata or from company
        if subscription_id:
            subscription = Subscription.objects.get(id=subscription_id, company=company)
        else:
            # Make sure the company has an active subscription
            if not hasattr(company, 'subscription') or not company.subscription.stripe_subscription_id:
                logger.error(f"Company {company.id} has no active subscription for add-on purchase")
                return
            subscription = company.subscription
        
        with transaction.atomic():
            # Create subscription add-on record
            subscription_addon, created = SubscriptionAddOn.objects.get_or_create(
                subscription=subscription,
                addon=addon,
                defaults={'quantity': quantity}
            )
            
            if not created:
                # If the add-on already exists, increment the quantity
                subscription_addon.quantity += quantity
                subscription_addon.save()
                logger.info(f"Updated existing addon quantity to {subscription_addon.quantity}")
            else:
                logger.info(f"Created new addon with quantity {quantity}")
            
            # Update usage limits based on add-on type
            addon_slug = addon_type.replace('-', '') if addon_type else addon.slug.replace('-', '')
            
            if addon_slug == 'extraProduction' or addon_slug == 'extraproduction':
                # Increase allowed productions
                productions_per_addon = 10  # Each add-on gives 10 more productions
                additional_productions = quantity * productions_per_addon
                
                # Update the plan features for this subscription
                custom_features = subscription.plan.features.copy()
                if 'max_productions_per_year' in custom_features:
                    custom_features['max_productions_per_year'] += additional_productions
                    logger.info(f"Adding {additional_productions} productions to subscription")
                    
                    # Create or update custom plan
                    custom_plan_name = f"{subscription.plan.name} (Custom)"
                    custom_plan_slug = f"{subscription.plan.slug}-custom-{subscription.id}"
                    
                    custom_plan, created = Plan.objects.get_or_create(
                        slug=custom_plan_slug,
                        defaults={
                            'name': custom_plan_name,
                            'description': f"Custom plan with additional productions",
                            'price': subscription.plan.price,
                            'interval': subscription.plan.interval,
                            'features': custom_features,
                            'is_active': False,  # Not available for new subscriptions
                            'stripe_price_id': subscription.plan.stripe_price_id
                        }
                    )
                    
                    if not created:
                        # Update the existing custom plan
                        custom_plan.features = custom_features
                        custom_plan.save()
                    
                    # Update the subscription to use the custom plan
                    subscription.plan = custom_plan
                    subscription.save()
                
            elif addon_slug == 'extraParcel' or addon_slug == 'extraparcel':
                # Increase allowed parcels
                parcels_per_addon = 5  # Each add-on gives 5 more parcels
                additional_parcels = quantity * parcels_per_addon
                
                # Update the plan features for this subscription
                custom_features = subscription.plan.features.copy()
                if 'max_parcels' in custom_features:
                    custom_features['max_parcels'] += additional_parcels
                    logger.info(f"Adding {additional_parcels} parcels to subscription")
                    
                    # Create or update custom plan
                    custom_plan_name = f"{subscription.plan.name} (Custom)"
                    custom_plan_slug = f"{subscription.plan.slug}-custom-{subscription.id}"
                    
                    custom_plan, created = Plan.objects.get_or_create(
                        slug=custom_plan_slug,
                        defaults={
                            'name': custom_plan_name,
                            'description': f"Custom plan with additional parcels",
                            'price': subscription.plan.price,
                            'interval': subscription.plan.interval,
                            'features': custom_features,
                            'is_active': False,
                            'stripe_price_id': subscription.plan.stripe_price_id
                        }
                    )
                    
                    if not created:
                        # Update the existing custom plan
                        custom_plan.features = custom_features
                        custom_plan.save()
                    
                    # Update the subscription to use the custom plan
                    subscription.plan = custom_plan
                    subscription.save()
                
            elif addon_slug == 'extraStorage' or addon_slug == 'extrastorage':
                # Increase storage limit
                storage_per_addon = 10  # Each add-on gives 10 more GB
                additional_storage = quantity * storage_per_addon
                
                # Update the plan features for this subscription
                custom_features = subscription.plan.features.copy()
                if 'storage_limit_gb' in custom_features:
                    custom_features['storage_limit_gb'] += additional_storage
                    logger.info(f"Adding {additional_storage} GB storage to subscription")
                    
                    # Create or update custom plan
                    custom_plan_name = f"{subscription.plan.name} (Custom)"
                    custom_plan_slug = f"{subscription.plan.slug}-custom-{subscription.id}"
                    
                    custom_plan, created = Plan.objects.get_or_create(
                        slug=custom_plan_slug,
                        defaults={
                            'name': custom_plan_name,
                            'description': f"Custom plan with additional storage",
                            'price': subscription.plan.price,
                            'interval': subscription.plan.interval,
                            'features': custom_features,
                            'is_active': False,
                            'stripe_price_id': subscription.plan.stripe_price_id
                        }
                    )
                    
                    if not created:
                        # Update the existing custom plan
                        custom_plan.features = custom_features
                        custom_plan.save()
                    
                    # Update the subscription to use the custom plan
                    subscription.plan = custom_plan
                    subscription.save()
            
            # Create an invoice record for the add-on purchase if there's a payment_intent
            payment_intent = session.get('payment_intent')
            if payment_intent:
                Invoice.objects.create(
                    company=company,
                    subscription=subscription,
                    stripe_invoice_id=payment_intent,
                    amount=addon.price * quantity,
                    status='paid',
                    description=f"{addon.name} x{quantity}",
                    invoice_date=timezone.now()
                )
            
            logger.info(f"Successfully processed add-on purchase: {addon.name} x{quantity} for {company.name}")
            return True
    except Exception as e:
        logger.error(f"Error processing add-on purchase: {str(e)}")
        return False

def handle_setup_intent_succeeded(setup_intent):
    """Process successful setup intent for payment methods"""
    try:
        # Get the payment method ID from the setup intent
        payment_method_id = setup_intent.get('payment_method')
        customer_id = setup_intent.get('customer')
        
        if not payment_method_id or not customer_id:
            print("Missing payment_method_id or customer_id in setup intent")
            return
        
        # Retrieve payment method details from Stripe
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
        
        # Find the subscription with this customer ID
        subscription = Subscription.objects.filter(stripe_customer_id=customer_id).first()
        if not subscription:
            print(f"No subscription found for customer {customer_id}")
            return
        
        company = subscription.company
        
        # Get card details
        card = payment_method.get('card', {})
        if not card:
            print("No card details in payment method")
            return
        
        # Create payment method record
        is_first = company.payment_methods.count() == 0
        
        payment_method_obj = PaymentMethod.objects.create(
            company=company,
            stripe_payment_method_id=payment_method_id,
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
                    'default_payment_method': payment_method_id
                }
            )
            
        print(f"Payment method {payment_method_id} successfully created for company {company.name}")
        
    except Exception as e:
        print(f"Error handling setup intent: {str(e)}")