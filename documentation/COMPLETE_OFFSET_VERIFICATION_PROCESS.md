# Complete Offset Verification Process Documentation

## Overview

This document provides a comprehensive overview of Trazo's carbon offset verification process, from the moment a producer creates an entry in the frontend application until it's validated through third-party APIs and audit systems.

## Table of Contents

1. [Process Flow Overview](#process-flow-overview)
2. [Frontend Submission Process](#frontend-submission-process)
3. [Backend Verification Pipeline](#backend-verification-pipeline)
4. [Third-Party Registry Integration](#third-party-registry-integration)
5. [Audit System](#audit-system)
6. [Trust Score Calculation](#trust-score-calculation)
7. [Anti-Gaming Mechanisms](#anti-gaming-mechanisms)
8. [API Endpoints](#api-endpoints)
9. [Database Models](#database-models)
10. [Implementation Details](#implementation-details)

---

## Process Flow Overview

The complete verification process follows this flow:

1. **Producer Opens Offset Modal** → Frontend form with dynamic requirements
2. **Amount-Based Validation** → Requirements scale with offset value
3. **Backend Submission** → Comprehensive validation and CarbonEntry creation
4. **Verification Service** → Multi-layer verification with anti-gaming checks
5. **Third-Party Registry Check** → Real-time validation against VCS, Gold Standard, etc.
6. **Audit Scheduling** → Risk-based and random audit assignment
7. **Trust Score Calculation** → Conservative crediting with buffer pools
8. **Final Approval** → Effective amount calculation and footprint update

---

## Frontend Submission Process

### 1. Offset Modal Interface (`ModernOffsetModal.tsx`)

The process begins when a producer opens the offset creation modal in their establishment dashboard.

#### Key Components:

- **Three Offset Types:**
  - Self-Reported (on-farm activities)
  - Community Verified (local projects)
  - Certified Projects (marketplace)

#### Dynamic Verification Requirements:

```typescript
const getVerificationRequirements = (amount: number) => {
  if (amount >= 1000) {
    return {
      required_level: "certified_project",
      requires_third_party: true,
      requires_additionality_proof: true,
      requires_permanence_plan: true,
      message:
        "High-value offsets (≥1000 kg CO₂e) require certified project verification",
    };
  } else if (amount >= 100) {
    return {
      required_level: "community_verified",
      requires_third_party: false,
      requires_additionality_proof: true,
      requires_permanence_plan: false,
      message:
        "Medium-value offsets (≥100 kg CO₂e) require additionality evidence",
    };
  }
  return {
    required_level: "self_reported",
    requires_third_party: false,
    requires_additionality_proof: false,
    requires_permanence_plan: false,
    message: "Standard verification requirements",
  };
};
```

#### Form Validation:

- **Required Fields:** Amount, source/project selection
- **Amount-Based Validation:**
  - ≥1000 kg CO₂e: Must select certified project
  - ≥100 kg CO₂e: Must provide additionality evidence
- **Evidence Upload:** Photos, documents, GPS coordinates

#### Submission Payload:

```typescript
const payload = {
  amount: parseFloat(formData.amount),
  type: "offset",
  year: new Date().getFullYear(),
  establishment: establishmentId,
  verification_level: formData.verification_level,
  offset_project_type: "on_farm" | "local_community" | "certified_marketplace",
  // Enhanced verification fields
  additionality_evidence: formData.additionality_evidence,
  permanence_plan: formData.permanence_plan,
  baseline_data: formData.baseline_data,
  methodology_template: formData.methodology_template,
  registry_verification_id: formData.registry_verification_id,
  // Evidence files
  evidence_photos: formData.evidence_photos,
  evidence_documents: formData.evidence_documents,
  gps_coordinates: formData.gps_coordinates,
  verification_notes: formData.verification_notes,
};
```

---

## Backend Verification Pipeline

### 1. Initial Validation (`CarbonOffsetViewSet.create()`)

Located in `carbon/views.py`, the backend performs initial validation:

```python
# Amount-based verification requirements
if amount >= 1000 and verification_level != 'certified_project':
    return Response({
        'error': 'High-value offsets (≥1000 kg CO₂e) require certified project verification',
        'required_verification_level': 'certified_project',
        'amount_threshold': 1000
    }, status=status.HTTP_400_BAD_REQUEST)

if amount >= 100 and not data.get('additionality_evidence'):
    return Response({
        'error': 'Medium-value offsets (≥100 kg CO₂e) require additionality evidence',
        'required_fields': ['additionality_evidence'],
        'amount_threshold': 100
    }, status=status.HTTP_400_BAD_REQUEST)
```

### 2. CarbonEntry Creation

A `CarbonEntry` model instance is created with comprehensive verification fields:

```python
carbon_entry = CarbonEntry.objects.create(
    establishment=establishment,
    production=production,
    created_by=request.user,
    type='offset',
    source=offset_source,
    amount=amount,
    year=year,
    # Verification system fields
    verification_level=verification_level,
    additionality_evidence=data.get('additionality_evidence', ''),
    permanence_plan=data.get('permanence_plan', ''),
    baseline_data=data.get('baseline_data', {}),
    methodology_template=data.get('methodology_template', ''),
    registry_verification_id=data.get('registry_verification_id', ''),
    evidence_requirements_met=self._check_evidence_requirements(data),
    documentation_complete=self._check_documentation_complete(data),
    # Evidence files
    evidence_photos=data.get('evidence_photos', []),
    evidence_documents=data.get('evidence_documents', []),
    # Default values
    attestation_count=0,
    community_attestations=[],
    trust_score=0.5,  # Will be recalculated
    audit_status='pending',
    additionality_verified=False
)
```

### 3. Verification Service Execution

The `VerificationService.verify_offset_entry()` method is called to perform comprehensive verification:

```python
verification_result = verification_service.verify_offset_entry(carbon_entry)

# Update carbon entry based on verification results
if verification_result['audit_required']:
    carbon_entry.audit_status = 'scheduled'
elif verification_result['approved']:
    carbon_entry.audit_status = 'passed'
else:
    carbon_entry.audit_status = 'failed'

carbon_entry.save()
```

---

## Third-Party Registry Integration

### 1. Registry Integration Service (`RegistryIntegrationService`)

The system integrates with major carbon registries:

- **VCS (Verra):** `https://registry.verra.org/api/v1`
- **Gold Standard:** `https://api.goldstandard.org/v1`
- **CAR (Climate Action Reserve):** `https://thereserve2.apx.com/myModule/rpt/myrpt.asp`
- **ACR (American Carbon Registry):** `https://acr2.apx.com/myModule/rpt/myrpt.asp`

### 2. Registry Verification Process

For certified projects (`verification_level == 'certified_project'`):

```python
def _verify_with_third_party_registry(self, carbon_entry) -> Dict[str, Any]:
    registry_id = carbon_entry.registry_verification_id

    # Try VCS first
    vcs_result = self.registry_service.verify_with_vcs({'project_id': registry_id})
    if vcs_result['verified']:
        return {
            'verified': True,
            'registry': 'VCS',
            'project_url': self.registry_service.get_registry_project_url(registry_id, 'vcs'),
            'verification_body': vcs_result.get('verification_body', 'Verra'),
            'methodology': vcs_result.get('methodology', 'VM0042'),
            'status': vcs_result.get('status', 'active'),
            'credits_available': vcs_result.get('credits_available', 0),
            'last_audit_date': vcs_result.get('last_audit_date')
        }

    # Try Gold Standard, CAR, ACR...
```

### 3. Registry Verification Impact

When registry verification succeeds:

- Trust score is set to 100% (full credit)
- `third_party_verification_url` is populated
- Buffer pool deduction is minimized (10% vs 20% for self-reported)
- Audit requirements may be reduced

---

## Audit System

### 1. Audit Scheduling (`AuditScheduler`)

The audit system operates on multiple triggers:

#### Random Audits:

- 10% of self-reported and community-verified offsets
- Scheduled automatically via `schedule_random_audits()`

#### Risk-Based Audits:

- High-value offsets (≥1000 kg CO₂e)
- Suspicious patterns detected by anti-gaming system
- Failed verification checks

### 2. Audit Process Flow

```python
def schedule_audit(self, carbon_entry: CarbonEntry) -> Dict[str, Any]:
    audit = VerificationAudit.objects.create(
        carbon_entry=carbon_entry,
        audit_type='random',
        audit_date=timezone.now() + timedelta(days=7),
        auditor_name='Trazo Verification Team',
        result='pending'
    )

    # Update carbon entry status
    carbon_entry.audit_status = 'scheduled'
    carbon_entry.audit_scheduled_date = audit.audit_date
    carbon_entry.save()

    # Send notification
    self.send_audit_notification(carbon_entry)
```

### 3. Audit Notification Email

Automated email sent to producers with:

- Offset details requiring verification
- Required evidence list
- Submission deadline
- Login instructions for dashboard

### 4. Audit Completion

```python
def complete_audit(self, audit_id: int, result: str, findings: Dict[str, Any]):
    audit = VerificationAudit.objects.get(id=audit_id)
    audit.result = result  # 'passed', 'failed', 'pending'
    audit.findings = findings
    audit.save()

    # Update carbon entry audit status
    carbon_entry = audit.carbon_entry
    carbon_entry.audit_status = result
    carbon_entry.save()
```

---

## Trust Score Calculation

### 1. Base Trust Scores by Verification Level

```python
TRUST_SCORES = {
    'self_reported': 0.50,      # 50% credit
    'community_verified': 0.75,  # 75% credit
    'certified_project': 1.00,   # 100% credit
}
```

### 2. Trust Score Modifiers

- **Registry Verification:** Certified projects verified through registries get 100% trust score
- **Audit Results:**
  - Passed audit: Maintains trust score
  - Failed audit: Trust score reduced to 0
- **Evidence Quality:** High-quality evidence can improve trust score
- **Anti-Gaming Flags:** Detected gaming reduces trust score

### 3. Effective Amount Calculation

```python
def calculate_effective_amount(self, carbon_entry) -> float:
    base_amount = carbon_entry.amount
    trust_score = carbon_entry.trust_score
    buffer_deduction = self.BUFFER_POOLS.get(carbon_entry.verification_level, 0.20)

    effective_amount = base_amount * trust_score * (1 - buffer_deduction)
    return effective_amount
```

---

## Anti-Gaming Mechanisms

### 1. Comprehensive Anti-Gaming Checks

The verification service implements industry-standard anti-gaming mechanisms:

#### A. Third-Party Registry Verification

- Validates certified project IDs against VCS, Gold Standard, CAR, ACR
- Prevents fake registry IDs

#### B. Additionality Testing

```python
def _assess_additionality(self, carbon_entry) -> Dict[str, Any]:
    # Oxford/Berkeley research-based additionality testing
    # Checks for practice commonality, financial barriers, implementation timeline
```

#### C. Cumulative Limits Enforcement

- Monthly self-reported limit: 500 kg CO₂e
- Annual self-reported limit: 5,000 kg CO₂e

#### D. Rapid Submission Pattern Detection

- Flags >5 entries per day as suspicious
- Triggers additional verification requirements

#### E. Unrealistic Offset Ratio Detection

- Flags offset-to-emission ratios >2:1 as unrealistic
- Requires additional verification

#### F. Acreage Capacity Validation

- Validates offset amounts against available acreage
- Prevents over-claiming from limited land

#### G. Evidence Requirements Validation

- Ensures appropriate evidence for verification level
- Validates GPS coordinates, photos, documentation

#### H. Conservative Baseline Validation

- Prevents overly optimistic baseline assumptions
- Requires conservative crediting approaches

### 2. Anti-Gaming Response Actions

When gaming is detected:

- Entry flagged for manual review
- Trust score reduced or zeroed
- Audit automatically scheduled
- Requirements added for approval
- Recommendations generated for compliance

---

## API Endpoints

### 1. Core Offset Creation

```
POST /carbon/offsets/
```

### 2. Registry Verification

```
POST /carbon/verify-registry-credentials/
{
  "registry_verification_id": "VCS-1001",
  "registry_type": "vcs",
  "carbon_entry_id": 123
}
```

### 3. Verification Status

```
GET /carbon/entries/{id}/verification-status/
```

### 4. Bulk Operations

```
POST /carbon/bulk-verify/
{
  "action": "schedule_audit|verify_registry|validate_evidence",
  "carbon_entry_ids": [1, 2, 3]
}
```

### 5. Methodology Templates

```
GET /carbon/methodology-templates/
```

---

## Database Models

### 1. CarbonEntry Model

Key verification fields:

```python
class CarbonEntry(models.Model):
    # Basic fields
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.FloatField()

    # Verification system
    verification_level = models.CharField(max_length=25, choices=VERIFICATION_LEVEL_CHOICES)
    trust_score = models.FloatField(default=0.5)
    effective_amount = models.FloatField(null=True, blank=True)

    # Evidence and documentation
    additionality_evidence = models.TextField(blank=True)
    permanence_plan = models.TextField(blank=True)
    baseline_data = models.JSONField(default=dict)
    evidence_photos = models.JSONField(default=list)
    evidence_documents = models.JSONField(default=list)

    # Audit tracking
    audit_status = models.CharField(max_length=20, choices=AUDIT_STATUS_CHOICES)
    audit_scheduled_date = models.DateTimeField(null=True, blank=True)

    # Registry integration
    registry_verification_id = models.CharField(max_length=100, blank=True)
    third_party_verification_url = models.URLField(blank=True)
    methodology_template = models.CharField(max_length=50, blank=True)

    # Community verification
    attestation_count = models.IntegerField(default=0)
    community_attestations = models.JSONField(default=list)
```

### 2. VerificationAudit Model

```python
class VerificationAudit(models.Model):
    carbon_entry = models.ForeignKey(CarbonEntry, on_delete=models.CASCADE)
    audit_type = models.CharField(max_length=20, choices=AUDIT_TYPE_CHOICES)
    auditor_name = models.CharField(max_length=200)
    audit_date = models.DateTimeField()
    findings = models.JSONField(default=dict)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES)
    corrective_actions = models.TextField(blank=True)
```

---

## Implementation Details

### 1. Methodology Templates

The system supports standardized methodologies:

```python
def get_methodology_template(self, methodology_type: str) -> Dict[str, Any]:
    templates = {
        'no_till': {
            'methodology': 'VCS VM0042',
            'emission_factor': 0.47,  # tCO2e/ha/year
            'uncertainty': 0.15,
            'required_data': ['field_area', 'soil_type', 'previous_practice'],
            'additionality_requirements': [
                'practice_uncommon_in_region',
                'financial_barrier_evidence',
                'implementation_timeline'
            ]
        },
        'cover_crop': {
            'methodology': 'VCS VM0042',
            'emission_factor': 0.29,  # tCO2e/ha/year
            'uncertainty': 0.20,
            'required_data': ['crop_type', 'planting_date', 'termination_method'],
            'monitoring_requirements': ['annual_verification', 'biomass_sampling']
        },
        # Additional methodologies...
    }
```

### 2. Buffer Pool Management

Conservative crediting with buffer pools:

- **Self-reported:** 20% buffer pool deduction
- **Community verified:** 15% buffer pool deduction
- **Certified project:** 10% buffer pool deduction

### 3. Celery Task Integration

Automated background tasks:

```python
@shared_task
def validate_registry_verifications():
    """Validate registry verification IDs against third-party APIs"""

@shared_task
def schedule_random_audits():
    """Schedule random audits for 10% of monthly offsets"""
```

### 4. Email Notifications

Automated notifications for:

- Audit scheduling
- Audit completion
- Verification status changes
- Evidence submission reminders

### 5. Internationalization Support

The system supports multiple languages with translations for:

- Carbon sources (no_till → "No-Till Farming")
- Verification levels
- Audit statuses
- Error messages

---

## Summary

The Trazo offset verification process implements a comprehensive, multi-layered approach to ensure the integrity of carbon offset claims:

1. **Frontend Validation:** Dynamic requirements based on offset amount and type
2. **Backend Verification:** Multi-step verification with anti-gaming mechanisms
3. **Third-Party Integration:** Real-time validation against major carbon registries
4. **Audit System:** Risk-based and random auditing with email notifications
5. **Trust Scoring:** Conservative crediting with buffer pools and evidence-based adjustments
6. **Anti-Gaming:** Industry-standard mechanisms to prevent fraudulent claims

This system balances accessibility for legitimate offset activities with robust verification to maintain credibility and prevent gaming, following best practices from leading platforms like Indigo Ag, Agoro Carbon Alliance, and Verra standards.

The process ensures that all offset entries undergo appropriate verification based on their value and risk profile, with higher-value offsets requiring stronger verification methods and third-party validation.
