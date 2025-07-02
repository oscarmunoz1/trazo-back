# Social Authentication Setup Guide for Trazo

This guide explains how to configure Google, Facebook, and Apple Sign In for both producer and consumer platforms in Trazo.

## Overview

Trazo supports social authentication for:
- **Producer Platform** (`app.localhost:3000`) - Agricultural businesses and farms
- **Consumer Platform** (`consumer.localhost:3000`) - End consumers scanning QR codes

## Architecture

### Backend
- **Framework**: Django with django-allauth
- **Endpoint**: `/auth/social/`
- **Authentication**: JWT tokens with custom user types
- **User Types**: 
  - `4` = Producer (agricultural business)
  - `5` = Consumer (end-user)

### Frontend
- **Provider**: React with custom OAuth utilities
- **State Management**: Redux Toolkit + RTK Query
- **UI Components**: Chakra UI with modern design patterns

## Setup Instructions

### 1. Google OAuth 2.0 Setup

#### Google Cloud Console Configuration

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   - Create a new project or select existing one

2. **Enable Required APIs**
   ```bash
   - Google Identity Toolkit API
   - Google+ API (deprecated but still needed for some legacy auth flows)
   ```

3. **Create OAuth 2.0 Credentials**
   - Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
   - Application type: Web application
   - Name: "Trazo Social Auth"

4. **Configure Authorized Domains**
   ```
   localhost
   app.localhost
   consumer.localhost
   ```

5. **Configure Authorized Redirect URIs**
   ```
   http://localhost:3000
   http://app.localhost:3000
   http://consumer.localhost:3000
   ```

6. **Get Credentials**
   - Client ID: `your_client_id.apps.googleusercontent.com`
   - Client Secret: `your_client_secret`

#### Environment Configuration

**Backend (.env)**
```bash
GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

**Frontend (.env)**
```bash
VITE_GOOGLE_CLIENT_ID=your_google_client_id.apps.googleusercontent.com
```

### 2. Facebook OAuth 2.0 Setup

#### Facebook Developers Configuration

1. **Go to Facebook Developers**
   - Visit: https://developers.facebook.com/
   - Create a new app or select existing one

2. **Add Facebook Login Product**
   - In app dashboard, click "Add Product"
   - Select "Facebook Login" → "Set Up"

3. **Configure OAuth Settings**
   - Go to Facebook Login → Settings
   - Valid OAuth Redirect URIs:
     ```
     http://localhost:3000
     http://app.localhost:3000
     http://consumer.localhost:3000
     ```

4. **Configure App Domains**
   - In App Settings → Basic
   - App Domains:
     ```
     localhost
     app.localhost
     consumer.localhost
     ```

5. **Get Credentials**
   - App ID: Found in App Settings → Basic
   - App Secret: Found in App Settings → Basic

#### Environment Configuration

**Backend (.env)**
```bash
FACEBOOK_APP_ID=your_facebook_app_id
FACEBOOK_APP_SECRET=your_facebook_app_secret
```

**Frontend (.env)**
```bash
VITE_FACEBOOK_APP_ID=your_facebook_app_id
```

### 3. Apple Sign In Setup

#### Apple Developer Configuration

1. **Create App ID**
   - Go to: https://developer.apple.com/account/resources/identifiers/
   - Create new App ID with "Sign In with Apple" capability

2. **Create Service ID**
   - Create new Service ID for web authentication
   - Configure return URLs:
     ```
     http://localhost:3000
     http://app.localhost:3000
     http://consumer.localhost:3000
     ```

3. **Create Private Key**
   - Create new key with "Sign In with Apple" capability
   - Download the .p8 file

4. **Get Required Information**
   - Client ID: Your Service ID
   - Team ID: Found in membership details
   - Key ID: From the private key you created
   - Private Key: Content of the .p8 file

#### Environment Configuration

**Backend (.env)**
```bash
APPLE_CLIENT_ID=your.apple.service.id
APPLE_CLIENT_SECRET=your_generated_jwt_token
APPLE_TEAM_ID=your_team_id
APPLE_KEY_ID=your_key_id
APPLE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----
your_private_key_content
-----END PRIVATE KEY-----
```

**Frontend (.env)**
```bash
VITE_APPLE_CLIENT_ID=your.apple.service.id
```

## Implementation Details

### Backend Implementation

The backend uses a unified social authentication endpoint at `/auth/social/` that handles all three providers:

```python
# POST /auth/social/
{
    "provider": "google|facebook|apple",
    "access_token": "provider_access_token",  # For Google & Facebook
    "id_token": "provider_id_token",          # For Google & Apple
    "user_type": 4,                           # 4=Producer, 5=Consumer
    "user": {                                 # For Apple (name data)
        "name": {
            "firstName": "John",
            "lastName": "Doe"
        }
    }
}
```

**Response:**
```json
{
    "user": {
        "id": 123,
        "email": "user@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "user_type": 4,
        "social_auth_provider": "google"
    },
    "access": "jwt_access_token",
    "refresh": "jwt_refresh_token",
    "user_type": 4
}
```

### Frontend Implementation

The frontend uses OAuth libraries and redirects users based on their type:

**Producer Flow:**
1. User clicks social login on `app.localhost:3000/auth/signin`
2. OAuth popup/redirect authenticates with provider
3. Frontend calls `/auth/social/` with `user_type: 4`
4. Success → Redirect to `/admin/dashboard`

**Consumer Flow:**
1. User clicks social login on `consumer.localhost:3000/auth/signin`
2. OAuth popup/redirect authenticates with provider
3. Frontend calls `/auth/social/` with `user_type: 5`
4. Success → Redirect to `/admin/dashboard/scans`

## Security Considerations

### CORS Configuration
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://app.localhost:3000",
    "http://consumer.localhost:3000"
]
```

### JWT Security
- Access tokens expire in 20 minutes
- Refresh tokens expire in 24 hours
- Tokens are stored in HTTP-only cookies
- CSRF protection enabled

### Provider Security
- **Google**: Verifies ID tokens using Google's public keys
- **Facebook**: Validates access tokens with Facebook Graph API
- **Apple**: Verifies ID tokens using Apple's public keys

## Testing

### Local Development Testing

1. **Start Backend**
   ```bash
   cd trazo-back
   poetry run python manage.py runserver
   ```

2. **Start Frontend**
   ```bash
   cd trazo-app
   npm start
   ```

3. **Test URLs**
   - Producer: http://app.localhost:3000/auth/signin
   - Consumer: http://consumer.localhost:3000/auth/signin

### Test Social Authentication

1. Click on Google/Facebook/Apple buttons
2. Complete OAuth flow in popup/redirect
3. Verify user creation in Django admin
4. Check JWT token in browser cookies
5. Verify redirect to correct dashboard

## Troubleshooting

### Common Issues

1. **"OAuth Client ID not configured"**
   - Check environment variables are set correctly
   - Verify client IDs match OAuth provider configuration

2. **"Invalid redirect URI"**
   - Ensure redirect URIs are exactly configured in OAuth provider
   - Check for http vs https mismatches

3. **"CORS errors"**
   - Verify CORS_ALLOWED_ORIGINS includes your frontend URL
   - Check that frontend is running on expected port

4. **"Token verification failed"**
   - For Google: Check client ID matches the ID token audience
   - For Apple: Verify private key and team ID are correct
   - For Facebook: Ensure access token is valid and not expired

### Debug Mode

Enable debug logging in Django settings:
```python
LOGGING = {
    'loggers': {
        'users.social_auth': {
            'level': 'DEBUG',
            'handlers': ['console'],
        }
    }
}
```

## Production Considerations

### Environment Variables
- Store all secrets in secure environment variable management
- Use different OAuth apps for development/staging/production
- Enable HTTPS for all OAuth redirect URIs

### Security Headers
```python
# Additional security for production
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### Rate Limiting
The social auth endpoint includes rate limiting to prevent abuse:
```python
# 5 requests per minute for social auth
RATELIMIT_ENABLE = True
```

## Support

For issues with social authentication:
1. Check Django logs for backend errors
2. Check browser console for frontend errors
3. Verify OAuth provider configuration
4. Test with different providers to isolate issues