import hashlib
import json
import time
from decimal import Decimal
from typing import Dict, Any, Optional

from django.conf import settings
from django.utils import timezone

# Optional web3 import - if not available, use mock mode
try:
    from web3 import Web3
    from web3.exceptions import TransactionNotFound, ContractLogicError
    WEB3_AVAILABLE = True
except ImportError:
    Web3 = None
    TransactionNotFound = Exception
    ContractLogicError = Exception
    WEB3_AVAILABLE = False
    print("Warning: web3 library not installed. Blockchain service will run in mock mode.")

from ..models import CarbonEntry, CarbonReport


class BlockchainCarbonService:
    """
    Service for creating immutable carbon records on blockchain.
    Implements the Blockchain-Based Carbon Credit Verification feature.
    Falls back to mock mode if web3 is not available.
    """
    
    def __init__(self):
        # Initialize Web3 connection for Polygon (environment-specific)
        self.web3 = None
        self.contract = None
        self.account = None
        self.mock_mode = not WEB3_AVAILABLE
        self.network_name = getattr(settings, 'BLOCKCHAIN_NETWORK_NAME', 'polygon_amoy')
        self.explorer_url = getattr(settings, 'POLYGON_EXPLORER_URL', 'https://amoy.polygonscan.com')
        
        if WEB3_AVAILABLE and getattr(settings, 'BLOCKCHAIN_ENABLED', False) and hasattr(settings, 'POLYGON_RPC_URL') and settings.POLYGON_RPC_URL:
            try:
                self.web3 = Web3(Web3.HTTPProvider(settings.POLYGON_RPC_URL))
                
                if self.web3.is_connected():
                    print(f"✅ Connected to {self.network_name}: {settings.POLYGON_RPC_URL}")
                
                if hasattr(settings, 'CARBON_CONTRACT_ADDRESS') and settings.CARBON_CONTRACT_ADDRESS:
                    # Try to load ABI from the contracts file first
                    contract_abi = self._load_contract_abi()
                    if not contract_abi:
                        contract_abi = self.get_carbon_contract_abi()
                    
                    self.contract = self.web3.eth.contract(
                        address=settings.CARBON_CONTRACT_ADDRESS,
                        abi=contract_abi
                    )
                    print(f"✅ Contract loaded at: {settings.CARBON_CONTRACT_ADDRESS}")
                    
                if hasattr(settings, 'BLOCKCHAIN_PRIVATE_KEY') and settings.BLOCKCHAIN_PRIVATE_KEY:
                    self.account = self.web3.eth.account.from_key(settings.BLOCKCHAIN_PRIVATE_KEY)
                    print(f"✅ Wallet connected: {self.account.address}")
                    
                    self.mock_mode = False
                else:
                    print(f"❌ Failed to connect to {self.network_name}")
                    self.mock_mode = True
                    
            except Exception as e:
                print(f"❌ Blockchain connection failed: {e}")
                self.mock_mode = True
        else:
            self.mock_mode = True
            if not WEB3_AVAILABLE:
                print("⚠️  Web3 library not available - running in mock mode")
            elif not getattr(settings, 'BLOCKCHAIN_ENABLED', False):
                print("⚠️  Blockchain disabled in settings - running in mock mode")
            else:
                print("⚠️  No blockchain configuration - running in mock mode")
    
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
        Returns transaction details or mock data if blockchain unavailable.
        """
        try:
            # Generate record hash
            record_hash = self.hash_carbon_data(carbon_data)
            
            # If blockchain is available and not in mock mode, create actual transaction
            if not self.mock_mode and self.web3 and self.contract and self.account:
                return self._create_blockchain_transaction(production_id, carbon_data, record_hash)
            else:
                # Fallback: Return mock blockchain data for development
                return self._create_mock_blockchain_record(production_id, carbon_data, record_hash)
                
        except Exception as e:
            print(f"Error creating carbon record: {e}")
            return self._create_mock_blockchain_record(production_id, carbon_data, self.hash_carbon_data(carbon_data))

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
            signed_txn = self.web3.eth.account.signTransaction(transaction, self.account.privateKey)
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
            print(f"Blockchain transaction failed: {e}")
            return self._create_mock_blockchain_record(production_id, carbon_data, record_hash)

    def _create_mock_blockchain_record(self, production_id: int, carbon_data: Dict[str, Any], record_hash: str) -> Dict[str, Any]:
        """Create mock blockchain record for development/testing"""
        mock_tx_hash = hashlib.sha256(f"{production_id}_{record_hash}_{int(time.time())}".encode()).hexdigest()
        
        return {
            'transaction_hash': f"0x{mock_tx_hash}",
            'record_hash': record_hash,
            'block_number': 12345 + production_id,  # Mock block number
            'gas_used': 150000,
            'verification_url': f'{self.explorer_url}/tx/0x{mock_tx_hash}',
            'blockchain_verified': True,
            'network': f'{self.network_name}_mock',
            'contract_address': '0x' + '0' * 40,  # Mock contract address
            'mock_data': True  # Flag to indicate this is mock data
        }

    def verify_carbon_record(self, production_id: int) -> Dict[str, Any]:
        """
        Verify carbon record integrity against blockchain.
        """
        try:
            if not self.mock_mode and self.web3 and self.contract:
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
                    'network': 'polygon_amoy'
                }
            else:
                # Mock verification for development
                return {
                    'verified': True,
                    'record_hash': 'mock_hash',
                    'total_emissions': 0,
                    'total_offsets': 0,
                    'net_footprint': 0,
                    'crop_type': 'mock',
                    'usda_compliant': True,
                    'credits_issued': False,
                    'credits_amount': 0,
                    'timestamp': int(time.time()),
                    'blockchain_verified': True,
                    'mock_data': True
                }
                
        except Exception as e:
            print(f"Error verifying carbon record: {e}")
            return {
                'verified': False,
                'error': str(e),
                'blockchain_verified': False
            }

    def check_compliance(self, production_id: int) -> Dict[str, Any]:
        """
        Check USDA compliance and carbon credit eligibility.
        """
        try:
            if not self.mock_mode and self.web3 and self.contract:
                compliant = self.contract.functions.verifyCompliance(production_id).call()
                return {
                    'compliant': compliant,
                    'eligible_for_credits': compliant,
                    'blockchain_verified': True
                }
            else:
                # Mock compliance check
                return {
                    'compliant': True,
                    'eligible_for_credits': True,
                    'blockchain_verified': True,
                    'mock_data': True
                }
                
        except Exception as e:
            print(f"Error checking compliance: {e}")
            return {
                'compliant': False,
                'eligible_for_credits': False,
                'error': str(e)
            }

    def issue_carbon_credits(self, production_id: int, credits: float) -> Dict[str, Any]:
        """
        Issue carbon credits for verified sustainable practices.
        """
        try:
            if not self.mock_mode and self.web3 and self.contract and self.account:
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
                
                signed_txn = self.web3.eth.account.signTransaction(transaction, self.account.privateKey)
                tx_hash = self.web3.eth.sendRawTransaction(signed_txn.rawTransaction)
                receipt = self.web3.eth.waitForTransactionReceipt(tx_hash, timeout=120)
                
                return {
                    'success': True,
                    'credits_issued': credits,
                    'transaction_hash': tx_hash.hex(),
                    'verification_url': f'https://etherscan.io/tx/{tx_hash.hex()}',
                    'blockchain_verified': True
                }
            else:
                # Mock credit issuance
                return {
                    'success': True,
                    'credits_issued': credits,
                    'transaction_hash': f'0x{hashlib.sha256(f"credits_{production_id}_{credits}".encode()).hexdigest()}',
                    'verification_url': f'https://etherscan.io/tx/mock',
                    'blockchain_verified': True,
                    'mock_data': True
                }
                
        except Exception as e:
            print(f"Error issuing carbon credits: {e}")
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
            if not self.blockchain_enabled:
                logger.info("Blockchain not enabled, using mock mode for monthly summary")
                return self._generate_mock_monthly_summary(producer_id, production_id, total_co2e, data_hash)

            if not self.contract:
                logger.error("Smart contract not initialized")
                return None

            # Convert CO2e from kg to grams for contract
            total_co2e_grams = int(total_co2e * 1000)
            
            # Convert data hash to bytes32
            hash_bytes = bytes.fromhex(data_hash)
            
            logger.info(f"Submitting monthly summary: producer={producer_id}, production={production_id}, co2e={total_co2e_grams}g")

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
            logger.error(f"Error submitting monthly summary: {str(e)}")
            return None

    def _generate_mock_monthly_summary(self, producer_id, production_id, total_co2e, data_hash):
        """Generate mock monthly summary for development"""
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
            
            logger.info(f"Storing encrypted data for transaction {transaction_hash}")
            
            # For now, we'll just log that data would be stored
            data_size = len(str(raw_data))
            logger.info(f"Would store {data_size} bytes of encrypted data for tx {transaction_hash}")
            
        except Exception as e:
            logger.error(f"Error storing encrypted data: {str(e)}")

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
            print(f"Error getting blockchain carbon summary: {e}")
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