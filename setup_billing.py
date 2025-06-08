#!/usr/bin/env python
"""
Trazo Billing Setup Script
==========================

This script sets up subscription plans and add-ons for different environments.
It validates Stripe configuration and creates all necessary products and prices.

Usage:
    python setup_billing.py --environment staging
    python setup_billing.py --environment production --force
    python setup_billing.py --help
"""

import os
import sys
import argparse
import subprocess
import django
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.conf import settings
import stripe

def validate_environment():
    """Validate required environment variables and Stripe connection."""
    required_vars = [
        'STRIPE_SECRET_KEY',
        'STRIPE_PUBLIC_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not getattr(settings, var, None):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease add these to your .env file or environment variables.")
        return False
    
    # Test Stripe connection
    try:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.Account.retrieve()
        print("✅ Stripe connection validated")
        return True
    except Exception as e:
        print(f"❌ Stripe connection failed: {str(e)}")
        print("Please check your STRIPE_SECRET_KEY")
        return False

def check_existing_data():
    """Check what plans and add-ons already exist."""
    from subscriptions.models import Plan, AddOn
    
    existing_plans = Plan.objects.all().count()
    existing_addons = AddOn.objects.all().count()
    
    print(f"📊 Current database state:")
    print(f"   - Plans: {existing_plans}")
    print(f"   - Add-ons: {existing_addons}")
    
    return existing_plans, existing_addons

def run_setup_command(environment, force=False):
    """Run the Django management command."""
    cmd = [
        sys.executable, 
        'manage.py', 
        'create_plans',
        '--environment', environment
    ]
    
    if force:
        cmd.append('--force')
    
    print(f"🚀 Running command: {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed with exit code {e.returncode}")
        return False

def display_summary():
    """Display final summary of created plans and add-ons."""
    from subscriptions.models import Plan, AddOn
    
    plans = Plan.objects.all().order_by('interval', 'price')
    addons = AddOn.objects.all().order_by('price')
    
    print("\n" + "=" * 60)
    print("📋 SETUP SUMMARY")
    print("=" * 60)
    
    print(f"\n📦 Plans Created ({plans.count()}):")
    for plan in plans:
        status = "✅ Active" if plan.is_active else "❌ Inactive"
        print(f"   - {plan.name} ({plan.interval}): ${plan.price} - {status}")
    
    print(f"\n🔧 Add-ons Created ({addons.count()}):")
    for addon in addons:
        status = "✅ Active" if addon.is_active else "❌ Inactive"
        special = " 🔗" if addon.slug == 'blockchain-verification' else ""
        print(f"   - {addon.name}: ${addon.price} - {status}{special}")
    
    print(f"\n💰 Revenue Potential:")
    monthly_plans = plans.filter(interval='monthly')
    if monthly_plans:
        min_monthly = min(plan.price for plan in monthly_plans)
        max_monthly = max(plan.price for plan in monthly_plans)
        print(f"   - Monthly plans: ${min_monthly} - ${max_monthly}")
        
    yearly_plans = plans.filter(interval='yearly')
    if yearly_plans:
        min_yearly = min(plan.price for plan in yearly_plans)
        max_yearly = max(plan.price for plan in yearly_plans)
        print(f"   - Yearly plans: ${min_yearly} - ${max_yearly}")
    
    blockchain_addon = addons.filter(slug='blockchain-verification').first()
    if blockchain_addon:
        print(f"   - Blockchain add-on: +${blockchain_addon.price}/month")
    
    print("\n🎯 Next Steps:")
    print("   1. Test the pricing page: http://localhost:3000/admin/dashboard/pricing")
    print("   2. Test Stripe checkout flow")
    print("   3. Verify webhook endpoints are configured")
    print("   4. Monitor subscription analytics")

def main():
    parser = argparse.ArgumentParser(
        description='Setup Trazo billing plans and add-ons',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup_billing.py --environment development
  python setup_billing.py --environment staging --force
  python setup_billing.py --environment production

Environments:
  development  - Local development with test Stripe keys
  staging      - Staging environment with test Stripe keys  
  production   - Production environment with live Stripe keys
        """
    )
    
    parser.add_argument(
        '--environment',
        choices=['development', 'staging', 'production'],
        default='development',
        help='Target environment (default: development)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force recreation of existing plans and add-ons'
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate configuration without creating anything'
    )
    
    args = parser.parse_args()
    
    print("🔄 Trazo Billing Setup")
    print("=" * 60)
    print(f"Environment: {args.environment.upper()}")
    print(f"Force mode: {'ON' if args.force else 'OFF'}")
    print("=" * 60)
    
    # Validate environment
    if not validate_environment():
        sys.exit(1)
    
    # Check existing data
    existing_plans, existing_addons = check_existing_data()
    
    if args.validate_only:
        print("✅ Validation complete. Exiting without changes.")
        sys.exit(0)
    
    # Warn about existing data
    if (existing_plans > 0 or existing_addons > 0) and not args.force:
        print(f"\n⚠️  Warning: Found existing data!")
        print("   Use --force to recreate existing plans and add-ons")
        response = input("   Continue anyway? (y/N): ").lower().strip()
        if response != 'y':
            print("❌ Setup cancelled by user")
            sys.exit(0)
    
    # Run the setup
    success = run_setup_command(args.environment, args.force)
    
    if success:
        display_summary()
        print("\n✅ Billing setup completed successfully!")
    else:
        print("\n❌ Billing setup failed!")
        sys.exit(1)

if __name__ == '__main__':
    main() 