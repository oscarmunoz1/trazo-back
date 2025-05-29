# Unified IoT Workflow - Smart Carbon Entry Processing

## Overview

This document explains the **unified IoT workflow** that resolves the previous inconsistency between automatic carbon entry creation and manual approval systems. The new system provides a single, intelligent workflow that processes IoT data based on confidence scores.

## Previous Problem

**Before**: Two conflicting workflows existed:

1. `simulate_data` → Immediate carbon entry creation
2. `pending_events` → Manual approval required

**Result**: Confusion about when entries are created automatically vs. requiring approval.

## New Unified Workflow

### 1. Data Collection Phase

- **All IoT data** first creates `IoTDataPoint` objects
- No immediate carbon entries are created
- Data includes quality scores and metadata

### 2. Intelligent Analysis Phase

- System analyzes each data point for:
  - **Data quality** (sensor reliability, signal strength)
  - **Realistic values** (fuel consumption within expected ranges)
  - **Temporal consistency** (operations during working hours)
  - **Device status** (online/offline, battery level)

### 3. Confidence Scoring

Each event receives a confidence score (0.0 - 1.0):

#### High Confidence (>0.9)

- **Action**: Auto-approve and create carbon entry
- **Criteria**:
  - High data quality (>0.9)
  - Realistic fuel consumption (5-50L)
  - Online device status
  - Normal working hours (6 AM - 6 PM)
- **Audit**: Logged as `iot_auto_approve`

#### Medium Confidence (0.7-0.9)

- **Action**: Require manual approval
- **Criteria**:
  - Good data quality (>0.7)
  - Slightly unusual values or timing
  - Device status concerns
- **Audit**: Logged as `iot_manual_approve` when approved

#### Low Confidence (<0.7)

- **Action**: Flag for review
- **Criteria**:
  - Poor data quality
  - Unrealistic values
  - Offline devices
  - Anomalies detected

### 4. Processing Results

- **Auto-processed events**: Appear immediately in Carbon Dashboard
- **Pending events**: Appear in IoT Dashboard for approval
- **Rejected events**: Marked as processed without carbon entry

## API Endpoints

### Simulate IoT Data

```
POST /carbon/iot-devices/simulate_data/
{
    "establishment_id": "123",
    "device_type": "fuel_sensor"
}
```

**Response**:

```json
{
  "status": "success",
  "message": "Simulated fuel sensor data created: 15.2L fuel consumption",
  "data_point_id": 456,
  "workflow": "Data point created - check Pending Events for approval",
  "note": "This data will appear in Pending Events and can be approved to create carbon entries"
}
```

### Get Pending Events

```
GET /carbon/automation-rules/pending_events/?establishment_id=123&auto_process=true
```

**Response**:

```json
{
    "establishment_id": "123",
    "pending_events": [...],
    "total_count": 3,
    "auto_processed_count": 2,
    "workflow_info": {
        "auto_approval_threshold": 0.9,
        "manual_approval_threshold": 0.7,
        "review_threshold": 0.5
    }
}
```

## Confidence Calculation Examples

### Fuel Sensor Event

```python
def _calculate_fuel_confidence(self, data_point, fuel_liters):
    confidence = 0.5  # Base confidence

    # Data quality factors
    if data_point.quality_score > 0.9:
        confidence += 0.2  # +0.2 for excellent data
    elif data_point.quality_score > 0.7:
        confidence += 0.1  # +0.1 for good data

    # Realistic fuel consumption (5-50L per session)
    if 5 <= fuel_liters <= 50:
        confidence += 0.2  # +0.2 for normal consumption
    elif fuel_liters > 50:
        confidence -= 0.1  # -0.1 for high consumption (needs review)

    # Device status
    if data_point.device.status == 'online':
        confidence += 0.1  # +0.1 for online device

    # Time consistency (working hours)
    hour = data_point.timestamp.hour
    if 6 <= hour <= 18:  # Normal working hours
        confidence += 0.1  # +0.1 for normal hours

    return min(1.0, confidence)
```

**Example Calculations**:

- **High confidence (0.95)**: 15L fuel, excellent data quality, online device, 2 PM
- **Medium confidence (0.8)**: 35L fuel, good data quality, online device, 8 PM
- **Low confidence (0.6)**: 75L fuel, poor data quality, offline device, 3 AM

## Frontend Integration

### IoT Dashboard Updates

- **Smart Processing Alert**: Shows auto-processed count
- **Workflow Explanation**: Visual guide to the three processing levels
- **Pending Events**: Only shows events requiring manual approval
- **Confidence Badges**: Color-coded confidence indicators

### User Experience

1. **Simulate Data** → Creates data point
2. **High confidence** → Auto-processed (appears in Carbon Dashboard)
3. **Medium confidence** → Appears in Pending Events for approval
4. **Low confidence** → Flagged for review

## Benefits

### For Producers

- **Reduced Manual Work**: High-confidence events processed automatically
- **Quality Control**: Medium-confidence events reviewed before processing
- **Transparency**: Clear understanding of when and why approval is needed
- **Audit Trail**: Complete logging of all decisions

### For System Integrity

- **Consistent Workflow**: Single path for all IoT data processing
- **Quality Assurance**: Confidence scoring prevents erroneous entries
- **Scalability**: Automatic processing reduces manual overhead
- **Compliance**: Full audit trail for regulatory requirements

## Configuration

### Auto-Processing Settings

```python
# In pending_events method
auto_process = request.query_params.get('auto_process', 'true').lower() == 'true'

# Confidence thresholds
AUTO_APPROVAL_THRESHOLD = 0.9
MANUAL_APPROVAL_THRESHOLD = 0.7
REVIEW_THRESHOLD = 0.5
```

### Device-Specific Rules

- **Fuel sensors**: Auto-approve normal consumption patterns
- **Weather stations**: Generate recommendations, not carbon entries
- **Soil moisture**: Always require approval for irrigation decisions
- **Equipment monitors**: Auto-approve maintenance-related emissions

## Testing

### Test Scenarios

1. **High-quality fuel data** → Should auto-approve
2. **Unusual fuel consumption** → Should require approval
3. **Weather alerts** → Should generate recommendations
4. **Offline device data** → Should flag for review

### Verification

- Check Carbon Dashboard for auto-processed entries
- Check IoT Dashboard for pending approvals
- Verify audit logs for proper action tracking
- Confirm confidence scores are calculated correctly

## Migration from Old System

### Backward Compatibility

- Existing manual approval endpoints still work
- Old carbon entries remain unchanged
- Gradual migration of IoT devices to new workflow

### Data Migration

- Existing `IoTDataPoint` objects can be reprocessed
- Historical confidence scores can be calculated retroactively
- Audit logs updated to reflect processing method

## Monitoring and Analytics

### Key Metrics

- **Auto-approval rate**: Percentage of events auto-processed
- **Confidence distribution**: Histogram of confidence scores
- **Processing time**: Time from data point to carbon entry
- **Error rate**: Failed auto-approvals requiring manual intervention

### Dashboard Widgets

- Real-time processing status
- Confidence score trends
- Device reliability metrics
- Processing efficiency reports

## Future Enhancements

### Machine Learning Integration

- **Pattern Recognition**: Learn from manual approval patterns
- **Seasonal Adjustments**: Adjust confidence based on time of year
- **Producer-Specific Models**: Customize confidence calculation per farm
- **Anomaly Detection**: Advanced detection of unusual patterns

### Advanced Automation

- **Weather Integration**: Adjust confidence based on weather conditions
- **Market Data**: Factor in commodity prices for timing decisions
- **Compliance Rules**: Automatic regulatory compliance checking
- **Cost Optimization**: Suggest timing based on cost-benefit analysis

This unified workflow ensures consistent, intelligent processing of IoT data while maintaining quality control and providing transparency to users.
