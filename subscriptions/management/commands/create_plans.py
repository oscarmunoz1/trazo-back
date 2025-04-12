from django.core.management.base import BaseCommand
from django.conf import settings
import stripe
from subscriptions.models import Plan, AddOn

stripe.api_key = settings.STRIPE_SECRET_KEY

class Command(BaseCommand):
    help = 'Creates initial subscription plans and add-ons in Stripe and syncs with the database'

    def handle(self, *args, **options):
        # Create plans
        self.create_plans()
        # Create add-ons
        self.create_addons()
        
    def create_plans(self):
        plans = [
            # Basic Monthly
            {
                'name': 'Basic',
                'slug': 'basic-monthly',
                'description': 'Basic plan for small producers',
                'price': 59.00,
                'interval': 'monthly',
                'features': {
                    'max_establishments': 1,
                    'max_parcels': 1,
                    'max_productions_per_year': 2,
                    'establishment_full_description': False,
                    'monthly_scan_limit': 5000,
                    'storage_limit_gb': 10,
                    'support_response_time': 48  # hours
                }
            },
            # Standard Monthly
            {
                'name': 'Standard',
                'slug': 'standard-monthly',
                'description': 'Standard plan for growing businesses',
                'price': 89.00,
                'interval': 'monthly',
                'features': {
                    'max_establishments': 1,
                    'max_parcels': 2,
                    'max_productions_per_year': 4,
                    'establishment_full_description': True,
                    'monthly_scan_limit': 10000,
                    'storage_limit_gb': 25,
                    'support_response_time': 24  # hours
                }
            },
            # Corporate Monthly
            {
                'name': 'Corporate',
                'slug': 'corporate-monthly',
                'description': 'Corporate plan for larger operations',
                'price': 99.00,
                'interval': 'monthly',
                'features': {
                    'max_establishments': 2,
                    'max_parcels_per_establishment': 4,
                    'max_productions_per_year': 8,
                    'establishment_full_description': True,
                    'monthly_scan_limit': 25000,
                    'storage_limit_gb': 50,
                    'support_response_time': 12  # hours
                }
            },
            # Basic Annual
            {
                'name': 'Basic',
                'slug': 'basic-yearly',
                'description': 'Basic plan for small producers (annual billing)',
                'price': 590.00,
                'interval': 'yearly',
                'features': {
                    'max_establishments': 1,
                    'max_parcels': 1,
                    'max_productions_per_year': 2,
                    'establishment_full_description': False,
                    'monthly_scan_limit': 5000,
                    'storage_limit_gb': 10,
                    'support_response_time': 48  # hours
                }
            },
            # Standard Annual
            {
                'name': 'Standard',
                'slug': 'standard-yearly',
                'description': 'Standard plan for growing businesses (annual billing)',
                'price': 890.00,
                'interval': 'yearly',
                'features': {
                    'max_establishments': 1,
                    'max_parcels': 2,
                    'max_productions_per_year': 4,
                    'establishment_full_description': True,
                    'monthly_scan_limit': 10000,
                    'storage_limit_gb': 25,
                    'support_response_time': 24  # hours
                }
            },
            # Corporate Annual
            {
                'name': 'Corporate',
                'slug': 'corporate-yearly',
                'description': 'Corporate plan for larger operations (annual billing)',
                'price': 990.00,
                'interval': 'yearly',
                'features': {
                    'max_establishments': 2,
                    'max_parcels_per_establishment': 4,
                    'max_productions_per_year': 8,
                    'establishment_full_description': True,
                    'monthly_scan_limit': 25000,
                    'storage_limit_gb': 50,
                    'support_response_time': 12  # hours
                }
            }
        ]
        
        for plan_data in plans:
            # Create product in Stripe if it doesn't exist
            product_name = f"{plan_data['name']} ({plan_data['interval']})"
            
            # Check if we already have this plan
            existing_plan = Plan.objects.filter(slug=plan_data['slug']).first()
            if existing_plan and existing_plan.stripe_price_id:
                self.stdout.write(self.style.WARNING(f'Plan already exists: {product_name}'))
                continue
                
            try:
                # Create product
                product = stripe.Product.create(
                    name=product_name,
                    description=plan_data['description'],
                )
                
                # Create price
                price = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(plan_data['price'] * 100),  # Convert to cents
                    currency='usd',
                    recurring={
                        'interval': 'month' if plan_data['interval'] == 'monthly' else 'year',
                    },
                    metadata={
                        'plan_slug': plan_data['slug']
                    }
                )
                
                # Create or update plan in the database
                Plan.objects.update_or_create(
                    slug=plan_data['slug'],
                    defaults={
                        'name': plan_data['name'],
                        'description': plan_data['description'],
                        'price': plan_data['price'],
                        'interval': plan_data['interval'],
                        'features': plan_data['features'],
                        'stripe_price_id': price.id,
                        'is_active': True
                    }
                )
                
                self.stdout.write(self.style.SUCCESS(f'Successfully created plan: {product_name}'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creating plan {product_name}: {str(e)}'))
    
    def create_addons(self):
        addons = [
            {
                'name': 'Extra Production',
                'slug': 'extra-production',
                'description': 'Add an additional production to your yearly limit',
                'price': 15.00
            },
            {
                'name': 'Extra Parcel',
                'slug': 'extra-parcel',
                'description': 'Add an additional parcel to your subscription',
                'price': 20.00
            },
            {
                'name': 'Extra Storage (1 year)',
                'slug': 'extra-storage',
                'description': 'Add an additional year of historical data storage',
                'price': 5.00
            }
        ]
        
        for addon_data in addons:
            # Check if we already have this add-on
            existing_addon = AddOn.objects.filter(slug=addon_data['slug']).first()
            if existing_addon and existing_addon.stripe_price_id:
                self.stdout.write(self.style.WARNING(f'Add-on already exists: {addon_data["name"]}'))
                continue
                
            try:
                # Create product
                product = stripe.Product.create(
                    name=addon_data['name'],
                    description=addon_data['description'],
                )
                
                # Create price
                price = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(addon_data['price'] * 100),  # Convert to cents
                    currency='usd',
                    metadata={
                        'addon_slug': addon_data['slug']
                    }
                )
                
                # Create or update add-on in the database
                AddOn.objects.update_or_create(
                    slug=addon_data['slug'],
                    defaults={
                        'name': addon_data['name'],
                        'description': addon_data['description'],
                        'price': addon_data['price'],
                        'stripe_price_id': price.id,
                        'is_active': True
                    }
                )
                
                self.stdout.write(self.style.SUCCESS(f'Successfully created add-on: {addon_data["name"]}'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creating add-on {addon_data["name"]}: {str(e)}')) 