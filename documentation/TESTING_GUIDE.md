# Trazo Compliance Testing Guide

This guide provides step-by-step instructions for testing all implemented compliance features to verify that the pricing plan promises are properly enforced.

## 🚀 Quick Setup

### 1. Set Up Test Data

```bash
cd trazo-back
poetry run python manage.py setup_compliance_test
```

This creates test accounts for each plan type with sample data:

- **Basic Plan**: `basic-test@trazo.com` (Password: `testpass123`)
- **Standard Plan**: `standard-test@trazo.com` (Password: `testpass123`)
- **Corporate Plan**: `corporate-test@trazo.com` (Password: `testpass123`)

### 2. Verify Implementation

```bash
poetry run python verify_compliance.py
```

This runs automated compliance verification tests.

### 3. Start Development Server

```bash
poetry run python manage.py runserver
```

## 📋 Manual Testing Checklist

### Support SLA System Testing

#### ✅ Basic Plan (48h SLA)

1. Login to admin: `/admin/` with superuser account
2. Go to Support → Support tickets
3. Find tickets created by `basic-test@trazo.com`
4. Verify **SLA Response Hours** = 48
5. Check that priority is set to "Normal" (not High)

#### ✅ Standard Plan (24h SLA)

1. Find tickets created by `standard-test@trazo.com`
2. Verify **SLA Response Hours** = 24
3. Check faster response time than Basic plan

#### ✅ Corporate Plan (12h SLA)

1. Find tickets created by `corporate-test@trazo.com`
2. Verify **SLA Response Hours** = 12
3. Check priority support enabled

**API Testing:**

```bash
# Get support tickets (requires authentication)
curl -X GET "http://localhost:8000/support/tickets/" \
  -H "Authorization: Bearer <token>"

# Check SLA metrics
curl -X GET "http://localhost:8000/support/sla-metrics/" \
  -H "Authorization: Bearer <token>"
```

### IoT Automation Level Testing

#### ✅ Basic Plan (50% Automation)

1. Login as `basic-test@trazo.com`
2. Navigate to IoT devices section
3. Check automation settings show 50% limit
4. Verify high confidence requirement (0.90) for automation

#### ✅ Standard Plan (75% Automation)

1. Login as `standard-test@trazo.com`
2. Check automation level increased to 75%
3. Verify medium confidence requirement (0.85)

#### ✅ Corporate Plan (85% Automation)

1. Login as `corporate-test@trazo.com`
2. Check highest automation level (85%)
3. Verify lower confidence requirement (0.80)

**API Testing:**

```bash
# Get automation statistics
curl -X GET "http://localhost:8000/carbon/automation-rules/automation_stats/" \
  -H "Authorization: Bearer <token>"

# Check pending automation events
curl -X GET "http://localhost:8000/carbon/automation-rules/pending_events/" \
  -H "Authorization: Bearer <token>"
```

### Carbon Tracking Mode Testing

#### ✅ Basic Plan (Manual Mode)

1. Login as `basic-test@trazo.com`
2. Go to carbon tracking section
3. Verify all entries require manual input
4. Check no automated calculations from IoT data

#### ✅ Standard/Corporate Plans (Automated Mode)

1. Login as `standard-test@trazo.com` or `corporate-test@trazo.com`
2. Verify automated carbon calculations available
3. Check IoT data can auto-generate carbon entries
4. Verify manual override still available

**API Testing:**

```bash
# Get carbon entries
curl -X GET "http://localhost:8000/carbon/entries/" \
  -H "Authorization: Bearer <token>"

# Check automation mode
curl -X GET "http://localhost:8000/carbon/tracking-mode/" \
  -H "Authorization: Bearer <token>"
```

### Plan Features Verification

#### ✅ Price Verification

- Basic: $69/month
- Standard: $119/month
- Corporate: $149/month
- Enterprise: $499/month

#### ✅ Feature Matrix Testing

| Feature          | Basic    | Standard  | Corporate | Enterprise |
| ---------------- | -------- | --------- | --------- | ---------- |
| IoT Automation   | 50%      | 75%       | 85%       | 85%        |
| Carbon Tracking  | Manual   | Automated | Automated | Automated  |
| Support SLA      | 48h      | 24h       | 12h       | 4h         |
| Priority Support | ❌       | ❌        | ✅        | ✅         |
| API Rate Limits  | 1000/day | 5000/day  | 15000/day | Unlimited  |
| Data Storage     | 1 year   | 3 years   | 5 years   | Unlimited  |

## 🔧 Advanced Testing Scenarios

### 1. Subscription Upgrade Testing

```bash
# Test what happens when a user upgrades from Basic to Standard
# 1. Create Basic subscription
# 2. Verify 50% automation limit
# 3. Upgrade to Standard plan
# 4. Verify automation level increases to 75%
# 5. Check SLA changes from 48h to 24h
```

### 2. Data Volume Limits Testing

```bash
# Test storage limits (requires large dataset)
# 1. Create many carbon entries for Basic plan user
# 2. Verify 1-year data retention enforced
# 3. Check older data gets archived/deleted
```

### 3. API Rate Limiting Testing

```bash
# Test rate limits per plan
# 1. Make rapid API calls as Basic user
# 2. Verify 1000/day limit enforced
# 3. Test Standard plan gets 5000/day limit
```

### 4. Support Escalation Testing

```bash
# Test support ticket escalation
# 1. Create high-priority ticket as Corporate user
# 2. Verify 12h SLA assigned automatically
# 3. Check priority queue handling
# 4. Test SLA breach notifications
```

## 🐛 Troubleshooting

### Common Issues

**Login "Access denied" Error:**

```bash
# This happens when test users have wrong user_type for the subdomain
# Solution: Ensure users are created as PRODUCER type for app subdomain access
# The setup script now creates users with correct type automatically
```

**Test Data Not Created:**

```bash
# Clean up and recreate
poetry run python manage.py shell
>>> from users.models import User
>>> User.objects.filter(email__contains='test@trazo.com').delete()
>>> exit()
poetry run python manage.py setup_compliance_test
```

**Automation Levels Not Working:**

```bash
# Check automation service
poetry run python manage.py shell
>>> from carbon.services.automation_service import AutomationLevelService
>>> service = AutomationLevelService()
>>> print(service.plan_automation_levels)
```

**SLA Not Applied:**

```bash
# Check support ticket SLA assignment
poetry run python manage.py shell
>>> from support.models import SupportTicket
>>> ticket = SupportTicket.objects.first()
>>> print(f"SLA: {ticket.sla_response_hours}h")
```

### Reset Test Environment

```bash
# Complete reset
poetry run python manage.py flush
poetry run python manage.py migrate
poetry run python manage.py setup_compliance_test
```

## 📊 Compliance Verification Results

After running `verify_compliance.py`, you should see:

```
🎯 Success Rate: 4/4 (100.0%)
🎉 ALL COMPLIANCE FEATURES WORKING CORRECTLY!
✅ Ready for production deployment!
```

### Expected Test Results:

- ✅ **Support SLA System**: All plans have correct response times
- ✅ **IoT Automation Levels**: 50%/75%/85% limits enforced correctly
- ✅ **Carbon Tracking Modes**: Manual vs Automated differentiation working
- ✅ **Plan Features**: All pricing promises properly implemented

## 🚀 Production Deployment Checklist

Before deploying to production:

1. [ ] All compliance tests pass (100% success rate)
2. [ ] Manual testing completed for each plan type
3. [ ] API endpoints respond correctly with authentication
4. [ ] Support SLA metrics tracking functional
5. [ ] IoT automation percentages enforced properly
6. [ ] Carbon tracking modes working per plan
7. [ ] Database migrations applied successfully
8. [ ] Admin interface accessible for support staff
9. [ ] Email notifications working for support tickets
10. [ ] Rate limiting configured for API endpoints

## 📞 Next Steps

1. **Deploy to staging environment** and repeat testing
2. **Set up monitoring** for SLA compliance metrics
3. **Train support staff** on new ticket management system
4. **Configure alerting** for SLA breaches
5. **Implement remaining features** (educational resources, advanced reporting)

---

**Compliance Status**: ✅ **75% Complete** (Target Features Implemented)
**Remaining**: Educational Resources (2 weeks), Advanced Reporting (3 weeks)
**Est. 95% Compliance**: 5 weeks
