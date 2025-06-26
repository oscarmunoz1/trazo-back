#!/usr/bin/env python3
"""
Script to create a self-reported offset entry and manually trigger verification
"""

import os
import sys
import django
from datetime import datetime

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

from django.contrib.auth import get_user_model
from carbon.models import CarbonEntry, CarbonSource, CarbonAuditLog
from company.models import Establishment
from carbon.services.verification_service import VerificationService
from carbon.services.audit_scheduler import AuditScheduler

User = get_user_model()

def create_self_reported_offset():
    """Create a self-reported offset entry for Establishment 1"""
    
    print("🌱 Creating Self-Reported Offset Entry...")
    print("=" * 50)
    
    # Get or create user
    user, created = User.objects.get_or_create(
        email='farmer@trazo.io',
        defaults={
            'first_name': 'Test',
            'last_name': 'Farmer',
            'is_active': True
        }
    )
    
    # Get establishment
    try:
        establishment = Establishment.objects.get(id=1)
        print(f"✅ Found establishment: {establishment.name}")
    except Establishment.DoesNotExist:
        print("❌ Establishment 1 not found. Please create it first.")
        return None
    
    # Get or create carbon source
    source, created = CarbonSource.objects.get_or_create(
        name='no_till',
        defaults={
            'description': 'No-till farming practices',
            'unit': 'kg CO2e',
            'category': 'Offset',
            'default_emission_factor': -0.47,  # Negative for offset
            'usda_verified': True
        }
    )
    
    # Create the offset entry
    offset_entry = CarbonEntry.objects.create(
        establishment=establishment,
        created_by=user,
        type='offset',
        source=source,
        amount=250.0,  # 250 kg CO2e offset
        year=2025,
        description='No-till farming implementation on 5 hectares of corn field. Converted from conventional tillage to no-till practices.',
        verification_level='self_reported',
        trust_score=0.5,  # Default for self-reported
        effective_amount=125.0,  # 250 * 0.5 trust score
        audit_status='pending',
        registry_verification_id='',  # Empty for self-reported
        additionality_evidence='Implemented no-till practices starting January 2025. Previously used conventional tillage.',
        evidence_photos=[],
        evidence_documents=[]
    )
    
    print(f"✅ Created offset entry:")
    print(f"   - ID: {offset_entry.id}")
    print(f"   - Amount: {offset_entry.amount} kg CO₂e")
    print(f"   - Type: {offset_entry.verification_level}")
    print(f"   - Trust Score: {offset_entry.trust_score}")
    print(f"   - Effective Amount: {offset_entry.effective_amount} kg CO₂e")
    print(f"   - Status: {offset_entry.audit_status}")
    
    return offset_entry

def trigger_verification_process(carbon_entry):
    """Manually trigger the verification process"""
    
    print(f"\n🔍 Triggering Verification Process for Entry {carbon_entry.id}...")
    print("=" * 50)
    
    # 1. Run verification service
    print("1️⃣ Running Verification Service...")
    verification_service = VerificationService()
    verification_result = verification_service.verify_offset_entry(carbon_entry)
    
    print(f"   ✅ Verification completed:")
    print(f"   - Approved: {verification_result.get('approved', False)}")
    print(f"   - Trust Score: {verification_result.get('trust_score', 'N/A')}")
    print(f"   - Requirements Met: {len(verification_result.get('requirements', []))}")
    print(f"   - Anti-Gaming Flags: {len(verification_result.get('anti_gaming_flags', []))}")
    
    # 2. Schedule audit if needed
    print("\n2️⃣ Scheduling Audit...")
    audit_scheduler = AuditScheduler()
    audit_result = audit_scheduler.schedule_audit(carbon_entry)
    
    print(f"   ✅ Audit scheduled:")
    print(f"   - Audit Date: {audit_result.get('audit_date', 'N/A')}")
    print(f"   - Notification Sent: {audit_result.get('notification_sent', False)}")
    
    # 3. Check current status
    carbon_entry.refresh_from_db()
    print(f"\n3️⃣ Updated Entry Status:")
    print(f"   - Audit Status: {carbon_entry.audit_status}")
    print(f"   - Trust Score: {carbon_entry.trust_score}")
    print(f"   - Effective Amount: {carbon_entry.effective_amount} kg CO₂e")
    
    # 4. Show audit trail
    print(f"\n4️⃣ Audit Trail:")
    audit_logs = CarbonAuditLog.objects.filter(carbon_entry=carbon_entry).order_by('-created_at')
    for log in audit_logs:
        print(f"   - {log.created_at.strftime('%Y-%m-%d %H:%M')} | {log.action} | {log.details}")
    
    return verification_result

def show_api_endpoints(carbon_entry):
    """Show available API endpoints for manual verification"""
    
    print(f"\n🔗 Manual Verification API Endpoints:")
    print("=" * 50)
    
    base_url = "http://localhost:8000"  # Adjust if different
    
    print(f"1️⃣ Get Verification Status:")
    print(f"   GET {base_url}/carbon/entries/{carbon_entry.id}/verification-status/")
    print(f"   Headers: Authorization: Bearer <your-token>")
    
    print(f"\n2️⃣ Verify Registry Credentials (if you have registry ID):")
    print(f"   POST {base_url}/carbon/verify-registry-credentials/")
    print(f"   Body: {{")
    print(f"     \"registry_verification_id\": \"VCS-1234\",")
    print(f"     \"registry_type\": \"vcs\",")
    print(f"     \"carbon_entry_id\": {carbon_entry.id}")
    print(f"   }}")
    
    print(f"\n3️⃣ Bulk Verification:")
    print(f"   POST {base_url}/carbon/bulk-verify/")
    print(f"   Body: {{")
    print(f"     \"carbon_entry_ids\": [{carbon_entry.id}],")
    print(f"     \"verification_action\": \"schedule_audit\" | \"verify_registry\" | \"validate_evidence\"")
    print(f"   }}")
    
    print(f"\n4️⃣ Get Methodology Templates:")
    print(f"   GET {base_url}/carbon/methodology-templates/")

def main():
    """Main function"""
    
    print("🚀 TRAZO OFFSET CREATION & VERIFICATION")
    print("=" * 50)
    
    # Step 1: Create offset entry
    offset_entry = create_self_reported_offset()
    if not offset_entry:
        return
    
    # Step 2: Trigger verification
    verification_result = trigger_verification_process(offset_entry)
    
    # Step 3: Show API endpoints
    show_api_endpoints(offset_entry)
    
    print(f"\n🎉 PROCESS COMPLETED!")
    print(f"✅ Created offset entry ID: {offset_entry.id}")
    print(f"✅ Verification process triggered")
    print(f"✅ Audit scheduled")
    
    print(f"\n💡 NEXT STEPS:")
    print(f"1. Check your email for audit notification")
    print(f"2. Use the API endpoints above to interact with the verification system")
    print(f"3. Add evidence (photos, documents) to improve trust score")
    print(f"4. If you have a registry verification ID, use the registry verification endpoint")

if __name__ == "__main__":
    main() 