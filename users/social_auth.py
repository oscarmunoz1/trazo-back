from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.db import transaction
import requests
import jwt
from jwt import PyJWKClient
import json
from datetime import datetime
import logging

from .serializers import BasicUserSerializer

User = get_user_model()
logger = logging.getLogger(__name__)


class SocialAuthView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Handle social authentication for Google, Facebook, and Apple
        """
        provider = request.data.get('provider')
        access_token = request.data.get('access_token')
        id_token = request.data.get('id_token')  # For Apple Sign In
        user_type = request.data.get('user_type', 4)  # Default to producer
        
        if not provider:
            return Response(
                {'error': 'Provider is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if provider == 'google':
            # Google can send either access_token or id_token
            token = access_token or id_token
            return self.handle_google_auth(token, user_type)
        elif provider == 'facebook':
            return self.handle_facebook_auth(access_token, user_type)
        elif provider == 'apple':
            return self.handle_apple_auth(id_token, request.data, user_type)
        else:
            return Response(
                {'error': 'Invalid provider'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def handle_google_auth(self, access_token, user_type):
        """
        Verify Google access token/ID token and create/login user
        """
        if not access_token:
            return Response(
                {'error': 'Access token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # First try to verify as an ID token (JWT)
            try:
                import jwt
                from jwt import PyJWKClient
                
                # Get Google's public keys
                jwks_client = PyJWKClient('https://www.googleapis.com/oauth2/v3/certs')
                signing_key = jwks_client.get_signing_key_from_jwt(access_token)
                
                # Decode and verify the token
                decoded_token = jwt.decode(
                    access_token,
                    signing_key.key,
                    algorithms=['RS256'],
                    audience=settings.GOOGLE_CLIENT_ID,
                    issuer='https://accounts.google.com'
                )
                
                # Extract user info from ID token
                email = decoded_token.get('email')
                first_name = decoded_token.get('given_name', '')
                last_name = decoded_token.get('family_name', '')
                google_id = decoded_token.get('sub')
                
            except jwt.exceptions.InvalidTokenError:
                # If ID token verification fails, try as access token
                response = requests.get(
                    'https://www.googleapis.com/oauth2/v1/userinfo',
                    headers={'Authorization': f'Bearer {access_token}'}
                )
                
                if response.status_code != 200:
                    return Response(
                        {'error': 'Invalid access token'},
                        status=status.HTTP_401_UNAUTHORIZED
                    )
                
                user_data = response.json()
                email = user_data.get('email')
                first_name = user_data.get('given_name', '')
                last_name = user_data.get('family_name', '')
                google_id = user_data.get('id')
            
            if not email:
                return Response(
                    {'error': 'Email not provided by Google'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create or update user
            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'is_verified': True,  # Social auth users are pre-verified
                        'user_type': user_type,
                        'social_auth_provider': 'google',
                        'social_auth_id': google_id
                    }
                )
                
                if not created:
                    # Update existing user's social auth info
                    user.social_auth_provider = 'google'
                    user.social_auth_id = google_id
                    if not user.first_name:
                        user.first_name = first_name
                    if not user.last_name:
                        user.last_name = last_name
                    user.save()
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'user': BasicUserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user_type': user.user_type
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Google auth error: {str(e)}")
            return Response(
                {'error': 'Authentication failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def handle_facebook_auth(self, access_token, user_type):
        """
        Verify Facebook access token and create/login user
        """
        if not access_token:
            return Response(
                {'error': 'Access token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Verify token with Facebook
            response = requests.get(
                'https://graph.facebook.com/me',
                params={
                    'fields': 'id,email,first_name,last_name',
                    'access_token': access_token
                }
            )
            
            if response.status_code != 200:
                return Response(
                    {'error': 'Invalid access token'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            user_data = response.json()
            email = user_data.get('email')
            first_name = user_data.get('first_name', '')
            last_name = user_data.get('last_name', '')
            facebook_id = user_data.get('id')
            
            if not email:
                # Facebook might not provide email, generate a placeholder
                email = f"fb_{facebook_id}@trazo.placeholder"
            
            # Create or update user
            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'is_verified': True,
                        'user_type': user_type,
                        'social_auth_provider': 'facebook',
                        'social_auth_id': facebook_id
                    }
                )
                
                if not created:
                    # Update existing user's social auth info
                    user.social_auth_provider = 'facebook'
                    user.social_auth_id = facebook_id
                    if not user.first_name:
                        user.first_name = first_name
                    if not user.last_name:
                        user.last_name = last_name
                    user.save()
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'user': BasicUserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user_type': user.user_type
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Facebook auth error: {str(e)}")
            return Response(
                {'error': 'Authentication failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def handle_apple_auth(self, id_token, request_data, user_type):
        """
        Verify Apple ID token and create/login user
        """
        if not id_token:
            return Response(
                {'error': 'ID token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Apple's public key URL
            jwks_client = PyJWKClient('https://appleid.apple.com/auth/keys')
            
            # Decode and verify the token
            signing_key = jwks_client.get_signing_key_from_jwt(id_token)
            data = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=['RS256'],
                audience=settings.APPLE_CLIENT_ID,
                issuer='https://appleid.apple.com'
            )
            
            # Extract user info
            email = data.get('email')
            apple_id = data.get('sub')
            
            # Apple provides name only on first sign-in
            user_info = request_data.get('user', {})
            first_name = ''
            last_name = ''
            
            if user_info:
                name_parts = user_info.get('name', {})
                first_name = name_parts.get('firstName', '')
                last_name = name_parts.get('lastName', '')
            
            if not email:
                # Apple might hide email, use relay email
                email = f"apple_{apple_id}@privaterelay.appleid.com"
            
            # Create or update user
            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'is_verified': True,
                        'user_type': user_type,
                        'social_auth_provider': 'apple',
                        'social_auth_id': apple_id
                    }
                )
                
                if not created:
                    # Update existing user's social auth info
                    user.social_auth_provider = 'apple'
                    user.social_auth_id = apple_id
                    # Only update name if provided (Apple only sends it once)
                    if first_name and not user.first_name:
                        user.first_name = first_name
                    if last_name and not user.last_name:
                        user.last_name = last_name
                    user.save()
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'user': BasicUserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user_type': user.user_type
            }, status=status.HTTP_200_OK)
            
        except jwt.exceptions.InvalidTokenError as e:
            logger.error(f"Apple auth token error: {str(e)}")
            return Response(
                {'error': 'Invalid ID token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.error(f"Apple auth error: {str(e)}")
            return Response(
                {'error': 'Authentication failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )