from django.core.management.base import BaseCommand
from django.conf import settings
import stripe
from subscriptions.models import Plan, AddOn

stripe.api_key = settings.STRIPE_SECRET_KEY

class Command(BaseCommand):
    help = 'Creates initial subscription plans and add-ons in Stripe and syncs with the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of existing plans and add-ons',
        )
        parser.add_argument(
            '--environment',
            type=str,
            default='development',
            help='Environment (development, staging, production)',
        )

    def handle(self, *args, **options):
        self.force = options['force']
        self.environment = options['environment']
        
        self.stdout.write(self.style.SUCCESS(f'Setting up plans and add-ons for {self.environment} environment...'))
        
        # Create plans
        self.create_plans()
        # Create add-ons
        self.create_addons()
        
        self.stdout.write(self.style.SUCCESS('Setup completed successfully!'))
        
    def create_plans(self):
        plans = [
            # Basic Monthly
            {
                'name': 'Basic',
                'slug': 'basic-monthly',
                'description': 'Basic plan for small producers with manual carbon tracking and 50% IoT automation',
                'price': 69.00,
                'interval': 'monthly',
                'features': {
                    'max_establishments': 1,
                    'max_parcels': 1,
                    'max_productions_per_year': 2,
                    'establishment_full_description': True,
                    'monthly_scan_limit': 5000,
                    'storage_limit_gb': 10,
                    'support_response_time': 48,
                    'iot_automation_level': 50,
                    'carbon_tracking': 'manual',
                    'trial_no_card_days': 7,
                    'trial_with_card_days': 14,
                    'educational_resources': False,
                    'custom_reporting': False,
                    'priority_support': False
                }
            },
            # Standard Monthly
            {
                'name': 'Standard',
                'slug': 'standard-monthly',
                'description': 'Standard plan for growing businesses with automated IoT carbon tracking and educational resources',
                'price': 119.00,
                'interval': 'monthly',
                'features': {
                    'max_establishments': 2,
                    'max_parcels': 2,
                    'max_productions_per_year': 4,
                    'establishment_full_description': True,
                    'monthly_scan_limit': 10000,
                    'storage_limit_gb': 25,
                    'support_response_time': 24,
                    'iot_automation_level': 75,
                    'carbon_tracking': 'automated',
                    'trial_no_card_days': 7,
                    'trial_with_card_days': 14,
                    'educational_resources': True,
                    'custom_reporting': False,
                    'priority_support': False,
                    'blockchain_eligible': True
                }
            },
            # Corporate Monthly
            {
                'name': 'Corporate',
                'slug': 'corporate-monthly',
                'description': 'Corporate plan for larger operations with full IoT automation, custom reporting, and priority support',
                'price': 149.00,
                'interval': 'monthly',
                'features': {
                    'max_establishments': 4,
                    'max_parcels_per_establishment': 4,
                    'max_productions_per_year': 6,
                    'establishment_full_description': True,
                    'monthly_scan_limit': 20000,
                    'storage_limit_gb': 50,
                    'support_response_time': 12,
                    'iot_automation_level': 85,
                    'carbon_tracking': 'automated',
                    'trial_no_card_days': 7,
                    'trial_with_card_days': 14,
                    'educational_resources': True,
                    'custom_reporting': True,
                    'priority_support': True,
                    'blockchain_eligible': True
                }
            },
            # Enterprise Monthly
            {
                'name': 'Enterprise',
                'slug': 'enterprise-monthly',
                'description': 'Enterprise plan for large-scale operations with unlimited features',
                'price': 499.00,
                'interval': 'monthly',
                'features': {
                    'max_establishments': -1,
                    'max_parcels_per_establishment': -1,
                    'max_productions_per_year': -1,
                    'establishment_full_description': True,
                    'monthly_scan_limit': -1,
                    'storage_limit_gb': -1,
                    'support_response_time': 4,
                    'iot_automation_level': 85,
                    'carbon_tracking': 'automated',
                    'trial_no_card_days': 7,
                    'trial_with_card_days': 14,
                    'educational_resources': True,
                    'custom_reporting': True,
                    'priority_support': True,
                    'white_label': True,
                    'api_access': True,
                    'dedicated_support': True,
                    'blockchain_eligible': True
                }
            },
            # Basic Annual
            {
                'name': 'Basic',
                'slug': 'basic-yearly',
                'description': 'Basic plan for small producers with manual carbon tracking (annual billing - save 10%)',
                'price': 745.20,
                'interval': 'yearly',
                'features': {
                    'max_establishments': 1,
                    'max_parcels': 1,
                    'max_productions_per_year': 2,
                    'establishment_full_description': True,
                    'monthly_scan_limit': 5000,
                    'storage_limit_gb': 10,
                    'support_response_time': 48,
                    'iot_automation_level': 50,
                    'carbon_tracking': 'manual',
                    'trial_no_card_days': 7,
                    'trial_with_card_days': 14,
                    'educational_resources': False,
                    'custom_reporting': False,
                    'priority_support': False
                }
            },
            # Standard Annual
            {
                'name': 'Standard',
                'slug': 'standard-yearly',
                'description': 'Standard plan for growing businesses with automated carbon tracking (annual billing - save 10%)',
                'price': 1285.20,
                'interval': 'yearly',
                'features': {
                    'max_establishments': 2,
                    'max_parcels': 2,
                    'max_productions_per_year': 4,
                    'establishment_full_description': True,
                    'monthly_scan_limit': 10000,
                    'storage_limit_gb': 25,
                    'support_response_time': 24,
                    'iot_automation_level': 75,
                    'carbon_tracking': 'automated',
                    'trial_no_card_days': 7,
                    'trial_with_card_days': 14,
                    'educational_resources': True,
                    'custom_reporting': False,
                    'priority_support': False,
                    'blockchain_eligible': True
                }
            },
            # Corporate Annual
            {
                'name': 'Corporate',
                'slug': 'corporate-yearly',
                'description': 'Corporate plan for larger operations with full automation and reporting (annual billing - save 10%)',
                'price': 1612.80,
                'interval': 'yearly',
                'features': {
                    'max_establishments': 4,
                    'max_parcels_per_establishment': 4,
                    'max_productions_per_year': 6,
                    'establishment_full_description': True,
                    'monthly_scan_limit': 20000,
                    'storage_limit_gb': 50,
                    'support_response_time': 12,
                    'iot_automation_level': 85,
                    'carbon_tracking': 'automated',
                    'trial_no_card_days': 7,
                    'trial_with_card_days': 14,
                    'educational_resources': True,
                    'custom_reporting': True,
                    'priority_support': True,
                    'blockchain_eligible': True
                }
            },
            # Enterprise Annual
            {
                'name': 'Enterprise',
                'slug': 'enterprise-yearly',
                'description': 'Enterprise plan for large-scale operations with unlimited features (annual billing - save 10%)',
                'price': 5389.20,
                'interval': 'yearly',
                'features': {
                    'max_establishments': -1,
                    'max_parcels_per_establishment': -1,
                    'max_productions_per_year': -1,
                    'establishment_full_description': True,
                    'monthly_scan_limit': -1,
                    'storage_limit_gb': -1,
                    'support_response_time': 4,
                    'iot_automation_level': 85,
                    'carbon_tracking': 'automated',
                    'trial_no_card_days': 7,
                    'trial_with_card_days': 14,
                    'educational_resources': True,
                    'custom_reporting': True,
                    'priority_support': True,
                    'white_label': True,
                    'api_access': True,
                    'dedicated_support': True,
                    'blockchain_eligible': True
                }
            }
        ]
        
        self.stdout.write(self.style.SUCCESS(f'Creating {len(plans)} plans...'))
        
        for plan_data in plans:
            # Create product in Stripe if it doesn't exist
            product_name = f"Trazo {plan_data['name']} ({plan_data['interval'].title()})"
            
            # Check if we already have this plan
            existing_plan = Plan.objects.filter(slug=plan_data['slug']).first()
            if existing_plan and existing_plan.stripe_price_id and not self.force:
                self.stdout.write(self.style.WARNING(f'Plan already exists: {product_name}'))
                continue
                
            try:
                # Create product
                product = stripe.Product.create(
                    name=product_name,
                    description=plan_data['description'],
                    metadata={
                        'environment': self.environment,
                        'plan_slug': plan_data['slug']
                    }
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
                        'plan_slug': plan_data['slug'],
                        'environment': self.environment
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
                
                self.stdout.write(self.style.SUCCESS(f'✓ Created plan: {product_name}'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error creating plan {product_name}: {str(e)}'))
    
    def create_addons(self):
        addons = [
            {
                'name': 'Extra Production',
                'slug': 'extra-production',
                'description': 'Add an additional production to your yearly limit with IoT monitoring and carbon tracking',
                'price': 20.00  # Updated from 15.00
            },
            {
                'name': 'Extra Parcel',
                'slug': 'extra-parcel',
                'description': 'Add an additional parcel to your subscription with carbon footprint mapping',
                'price': 25.00  # Updated from 20.00
            },
            {
                'name': 'Extra Storage (1 year)',
                'slug': 'extra-storage',
                'description': 'Add an additional year of historical data storage including IoT logs and carbon data',
                'price': 10.00  # Updated from 5.00
            },
            {
                'name': 'Blockchain Verification',
                'slug': 'blockchain-verification',
                'description': 'Add immutable blockchain records with USDA verification and tradable carbon credits',
                'price': 15.00  # Updated from 5.00
            }
        ]
        
        self.stdout.write(self.style.SUCCESS(f'Creating {len(addons)} add-ons...'))
        
        for addon_data in addons:
            # Check if we already have this add-on
            existing_addon = AddOn.objects.filter(slug=addon_data['slug']).first()
            if existing_addon and existing_addon.stripe_price_id and not self.force:
                self.stdout.write(self.style.WARNING(f'Add-on already exists: {addon_data["name"]}'))
                continue
                
            try:
                # Create product
                product = stripe.Product.create(
                    name=f"Trazo {addon_data['name']}",
                    description=addon_data['description'],
                    metadata={
                        'environment': self.environment,
                        'addon_slug': addon_data['slug']
                    }
                )
                
                # Create price
                price = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(addon_data['price'] * 100),  # Convert to cents
                    currency='usd',
                    metadata={
                        'addon_slug': addon_data['slug'],
                        'environment': self.environment
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
                
                self.stdout.write(self.style.SUCCESS(f'✓ Created add-on: {addon_data["name"]}'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error creating add-on {addon_data["name"]}: {str(e)}')) 