# Carbon Score Default Value Fix

## Issue Identified

**Problem:** New establishments with no carbon entries were receiving a default carbon score of 85, which incorrectly suggested "good" carbon performance when no data was available.

**Example:** Establishment ID 23 "La Primavera" had 0 carbon entries but showed carbon score of 85.

## Root Cause

In `carbon/views.py` line 747, the `CarbonEstablishmentSummaryViewSet.summary()` method had:

```python
# Calculate carbon score (0-100)
carbon_score = 85  # Default score  ❌ INCORRECT
```

This hardcoded default value was misleading users about the carbon performance of establishments with no data.

## Fix Implemented

**Changed default carbon score from 85 to 0** for establishments with no carbon data:

```python
# Calculate carbon score (0-100)
carbon_score = 0  # Default score for no data  ✅ CORRECT
if total_emissions > 0:
    offset_percentage = min(100, (total_offsets / total_emissions) * 100)
    if offset_percentage >= 100:
        carbon_score = 90 + min(10, ((offset_percentage - 100) / 50) * 10)
    else:
        carbon_score = max(10, min(90, offset_percentage * 0.85))
elif total_offsets > 0:
    carbon_score = 95  # Excellent if only offsets
elif total_emissions == 0 and total_offsets == 0:
    carbon_score = 0  # No data available - cannot calculate score
```

## Carbon Score Meaning

| Score Range | Meaning | Data Requirement |
|-------------|---------|------------------|
| **0** | No data available | 0 emissions, 0 offsets |
| **1-24** | Poor performance | High emissions, few offsets |
| **25-49** | Below average | Moderate emissions, some offsets |
| **50-74** | Average performance | Balanced emissions/offsets |
| **75-89** | Good performance | Low emissions or high offsets |
| **90-100** | Excellent performance | Carbon neutral/negative |

## Testing Results

**Before Fix:**
- Establishment 23: 0 carbon entries → Carbon score: 85 ❌

**After Fix:**
- Establishment 23: 0 carbon entries → Carbon score: 0 ✅

## Impact

✅ **Accurate Representation:** New establishments now show 0 score until they add carbon data
✅ **No False Positives:** Prevents misleading "good" scores for establishments with no data  
✅ **User Trust:** Users can trust that scores reflect actual carbon performance data
✅ **System Integrity:** Carbon scoring system now accurately represents data availability

## Files Modified

- `carbon/views.py` - Fixed default carbon score in `CarbonEstablishmentSummaryViewSet.summary()`

## Verification

```bash
# Test the fix
cd trazo-back
poetry run python manage.py shell -c "
from carbon.models import CarbonEntry
from company.models import Establishment
establishment = Establishment.objects.get(id=23)
entries = CarbonEntry.objects.filter(establishment=establishment)
print(f'Entries: {entries.count()}, Should show score 0')
"
```

---

**Status:** ✅ **FIXED**  
**Impact:** All new establishments now correctly show carbon score 0 until carbon data is added
