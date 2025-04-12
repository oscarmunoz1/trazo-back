from rest_framework import permissions
from django.conf import settings

class HasEstablishmentCreationPermission(permissions.BasePermission):
    """
    Check if the user's company has permission to create a new establishment
    """
    message = "Your subscription plan does not allow creating more establishments."

    def has_permission(self, request, view):
        if request.method != 'POST':
            return True
            
        company = request.user.get_active_company()
        return company and company.can_create_establishment()

class HasParcelCreationPermission(permissions.BasePermission):
    """
    Check if the user's company has permission to create a new parcel
    """
    message = "Your subscription plan does not allow creating more parcels."

    def has_permission(self, request, view):
        # Bypass check in development environment
        if settings.DEBUG:
            return True
            
        if request.method != 'POST':
            return True
            
        company = request.user.get_active_company()
        establishment_id = request.data.get('establishment')
        
        if not company or not establishment_id:
            return False
            
        try:
            # Ensure establishment_id is an integer
            establishment_id = int(establishment_id)
            establishment = company.establishment_set.get(id=establishment_id)
            
            # Debug output
            print(f"Checking parcel creation permission for company: {company.id}, establishment: {establishment_id}")
            print(f"Company can create parcel: {company.can_create_parcel(establishment)}")
            print(f"Subscription plan: {company.subscription_plan}")
            if company.subscription_plan:
                print(f"Max parcels: {company.subscription_plan.features.get('max_parcels', 0)}")
                
            return company.can_create_parcel(establishment)
        except Exception as e:
            print(f"Error in HasParcelCreationPermission: {str(e)}")
            return False

class HasProductionCreationPermission(permissions.BasePermission):
    """
    Check if the user's company has permission to create a new production
    """
    message = "Your subscription plan has reached the maximum number of productions for this year."

    def has_permission(self, request, view):
        if request.method != 'POST':
            return True
            
        company = request.user.get_active_company()
        return company and company.can_create_production()
        
class HasFeaturePermission(permissions.BasePermission):
    """
    Check if the user's company has access to a specific feature
    Usage: HasFeaturePermission('establishment_full_description')
    """
    def __init__(self, feature_name):
        self.feature_name = feature_name
        self.message = f"Your subscription plan does not include the {feature_name} feature."
        
    def has_permission(self, request, view):
        company = request.user.get_active_company()
        return company and company.has_feature(self.feature_name) 