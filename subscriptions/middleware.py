from django.utils.functional import SimpleLazyObject
from django.conf import settings

class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Add subscription features to the request
        if hasattr(request, 'user') and request.user.is_authenticated:
            def get_subscription_features():
                active_company = getattr(request.user, 'active_company', None)
                if active_company:
                    if hasattr(active_company, 'subscription_plan') and active_company.subscription_plan:
                        return active_company.subscription_plan.features
                return {}
                
            request.subscription_features = SimpleLazyObject(get_subscription_features)
        else:
            request.subscription_features = {}
            
        response = self.get_response(request)
        return response 

class UsageTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Track scan usage for QR code scans
        if request.path.startswith('/api/scan/') and hasattr(request, 'user') and request.user.is_authenticated:
            try:
                company = request.user.active_company
                if company and hasattr(company, 'subscription'):
                    company.subscription.scan_count += 1
                    company.subscription.save(update_fields=['scan_count'])
            except Exception as e:
                # Log error but don't fail the request
                print(f"Error tracking scan usage: {str(e)}")
        
        return response 