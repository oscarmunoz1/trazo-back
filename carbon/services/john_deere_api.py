"""
John Deere API Integration Service

This service handles integration with John Deere Operations Center API
for real-time equipment data collection and carbon tracking automation.

API Documentation: https://developer.deere.com/
"""

import requests
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from typing import Dict, List, Optional, Any
import json
import base64
from urllib.parse import urlencode, parse_qs, urlparse

logger = logging.getLogger(__name__)


class JohnDeereAPIError(Exception):
    """Custom exception for John Deere API errors"""
    pass


class JohnDeereAPI:
    """
    John Deere Operations Center API integration service.
    
    Handles OAuth 2.0 authentication, machine data fetching,
    and real-time equipment monitoring for carbon tracking.
    """
    
    def __init__(self):
        self.client_id = getattr(settings, 'JOHN_DEERE_CLIENT_ID', None)
        self.client_secret = getattr(settings, 'JOHN_DEERE_CLIENT_SECRET', None)
        self.redirect_uri = getattr(settings, 'JOHN_DEERE_REDIRECT_URI', 'http://localhost:8000/carbon/john-deere/callback/')
        
        # Use sandbox for development, production for live
        self.use_sandbox = getattr(settings, 'JOHN_DEERE_USE_SANDBOX', True)
        
        if self.use_sandbox:
            self.base_url = "https://sandboxapi.deere.com/platform"
            self.auth_url = "https://sandboxapi.deere.com/platform/oauth2/authorize"
            self.token_url = "https://sandboxapi.deere.com/platform/oauth2/token"
        else:
            self.base_url = "https://api.deere.com/platform"
            self.auth_url = "https://api.deere.com/platform/oauth2/authorize"
            self.token_url = "https://api.deere.com/platform/oauth2/token"
        
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/vnd.deere.axiom.v3+json',
            'Content-Type': 'application/json'
        })
        
        if not self.client_id or not self.client_secret:
            logger.warning("John Deere API credentials not configured. Set JOHN_DEERE_CLIENT_ID and JOHN_DEERE_CLIENT_SECRET in settings.")
    
    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate OAuth authorization URL for user consent.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL for redirecting users
        """
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'scope': 'ag1 ag2 ag3',  # Agricultural data scopes
            'redirect_uri': self.redirect_uri,
        }
        
        if state:
            params['state'] = state
            
        return f"{self.auth_url}?{urlencode(params)}"
    
    def exchange_code_for_token(self, authorization_code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            authorization_code: Code received from OAuth callback
            
        Returns:
            Token response with access_token, refresh_token, etc.
        """
        try:
            # Prepare basic auth header
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            data = {
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'redirect_uri': self.redirect_uri,
            }
            
            response = requests.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Cache the token for future use
            cache_key = f"john_deere_token_{self.client_id}"
            cache.set(cache_key, token_data, timeout=token_data.get('expires_in', 3600))
            
            logger.info("Successfully obtained John Deere access token")
            return token_data
            
        except requests.RequestException as e:
            logger.error(f"Failed to exchange authorization code: {e}")
            raise JohnDeereAPIError(f"Token exchange failed: {e}")
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh expired access token using refresh token.
        
        Args:
            refresh_token: Refresh token from previous authentication
            
        Returns:
            New token response
        """
        try:
            credentials = f"{self.client_id}:{self.client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            }
            
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
            }
            
            response = requests.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Update cached token
            cache_key = f"john_deere_token_{self.client_id}"
            cache.set(cache_key, token_data, timeout=token_data.get('expires_in', 3600))
            
            logger.info("Successfully refreshed John Deere access token")
            return token_data
            
        except requests.RequestException as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise JohnDeereAPIError(f"Token refresh failed: {e}")
    
    def get_access_token(self) -> Optional[str]:
        """
        Get valid access token from cache or raise error if not available.
        
        Returns:
            Valid access token or None if not authenticated
        """
        cache_key = f"john_deere_token_{self.client_id}"
        token_data = cache.get(cache_key)
        
        if not token_data:
            logger.warning("No John Deere access token found in cache")
            return None
            
        return token_data.get('access_token')
    
    def _make_authenticated_request(self, endpoint: str, method: str = 'GET', data: Dict = None) -> Dict[str, Any]:
        """
        Make authenticated request to John Deere API.
        
        Args:
            endpoint: API endpoint (relative to base_url)
            method: HTTP method (GET, POST, etc.)
            data: Request payload for POST/PUT requests
            
        Returns:
            API response data
        """
        access_token = self.get_access_token()
        if not access_token:
            raise JohnDeereAPIError("No valid access token available. Please authenticate first.")
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.deere.axiom.v3+json',
        }
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers)
            elif method.upper() == 'POST':
                headers['Content-Type'] = 'application/json'
                response = requests.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"John Deere API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            raise JohnDeereAPIError(f"API request failed: {e}")
    
    def get_organizations(self) -> List[Dict[str, Any]]:
        """
        Get list of organizations (farms) associated with the authenticated user.
        
        Returns:
            List of organization data
        """
        try:
            response = self._make_authenticated_request('/organizations')
            return response.get('values', [])
        except JohnDeereAPIError as e:
            logger.error(f"Failed to fetch organizations: {e}")
            return []
    
    def get_machines(self, organization_id: str = None) -> List[Dict[str, Any]]:
        """
        Get list of machines (equipment) for an organization.
        
        Args:
            organization_id: Specific organization ID, or None for all
            
        Returns:
            List of machine data
        """
        try:
            if organization_id:
                endpoint = f'/organizations/{organization_id}/machines'
            else:
                endpoint = '/machines'
                
            response = self._make_authenticated_request(endpoint)
            return response.get('values', [])
        except JohnDeereAPIError as e:
            logger.error(f"Failed to fetch machines: {e}")
            return []
    
    def get_machine_details(self, machine_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific machine.
        
        Args:
            machine_id: John Deere machine ID
            
        Returns:
            Machine details including model, status, location
        """
        try:
            response = self._make_authenticated_request(f'/machines/{machine_id}')
            return response
        except JohnDeereAPIError as e:
            logger.error(f"Failed to fetch machine details for {machine_id}: {e}")
            return {}
    
    def get_machine_fuel_data(self, machine_id: str, start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Get fuel consumption data for a specific machine.
        
        Args:
            machine_id: John Deere machine ID
            start_date: Start date for data range (defaults to 24 hours ago)
            end_date: End date for data range (defaults to now)
            
        Returns:
            List of fuel consumption records
        """
        if not start_date:
            start_date = timezone.now() - timedelta(hours=24)
        if not end_date:
            end_date = timezone.now()
        
        try:
            # Format dates for API
            start_str = start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            end_str = end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            endpoint = f'/machines/{machine_id}/fuelConsumption'
            params = {
                'startTime': start_str,
                'endTime': end_str
            }
            
            # Add query parameters to endpoint
            endpoint += '?' + urlencode(params)
            
            response = self._make_authenticated_request(endpoint)
            return response.get('values', [])
            
        except JohnDeereAPIError as e:
            logger.error(f"Failed to fetch fuel data for machine {machine_id}: {e}")
            return []
    
    def get_machine_location_data(self, machine_id: str, start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Get location/GPS data for a specific machine.
        
        Args:
            machine_id: John Deere machine ID
            start_date: Start date for data range
            end_date: End date for data range
            
        Returns:
            List of location records with GPS coordinates
        """
        if not start_date:
            start_date = timezone.now() - timedelta(hours=24)
        if not end_date:
            end_date = timezone.now()
        
        try:
            start_str = start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            end_str = end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            endpoint = f'/machines/{machine_id}/locations'
            params = {
                'startTime': start_str,
                'endTime': end_str
            }
            
            endpoint += '?' + urlencode(params)
            
            response = self._make_authenticated_request(endpoint)
            return response.get('values', [])
            
        except JohnDeereAPIError as e:
            logger.error(f"Failed to fetch location data for machine {machine_id}: {e}")
            return []
    
    def get_machine_status(self, machine_id: str) -> Dict[str, Any]:
        """
        Get current status of a machine (online/offline, fuel level, location).
        
        Args:
            machine_id: John Deere machine ID
            
        Returns:
            Machine status data
        """
        try:
            # Get basic machine details
            machine_details = self.get_machine_details(machine_id)
            
            # Get recent fuel data to determine if machine is active
            recent_fuel = self.get_machine_fuel_data(machine_id, 
                                                   start_date=timezone.now() - timedelta(hours=2))
            
            # Get recent location data
            recent_location = self.get_machine_location_data(machine_id,
                                                           start_date=timezone.now() - timedelta(hours=1))
            
            # Determine if machine is active based on recent data
            is_active = len(recent_fuel) > 0 or len(recent_location) > 0
            
            # Get latest location
            latest_location = None
            if recent_location:
                latest_location = recent_location[-1]  # Most recent location
            
            # Calculate fuel level (if available)
            fuel_level = None
            if recent_fuel:
                # This would depend on the actual API response structure
                # For now, we'll estimate based on recent consumption
                fuel_level = 75  # Placeholder - would be calculated from actual data
            
            return {
                'machine_id': machine_id,
                'is_active': is_active,
                'status': 'online' if is_active else 'offline',
                'fuel_level': fuel_level,
                'gps_location': latest_location,
                'last_activity': timezone.now() if is_active else None,
                'machine_details': machine_details
            }
            
        except JohnDeereAPIError as e:
            logger.error(f"Failed to get machine status for {machine_id}: {e}")
            return {
                'machine_id': machine_id,
                'is_active': False,
                'status': 'error',
                'error': str(e)
            }
    
    def process_fuel_consumption_webhook(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming fuel consumption data from John Deere webhook.
        
        Args:
            webhook_data: Raw webhook payload from John Deere
            
        Returns:
            Processed fuel consumption data for carbon calculation
        """
        try:
            # Extract relevant data from webhook payload
            # Note: Actual structure depends on John Deere webhook format
            machine_id = webhook_data.get('machineId')
            fuel_consumed = webhook_data.get('fuelConsumed', 0)  # in liters
            timestamp = webhook_data.get('timestamp')
            location = webhook_data.get('location', {})
            engine_hours = webhook_data.get('engineHours', 0)
            
            # Convert timestamp if needed
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            # Calculate fuel efficiency
            fuel_efficiency = fuel_consumed / max(engine_hours, 0.1) if engine_hours > 0 else 0
            
            # Prepare data for carbon calculation
            processed_data = {
                'device_id': machine_id,
                'fuel_liters': fuel_consumed,
                'engine_hours': engine_hours,
                'fuel_efficiency': fuel_efficiency,
                'equipment_type': 'tractor',  # Could be determined from machine details
                'operation_type': 'field_operations',
                'gps_location': {
                    'lat': location.get('latitude'),
                    'lng': location.get('longitude')
                },
                'timestamp': timestamp.isoformat() if timestamp else timezone.now().isoformat(),
                'source': 'john_deere_api',
                'raw_webhook_data': webhook_data
            }
            
            logger.info(f"Processed fuel consumption data for machine {machine_id}: {fuel_consumed}L")
            return processed_data
            
        except Exception as e:
            logger.error(f"Failed to process fuel consumption webhook: {e}")
            raise JohnDeereAPIError(f"Webhook processing failed: {e}")
    
    def sync_machine_with_iot_device(self, machine_id: str, iot_device) -> bool:
        """
        Sync John Deere machine data with IoT device record.
        
        Args:
            machine_id: John Deere machine ID
            iot_device: IoTDevice model instance
            
        Returns:
            True if sync successful, False otherwise
        """
        try:
            # Get current machine status
            machine_status = self.get_machine_status(machine_id)
            
            if machine_status.get('status') == 'error':
                logger.warning(f"Cannot sync machine {machine_id} due to API error")
                return False
            
            # Update IoT device with real data
            iot_device.john_deere_machine_id = machine_id
            iot_device.status = machine_status.get('status', 'offline')
            iot_device.last_api_sync = timezone.now()
            iot_device.api_connection_status = 'connected' if machine_status.get('is_active') else 'disconnected'
            
            # Update location if available
            location = machine_status.get('gps_location')
            if location:
                iot_device.latitude = location.get('latitude')
                iot_device.longitude = location.get('longitude')
            
            # Update fuel level as battery level (conceptual mapping)
            fuel_level = machine_status.get('fuel_level')
            if fuel_level is not None:
                iot_device.battery_level = fuel_level
            
            # Update last seen time
            if machine_status.get('last_activity'):
                iot_device.last_seen = machine_status['last_activity']
            
            iot_device.save()
            
            logger.info(f"Successfully synced machine {machine_id} with IoT device {iot_device.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync machine {machine_id} with IoT device: {e}")
            return False


# Convenience functions for easy integration

def get_john_deere_api() -> JohnDeereAPI:
    """Get configured John Deere API instance."""
    return JohnDeereAPI()


def is_john_deere_configured() -> bool:
    """Check if John Deere API is properly configured."""
    api = JohnDeereAPI()
    return bool(api.client_id and api.client_secret)


def get_authorization_url(state: str = None) -> str:
    """Get John Deere OAuth authorization URL."""
    api = JohnDeereAPI()
    return api.get_authorization_url(state)


def process_oauth_callback(authorization_code: str) -> Dict[str, Any]:
    """Process OAuth callback and exchange code for token."""
    api = JohnDeereAPI()
    return api.exchange_code_for_token(authorization_code) 