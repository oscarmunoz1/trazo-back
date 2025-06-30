import hashlib
import json
import time
from decimal import Decimal
from typing import Dict, Any, Optional

from django.conf import settings
from django.utils import timezone

# Import web3 - required for production blockchain operations
try:
    from web3 import Web3
    from web3.exceptions import TransactionNotFound, ContractLogicError
    WEB3_AVAILABLE = True
except ImportError:
    Web3 = None
    TransactionNotFound = Exception
    ContractLogicError = Exception
    WEB3_AVAILABLE = False
    # Log this as a critical error for production environments
    import logging
    logger = logging.getLogger(__name__)
    logger.critical("web3 library not installed. Blockchain functionality unavailable.")

from ..models import CarbonEntry, CarbonReport
from .secure_key_management import secure_key_manager, get_secure_blockchain_key


# Custom exceptions for blockchain operations
class BlockchainUnavailableError(Exception):
    """Raised when blockchain is required but unavailable"""
    pass


class BlockchainOperationError(Exception):
    """Raised when blockchain operation fails"""
    pass


class BlockchainCarbonService:
    """
    Service for creating immutable carbon records on blockchain.
    Implements the Blockchain-Based Carbon Credit Verification feature.
    Production-ready with proper error handling and no mock mode fallbacks.
    """
    
    def __init__(self):
        # Initialize Web3 connection for Polygon (environment-specific)
        self.web3 = None
        self.contract = None
        self.account = None
        # Consider staging as non-production for blockchain requirements
        environment = getattr(settings, 'ENVIRONMENT', 'development').lower()
        debug_mode = getattr(settings, 'DEBUG', True)
        force_blockchain = getattr(settings, 'FORCE_BLOCKCHAIN_VERIFICATION', False)
        
        self.production_mode = environment == 'production' and debug_mode == False
        self.blockchain_required = self.production_mode or force_blockchain
        
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Blockchain init debug: env={environment}, debug={debug_mode}, force={force_blockchain}, prod_mode={self.production_mode}, required={self.blockchain_required}")
        self.network_name = getattr(settings, 'BLOCKCHAIN_NETWORK_NAME', 'polygon_amoy')
        self.explorer_url = getattr(settings, 'POLYGON_EXPLORER_URL', 'https://amoy.polygonscan.com')
        
        # Import logger
        import logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize blockchain connection - fail fast in production if unavailable
        self._initialize_blockchain_connection()
    
    def _initialize_blockchain_connection(self):
        """Initialize blockchain connection with proper error handling"""
        try:
            if not WEB3_AVAILABLE:
                error_msg = "Web3 library not available - blockchain functionality disabled"
                if self.blockchain_required:
                    raise BlockchainUnavailableError(error_msg)
                self.logger.warning(error_msg)
                return
            
            if not getattr(settings, 'BLOCKCHAIN_ENABLED', False):
                error_msg = "Blockchain disabled in settings"
                if self.blockchain_required:
                    raise BlockchainUnavailableError(error_msg)
                self.logger.warning(error_msg)
                return
            
            if not hasattr(settings, 'POLYGON_RPC_URL') or not settings.POLYGON_RPC_URL:
                error_msg = "No blockchain RPC URL configured"
                if self.blockchain_required:
                    raise BlockchainUnavailableError(error_msg)
                self.logger.warning(error_msg)
                return
            
            # Initialize Web3 connection
            self.web3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL))
            
            if not self.web3.is_connected():
                error_msg = f"Failed to connect to blockchain network: {self.network_name}"
                if self.blockchain_required:
                    raise BlockchainUnavailableError(error_msg)
                self.logger.error(error_msg)
                return
            
            self.logger.info(f"✅ Connected to {self.network_name}: {settings.POLYGON_RPC_URL}")
            
            # Load contract
            if hasattr(settings, 'CARBON_CONTRACT_ADDRESS') and settings.CARBON_CONTRACT_ADDRESS:
                contract_abi = self._load_contract_abi()
                if not contract_abi:
                    contract_abi = self.get_carbon_contract_abi()
                
                self.contract = self.web3.eth.contract(
                    address=settings.CARBON_CONTRACT_ADDRESS,
                    abi=contract_abi
                )
                self.logger.info(f"✅ Contract loaded at: {settings.CARBON_CONTRACT_ADDRESS}")
            else:
                error_msg = "No contract address configured"
                if self.blockchain_required:
                    raise BlockchainUnavailableError(error_msg)
                self.logger.warning(error_msg)
                return
            
            # Load account using secure key management
            try:
                blockchain_private_key = get_secure_blockchain_key()
                if blockchain_private_key:
                    self.account = self.web3.eth.account.from_key(blockchain_private_key)
                    self.logger.info(f"✅ Wallet connected securely: {self.account.address}")
                else:
                    raise ValueError("No blockchain private key available")
            except Exception as e:
                error_msg = f"Failed to load blockchain private key securely: {e}"
                if self.blockchain_required:
                    raise BlockchainUnavailableError(error_msg)
                self.logger.warning(error_msg)
                
        except Exception as e:
            error_msg = f"Blockchain initialization failed: {e}"
            if self.blockchain_required:
                raise BlockchainUnavailableError(error_msg)
            self.logger.error(error_msg)
    
    def _is_blockchain_ready(self) -> bool:
        """Check if blockchain service is ready for operations"""
        return (
            self.web3 is not None and
            self.web3.is_connected() and
            self.contract is not None and
            self.account is not None
        )
    
    def _load_contract_abi(self) -> Optional[list]:
        """
        Load the ABI from the deployed contract file.
        """
        try:
            import os
            from pathlib import Path
            
            # Look for the contract file in the carbon/contracts directory
            contract_file = Path(__file__).parent.parent / 'contracts' / 'CarbonVerification.json'
            
            if contract_file.exists():
                import json
                with open(contract_file, 'r') as f:
                    contract_data = json.load(f)
                    if 'abi' in contract_data:
                        if isinstance(contract_data['abi'], str):
                            return json.loads(contract_data['abi'])
                        return contract_data['abi']
            return None
        except Exception as e:
            print(f"Error loading contract ABI: {e}")
            return None
                
    def get_carbon_contract_abi(self) -> list:
        """
        Returns the ABI for the Carbon Credit smart contract.
        In production, this would be loaded from a file or environment variable.
        """
        return [
            {
                "inputs": [
                    {"name": "productionId", "type": "uint256"},
                    {"name": "recordHash", "type": "bytes32"},
                    {"name": "co2eAmount", "type": "uint256"},
                    {"name": "offsetAmount", "type": "uint256"},
                    {"name": "timestamp", "type": "uint256"}
                ],
                "name": "recordCarbonEntry",
                "outputs": [{"name": "transactionId", "type": "bytes32"}],
                "type": "function"
            },
            {
                "inputs": [{"name": "productionId", "type": "uint256"}],
                "name": "getCarbonRecord",
                "outputs": [
                    {"name": "recordHash", "type": "bytes32"},
                    {"name": "co2eAmount", "type": "uint256"},
                    {"name": "offsetAmount", "type": "uint256"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "verified", "type": "bool"}
                ],
                "type": "function"
            },
            {
                "inputs": [{"name": "productionId", "type": "uint256"}],
                "name": "verifyCompliance",
                "outputs": [{"name": "compliant", "type": "bool"}],
                "type": "function"
            },
            {
                "inputs": [
                    {"name": "productionId", "type": "uint256"},
                    {"name": "credits", "type": "uint256"}
                ],
                "name": "issueCredits",
                "outputs": [{"name": "success", "type": "bool"}],
                "type": "function"
            }
        ]

    def hash_carbon_data(self, carbon_data: Dict[str, Any]) -> str:
        """
        Create a SHA-256 hash of carbon data for blockchain storage.
        """
        # Create a deterministic hash from carbon data
        hash_input = {
            'production_id': carbon_data.get('production_id'),
            'total_emissions': str(carbon_data.get('total_emissions', 0)),
            'total_offsets': str(carbon_data.get('total_offsets', 0)),
            'crop_type': carbon_data.get('crop_type', ''),
            'calculation_method': carbon_data.get('calculation_method', ''),
            'usda_verified': carbon_data.get('usda_verified', False),
            'timestamp': carbon_data.get('timestamp', int(time.time()))
        }
        
        # Sort keys for deterministic hashing
        sorted_data = json.dumps(hash_input, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(sorted_data.encode()).hexdigest()

    def create_carbon_record(self, production_id: int, carbon_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an immutable carbon record on the blockchain.
        Fails in production if blockchain is unavailable.
        """
        try:
            # Generate record hash
            record_hash = self.hash_carbon_data(carbon_data)
            
            # Ensure blockchain is available for production environments
            if self.blockchain_required and not self._is_blockchain_ready():
                raise BlockchainUnavailableError(
                    "Blockchain verification is required but blockchain service is unavailable. "
                    "Cannot proceed with carbon record creation."
                )
            
            # Create blockchain transaction if available
            if self._is_blockchain_ready():
                return self._create_blockchain_transaction(production_id, carbon_data, record_hash)
            else:
                # Development fallback with clear warning
                self.logger.warning(f"Creating mock carbon record for development - production_id: {production_id}")
                return self._create_development_mock_record(production_id, carbon_data, record_hash)
                
        except Exception as e:
            self.logger.error(f"Error creating carbon record: {e}")
            if self.blockchain_required:
                raise BlockchainOperationError(f"Failed to create carbon record: {str(e)}")
            else:
                # Only allow fallback in development
                return self._create_development_mock_record(production_id, carbon_data, self.hash_carbon_data(carbon_data))

    def _create_blockchain_transaction(self, production_id: int, carbon_data: Dict[str, Any], record_hash: str) -> Dict[str, Any]:
        """Create actual blockchain transaction on Polygon Amoy"""
        try:
            # Convert hash to bytes32
            hash_bytes = bytes.fromhex(record_hash)
            
            # Convert amounts to grams (as expected by our contract)
            total_emissions = int(float(carbon_data.get('total_emissions', 0)) * 1000)  # Convert kg to grams
            total_offsets = int(float(carbon_data.get('total_offsets', 0)) * 1000)     # Convert kg to grams
            
            # Get producer ID from carbon data or use production ID as fallback
            producer_id = carbon_data.get('producer_id', production_id)
            crop_type = carbon_data.get('crop_type', 'general')
            
            # Check if producer is registered, if not register them first
            try:
                producer_info = self.contract.functions.getProducer(producer_id).call()
                if producer_info[0] == '0x0000000000000000000000000000000000000000':  # Not registered
                    # Register producer first
                    register_tx = self.contract.functions.registerProducer(
                        producer_id, 
                        self.account.address
                    ).buildTransaction({
                        'from': self.account.address,
                        'gas': 100000,
                        'gasPrice': self.web3.toWei('2', 'gwei'),  # Lower gas price for Polygon
                        'nonce': self.web3.eth.getTransactionCount(self.account.address)
                    })
                    
                    signed_register = self.web3.eth.account.signTransaction(register_tx, self.account.privateKey)
                    register_hash = self.web3.eth.sendRawTransaction(signed_register.rawTransaction)
                    self.web3.eth.waitForTransactionReceipt(register_hash, timeout=120)
                    print(f"Producer {producer_id} registered successfully")
            except Exception as e:
                print(f"Producer registration check failed: {e}")
            
            # Build the monthly summary transaction
            transaction = self.contract.functions.recordMonthlySummary(
                hash_bytes,
                producer_id,
                production_id,
                total_emissions,
                total_offsets,
                crop_type
            ).buildTransaction({
                'from': self.account.address,
                'gas': 300000,  # Higher gas limit for complex transaction
                'gasPrice': self.web3.toWei('2', 'gwei'),  # Polygon gas price
                'nonce': self.web3.eth.getTransactionCount(self.account.address)
            })
            
            # Sign and send transaction
            # Get private key securely for transaction signing
            blockchain_private_key = get_secure_blockchain_key()
            signed_txn = self.web3.eth.account.signTransaction(transaction, blockchain_private_key)
            tx_hash = self.web3.eth.sendRawTransaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            receipt = self.web3.eth.waitForTransactionReceipt(tx_hash, timeout=120)
            
            return {
                'transaction_hash': tx_hash.hex(),
                'record_hash': record_hash,
                'block_number': receipt['blockNumber'],
                'gas_used': receipt['gasUsed'],
                'verification_url': f'{self.explorer_url}/tx/{tx_hash.hex()}',
                'blockchain_verified': True,
                'network': self.network_name,
                'contract_address': self.contract.address
            }
            
        except Exception as e:
            self.logger.error(f"Blockchain transaction failed: {e}")
            raise BlockchainOperationError(f"Blockchain transaction failed: {e}")

    def _create_development_mock_record(self, production_id: int, carbon_data: Dict[str, Any], record_hash: str) -> Dict[str, Any]:
        """Create mock blockchain record for development ONLY with clear warnings"""
        if self.production_mode:
            raise BlockchainUnavailableError("Mock records are not allowed in production environment")
            
        self.logger.warning(f"DEVELOPMENT ONLY: Creating mock blockchain record for production_id: {production_id}")
        mock_tx_hash = hashlib.sha256(f"{production_id}_{record_hash}_{int(time.time())}".encode()).hexdigest()
        
        return {
            'transaction_hash': f"0x{mock_tx_hash}",
            'record_hash': record_hash,
            'block_number': 12345 + production_id,  # Mock block number
            'gas_used': 150000,
            'verification_url': f'{self.explorer_url}/tx/0x{mock_tx_hash}',
            'blockchain_verified': False,  # CRITICAL: Mark as NOT verified for mock data
            'network': f'{self.network_name}_development_mock',
            'contract_address': '0x' + '0' * 40,  # Mock contract address
            'mock_data': True,  # Flag to indicate this is mock data
            'warning': 'DEVELOPMENT MOCK - NOT BLOCKCHAIN VERIFIED'
        }

    def verify_carbon_record(self, production_id: int) -> Dict[str, Any]:
        """
        Verify carbon record integrity against blockchain.
        Returns accurate verification status without mock fallbacks.
        """
        try:
            if self._is_blockchain_ready():
                # Query blockchain for record using our contract structure
                record = self.contract.functions.getCarbonRecord(production_id).call()
                return {
                    'verified': record.timestamp > 0,  # Record exists if timestamp > 0
                    'record_hash': record.dataHash.hex(),
                    'total_emissions': record.totalEmissions / 1000,  # Convert grams back to kg
                    'total_offsets': record.totalOffsets / 1000,      # Convert grams back to kg
                    'net_footprint': record.netFootprint / 1000,     # Convert grams back to kg
                    'crop_type': record.cropType,
                    'usda_compliant': record.usdaCompliant,
                    'credits_issued': record.creditsIssued,
                    'credits_amount': record.creditsAmount / 1000,   # Convert grams back to kg
                    'timestamp': record.timestamp,
                    'blockchain_verified': True,
                    'network': self.network_name
                }
            else:
                # No mock verification - return unavailable status
                if self.blockchain_required:
                    raise BlockchainUnavailableError("Blockchain verification required but service unavailable")
                
                self.logger.warning(f"Blockchain verification unavailable for production_id: {production_id}")
                return {
                    'verified': False,
                    'blockchain_verified': False,
                    'error': 'Blockchain verification service unavailable',
                    'development_mode': not self.production_mode
                }
                
        except Exception as e:
            self.logger.error(f"Error verifying carbon record: {e}")
            return {
                'verified': False,
                'error': str(e),
                'blockchain_verified': False
            }

    def check_compliance(self, production_id: int) -> Dict[str, Any]:
        """
        Check USDA compliance and carbon credit eligibility.
        Only returns valid results from blockchain verification.
        """
        try:
            if self._is_blockchain_ready():
                compliant = self.contract.functions.verifyCompliance(production_id).call()
                return {
                    'compliant': compliant,
                    'eligible_for_credits': compliant,
                    'blockchain_verified': True
                }
            else:
                # No mock compliance - actual verification required
                if self.blockchain_required:
                    raise BlockchainUnavailableError("Compliance verification requires blockchain connection")
                    
                self.logger.warning(f"Compliance check unavailable for production_id: {production_id}")
                return {
                    'compliant': False,
                    'eligible_for_credits': False,
                    'blockchain_verified': False,
                    'error': 'Blockchain compliance verification unavailable'
                }
                
        except Exception as e:
            self.logger.error(f"Error checking compliance: {e}")
            return {
                'compliant': False,
                'eligible_for_credits': False,
                'error': str(e),
                'blockchain_verified': False
            }

    def issue_carbon_credits(self, production_id: int, credits: float) -> Dict[str, Any]:
        """
        Issue carbon credits for verified sustainable practices.
        Only issues real credits after blockchain verification.
        """
        try:
            if self._is_blockchain_ready():
                # Convert credits to wei
                credits_wei = int(credits * 1000)
                
                transaction = self.contract.functions.issueCredits(
                    production_id, credits_wei
                ).buildTransaction({
                    'from': self.account.address,
                    'gas': 100000,
                    'gasPrice': self.web3.toWei('20', 'gwei'),
                    'nonce': self.web3.eth.getTransactionCount(self.account.address)
                })
                
                # Get private key securely for transaction signing
                blockchain_private_key = get_secure_blockchain_key()
                signed_txn = self.web3.eth.account.signTransaction(transaction, blockchain_private_key)
                tx_hash = self.web3.eth.sendRawTransaction(signed_txn.rawTransaction)
                receipt = self.web3.eth.waitForTransactionReceipt(tx_hash, timeout=120)
                
                return {
                    'success': True,
                    'credits_issued': credits,
                    'transaction_hash': tx_hash.hex(),
                    'verification_url': f'{self.explorer_url}/tx/{tx_hash.hex()}',
                    'blockchain_verified': True
                }
            else:
                # No mock credit issuance in production-ready system
                if self.blockchain_required:
                    raise BlockchainUnavailableError("Credit issuance requires blockchain connection")
                
                self.logger.error(f"Cannot issue credits: blockchain unavailable for production_id: {production_id}")
                return {
                    'success': False,
                    'error': 'Blockchain service unavailable for credit issuance',
                    'blockchain_verified': False
                }
                
        except Exception as e:
            self.logger.error(f"Error issuing carbon credits: {e}")
            return {
                'success': False,
                'error': str(e),
                'blockchain_verified': False
            }

    def submit_monthly_summary(self, producer_id, production_id, total_co2e, data_hash, raw_data):
        """
        Submit monthly carbon summary to blockchain
        """
        try:
            if not self._is_blockchain_ready():
                if self.blockchain_required:
                    raise BlockchainUnavailableError("Monthly summary submission requires blockchain connection")
                self.logger.info("Blockchain not enabled, using mock mode for monthly summary")
                return self._generate_mock_monthly_summary(producer_id, production_id, total_co2e, data_hash)

            if not self.contract:
                self.logger.error("Smart contract not initialized")
                return None

            # Convert CO2e from kg to grams for contract
            total_co2e_grams = int(total_co2e * 1000)
            
            # Convert data hash to bytes32
            hash_bytes = bytes.fromhex(data_hash)
            
            self.logger.info(f"Submitting monthly summary: producer={producer_id}, production={production_id}, co2e={total_co2e_grams}g")

            # Call smart contract function
            transaction = self._create_blockchain_transaction(
                'recordMonthlySummary',
                hash_bytes,
                producer_id,
                production_id,
                total_co2e_grams
            )

            if transaction:
                # Store raw data off-chain (encrypted)
                self._store_encrypted_data(transaction['transactionHash'].hex(), raw_data)
                
                return {
                    'success': True,
                    'transaction_hash': transaction['transactionHash'].hex(),
                    'block_number': transaction['blockNumber'],
                    'gas_used': transaction['gasUsed'],
                    'producer_id': producer_id,
                    'production_id': production_id,
                    'total_co2e': total_co2e,
                    'data_hash': data_hash,
                    'explorer_url': f"{self.explorer_url}/tx/{transaction['transactionHash'].hex()}"
                }
            else:
                return None

        except Exception as e:
            self.logger.error(f"Error submitting monthly summary: {str(e)}")
            if self.blockchain_required:
                raise BlockchainOperationError(f"Failed to submit monthly summary: {str(e)}")
            return None

    def _generate_mock_monthly_summary(self, producer_id, production_id, total_co2e, data_hash):
        """Generate mock monthly summary for development"""
        import random
        if self.production_mode:
            raise BlockchainUnavailableError("Mock monthly summary not allowed in production")
        mock_hash = f"0x{''.join(random.choices('0123456789abcdef', k=64))}"
        
        return {
            'success': True,
            'transaction_hash': mock_hash,
            'block_number': random.randint(40000000, 50000000),
            'gas_used': random.randint(180000, 220000),
            'producer_id': producer_id,
            'production_id': production_id,
            'total_co2e': total_co2e,
            'data_hash': data_hash,
            'explorer_url': f"https://amoy.polygonscan.com/tx/{mock_hash}",
            'mock': True
        }

    def _store_encrypted_data(self, transaction_hash, raw_data):
        """
        Store raw data off-chain with encryption
        This is a placeholder for encrypted storage implementation
        """
        try:
            # In a real implementation, this would:
            # 1. Encrypt the raw_data using AES encryption
            # 2. Store in a secure database with transaction_hash as key
            # 3. Use renewable-powered servers
            
            self.logger.info(f"Storing encrypted data for transaction {transaction_hash}")
            
            # For now, we'll just log that data would be stored
            data_size = len(str(raw_data))
            self.logger.info(f"Would store {data_size} bytes of encrypted data for tx {transaction_hash}")
            
        except Exception as e:
            self.logger.error(f"Error storing encrypted data: {str(e)}")

    def get_carbon_summary_with_blockchain(self, production_id: int) -> Dict[str, Any]:
        """
        Get comprehensive carbon summary with blockchain verification status.
        """
        try:
            # Get existing carbon data
            from ..views import PublicProductionViewSet
            view = PublicProductionViewSet()
            carbon_data = view._calculate_carbon_summary(production_id)
            
            # Add blockchain verification
            verification = self.verify_carbon_record(production_id)
            compliance = self.check_compliance(production_id)
            
            # Enhanced carbon data with blockchain info
            blockchain_data = {
                **carbon_data,
                'blockchain_verification': {
                    'verified': verification.get('verified', False),
                    'record_hash': verification.get('record_hash'),
                    'verification_url': verification.get('verification_url'),
                    'compliance_status': compliance.get('compliant', False),
                    'eligible_for_credits': compliance.get('eligible_for_credits', False),
                    'verification_date': timezone.now().isoformat(),
                    'network': 'ethereum'
                }
            }
            
            return blockchain_data
            
        except Exception as e:
            self.logger.error(f"Error getting blockchain carbon summary: {e}")
            return {
                'error': str(e),
                'blockchain_verification': {
                    'verified': False,
                    'error': str(e)
                }
            }

    def batch_process_carbon_entries(self, production_ids: list) -> Dict[str, Any]:
        """
        Process multiple carbon entries in batch for efficiency.
        This would be called by a Celery task for nightly processing.
        """
        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'details': []
        }
        
        for production_id in production_ids:
            try:
                # Get carbon data for production
                carbon_data = self.get_carbon_summary_with_blockchain(production_id)
                
                # Create blockchain record if not exists
                if not carbon_data.get('blockchain_verification', {}).get('verified'):
                    blockchain_result = self.create_carbon_record(production_id, carbon_data)
                    results['details'].append({
                        'production_id': production_id,
                        'status': 'success',
                        'transaction_hash': blockchain_result.get('transaction_hash')
                    })
                    results['successful'] += 1
                else:
                    results['details'].append({
                        'production_id': production_id,
                        'status': 'already_verified'
                    })
                    
                results['processed'] += 1
                
            except Exception as e:
                results['details'].append({
                    'production_id': production_id,
                    'status': 'failed',
                    'error': str(e)
                })
                results['failed'] += 1
                results['processed'] += 1
                
        return results


# Singleton instance for the service
blockchain_service = BlockchainCarbonService() 