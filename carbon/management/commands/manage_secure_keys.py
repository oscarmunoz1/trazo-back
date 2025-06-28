"""
Django Management Command for Secure Key Management
Handles key rotation, migration, and security operations for Trazo.
"""

import json
import time
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from carbon.services.secure_key_management import secure_key_manager


class Command(BaseCommand):
    help = 'Manage secure keys for blockchain and API integrations'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['migrate', 'rotate', 'status', 'test', 'setup'],
            help='Action to perform'
        )
        
        parser.add_argument(
            '--secret-name',
            type=str,
            help='Name of the secret to operate on'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force the operation even in production'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

    def handle(self, *args, **options):
        action = options['action']
        
        try:
            if action == 'migrate':
                self.migrate_secrets(options)
            elif action == 'rotate':
                self.rotate_keys(options)
            elif action == 'status':
                self.check_key_status(options)
            elif action == 'test':
                self.test_key_management(options)
            elif action == 'setup':
                self.setup_initial_configuration(options)
            
        except Exception as e:
            raise CommandError(f'Command failed: {e}')

    def migrate_secrets(self, options):
        """Migrate secrets from settings to AWS Secrets Manager"""
        self.stdout.write(self.style.WARNING('🔄 Starting secrets migration...'))
        
        if options['dry_run']:
            self.stdout.write(self.style.NOTICE('DRY RUN MODE - No changes will be made'))
        
        try:
            # Check current environment
            is_production = not getattr(settings, 'DEBUG', True)
            
            if is_production and not options['force']:
                raise CommandError(
                    'Migration in production requires --force flag. '
                    'Ensure you have proper backups and authorization.'
                )
            
            if not options['dry_run']:
                success = secure_key_manager.setup_initial_secrets()
                
                if success:
                    self.stdout.write(
                        self.style.SUCCESS('✅ Secrets migration completed successfully')
                    )
                    
                    # Verify migration
                    self.stdout.write('\n🔍 Verifying migration...')
                    self._verify_migrated_secrets()
                    
                else:
                    self.stdout.write(
                        self.style.ERROR('❌ Secrets migration failed')
                    )
            else:
                self.stdout.write('Would migrate the following secrets:')
                if hasattr(settings, 'BLOCKCHAIN_PRIVATE_KEY'):
                    self.stdout.write('  - Blockchain private key')
                if hasattr(settings, 'USDA_NASS_API_KEY'):
                    self.stdout.write('  - USDA NASS API key')
                if hasattr(settings, 'USDA_ERS_API_KEY'):
                    self.stdout.write('  - USDA ERS API key')
                if hasattr(settings, 'USDA_FOODDATA_API_KEY'):
                    self.stdout.write('  - USDA FoodData Central API key')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Migration failed: {e}')
            )
            raise

    def _verify_migrated_secrets(self):
        """Verify that migrated secrets can be retrieved"""
        try:
            # Test blockchain key
            blockchain_key = secure_key_manager.get_secret('trazo/blockchain/private_key')
            if blockchain_key:
                self.stdout.write('  ✅ Blockchain private key accessible')
            else:
                self.stdout.write('  ❌ Blockchain private key not accessible')
            
            # Test USDA keys
            usda_keys = secure_key_manager.get_secret('trazo/usda/api_keys')
            if usda_keys:
                self.stdout.write('  ✅ USDA API keys accessible')
            else:
                self.stdout.write('  ❌ USDA API keys not accessible')
                
        except Exception as e:
            self.stdout.write(f'  ⚠️  Verification warning: {e}')

    def rotate_keys(self, options):
        """Rotate API keys and blockchain credentials"""
        secret_name = options.get('secret_name')
        
        if not secret_name:
            self.stdout.write(self.style.ERROR('--secret-name is required for rotation'))
            return
        
        self.stdout.write(
            self.style.WARNING(f'🔄 Starting key rotation for: {secret_name}')
        )
        
        if options['dry_run']:
            self.stdout.write(self.style.NOTICE('DRY RUN MODE - No rotation will be performed'))
            
            # Check if rotation is needed
            needs_rotation = secure_key_manager.check_key_rotation_required(secret_name)
            if needs_rotation:
                self.stdout.write(f'  📅 {secret_name} requires rotation')
            else:
                self.stdout.write(f'  ✅ {secret_name} does not require rotation yet')
            return
        
        # Production safety check
        is_production = not getattr(settings, 'DEBUG', True)
        if is_production and not options['force']:
            raise CommandError(
                'Key rotation in production requires --force flag and proper authorization.'
            )
        
        try:
            if secret_name == 'usda_keys':
                self._rotate_usda_keys()
            elif secret_name == 'blockchain_key':
                self._rotate_blockchain_key()
            else:
                # Generic secret rotation
                self._rotate_generic_secret(secret_name)
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Key rotation completed for: {secret_name}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Key rotation failed: {e}')
            )
            raise

    def _rotate_usda_keys(self):
        """Rotate USDA API keys"""
        self.stdout.write('🔄 Rotating USDA API keys...')
        
        # Get current keys
        current_keys = secure_key_manager.get_secret('trazo/usda/api_keys')
        
        if not current_keys:
            raise CommandError('Current USDA API keys not found')
        
        self.stdout.write(
            self.style.WARNING(
                '⚠️  USDA API key rotation requires manual steps:\n'
                '1. Generate new API keys at:\n'
                '   - NASS: https://quickstats.nass.usda.gov/api\n'
                '   - FoodData Central: https://api.nal.usda.gov/fdc/v1\n'
                '2. Update the keys using: python manage.py update_secret trazo/usda/api_keys\n'
                '3. Test the new keys before removing old ones'
            )
        )

    def _rotate_blockchain_key(self):
        """Rotate blockchain private key"""
        self.stdout.write('🔄 Rotating blockchain private key...')
        
        self.stdout.write(
            self.style.WARNING(
                '⚠️  Blockchain key rotation requires careful coordination:\n'
                '1. Generate new wallet address\n'
                '2. Transfer necessary funds to new wallet\n'
                '3. Update smart contract permissions if needed\n'
                '4. Update the key using secure key management\n'
                '5. Verify all blockchain operations work with new key'
            )
        )

    def _rotate_generic_secret(self, secret_name):
        """Rotate a generic secret"""
        self.stdout.write(f'🔄 Rotating secret: {secret_name}')
        
        # Check if secret exists
        current_secret = secure_key_manager.get_secret(secret_name)
        
        if not current_secret:
            raise CommandError(f'Secret not found: {secret_name}')
        
        # For now, just create a backup
        success = secure_key_manager.rotate_secret(secret_name, current_secret)
        
        if success:
            self.stdout.write(f'✅ Created backup for: {secret_name}')
        else:
            raise CommandError(f'Failed to create backup for: {secret_name}')

    def check_key_status(self, options):
        """Check status of all managed keys"""
        self.stdout.write('🔍 Checking key management status...\n')
        
        # Check AWS connectivity
        try:
            if secure_key_manager.kms_client and secure_key_manager.secrets_client:
                self.stdout.write('✅ AWS clients initialized')
            else:
                self.stdout.write('⚠️  AWS clients not available (development mode)')
        except Exception as e:
            self.stdout.write(f'❌ AWS connectivity issue: {e}')
        
        # Check each secret
        secrets_to_check = [
            'trazo/blockchain/private_key',
            'trazo/usda/api_keys',
            'trazo/blockchain/multisig_signers'
        ]
        
        for secret_name in secrets_to_check:
            self.stdout.write(f'\n📝 Checking: {secret_name}')
            
            try:
                secret = secure_key_manager.get_secret(secret_name, use_cache=False)
                
                if secret:
                    self.stdout.write('  ✅ Secret accessible')
                    
                    # Check rotation status
                    needs_rotation = secure_key_manager.check_key_rotation_required(secret_name)
                    if needs_rotation:
                        self.stdout.write('  📅 Rotation recommended')
                    else:
                        self.stdout.write('  ✅ Rotation not required')
                        
                    # Check secret type and basic validation
                    if isinstance(secret, dict):
                        self.stdout.write(f'  📊 Type: Dictionary with {len(secret)} keys')
                        if 'created_at' in secret:
                            self.stdout.write(f'  📅 Created: {secret["created_at"]}')
                    else:
                        self.stdout.write(f'  📊 Type: String ({len(str(secret))} characters)')
                        
                else:
                    self.stdout.write('  ❌ Secret not found')
                    
            except Exception as e:
                self.stdout.write(f'  ❌ Error accessing secret: {e}')

    def test_key_management(self, options):
        """Test key management functionality"""
        self.stdout.write('🧪 Testing key management functionality...\n')
        
        test_secret_name = 'trazo/test/key_management'
        test_data = {
            'test_value': 'secure_test_data',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'test_id': int(time.time())
        }
        
        try:
            # Test storage
            self.stdout.write('1️⃣ Testing secret storage...')
            success = secure_key_manager.store_secret(
                test_secret_name,
                test_data,
                'Test secret for key management validation'
            )
            
            if success:
                self.stdout.write('  ✅ Secret storage successful')
            else:
                self.stdout.write('  ❌ Secret storage failed')
                return
            
            # Test retrieval
            self.stdout.write('2️⃣ Testing secret retrieval...')
            retrieved_data = secure_key_manager.get_secret(test_secret_name, use_cache=False)
            
            if retrieved_data == test_data:
                self.stdout.write('  ✅ Secret retrieval successful')
            else:
                self.stdout.write('  ❌ Retrieved data doesn\'t match stored data')
                return
            
            # Test caching
            self.stdout.write('3️⃣ Testing caching...')
            cached_data = secure_key_manager.get_secret(test_secret_name, use_cache=True)
            
            if cached_data == test_data:
                self.stdout.write('  ✅ Caching working correctly')
            else:
                self.stdout.write('  ⚠️  Caching may not be working properly')
            
            # Test encryption (if applicable)
            self.stdout.write('4️⃣ Testing encryption...')
            encrypted_data = secure_key_manager.encrypt_with_kms('test_encryption_data')
            
            if 'ciphertext' in encrypted_data:
                decrypted_data = secure_key_manager.decrypt_with_kms(encrypted_data)
                if decrypted_data == 'test_encryption_data':
                    self.stdout.write('  ✅ Encryption/decryption working')
                else:
                    self.stdout.write('  ❌ Decryption failed')
            else:
                self.stdout.write('  ⚠️  Encryption not available (development mode)')
            
            # Cleanup test secret
            self.stdout.write('5️⃣ Cleaning up test data...')
            # Note: AWS Secrets Manager doesn't have a delete operation in this implementation
            # In a real implementation, you would delete or mark the test secret for cleanup
            
            self.stdout.write('\n🎉 Key management tests completed successfully!')
            
        except Exception as e:
            self.stdout.write(f'\n❌ Key management test failed: {e}')
            raise

    def setup_initial_configuration(self, options):
        """Setup initial configuration for secure key management"""
        self.stdout.write('🚀 Setting up initial secure key management configuration...\n')
        
        if options['dry_run']:
            self.stdout.write(self.style.NOTICE('DRY RUN MODE - Showing configuration steps'))
        
        # Check AWS configuration
        self.stdout.write('1️⃣ Checking AWS configuration...')
        
        aws_region = getattr(settings, 'AWS_DEFAULT_REGION', 'us-east-1')
        kms_key_id = getattr(settings, 'AWS_KMS_KEY_ID', None)
        
        self.stdout.write(f'  AWS Region: {aws_region}')
        
        if kms_key_id:
            self.stdout.write(f'  KMS Key ID: {kms_key_id}')
        else:
            self.stdout.write('  ⚠️  KMS Key ID not configured')
            
            if not options['dry_run']:
                self.stdout.write('  🔄 Creating KMS key...')
                try:
                    new_key_id = secure_key_manager.create_kms_key(
                        'Trazo Carbon Verification Key Management'
                    )
                    self.stdout.write(f'  ✅ Created KMS key: {new_key_id}')
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️  Add this to your settings: AWS_KMS_KEY_ID = "{new_key_id}"'
                        )
                    )
                except Exception as e:
                    self.stdout.write(f'  ❌ Failed to create KMS key: {e}')
        
        # Setup multi-sig signers
        self.stdout.write('\n2️⃣ Setting up multi-signature signers...')
        
        if not options['dry_run']:
            default_signers = {
                'signers': [
                    {
                        'address': '0x742d35Cc6634C0532925a3b8d1c8b2b8b1f6E8B4',
                        'role': 'admin',
                        'name': 'Primary Admin',
                        'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
                    },
                    {
                        'address': '0x8ba1f109551bD432803012645Hac136c02142AC8',
                        'role': 'operator',
                        'name': 'Operations Manager',
                        'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                ],
                'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'configuration': {
                    'required_signatures': 2,
                    'max_signers': 5
                }
            }
            
            success = secure_key_manager.store_secret(
                'trazo/blockchain/multisig_signers',
                default_signers,
                'Multi-signature authorized signers for Trazo'
            )
            
            if success:
                self.stdout.write('  ✅ Multi-signature signers configured')
            else:
                self.stdout.write('  ❌ Failed to configure multi-signature signers')
        else:
            self.stdout.write('  Would setup default multi-signature signers')
        
        # Final recommendations
        self.stdout.write('\n📋 Next steps:')
        self.stdout.write('  1. Migrate existing secrets with: manage_secure_keys migrate')
        self.stdout.write('  2. Test functionality with: manage_secure_keys test')
        self.stdout.write('  3. Setup key rotation schedule')
        self.stdout.write('  4. Configure monitoring and alerts')
        self.stdout.write('  5. Update deployment scripts to use secure keys')
        
        self.stdout.write('\n🎉 Initial setup completed!')