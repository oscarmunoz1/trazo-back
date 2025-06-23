# 🔑 **Real USDA API Setup Guide**

## 📋 **Overview**

This guide shows you how to get **real USDA API keys** and integrate them with our carbon footprint system. We'll use actual government APIs instead of mock data.

---

## 🎯 **Available Real APIs**

### 1. **USDA NASS QuickStats API** ✅

- **What it provides:** Real crop yields, acreage, production data
- **Cost:** **FREE**
- **Registration:** Required
- **URL:** https://quickstats.nass.usda.gov/api

### 2. **USDA ERS Data API** ✅

- **What it provides:** Farm economic data, ARMS survey data
- **Cost:** **FREE**
- **Registration:** Required
- **URL:** https://www.ers.usda.gov/developer/data-apis/

### 3. **USDA FoodData Central API** ✅

- **What it provides:** Food composition and nutrition data
- **Cost:** **FREE**
- **Registration:** Required
- **URL:** https://fdc.nal.usda.gov/api-key-signup.html

---

## 🚀 **Step-by-Step Setup**

### **Step 1: Register for USDA NASS API Key**

1. **Go to:** https://quickstats.nass.usda.gov/api
2. **Fill out the registration form:**
   ```
   Name/Organization: Your name or company
   Email Address: your-email@example.com
   ✅ Agree to Terms of Service
   ✅ Check for email updates (optional)
   ```
3. **Click "Submit"**
4. **Check your email** - You'll receive the API key immediately
5. **Copy the API key** (it looks like: `A1B2C3D4-E5F6-7890-ABCD-1234567890AB`)

### **Step 2: Register for USDA ERS API Key**

1. **Go to:** https://www.ers.usda.gov/developer/data-apis/
2. **Fill out the form** (similar to NASS)
3. **Receive API key via email**

### **Step 3: Configure Django Settings**

Add your API keys to your Django settings:

```python
# trazo-back/backend/settings/dev.py
# Add these lines:

# USDA API Keys
USDA_NASS_API_KEY = 'YOUR_NASS_API_KEY_HERE'
USDA_ERS_API_KEY = 'YOUR_ERS_API_KEY_HERE'

# For production, use environment variables:
# USDA_NASS_API_KEY = os.environ.get('USDA_NASS_API_KEY')
# USDA_ERS_API_KEY = os.environ.get('USDA_ERS_API_KEY')
```

### **Step 4: Test the Real API Connection**

```python
# Test script - save as trazo-back/test_real_usda_api.py

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings.dev')
django.setup()

from carbon.services.real_usda_integration import RealUSDAAPIClient

def test_real_usda_api():
    """Test real USDA API integration"""
    print("🧪 Testing Real USDA API Integration...")

    client = RealUSDAAPIClient()

    # Test 1: Get corn data for Iowa
    print("\\n1. Testing NASS corn data for Iowa...")
    corn_data = client.get_nass_crop_data('corn', 'IA', 2023)

    if corn_data:
        print(f"✅ Success! Found {len(corn_data.get('data', []))} records")
        if 'data' in corn_data and corn_data['data']:
            sample = corn_data['data'][0]
            print(f"   Sample: {sample.get('short_desc', 'N/A')} = {sample.get('Value', 'N/A')}")
    else:
        print("❌ No data returned - check your API key")

    # Test 2: Get benchmark yield
    print("\\n2. Testing benchmark yield calculation...")
    benchmark = client.get_benchmark_yield('corn', 'IA')

    if benchmark:
        print(f"✅ Benchmark yield for Iowa corn: {benchmark:.2f} bushels/acre")
    else:
        print("❌ No benchmark data available")

    # Test 3: Full carbon calculation
    print("\\n3. Testing full carbon intensity calculation...")

    farm_practices = {
        'inputs': {
            'nitrogen_kg': 150,  # kg per hectare
            'phosphorus_kg': 50,
            'diesel_liters': 80
        },
        'area_hectares': 100,
        'yield_per_hectare': 9000  # kg per hectare (corn)
    }

    carbon_result = client.calculate_carbon_intensity('corn', 'IA', farm_practices)

    if carbon_result and not carbon_result.get('error'):
        print(f"✅ Carbon intensity: {carbon_result['carbon_intensity']:.4f} kg CO2e/kg")
        print(f"   Total emissions: {carbon_result['total_emissions']:.2f} kg CO2e")
        print(f"   Data source: {carbon_result['data_source']}")

        if carbon_result.get('benchmark_comparison'):
            benchmark_comp = carbon_result['benchmark_comparison']
            print(f"   Benchmark comparison: {benchmark_comp['yield_efficiency']}")
    else:
        print(f"❌ Carbon calculation failed: {carbon_result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    test_real_usda_api()
```

---

## 🔧 **Integration with Existing System**

### **Update Enhanced USDA Factors Service**

Modify your existing `enhanced_usda_factors.py` to use real data:

```python
# In trazo-back/carbon/services/enhanced_usda_factors.py
# Add this import at the top:
from .real_usda_integration import get_real_usda_carbon_data

# Replace the get_real_time_emission_factors method:
def get_real_time_emission_factors(self, crop_type: str, state: str) -> Dict[str, float]:
    """Get real-time data using actual USDA APIs"""
    try:
        # Use the real USDA integration
        farm_practices = {
            'inputs': {},
            'area_hectares': 1,
            'yield_per_hectare': 0
        }

        real_data = get_real_usda_carbon_data(crop_type, state, farm_practices)

        if real_data and real_data.get('real_data'):
            # Extract emission factors from real data
            return {
                'nitrogen': real_data.get('emission_breakdown', {}).get('nitrogen', self.base_usda_factors['nitrogen']),
                'phosphorus': real_data.get('emission_breakdown', {}).get('phosphorus', self.base_usda_factors['phosphorus']),
                'diesel': real_data.get('emission_breakdown', {}).get('fuel', self.base_usda_factors['diesel']),
                'data_source': 'USDA NASS + EPA',
                'real_time': True
            }

        # Fallback to base factors
        return self.get_regional_factors(crop_type, state)

    except Exception as e:
        logger.error(f"Error getting real-time factors: {e}")
        return self.get_regional_factors(crop_type, state)
```

---

## 🧪 **Testing Real Data Flow**

### **Test 1: Basic API Connection**

```bash
# Run the test
cd trazo-back
poetry run python test_real_usda_api.py
```

**Expected Output:**

```
🧪 Testing Real USDA API Integration...

1. Testing NASS corn data for Iowa...
✅ Success! Found 15 records
   Sample: CORN - YIELD, MEASURED IN BU / ACRE = 195.0

2. Testing benchmark yield calculation...
✅ Benchmark yield for Iowa corn: 195.00 bushels/acre

3. Testing full carbon intensity calculation...
✅ Carbon intensity: 0.1234 kg CO2e/kg
   Total emissions: 1110.80 kg CO2e
   Data source: USDA NASS + EPA emission factors
   Benchmark comparison: above_average
```

### **Test 2: API Endpoint Integration**

```python
# Test via Django API
import requests

# Test the USDA endpoint
response = requests.get('http://localhost:8000/api/carbon/usda-factors/', {
    'crop_type': 'corn',
    'state': 'IA'
})

print(response.json())
```

---

## 📊 **What You'll Get with Real APIs**

### **Real NASS Data Examples:**

```json
{
  "commodity_desc": "CORN",
  "state_name": "IOWA",
  "year": "2023",
  "statisticcat_desc": "YIELD",
  "unit_desc": "BU / ACRE",
  "Value": "195.0",
  "data_source": "USDA NASS QuickStats"
}
```

### **Enhanced Carbon Calculations:**

```json
{
  "carbon_intensity": 0.1234,
  "total_emissions": 1110.8,
  "emission_breakdown": {
    "nitrogen": 879.0,
    "phosphorus": 10.0,
    "fuel": 214.4
  },
  "benchmark_comparison": {
    "farm_yield": 9000,
    "regional_benchmark": 8500,
    "performance_ratio": 1.059,
    "yield_efficiency": "above_average"
  },
  "data_source": "USDA NASS + EPA emission factors",
  "confidence_level": "high",
  "real_data": true
}
```

---

## 🚨 **Important Notes**

### **API Limits:**

- **NASS API:** 50,000 records per request
- **Rate limiting:** Be respectful, cache results
- **Data availability:** Previous year data is most reliable

### **Data Quality:**

- Some data may be marked as `(D)` (withheld to avoid disclosure)
- Regional variations exist
- Seasonal data availability

### **Cost:**

- **All USDA APIs are FREE** 🎉
- No credit card required
- Just email registration

---

## 🔄 **Next Steps**

1. **Get your API keys** (5 minutes)
2. **Configure Django settings** (2 minutes)
3. **Run the test script** (1 minute)
4. **Integration testing** (10 minutes)
5. **Deploy to production** with environment variables

---

## 🆘 **Troubleshooting**

### **Common Issues:**

1. **"unauthorized" error:**

   - Check your API key is correct
   - Ensure no extra spaces or characters

2. **"No data returned":**

   - Try a different year (2022-2023 is most reliable)
   - Check crop name spelling (use NASS commodity names)

3. **"Request timeout":**
   - USDA servers can be slow
   - Implement retry logic
   - Use caching for repeated requests

### **Need Help?**

- Check USDA API documentation
- Review the test script output
- Monitor Django logs for detailed error messages

---

**Ready to test with real government data! 🚀**
