#!/usr/bin/env python3
"""
Debug script to identify Railway startup issues
"""
import os
import sys
import traceback

def test_django_startup():
    """Test if Django can start properly"""
    try:
        print("=== DJANGO STARTUP DEBUG ===")
        
        # Check environment variables
        print(f"DJANGO_SETTINGS_MODULE: {os.environ.get('DJANGO_SETTINGS_MODULE', 'NOT SET')}")
        print(f"DATABASE_URL: {'SET' if os.environ.get('DATABASE_URL') else 'NOT SET'}")
        print(f"SECRET_KEY: {'SET' if os.environ.get('SECRET_KEY') else 'NOT SET'}")
        print(f"PORT: {os.environ.get('PORT', 'NOT SET')}")
        
        # Try to import Django
        print("\n--- Testing Django Import ---")
        import django
        print(f"Django version: {django.VERSION}")
        
        # Set settings module
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.prod')
        
        # Try to setup Django
        print("\n--- Testing Django Setup ---")
        django.setup()
        print("Django setup successful!")
        
        # Test database connection
        print("\n--- Testing Database Connection ---")
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            print("Database connection successful!")
        
        # Test settings
        print("\n--- Testing Settings ---")
        from django.conf import settings
        print(f"DEBUG: {settings.DEBUG}")
        print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
        
        print("\n=== ALL TESTS PASSED ===")
        return True
        
    except Exception as e:
        print(f"\n=== ERROR DETECTED ===")
        print(f"Error: {e}")
        print(f"Traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_django_startup()
    sys.exit(0 if success else 1) 