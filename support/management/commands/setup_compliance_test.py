from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from users.models import User, WorksIn
from users.constants import PRODUCER
from company.models import Company, Establishment
from subscriptions.models import Plan, Subscription
from carbon.models import IoTDevice, IoTDataPoint, CarbonSource, CarbonEntry
from support.models import SupportTicket, SupportMessage
import random

class Command(BaseCommand):
    help = 'Setup test data for compliance testing'

    def handle(self, *args, **options):
        self.stdout.write('🚀 Setting up compliance test data...\n')

        # Clean up existing test data
        self.cleanup_test_data()
        
        # Create test users and companies
        test_data = self.create_test_accounts()
        
        # Create IoT devices and data
        self.create_iot_test_data(test_data)
        
        # Create support tickets
        self.create_support_test_data(test_data)
        
        # Create carbon entries
        self.create_carbon_test_data(test_data)
        
        # Print summary
        self.print_summary(test_data)

    def cleanup_test_data(self):
        """Clean up any existing test data"""
        self.stdout.write('🧹 Cleaning up existing test data...')
        
        # Delete test users
        test_emails = [
            'basic-test@trazo.com',
            'standard-test@trazo.com', 
            'corporate-test@trazo.com'
        ]
        
        for email in test_emails:
            try:
                user = User.objects.get(email=email)
                # This will cascade delete related data
                user.delete()
                self.stdout.write(f'   ✅ Deleted test user: {email}')
            except User.DoesNotExist:
                pass

    def create_test_accounts(self):
        """Create test user accounts for each plan type"""
        self.stdout.write('\n👥 Creating test accounts...')
        
        # Get existing plans
        try:
            basic_plan = Plan.objects.filter(name='Basic').first()
            standard_plan = Plan.objects.filter(name='Standard').first()
            corporate_plan = Plan.objects.filter(name='Corporate').first()
            
            if not all([basic_plan, standard_plan, corporate_plan]):
                self.stdout.write(self.style.ERROR('⚠️  Plans not found. Run: python manage.py create_plans first'))
                return []
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting plans: {e}'))
            return []

        test_accounts = [
            {
                'plan': basic_plan,
                'email': 'basic-test@trazo.com',
                'company_name': 'Test Basic Farm Co.',
                'establishment_name': 'Basic Test Farm'
            },
            {
                'plan': standard_plan,
                'email': 'standard-test@trazo.com',
                'company_name': 'Test Standard Agri Ltd.',
                'establishment_name': 'Standard Test Farm'
            },
            {
                'plan': corporate_plan,
                'email': 'corporate-test@trazo.com',
                'company_name': 'Test Corporate Enterprises Inc.',
                'establishment_name': 'Corporate Test Farm'
            }
        ]

        created_accounts = []

        for account_data in test_accounts:
            try:
                # Create user
                user = User.objects.create_user(
                    email=account_data['email'],
                    password='testpass123',
                    first_name=f'{account_data["plan"].name}',
                    last_name='Tester',
                    is_active=True,
                    is_verified=True,
                    user_type=PRODUCER  # Set as PRODUCER to allow app subdomain access
                )

                # Create company
                company = Company.objects.create(
                    name=account_data['company_name'],
                    address=f'{account_data["plan"].name} Test Street 123',
                    city='Test City',
                    state='Test State',
                    country='USA',
                    contact_email=account_data['email']
                )

                # Create establishment
                establishment = Establishment.objects.create(
                    name=account_data['establishment_name'],
                    company=company,
                    address=f'{account_data["plan"].name} Farm Road 456',
                    city='Farm City',
                    state='Farm State',
                    latitude=40.7128 + random.uniform(-0.5, 0.5),
                    longitude=-74.0060 + random.uniform(-0.5, 0.5)
                )

                # Link user to company
                WorksIn.objects.create(
                    user=user,
                    company=company,
                    role=WorksIn.COMPANY_ADMIN
                )

                # Create active subscription
                subscription = Subscription.objects.create(
                    company=company,
                    plan=account_data['plan'],
                    status='active',
                    current_period_start=timezone.now(),
                    current_period_end=timezone.now() + timedelta(days=30),
                    stripe_subscription_id=f'sub_test_{account_data["plan"].name.lower()}',
                    stripe_customer_id=f'cus_test_{account_data["plan"].name.lower()}'
                )

                created_accounts.append({
                    'user': user,
                    'company': company,
                    'establishment': establishment,
                    'subscription': subscription,
                    'plan': account_data['plan']
                })

                self.stdout.write(f'   ✅ Created {account_data["plan"].name} account: {user.email}')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Error creating {account_data["plan"].name} account: {e}'))

        return created_accounts

    def create_iot_test_data(self, test_accounts):
        """Create IoT devices and sample data for automation testing"""
        self.stdout.write('\n🤖 Creating IoT test data...')

        device_types = ['fuel_sensor', 'weather_station', 'soil_moisture']

        for account in test_accounts:
            establishment = account['establishment']
            plan_name = account['plan'].name

            try:
                # Create IoT devices
                for i, device_type in enumerate(device_types):
                    device = IoTDevice.objects.create(
                        establishment=establishment,
                        device_type=device_type,
                        device_id=f'{plan_name.lower()}_test_{device_type}_{i+1}',
                        name=f'{plan_name} Test {device_type.replace("_", " ").title()}',
                        status='online',
                        battery_level=random.randint(80, 100),
                        last_seen=timezone.now()
                    )

                    # Create sample data points
                    for j in range(5):
                        timestamp = timezone.now() - timedelta(hours=random.randint(1, 24))
                        
                        if device_type == 'fuel_sensor':
                            data = {
                                'fuel_liters': round(random.uniform(10, 40), 2),
                                'efficiency': round(random.uniform(12, 18), 2)
                            }
                        elif device_type == 'weather_station':
                            data = {
                                'temperature': round(random.uniform(15, 35), 1),
                                'humidity': random.randint(40, 80),
                                'wind_speed': round(random.uniform(5, 25), 1)
                            }
                        else:  # soil_moisture
                            data = {
                                'soil_moisture_percent': random.randint(20, 70),
                                'soil_temperature': round(random.uniform(18, 28), 1)
                            }

                        IoTDataPoint.objects.create(
                            device=device,
                            timestamp=timestamp,
                            data=data,
                            quality_score=round(random.uniform(0.7, 1.0), 2),
                            processed=False
                        )

                self.stdout.write(f'   ✅ Created IoT devices for {establishment.name}')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Error creating IoT data for {plan_name}: {e}'))

    def create_support_test_data(self, test_accounts):
        """Create sample support tickets"""
        self.stdout.write('\n🎫 Creating support test tickets...')

        for account in test_accounts:
            user = account['user']
            company = account['company']
            plan_name = account['plan'].name

            try:
                # Create test tickets
                for i in range(2):
                    priority = 'high' if plan_name == 'Corporate' and i == 0 else 'normal'
                    
                    ticket = SupportTicket.objects.create(
                        subject=f'{plan_name} Plan Test Issue #{i+1}',
                        description=f'This is a test support ticket for {plan_name} plan testing. Issue #{i+1}.',
                        category='technical',
                        priority=priority,
                        user=user,
                        company=company,
                        status='open'
                    )

                    # Add a staff response to first ticket
                    if i == 0:
                        SupportMessage.objects.create(
                            ticket=ticket,
                            author=user,
                            message_type='staff',
                            content='Thank you for contacting support. We are investigating your issue.'
                        )
                        ticket.mark_first_response()

                self.stdout.write(f'   ✅ Created support tickets for {company.name}')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Error creating support tickets for {plan_name}: {e}'))

    def create_carbon_test_data(self, test_accounts):
        """Create sample carbon entries"""
        self.stdout.write('\n🌱 Creating carbon test data...')

        # Get or create carbon source
        fuel_source, created = CarbonSource.objects.get_or_create(
            name='Test Diesel Fuel',
            defaults={
                'category': 'fuel',
                'default_emission_factor': 2.7,
                'unit': 'kg CO2e/L',
                'description': 'Test fuel source for compliance testing'
            }
        )

        for account in test_accounts:
            establishment = account['establishment']
            user = account['user']
            plan_name = account['plan'].name

            try:
                # Create test carbon entries
                for i in range(3):
                    CarbonEntry.objects.create(
                        establishment=establishment,
                        type='emission',
                        source=fuel_source,
                        amount=round(random.uniform(50, 200), 2),
                        year=2024,
                        description=f'{plan_name} test entry #{i+1}',
                        created_by=user
                    )

                self.stdout.write(f'   ✅ Created carbon entries for {establishment.name}')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'   ❌ Error creating carbon entries for {plan_name}: {e}'))

    def print_summary(self, test_accounts):
        """Print summary of created test data"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('🎉 COMPLIANCE TEST DATA READY!')
        self.stdout.write('='*60)

        self.stdout.write('\n📊 TEST ACCOUNTS CREATED:')
        
        for account in test_accounts:
            plan = account['plan']
            user = account['user']
            company = account['company']
            
            self.stdout.write(f'\n🏢 {plan.name} Plan - {company.name}')
            self.stdout.write(f'   👤 Email: {user.email}')
            self.stdout.write(f'   🔑 Password: testpass123')
            self.stdout.write(f'   💰 Price: ${plan.price}/month')
            self.stdout.write(f'   🤖 IoT Automation: {plan.features.get("iot_automation_level", "N/A")}%')
            self.stdout.write(f'   🌱 Carbon Tracking: {plan.features.get("carbon_tracking", "N/A")}')
            self.stdout.write(f'   ⏱️  Support SLA: {plan.features.get("support_response_time", "N/A")}h')
            self.stdout.write(f'   ⭐ Priority Support: {"Yes" if plan.features.get("priority_support") else "No"}')

        self.stdout.write(f'\n🧪 TESTING GUIDE:')
        self.stdout.write(f'1. Start server: python manage.py runserver')
        self.stdout.write(f'2. Login with test accounts above')
        self.stdout.write(f'3. Test API endpoints:')
        self.stdout.write(f'   - /support/tickets/ (Support system)')
        self.stdout.write(f'   - /carbon/automation-rules/pending_events/ (IoT automation)')
        self.stdout.write(f'   - /carbon/automation-rules/automation_stats/ (Automation stats)')
        self.stdout.write(f'4. Check admin interface: /admin/')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Test data setup complete!')) 