# Trazo Backend Security Fixes Documentation

## Overview
This document details the critical security vulnerabilities that were identified and fixed in the Trazo backend application.

## Critical Issues Fixed

### 1. ✅ Exposed API Keys
**Issue**: Hardcoded USDA API keys in settings files
**Risk**: High - API keys exposed in source code could be compromised
**Fix**: 
- Removed hardcoded API keys from `dev.py` and `prod.py`
- Replaced with environment variables using `os.environ.get()`
- Created `.env.template` for secure configuration

**Files Modified**:
- `/backend/settings/dev.py`
- `/backend/settings/prod.py`
- `/backend/settings/base.py`

### 2. ✅ Missing Rate Limiting
**Issue**: No rate limiting on carbon calculation endpoints
**Risk**: High - API abuse, DoS attacks, resource exhaustion
**Fix**:
- Added `django-ratelimit` dependency
- Implemented rate limiting on all carbon calculation endpoints
- Different limits for different operation types:
  - Carbon calculations: 5 requests/minute
  - Bulk operations: 3 requests/minute
  - General queries: 10-20 requests/minute

**Files Modified**:
- `requirements.txt`
- `pyproject.toml`
- `/carbon/views.py`

### 3. ✅ Input Validation
**Issue**: Insufficient validation for carbon amounts and calculations
**Risk**: Medium - Data integrity issues, potential injection attacks
**Fix**:
- Added comprehensive validation to `CarbonEntrySerializer`
- Validates carbon amounts (0.01-10,000 kg CO2e)
- Validates year ranges (1900 to current+5 years)
- Validates carbon entry types
- Added XSS protection for description fields

**Files Modified**:
- `/carbon/serializers.py`

### 4. ✅ Authentication Bypass
**Issue**: Some carbon endpoints missing authentication requirements
**Risk**: High - Unauthorized access to sensitive data
**Fix**:
- Added `IsAuthenticated` permission to all carbon endpoints
- Verified authentication requirements across all ViewSets
- Added proper permission classes

**Files Modified**:
- `/carbon/views.py`

### 5. ✅ USDA API Rate Limiting
**Issue**: No rate limiting for external USDA API calls
**Risk**: Medium - API quota exhaustion, service blocking
**Fix**:
- Implemented custom `APIRateLimiter` class
- Added rate limiting to NASS and FoodData Central API calls
- Conservative limits: 10 calls/minute for NASS, 30 calls/minute for FoodData Central

**Files Modified**:
- `/carbon/services/real_usda_integration.py`

### 6. ✅ Security Logging
**Issue**: No logging for security events
**Risk**: Medium - Inability to detect and respond to attacks
**Fix**:
- Created custom security middleware
- Added logging for rate limit violations
- Added logging for authentication failures
- Added logging for suspicious requests
- Configured rotating log files

**Files Created**:
- `/backend/security_middleware.py`

**Files Modified**:
- `/backend/settings/base.py`

## Security Enhancements Added

### Rate Limiting Configuration
```python
# Examples of rate limiting applied:
@ratelimit(key='user', rate='5/m', method='POST', block=True)  # Carbon calculations
@ratelimit(key='user', rate='10/m', method='GET', block=True)  # Data queries
@ratelimit(key='user', rate='3/m', method='POST', block=True)  # Bulk operations
```

### Input Validation Examples
```python
def validate_amount(self, value):
    # Validates range (0.01-10,000 kg CO2e)
    if amount < 0.01:
        raise ValidationError("Amount must be at least 0.01 kg CO2e")
    if amount > 10000:
        raise ValidationError("Amount cannot exceed 10,000 kg CO2e")
```

### Security Middleware Features
- Logs rate limit violations with IP, user, and request details
- Logs authentication failures (401/403 responses)
- Logs suspicious requests (large payloads, missing headers)
- Logs to both console and rotating files

## Environment Variables Required

### Critical Security Variables
```bash
# USDA API Keys - NEVER commit these to version control
USDA_NASS_API_KEY=your-usda-nass-api-key-here
USDA_ERS_API_KEY=your-usda-ers-api-key-here
USDA_FOODDATA_API_KEY=your-usda-fooddata-api-key-here

# Django Security
SECRET_KEY=your-super-secret-django-key-here
DEBUG=False

# Database
DATABASE_URL=postgresql://username:password@host:port/database_name
```

## Deployment Security Checklist

### ✅ Pre-Deployment
- [ ] Copy `.env.template` to `.env` and fill in all required values
- [ ] Ensure `DEBUG=False` in production
- [ ] Set strong `SECRET_KEY` (at least 50 characters)
- [ ] Configure proper `ALLOWED_HOSTS`
- [ ] Set up SSL/HTTPS certificates
- [ ] Configure secure database credentials

### ✅ API Key Security
- [ ] Register for USDA API keys at official USDA sites
- [ ] Store API keys in environment variables only
- [ ] Never commit API keys to version control
- [ ] Rotate API keys regularly
- [ ] Monitor API usage and quotas

### ✅ Monitoring and Logging
- [ ] Ensure logs directory exists and is writable
- [ ] Monitor security.log for suspicious activity
- [ ] Set up log rotation to prevent disk space issues
- [ ] Configure alerts for rate limit violations
- [ ] Monitor authentication failure patterns

### ✅ Network Security
- [ ] Configure firewall rules
- [ ] Use HTTPS only (no HTTP)
- [ ] Set proper CORS headers
- [ ] Enable CSRF protection
- [ ] Configure secure headers (HSTS, etc.)

## Monitoring and Alerts

### Log Files Location
- Security events: `/logs/security.log`
- Application logs: Console output (configure as needed)

### Key Metrics to Monitor
- Rate limit violations per hour
- Authentication failure rate
- Large request payload frequency
- API response times
- USDA API quota usage

## API Rate Limits Summary

| Endpoint Type | Rate Limit | Reason |
|---------------|------------|---------|
| Carbon calculations | 5/minute | CPU-intensive operations |
| Data queries | 10-20/minute | Database operations |
| Bulk operations | 3/minute | Large data processing |
| USDA NASS API | 10/minute | External API limits |
| FoodData Central | 30/minute | Higher external API limits |

## Testing Security Fixes

### Rate Limiting Tests
```bash
# Test rate limiting (should get 429 after limit)
for i in {1..6}; do curl -X POST "http://localhost:8000/carbon/entries/calculate_emissions/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"crop_type": "corn", "acreage": 10}'; done
```

### Input Validation Tests
```bash
# Test invalid carbon amount (should fail)
curl -X POST "http://localhost:8000/carbon/entries/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"amount": 50000, "type": "emission"}'  # Exceeds 10,000 limit
```

### Authentication Tests
```bash
# Test without authentication (should get 401)
curl -X GET "http://localhost:8000/carbon/entries/"
```

## Additional Security Recommendations

### Future Enhancements
1. **Multi-Factor Authentication (MFA)**: Implement for admin accounts
2. **API Versioning**: Add versioning to maintain compatibility
3. **Request Signing**: Implement request signing for sensitive operations
4. **Data Encryption**: Encrypt sensitive data at rest
5. **Audit Trail**: Enhanced audit logging for all data changes
6. **WAF Integration**: Use Web Application Firewall for additional protection

### Regular Security Tasks
1. Update dependencies regularly
2. Monitor security advisories
3. Conduct penetration testing
4. Review and rotate API keys
5. Audit user permissions
6. Monitor log files for anomalies

## Support and Maintenance

For security-related issues or questions:
1. Check security logs for suspicious activity
2. Monitor rate limiting metrics
3. Verify environment variable configuration
4. Test API endpoints after updates
5. Review authentication flows regularly

This security implementation follows industry best practices and provides a solid foundation for secure API operations while maintaining system performance and user experience.