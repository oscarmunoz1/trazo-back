# 🎯 **USDA API Usage Strategy for Trazo**

## **📋 Executive Summary**

This document defines **when, where, and how** USDA API requests should be made in the Trazo carbon transparency platform. Based on analysis of the system architecture, performance issues, and Trazo's core mission of agricultural carbon transparency.

---

## **🎯 Trazo's Core Mission & USDA Role**

**Primary Goal**: Agricultural carbon data transparency and actionable insights
**USDA Role**: Provide government-verified emission factors and benchmarks for credible carbon calculations
**NOT**: Real-time farm optimization or live data streaming

---

## **✅ CORRECT: When USDA API Requests Should Happen**

### **1. Event Creation (Primary Trigger) ✅**

**WHEN**: When farmers create/update agricultural events (chemical applications, equipment use, etc.)
**WHERE**: Django signals in `history/signals.py`
**WHY**: Calculate accurate carbon impact using USDA-verified emission factors
**FREQUENCY**: Once per event creation/update

```python
# CORRECT: In history/signals.py
@receiver(post_save, sender=ChemicalEvent)
def calculate_chemical_event_carbon(sender, instance, created, **kwargs):
    if created:  # Only on creation
        calculator = EventCarbonCalculator()
        # This should trigger USDA API call for emission factors
        calculation_result = calculator.calculate_chemical_event_impact(instance)
```

### **2. Production Template Setup ✅**

**WHEN**: When creating production templates with USDA compliance data
**WHERE**: Admin interface or template creation APIs
**WHY**: Pre-populate templates with USDA-verified practices and emission factors
**FREQUENCY**: Once per template creation (rare)

### **3. Regional Benchmark Updates ✅**

**WHEN**: Scheduled background tasks (daily/weekly)
**WHERE**: Celery background tasks
**WHY**: Keep regional benchmarks current for accurate comparisons
**FREQUENCY**: Scheduled (1-7 days)

```python
# CORRECT: Scheduled task
@shared_task
def update_usda_regional_benchmarks():
    """Update USDA benchmarks for all active regions/crops"""
    for region in active_regions:
        for crop in active_crops:
            # Fetch and cache USDA benchmark data
            usda_client.get_benchmark_yield(crop, region)
```

### **4. USDA Compliance Verification ✅**

**WHEN**: When farmers request USDA compliance verification for carbon credits
**WHERE**: Compliance verification endpoints
**WHY**: Validate carbon calculations against USDA standards for credit markets
**FREQUENCY**: On-demand (user-initiated)

---

## **❌ INCORRECT: When USDA API Requests Should NOT Happen**

### **1. Dashboard/UI Loading ❌**

**PROBLEM**: Every dashboard load triggers USDA API calls
**SOLUTION**: Use cached carbon data from event calculations
**IMPACT**: 10+ second load times → <200ms

```python
# WRONG: In dashboard views
def get_carbon_summary():
    # ❌ Don't call USDA API on every dashboard load
    usda_data = get_real_usda_factors(crop, state)

# CORRECT: Use pre-calculated data
def get_carbon_summary():
    # ✅ Use cached carbon data from events
    carbon_entries = CarbonEntry.objects.filter(production=production)
```

### **2. QR Code Scanning ❌**

**PROBLEM**: Consumer QR scans trigger real-time USDA API calls
**SOLUTION**: Pre-calculated carbon scores stored in database
**IMPACT**: Consumer experience ruined by slow loading

### **3. Event Serialization ❌**

**PROBLEM**: Every event API call recalculates carbon with USDA data
**SOLUTION**: Store calculated carbon data in event's `extra_data` field
**IMPACT**: History endpoints take 10+ seconds

### **4. Frontend Real-time Queries ❌**

**PROBLEM**: Frontend components making direct USDA API calls
**SOLUTION**: Load USDA data only when user explicitly requests comparison
**IMPACT**: Unnecessary API usage and slow UX

---

## **🏗️ Recommended Architecture**

### **Data Flow Strategy**

```
1. Farmer creates event → USDA API call → Carbon calculation → Store in DB
2. Dashboard loads → Read from DB (no USDA call)
3. QR scan → Read from DB (no USDA call)
4. Consumer views → Read from DB (no USDA call)
5. Background sync → Periodic USDA API calls → Update benchmarks
```

### **Caching Strategy**

- **Event Carbon Data**: Permanent storage in `CarbonEntry` model
- **USDA Benchmarks**: Redis cache (24-hour TTL)
- **Regional Factors**: Redis cache (1-week TTL)
- **API Responses**: Redis cache (30-minute TTL)

---

## **🔧 Implementation Plan**

### **Phase 1: Fix Current Issues**

1. **Optimize Event Signals**: Ensure USDA calls only on event creation
2. **Cache Dashboard Data**: Use pre-calculated carbon scores
3. **Fix Frontend Loading**: Remove unnecessary USDA API hooks
4. **Optimize Serializers**: Use cached data instead of real-time calculations

### **Phase 2: Implement Proper Architecture**

1. **Background Tasks**: Schedule USDA benchmark updates
2. **Compliance Endpoints**: Create on-demand USDA verification
3. **Template Pre-population**: USDA data in production templates
4. **Performance Monitoring**: Track USDA API usage patterns

### **Phase 3: Advanced Features**

1. **Smart Caching**: Predictive USDA data caching
2. **Compliance Dashboard**: USDA verification status tracking
3. **Regional Optimization**: State-specific emission factors
4. **Carbon Credit Integration**: USDA-verified carbon credit calculations

---

## **📊 Expected Performance Improvements**

| **Metric**          | **Before**       | **After** | **Improvement** |
| ------------------- | ---------------- | --------- | --------------- |
| Dashboard Load Time | 10+ seconds      | <200ms    | 98% faster      |
| QR Code Scan        | 5-8 seconds      | <100ms    | 95% faster      |
| History Endpoint    | 10+ seconds      | <50ms     | 99% faster      |
| USDA API Calls/Day  | 1000+            | <50       | 95% reduction   |
| Database Queries    | 200+ per request | 1-3       | 99% reduction   |

---

## **🎯 Success Metrics**

### **Performance**

- API response times <200ms for 95% of requests
- USDA API calls <50 per day (vs current 1000+)
- Database queries <5 per carbon calculation request

### **Accuracy**

- 100% USDA compliance for carbon calculations
- Regional emission factors updated weekly
- Carbon scores accurate within 5% of USDA standards

### **User Experience**

- Dashboard loads in <200ms
- QR scans complete in <100ms
- No "Loading..." states for carbon data display

---

## **🔍 Monitoring & Alerts**

### **USDA API Usage Monitoring**

```python
# Track USDA API calls
logger.info(f"USDA API call: {endpoint} - {crop_type} - {state}")

# Alert on excessive usage
if daily_usda_calls > 100:
    send_alert("Excessive USDA API usage detected")
```

### **Performance Monitoring**

```python
# Track response times
with timer("carbon_calculation"):
    result = calculate_carbon_impact(event)

# Alert on slow responses
if response_time > 200:
    send_alert("Slow carbon calculation detected")
```

---

## **🎯 Conclusion**

**USDA API calls should be strategic, not reactive.** The goal is to use USDA data to enhance carbon calculation accuracy and credibility, not to provide real-time farm optimization. By limiting USDA API calls to event creation and scheduled updates, Trazo can maintain fast performance while delivering accurate, USDA-verified carbon transparency to farmers and consumers.

**Key Principle**: _Calculate once with USDA data, serve many times from cache._
