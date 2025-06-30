"""
Secure Key Management Service for Trazo
Implements AWS KMS and Secrets Manager integration for secure blockchain and API key management.
Addresses CRITICAL security vulnerabilities found in blockchain and USDA API integrations.
"""

import boto3
import json
import logging
from typing import Dict, Any, Optional, Union
from django.conf import settings
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from botocore.exceptions import ClientError, BotoCoreError
import base64
import time
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os

logger = logging.getLogger(__name__)


class AWSSecurityError(Exception):
    """Raised when AWS security operations fail"""
    pass


class KeyRotationRequiredError(Exception):
    """Raised when key rotation is required"""
    pass


class SecureKeyManager:
    """
    Secure key management using AWS KMS and Secrets Manager.
    Implements encryption, rotation, and secure access patterns for sensitive credentials.
    """
    
    def __init__(self):
        self.aws_region = getattr(settings, 'AWS_DEFAULT_REGION', 'us-east-1')
        self.kms_key_id = getattr(settings, 'AWS_KMS_KEY_ID', None)
        
        # Environment checks - need to be set before AWS client initialization
        # Consider staging as non-production for AWS requirements
        environment = getattr(settings, 'ENVIRONMENT', 'development').lower()
        self.is_production = environment == 'production' and not getattr(settings, 'DEBUG', True)
        self.force_aws_keys = getattr(settings, 'FORCE_AWS_KEY_MANAGEMENT', False)
        
        # Key rotation settings
        self.key_rotation_days = getattr(settings, 'KEY_ROTATION_DAYS', 90)
        self.cache_timeout = getattr(settings, 'KEY_CACHE_TIMEOUT', 300)  # 5 minutes
        
        # Initialize AWS clients with proper error handling
        self._init_aws_clients()
        
        logger.info(f"SecureKeyManager initialized - Production: {self.is_production}, Region: {self.aws_region}")
    
    def _init_aws_clients(self):
        """Initialize AWS clients with proper configuration and error handling"""
        # Check if AWS services are explicitly disabled
        aws_enabled = getattr(settings, 'AWS_SERVICES_ENABLED', True)
        if isinstance(aws_enabled, str):
            aws_enabled = aws_enabled.lower() == 'true'
        
        if not aws_enabled:
            logger.info("AWS services disabled via settings - using local fallbacks")
            self.kms_client = None
            self.secrets_client = None
            return
        
        try:
            # Use IAM roles in production, credentials for development
            session = boto3.Session(region_name=self.aws_region)
            
            self.kms_client = session.client('kms')
            self.secrets_client = session.client('secretsmanager')
            
            # Test connectivity
            self._test_aws_connectivity()
            
            logger.info("✅ AWS clients initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize AWS clients: {e}"
            
            if self.is_production or self.force_aws_keys:
                logger.critical(error_msg)
                raise AWSSecurityError(error_msg)
            else:
                logger.warning(f"{error_msg} - Falling back to development mode")
                self.kms_client = None
                self.secrets_client = None
    
    def _test_aws_connectivity(self):
        """Test AWS connectivity and permissions"""
        try:
            if self.kms_client:
                # Test KMS access
                self.kms_client.list_keys(Limit=1)
                
            if self.secrets_client:
                # Test Secrets Manager access
                self.secrets_client.list_secrets(MaxResults=1)
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['AccessDenied', 'UnauthorizedOperation']:
                raise AWSSecurityError(f"Insufficient AWS permissions: {error_code}")
            else:
                raise AWSSecurityError(f"AWS connectivity test failed: {e}")
    
    def create_kms_key(self, description: str, key_spec: str = 'SYMMETRIC_DEFAULT') -> str:
        """Create a new KMS key for encryption operations"""
        try:
            if not self.kms_client:
                raise AWSSecurityError("KMS client not available")
            
            response = self.kms_client.create_key(
                KeyUsage='ENCRYPT_DECRYPT',
                KeySpec=key_spec,
                Description=description,
                Tags=[
                    {'TagKey': 'Service', 'TagValue': 'Trazo'},
                    {'TagKey': 'Purpose', 'TagValue': 'BlockchainKeyManagement'},
                    {'TagKey': 'Environment', 'TagValue': 'production' if self.is_production else 'development'}
                ]
            )
            
            key_id = response['KeyMetadata']['KeyId']
            logger.info(f"✅ Created KMS key: {key_id}")
            
            return key_id
            
        except Exception as e:
            logger.error(f"Failed to create KMS key: {e}")
            raise AWSSecurityError(f"KMS key creation failed: {e}")
    
    def encrypt_with_kms(self, plaintext: Union[str, bytes], encryption_context: Dict[str, str] = None) -> Dict[str, Any]:
        """Encrypt data using AWS KMS with encryption context for additional security"""
        try:
            if not self.kms_client or not self.kms_key_id:
                return self._encrypt_locally(plaintext)
            
            # Convert string to bytes if necessary
            if isinstance(plaintext, str):
                plaintext_bytes = plaintext.encode('utf-8')
            else:
                plaintext_bytes = plaintext
            
            # Add default encryption context
            context = encryption_context or {}
            context.update({
                'service': 'trazo',
                'timestamp': str(int(time.time())),
                'environment': 'production' if self.is_production else 'development'
            })
            
            response = self.kms_client.encrypt(
                KeyId=self.kms_key_id,
                Plaintext=plaintext_bytes,
                EncryptionContext=context
            )
            
            return {
                'ciphertext': base64.b64encode(response['CiphertextBlob']).decode('utf-8'),
                'encryption_context': context,
                'key_id': response['KeyId'],
                'encrypted_with': 'aws_kms',
                'timestamp': int(time.time())
            }
            
        except Exception as e:
            logger.error(f"KMS encryption failed: {e}")
            if self.is_production:
                raise AWSSecurityError(f"KMS encryption failed: {e}")
            else:
                return self._encrypt_locally(plaintext)
    
    def decrypt_with_kms(self, encrypted_data: Dict[str, Any]) -> str:
        """Decrypt data using AWS KMS with encryption context validation"""
        try:
            if encrypted_data.get('encrypted_with') == 'local':
                return self._decrypt_locally(encrypted_data)
            
            if not self.kms_client:
                raise AWSSecurityError("KMS client not available for decryption")
            
            ciphertext_blob = base64.b64decode(encrypted_data['ciphertext'])
            encryption_context = encrypted_data.get('encryption_context', {})
            
            response = self.kms_client.decrypt(
                CiphertextBlob=ciphertext_blob,
                EncryptionContext=encryption_context
            )
            
            return response['Plaintext'].decode('utf-8')
            
        except Exception as e:
            logger.error(f"KMS decryption failed: {e}")
            raise AWSSecurityError(f"KMS decryption failed: {e}")
    
    def _encrypt_locally(self, plaintext: Union[str, bytes]) -> Dict[str, Any]:
        """Local encryption fallback for development environments"""
        if self.is_production:
            raise AWSSecurityError("Local encryption not allowed in production")
        
        logger.warning("Using local encryption - NOT SUITABLE FOR PRODUCTION")
        
        # Generate key from Django SECRET_KEY
        password = settings.SECRET_KEY.encode()
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        
        fernet = Fernet(key)
        
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')
        
        encrypted = fernet.encrypt(plaintext)
        
        return {
            'ciphertext': base64.b64encode(encrypted).decode('utf-8'),
            'salt': base64.b64encode(salt).decode('utf-8'),
            'encrypted_with': 'local',
            'timestamp': int(time.time()),
            'warning': 'LOCAL ENCRYPTION - NOT SUITABLE FOR PRODUCTION'
        }
    
    def _decrypt_locally(self, encrypted_data: Dict[str, Any]) -> str:
        """Local decryption fallback for development environments"""
        if self.is_production:
            raise AWSSecurityError("Local decryption not allowed in production")
        
        password = settings.SECRET_KEY.encode()
        salt = base64.b64decode(encrypted_data['salt'])
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        
        fernet = Fernet(key)
        encrypted = base64.b64decode(encrypted_data['ciphertext'])
        
        return fernet.decrypt(encrypted).decode('utf-8')
    
    def store_secret(self, secret_name: str, secret_value: Union[str, Dict], description: str = None) -> bool:
        """Store a secret in AWS Secrets Manager with automatic encryption"""
        try:
            if not self.secrets_client:
                return self._store_secret_locally(secret_name, secret_value, description)
            
            # Convert dict to JSON string if necessary
            if isinstance(secret_value, dict):
                secret_string = json.dumps(secret_value)
            else:
                secret_string = secret_value
            
            # Check if secret exists
            try:
                self.secrets_client.describe_secret(SecretId=secret_name)
                # Update existing secret
                self.secrets_client.update_secret(
                    SecretId=secret_name,
                    SecretString=secret_string,
                    Description=description or f"Trazo {secret_name} - Updated {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                logger.info(f"✅ Updated secret: {secret_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    # Create new secret
                    self.secrets_client.create_secret(
                        Name=secret_name,
                        SecretString=secret_string,
                        Description=description or f"Trazo {secret_name}",
                        Tags=[
                            {'Key': 'Service', 'Value': 'Trazo'},
                            {'Key': 'Environment', 'Value': 'production' if self.is_production else 'development'},
                            {'Key': 'CreatedBy', 'Value': 'SecureKeyManager'}
                        ]
                    )
                    logger.info(f"✅ Created secret: {secret_name}")
                else:
                    raise
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to store secret {secret_name}: {e}")
            if self.is_production:
                raise AWSSecurityError(f"Secret storage failed: {e}")
            else:
                return self._store_secret_locally(secret_name, secret_value, description)
    
    def get_secret(self, secret_name: str, use_cache: bool = True) -> Union[str, Dict, None]:
        """Retrieve a secret from AWS Secrets Manager with caching"""
        try:
            # Check cache first
            if use_cache:
                cache_key = f"secure_secret_{secret_name}"
                cached_value = cache.get(cache_key)
                if cached_value:
                    logger.debug(f"✅ Retrieved {secret_name} from cache")
                    return cached_value
            
            if not self.secrets_client:
                return self._get_secret_locally(secret_name)
            
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            secret_value = response['SecretString']
            
            # Try to parse as JSON
            try:
                parsed_value = json.loads(secret_value)
                secret_value = parsed_value
            except json.JSONDecodeError:
                # Keep as string if not valid JSON
                pass
            
            # Cache the secret for a short time
            if use_cache:
                cache.set(f"secure_secret_{secret_name}", secret_value, self.cache_timeout)
            
            logger.debug(f"✅ Retrieved secret: {secret_name}")
            return secret_value
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.warning(f"Secret not found: {secret_name}")
                return None
            else:
                logger.error(f"Failed to retrieve secret {secret_name}: {e}")
                if self.is_production:
                    raise AWSSecurityError(f"Secret retrieval failed: {e}")
                else:
                    return self._get_secret_locally(secret_name)
        
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret {secret_name}: {e}")
            return None
    
    def _store_secret_locally(self, secret_name: str, secret_value: Union[str, Dict], description: str = None) -> bool:
        """Store secret locally for development (NOT SECURE)"""
        if self.is_production:
            raise AWSSecurityError("Local secret storage not allowed in production")
        
        logger.warning(f"Storing secret locally: {secret_name} - NOT SUITABLE FOR PRODUCTION")
        
        # Use Django cache for development
        cache_key = f"dev_secret_{secret_name}"
        cache.set(cache_key, secret_value, timeout=86400)  # 24 hours
        return True
    
    def _get_secret_locally(self, secret_name: str) -> Union[str, Dict, None]:
        """Get secret locally for development (NOT SECURE)"""
        if self.is_production:
            raise AWSSecurityError("Local secret retrieval not allowed in production")
        
        cache_key = f"dev_secret_{secret_name}"
        return cache.get(cache_key)
    
    def rotate_secret(self, secret_name: str, new_value: Union[str, Dict]) -> bool:
        """Rotate a secret with validation and backup"""
        try:
            # Get current secret for backup
            current_secret = self.get_secret(secret_name, use_cache=False)
            
            if current_secret:
                # Store backup
                backup_name = f"{secret_name}_backup_{int(time.time())}"
                self.store_secret(backup_name, current_secret, f"Backup of {secret_name}")
                logger.info(f"✅ Created backup: {backup_name}")
            
            # Store new secret
            success = self.store_secret(secret_name, new_value, f"Rotated on {time.strftime('%Y-%m-%d')}")
            
            if success:
                # Clear cache
                cache.delete(f"secure_secret_{secret_name}")
                logger.info(f"✅ Rotated secret: {secret_name}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Secret rotation failed for {secret_name}: {e}")
            raise AWSSecurityError(f"Secret rotation failed: {e}")
    
    def check_key_rotation_required(self, secret_name: str) -> bool:
        """Check if a secret requires rotation based on age"""
        try:
            if not self.secrets_client:
                return False
            
            response = self.secrets_client.describe_secret(SecretId=secret_name)
            last_changed = response.get('LastChangedDate')
            
            if last_changed:
                days_old = (time.time() - last_changed.timestamp()) / 86400
                return days_old > self.key_rotation_days
            
            return True  # Rotate if we can't determine age
            
        except Exception as e:
            logger.warning(f"Could not check rotation status for {secret_name}: {e}")
            return False
    
    def get_blockchain_private_key(self) -> str:
        """Securely retrieve blockchain private key"""
        try:
            # Try AWS Secrets Manager first
            secret = self.get_secret('trazo/blockchain/private_key')
            
            if secret:
                if isinstance(secret, dict):
                    return secret.get('private_key', '')
                return secret
            
            # Fallback to settings for development
            if not self.is_production and hasattr(settings, 'BLOCKCHAIN_PRIVATE_KEY'):
                logger.warning("Using private key from settings - NOT SECURE FOR PRODUCTION")
                return settings.BLOCKCHAIN_PRIVATE_KEY
            
            raise AWSSecurityError("Blockchain private key not found in secure storage")
            
        except Exception as e:
            logger.error(f"Failed to retrieve blockchain private key: {e}")
            raise AWSSecurityError(f"Blockchain key retrieval failed: {e}")
    
    def get_usda_api_keys(self) -> Dict[str, str]:
        """Securely retrieve USDA API keys"""
        try:
            # Try AWS Secrets Manager first
            secret = self.get_secret('trazo/usda/api_keys')
            
            if secret and isinstance(secret, dict):
                return {
                    'nass_api_key': secret.get('nass_api_key', ''),
                    'ers_api_key': secret.get('ers_api_key', ''),
                    'fooddata_api_key': secret.get('fooddata_api_key', '')
                }
            
            # Fallback to settings for development
            if not self.is_production:
                logger.warning("Using USDA API keys from settings - NOT SECURE FOR PRODUCTION")
                return {
                    'nass_api_key': getattr(settings, 'USDA_NASS_API_KEY', ''),
                    'ers_api_key': getattr(settings, 'USDA_ERS_API_KEY', ''),
                    'fooddata_api_key': getattr(settings, 'USDA_FOODDATA_API_KEY', '')
                }
            
            raise AWSSecurityError("USDA API keys not found in secure storage")
            
        except Exception as e:
            logger.error(f"Failed to retrieve USDA API keys: {e}")
            raise AWSSecurityError(f"USDA API key retrieval failed: {e}")
    
    def setup_initial_secrets(self):
        """Setup initial secrets from environment variables (one-time migration)"""
        try:
            logger.info("🔄 Setting up initial secrets migration...")
            
            # Migrate blockchain private key
            if hasattr(settings, 'BLOCKCHAIN_PRIVATE_KEY') and settings.BLOCKCHAIN_PRIVATE_KEY:
                blockchain_secret = {
                    'private_key': settings.BLOCKCHAIN_PRIVATE_KEY,
                    'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'rotated_from': 'settings_migration'
                }
                
                success = self.store_secret(
                    'trazo/blockchain/private_key',
                    blockchain_secret,
                    'Blockchain private key for Trazo carbon verification'
                )
                
                if success:
                    logger.info("✅ Migrated blockchain private key to secure storage")
                else:
                    logger.error("❌ Failed to migrate blockchain private key")
            
            # Migrate USDA API keys
            usda_keys = {}
            if hasattr(settings, 'USDA_NASS_API_KEY') and settings.USDA_NASS_API_KEY:
                usda_keys['nass_api_key'] = settings.USDA_NASS_API_KEY
            
            if hasattr(settings, 'USDA_ERS_API_KEY') and settings.USDA_ERS_API_KEY:
                usda_keys['ers_api_key'] = settings.USDA_ERS_API_KEY
            
            if hasattr(settings, 'USDA_FOODDATA_API_KEY') and settings.USDA_FOODDATA_API_KEY:
                usda_keys['fooddata_api_key'] = settings.USDA_FOODDATA_API_KEY
            
            if usda_keys:
                usda_keys.update({
                    'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'rotated_from': 'settings_migration'
                })
                
                success = self.store_secret(
                    'trazo/usda/api_keys',
                    usda_keys,
                    'USDA API keys for carbon calculation services'
                )
                
                if success:
                    logger.info("✅ Migrated USDA API keys to secure storage")
                else:
                    logger.error("❌ Failed to migrate USDA API keys")
            
            logger.info("🎉 Initial secrets migration completed")
            return True
            
        except Exception as e:
            logger.error(f"Initial secrets migration failed: {e}")
            return False


# Singleton instance
secure_key_manager = SecureKeyManager()


def get_secure_blockchain_key() -> str:
    """Convenience function to get blockchain private key securely"""
    return secure_key_manager.get_blockchain_private_key()


def get_secure_usda_keys() -> Dict[str, str]:
    """Convenience function to get USDA API keys securely"""
    return secure_key_manager.get_usda_api_keys()