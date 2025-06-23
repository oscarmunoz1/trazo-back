# 🤖 AI Voice Processing Setup Guide

This guide shows you how to set up **real AI voice processing** using OpenAI's GPT models for intelligent agricultural event extraction.

## 📋 Overview

The AI voice processing system replaces mock pattern matching with real artificial intelligence that can:

- **Understand natural language** in multiple languages (English, Spanish, Portuguese)
- **Extract complex agricultural data** from voice inputs
- **Provide confidence scores** based on AI analysis
- **Generate carbon impact estimates** using AI reasoning
- **Auto-approve high-confidence events** for streamlined workflows

## 🔑 Step 1: Get OpenAI API Key

### Option A: OpenAI Platform (Recommended)

1. **Go to:** https://platform.openai.com/api-keys
2. **Sign up** or log in to your OpenAI account
3. **Click "Create new secret key"**
4. **Copy the API key** (starts with `sk-...`)
5. **Save it securely** - you won't see it again!

### Option B: Azure OpenAI (Enterprise)

If you prefer Azure OpenAI Service:

1. **Go to:** https://azure.microsoft.com/en-us/products/ai-services/openai-service
2. **Set up Azure OpenAI resource**
3. **Get your endpoint and API key**

## ⚙️ Step 2: Configure Django Settings

### Development Environment

Add to your `.env` file in `trazo-back/`:

```bash
# OpenAI Configuration for AI Voice Processing
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4
OPENAI_MAX_TOKENS=500
OPENAI_TEMPERATURE=0.3
```

### Production Environment

For production, use environment variables or secrets management:

```bash
# Production environment variables
export OPENAI_API_KEY="sk-your-production-key"
export OPENAI_MODEL="gpt-4"
export OPENAI_MAX_TOKENS=500
export OPENAI_TEMPERATURE=0.3
```

## 🧪 Step 3: Test the Integration

Run the test script to verify everything works:

```bash
cd trazo-back
poetry run python test_ai_voice_integration.py
```

Expected output:

```
🧪 Testing AI Voice Processing Integration...
============================================================

🔑 Checking AI Configuration...
✅ OpenAI API key configured: sk-proj-...
✅ Model: gpt-4
✅ Max tokens: 500
✅ Temperature: 0.3

1️⃣ Testing: Irrigated field for 6 hours with drip system
   Crop: strawberries, Language: en-US
   ✅ Detected: irrigation (confidence: 92%)
   ⏱️  Processing time: 1247ms
   🔧 Source: openai_gpt
   📊 Amounts: 6 hours
   ⚙️  Systems: drip irrigation
   🌍 Carbon impact: 3.2 kg CO₂e
   🤖 Real AI processing successful!
```

## 🚀 Step 4: Frontend Integration

The frontend automatically uses the AI endpoint. No additional configuration needed!

### How it Works:

1. **User speaks:** "Irrigated field for 6 hours with drip system"
2. **Frontend calls:** `/api/carbon/process-voice-event/`
3. **AI processes:** OpenAI GPT analyzes the agricultural context
4. **Results returned:** Structured event data with confidence scores
5. **Auto-approval:** High confidence events (85%+) are automatically created

## 📊 AI Model Configuration

### Model Options:

| Model           | Speed   | Accuracy | Cost   | Use Case                 |
| --------------- | ------- | -------- | ------ | ------------------------ |
| `gpt-4`         | Slower  | Highest  | Higher | Production (recommended) |
| `gpt-4-turbo`   | Fast    | High     | Medium | Development              |
| `gpt-3.5-turbo` | Fastest | Good     | Lowest | Testing                  |

### Temperature Settings:

- **0.0-0.3:** Conservative, consistent results (recommended for agriculture)
- **0.4-0.7:** Balanced creativity and consistency
- **0.8-1.0:** More creative, less predictable

## 🔧 Troubleshooting

### Common Issues:

**❌ "OpenAI API key not configured"**

```bash
# Check your .env file
cat trazo-back/.env | grep OPENAI

# Add the key if missing
echo "OPENAI_API_KEY=sk-your-key-here" >> trazo-back/.env
```

**❌ "AI processing failed: 401 Unauthorized"**

- Check if your API key is valid
- Verify you have credits in your OpenAI account
- Test the key at https://platform.openai.com/playground

**❌ "AI processing failed: 429 Rate limit exceeded"**

- You've exceeded your rate limits
- Upgrade your OpenAI plan or wait for reset
- Consider using `gpt-3.5-turbo` for higher rate limits

**❌ "AI processing failed: Connection error"**

- Check internet connectivity
- Verify firewall settings
- OpenAI API requires HTTPS outbound access

### Fallback Behavior:

If AI processing fails, the system automatically falls back to pattern matching:

```
⚠️ Voice Processed (Fallback Mode)
AI unavailable - used pattern matching with 65% confidence
```

## 🌍 Multi-Language Support

The AI supports multiple languages automatically:

### English:

```
"Applied fertilizer today, 200 pounds per acre NPK"
→ Detected: fertilization (95% confidence)
```

### Spanish:

```
"Aplicé fertilizante hoy, 100 kilos por hectárea"
→ Detected: fertilization (93% confidence)
```

### Portuguese:

```
"Apliquei fertilizante hoje, 100 quilos por hectare"
→ Detected: fertilization (91% confidence)
```

## 💰 Cost Estimation

Typical costs per voice processing:

| Model         | Tokens Used | Cost per Call | Monthly (1000 calls) |
| ------------- | ----------- | ------------- | -------------------- |
| GPT-4         | ~300 tokens | $0.006        | $6.00                |
| GPT-4 Turbo   | ~300 tokens | $0.003        | $3.00                |
| GPT-3.5 Turbo | ~300 tokens | $0.0006       | $0.60                |

## 🎯 Performance Optimization

### For High Volume:

1. **Use GPT-3.5 Turbo** for faster processing
2. **Implement caching** for repeated phrases
3. **Batch process** multiple voice inputs
4. **Use shorter prompts** to reduce token usage

### For High Accuracy:

1. **Use GPT-4** for maximum accuracy
2. **Lower temperature** (0.1-0.2) for consistency
3. **Provide crop context** for better classification
4. **Use confidence thresholds** (90%+ for auto-approval)

## 🔐 Security Best Practices

### API Key Security:

- ✅ **Use environment variables** - never commit keys to git
- ✅ **Rotate keys regularly** - OpenAI allows multiple keys
- ✅ **Monitor usage** - set up billing alerts
- ✅ **Use separate keys** for development/production

### Data Privacy:

- ✅ **Voice data is not stored** by OpenAI (per their policy)
- ✅ **Transcripts are processed temporarily** for analysis
- ✅ **No personal information** is sent to OpenAI
- ✅ **Agricultural data only** - crop types and activities

## 📈 Monitoring and Analytics

### Track AI Performance:

```python
# Log AI processing metrics
logger.info(f"AI processing: {confidence}% confidence, {processing_time}ms")
```

### Monitor Costs:

- Check OpenAI usage dashboard monthly
- Set up billing alerts at $10, $50, $100
- Monitor token usage patterns

### Quality Assurance:

- Review low-confidence events (< 70%)
- Validate AI classifications against user corrections
- Adjust prompts based on common misclassifications

## 🎉 Ready to Use!

Once configured, your voice processing will use real AI instead of pattern matching!
