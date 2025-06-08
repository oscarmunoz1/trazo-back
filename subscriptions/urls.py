from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'plans', views.PlanViewSet, basename='plan')
router.register(r'subscriptions', views.SubscriptionViewSet, basename='subscription')
router.register(r'addons', views.AddOnViewSet, basename='addon')
router.register(r'invoices', views.InvoiceViewSet, basename='invoice')
router.register(r'payment-methods', views.PaymentMethodViewSet, basename='payment-method')
router.register(r'checkout', views.CheckoutViewSet, basename='checkout')

urlpatterns = [
    path('subscriptions/', include(router.urls)),
    path('subscriptions/webhook/', views.stripe_webhook, name='webhook'),
    
    # Blockchain subscription endpoints
    path('billing/subscribe-blockchain/', views.BlockchainSubscriptionView.as_view(), name='subscribe-blockchain'),
    path('billing/subscription-status/', views.BlockchainSubscriptionStatusView.as_view(), name='subscription-status'),
    path('billing/webhook/', views.StripeWebhookView.as_view(), name='stripe-webhook-new'),
    # Ensures that dashboard endpoint is accessible at /subscriptions/subscriptions/dashboard/
]
