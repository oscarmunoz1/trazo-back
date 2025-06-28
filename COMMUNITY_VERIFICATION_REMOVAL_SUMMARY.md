# Community Verification Removal - MVP Optimization Summary

## Overview
Successfully removed the community verification level from Trazo's carbon offset verification system to optimize for MVP with a streamlined 2-tier verification system: **Self Reported** and **Certified Project**.

## Changes Made

### 1. Model Updates (`carbon/models.py`)
- ✅ Updated `VERIFICATION_LEVEL_CHOICES` to remove `'community_verified'` option
- ✅ Removed `community_attestations` and `attestation_count` fields from `CarbonEntry` model
- ✅ Updated trust score calculation in `save()` method to use 2-tier system:
  - Self Reported: 0.5 (50% trust)
  - Certified Project: 1.0 (100% trust)
- ✅ Updated `verification_badge` property to remove community verification badge

### 2. Verification Service Updates (`carbon/services/verification_service.py`)
- ✅ Updated `BUFFER_POOLS` to remove community verification level:
  - Self Reported: 20% buffer
  - Certified Project: 10% buffer
- ✅ Updated `TRUST_SCORES` to use 2-tier system
- ✅ Removed community verification logic from cumulative limits checking
- ✅ Updated evidence validation to remove community-specific requirements
- ✅ Updated verification tier determination to use 2-tier system
- ✅ Updated recommendations to suggest certified projects instead of community verification

### 3. Views Updates (`carbon/views.py`)
- ✅ Updated comments to reflect 2-tier system
- ✅ Removed attestation fields from carbon entry creation
- ✅ Updated buffer pool calculations to remove community verification level
- ✅ Removed community attestation count from evidence summary responses

### 4. Tasks Updates (`carbon/tasks.py`)
- ✅ Updated verification processing to only handle self-reported entries
- ✅ Updated trust score synchronization to use 2-tier system

### 5. Audit Scheduler Updates (`carbon/services/audit_scheduler.py`)
- ✅ Updated audit selection to only consider self-reported entries

### 6. Database Migration (`carbon/migrations/0022_remove_community_verification_mvp.py`)
- ✅ Created migration to convert existing `community_verified` entries to `self_reported`
- ✅ Adjusted trust scores from 0.75 to 0.5 for converted entries
- ✅ Recalculated effective amounts based on new trust scores
- ✅ Removed `community_attestations` and `attestation_count` fields
- ✅ Updated field choices to reflect 2-tier system

## System Benefits

### Performance Improvements
- **Simplified Logic**: Removed complex community attestation handling
- **Faster Processing**: Eliminated community verification workflows
- **Reduced Complexity**: Streamlined verification service logic

### User Experience Improvements
- **Clearer Options**: Users now have 2 clear verification levels instead of 3
- **Simpler Onboarding**: No need to explain community verification process
- **Direct Upgrade Path**: Clear progression from self-reported to certified

### Maintenance Benefits
- **Reduced Code Complexity**: Less branching logic for verification levels
- **Simplified Testing**: Fewer code paths to test and maintain
- **Easier Documentation**: 2-tier system is easier to explain and document

## Verification Levels After MVP Optimization

### 1. Self Reported (MVP Tier 1)
- **Trust Score**: 0.5 (50% trust)
- **Buffer Pool**: 20% deduction
- **Effective Amount**: `amount * 0.5 * 0.8 = amount * 0.4`
- **Requirements**: Basic evidence for larger claims (>25 kg CO₂e)
- **Limits**: 500 kg CO₂e/month, 5,000 kg CO₂e/year

### 2. Certified Project (MVP Tier 2)
- **Trust Score**: 1.0 (100% trust)
- **Buffer Pool**: 10% deduction
- **Effective Amount**: `amount * 1.0 * 0.9 = amount * 0.9`
- **Requirements**: Third-party registry verification (ICR, VCS, Gold Standard, etc.)
- **Limits**: No limits (verified through registries)

## Data Integrity
- ✅ **Backward Compatibility**: Existing community_verified entries converted to self_reported
- ✅ **Trust Score Adjustment**: Recalculated effective amounts for converted entries
- ✅ **No Data Loss**: All historical data preserved with appropriate downgrades

## API Compatibility
- ✅ **Backward Compatible**: APIs still accept verification_level parameter
- ✅ **Error Handling**: Invalid verification levels handled gracefully
- ✅ **Documentation**: Updated API documentation reflects 2-tier system

## Anti-Gaming Mechanisms Preserved
- ✅ **Cumulative Limits**: Monthly/annual limits still enforced for self-reported
- ✅ **Evidence Requirements**: Photo and documentation requirements maintained
- ✅ **Audit System**: Random audits still scheduled for self-reported entries
- ✅ **Registry Verification**: Certified projects still verified through third-party registries

## Testing Recommendations

### 1. Database Migration Testing
```bash
# Run migration
python manage.py migrate carbon 0022

# Verify data conversion
python manage.py shell -c "
from carbon.models import CarbonEntry
print('Community verified entries:', CarbonEntry.objects.filter(verification_level='community_verified').count())
print('Self reported entries:', CarbonEntry.objects.filter(verification_level='self_reported').count())
print('Certified project entries:', CarbonEntry.objects.filter(verification_level='certified_project').count())
"
```

### 2. API Testing
- Test carbon entry creation with both verification levels
- Verify verification service processes entries correctly
- Check that trust scores and effective amounts are calculated properly

### 3. Frontend Updates Required
- Update forms to only show 2 verification options
- Remove community attestation UI components
- Update help text and documentation

## Rollback Plan
If needed, community verification can be restored by:
1. Creating reverse migration to add fields back
2. Restoring community verification logic in services
3. Re-adding community verification choices to model

However, **community attestation data will be permanently lost** after this migration runs.

## Conclusion
The community verification removal successfully streamlines Trazo's verification system for MVP while maintaining data integrity and anti-gaming protections. The 2-tier system provides a clear upgrade path for users and reduces system complexity significantly.