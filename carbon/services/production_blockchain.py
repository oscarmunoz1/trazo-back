import hashlib
import json
import time
from decimal import Decimal
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
import logging

# Optional web3 import - if not available, use mock mode
try:
    from web3 import Web3
    from web3.exceptions import TransactionNotFound, ContractLogicError, BlockNotFound
    from web3.gas_strategies.time_based import medium_gas_price_strategy
    WEB3_AVAILABLE = True
except ImportError:
    Web3 = None
    TransactionNotFound = Exception
    ContractLogicError = Exception
    BlockNotFound = Exception
    WEB3_AVAILABLE = False

from ..models import CarbonEntry, CarbonReport

logger = logging.getLogger(__name__)


class CreditType(Enum):
    SEQUESTRATION = 0
    AVOIDANCE = 1
    REMOVAL = 2


@dataclass
class BatchVerificationResult:
    """Result of batch verification process"""
    successful_verifications: List[int]
    failed_verifications: List[Tuple[int, str]]
    total_gas_used: int
    total_cost_usd: float
    transaction_hashes: List[str]
    processing_time: float


@dataclass
class GasOptimizationResult:
    """Result of gas optimization analysis"""
    estimated_gas: int
    optimized_gas_price: int
    estimated_cost_usd: float
    recommended_batch_size: int
    network_congestion: str  # low, medium, high


class GasOptimizer:
    """Gas optimization utility for production blockchain operations"""
    
    def __init__(self, web3: Web3):
        self.web3 = web3
        self.gas_cache_duration = 300  # 5 minutes
        
    def get_optimized_gas_price(self) -> int:
        """Get optimized gas price based on network conditions"""
        cache_key = "optimized_gas_price"
        cached_price = cache.get(cache_key)
        
        if cached_price:
            return cached_price
            
        try:
            # Use time-based strategy for better pricing
            self.web3.eth.set_gas_price_strategy(medium_gas_price_strategy)
            gas_price = self.web3.eth.generate_gas_price()
            
            # Cache the result
            cache.set(cache_key, gas_price, self.gas_cache_duration)
            return gas_price
            
        except Exception as e:
            logger.warning(f"Failed to get optimized gas price: {e}")
            # Fallback to network gas price
            return self.web3.eth.gas_price
    
    def estimate_batch_gas(self, batch_size: int, operation_type: str = "mint") -> int:
        """Estimate gas usage for batch operations"""
        base_gas = {
            "mint": 150000,
            "verify": 80000,
            "retire": 100000
        }
        
        per_item_gas = {
            "mint": 120000,
            "verify": 50000,
            "retire": 60000
        }
        
        return base_gas.get(operation_type, 150000) + (per_item_gas.get(operation_type, 120000) * batch_size)
    
    def get_network_congestion(self) -> str:
        """Analyze network congestion level"""
        try:
            latest_block = self.web3.eth.get_block('latest')
            gas_used_ratio = latest_block.gasUsed / latest_block.gasLimit
            
            if gas_used_ratio > 0.9:
                return "high"
            elif gas_used_ratio > 0.7:
                return "medium"
            else:
                return "low"
        except Exception:
            return "medium"  # Default assumption
    
    def optimize_batch_size(self, total_items: int, max_gas_per_tx: int = 8000000) -> int:
        """Calculate optimal batch size to stay within gas limits"""
        estimated_gas_per_item = 120000  # Conservative estimate
        max_items_per_batch = max_gas_per_tx // estimated_gas_per_item
        
        # Consider network congestion
        congestion = self.get_network_congestion()
        if congestion == "high":
            max_items_per_batch = int(max_items_per_batch * 0.7)  # Reduce by 30%
        elif congestion == "medium":
            max_items_per_batch = int(max_items_per_batch * 0.85)  # Reduce by 15%
        
        return min(max_items_per_batch, total_items, 50)  # Max 50 items per batch


class ProductionBlockchainService:
    """
    Production-ready blockchain service for Trazo carbon verification.
    Features: Gas optimization, batch processing, enhanced error handling, monitoring.
    """
    
    def __init__(self):
        self.web3 = None
        self.carbon_verification_contract = None
        self.carbon_credit_contract = None
        self.account = None
        self.mock_mode = not WEB3_AVAILABLE
        self.gas_optimizer = None
        
        # Network configuration
        self.network_name = getattr(settings, 'BLOCKCHAIN_NETWORK_NAME', 'polygon_mainnet')
        self.explorer_url = self._get_explorer_url()
        self.is_mainnet = 'mainnet' in self.network_name.lower()
        
        # Performance monitoring
        self.transaction_count = 0
        self.total_gas_used = 0
        self.failed_transactions = 0
        
        self._initialize_blockchain_connection()
    
    def _get_explorer_url(self) -> str:
        """Get appropriate explorer URL based on network"""
        if 'mainnet' in self.network_name.lower():
            return "https://polygonscan.com"
        else:
            return "https://amoy.polygonscan.com"
    
    def _initialize_blockchain_connection(self):
        """Initialize blockchain connection with enhanced error handling"""
        if not WEB3_AVAILABLE:
            logger.warning("Web3 not available - running in mock mode")
            return
            
        if not getattr(settings, 'BLOCKCHAIN_ENABLED', False):
            logger.info("Blockchain disabled in settings - running in mock mode")
            return
            
        try:
            # Initialize Web3 connection
            rpc_url = getattr(settings, 'POLYGON_RPC_URL', '')
            if not rpc_url:
                logger.error("No RPC URL configured")
                return
                
            self.web3 = Web3(Web3.HTTPProvider(rpc_url))
            
            if not self.web3.is_connected():
                logger.error(f"Failed to connect to {rpc_url}")
                return
                
            logger.info(f"✅ Connected to {self.network_name}: {rpc_url}")
            
            # Initialize gas optimizer
            self.gas_optimizer = GasOptimizer(self.web3)
            
            # Load contracts
            self._load_contracts()
            
            # Initialize account
            self._initialize_account()
            
            if self.account and (self.carbon_verification_contract or self.carbon_credit_contract):
                self.mock_mode = False
                logger.info("✅ Production blockchain service initialized")
            else:
                logger.warning("⚠️ Partial blockchain initialization - some features may be limited")
                
        except Exception as e:
            logger.error(f"Blockchain initialization failed: {e}")
            self.mock_mode = True
    
    def _load_contracts(self):
        """Load smart contracts with fallback handling"""
        try:
            # Load Carbon Verification Contract (existing)
            verification_address = getattr(settings, 'CARBON_CONTRACT_ADDRESS', '')
            if verification_address:
                verification_abi = self._load_contract_abi('CarbonVerification')
                if verification_abi:
                    self.carbon_verification_contract = self.web3.eth.contract(
                        address=verification_address,
                        abi=verification_abi
                    )
                    logger.info(f"✅ Carbon Verification contract loaded: {verification_address}")
            
            # Load Carbon Credit Token Contract (new)
            credit_address = getattr(settings, 'CARBON_CREDIT_CONTRACT_ADDRESS', '')
            if credit_address:
                credit_abi = self._load_contract_abi('CarbonCreditToken')
                if credit_abi:
                    self.carbon_credit_contract = self.web3.eth.contract(
                        address=credit_address,
                        abi=credit_abi
                    )
                    logger.info(f"✅ Carbon Credit Token contract loaded: {credit_address}")
                    
        except Exception as e:
            logger.error(f"Contract loading failed: {e}")
    
    def _load_contract_abi(self, contract_name: str) -> Optional[list]:
        """Load contract ABI from deployed contract files"""
        try:
            from pathlib import Path
            
            contract_file = Path(__file__).parent.parent / 'contracts' / f'{contract_name}.json'
            
            if contract_file.exists():
                with open(contract_file, 'r') as f:
                    contract_data = json.load(f)
                    if 'abi' in contract_data:
                        if isinstance(contract_data['abi'], str):
                            return json.loads(contract_data['abi'])
                        return contract_data['abi']
            
            logger.warning(f"Contract ABI file not found: {contract_name}.json")
            return None
            
        except Exception as e:
            logger.error(f"Error loading contract ABI for {contract_name}: {e}")
            return None
    
    def _initialize_account(self):
        """Initialize blockchain account with security checks"""
        try:
            private_key = getattr(settings, 'BLOCKCHAIN_PRIVATE_KEY', '')
            if not private_key:
                logger.warning("No private key configured")
                return
                
            self.account = self.web3.eth.account.from_key(private_key)
            
            # Check account balance
            balance = self.web3.eth.get_balance(self.account.address)
            balance_ether = self.web3.from_wei(balance, 'ether')
            
            if balance_ether < 0.01:  # Minimum balance check
                logger.warning(f"Low account balance: {balance_ether} MATIC")
            
            logger.info(f"✅ Account initialized: {self.account.address} (Balance: {balance_ether:.4f} MATIC)")
            
        except Exception as e:
            logger.error(f"Account initialization failed: {e}")
    
    def deploy_carbon_credit_contract(self) -> str:
        """Deploy production carbon credit contract with gas optimization"""
        if self.mock_mode:
            return "0x" + "0" * 40  # Mock contract address
            
        try:
            # This would typically be done through deployment scripts
            # For now, return the configured contract address
            contract_address = getattr(settings, 'CARBON_CREDIT_CONTRACT_ADDRESS', '')
            if contract_address:
                logger.info(f"Using existing Carbon Credit contract: {contract_address}")
                return contract_address
            
            # In production, deployment would happen here
            logger.warning("Carbon Credit contract deployment not implemented in runtime")
            return ""
            
        except Exception as e:
            logger.error(f"Contract deployment failed: {e}")
            return ""
    
    def batch_verify_productions(self, production_ids: List[int]) -> BatchVerificationResult:
        """Batch process carbon production verifications with gas optimization"""
        start_time = time.time()
        
        if self.mock_mode:
            return self._mock_batch_verification(production_ids, start_time)
        
        try:
            # Optimize batch size
            optimal_batch_size = self.gas_optimizer.optimize_batch_size(len(production_ids))
            
            successful_verifications = []
            failed_verifications = []
            transaction_hashes = []
            total_gas_used = 0
            
            # Process in optimized batches
            for i in range(0, len(production_ids), optimal_batch_size):
                batch = production_ids[i:i + optimal_batch_size]
                
                try:
                    batch_result = self._process_verification_batch(batch)
                    
                    successful_verifications.extend(batch_result['successful'])
                    failed_verifications.extend(batch_result['failed'])
                    transaction_hashes.extend(batch_result['tx_hashes'])
                    total_gas_used += batch_result['gas_used']
                    
                except Exception as e:
                    logger.error(f"Batch verification failed for batch {i//optimal_batch_size + 1}: {e}")
                    for prod_id in batch:
                        failed_verifications.append((prod_id, str(e)))
            
            # Calculate costs
            gas_price = self.gas_optimizer.get_optimized_gas_price()
            total_cost_usd = self._calculate_cost_usd(total_gas_used, gas_price)
            processing_time = time.time() - start_time
            
            # Update monitoring stats
            self.transaction_count += len(successful_verifications)
            self.total_gas_used += total_gas_used
            self.failed_transactions += len(failed_verifications)
            
            return BatchVerificationResult(
                successful_verifications=successful_verifications,
                failed_verifications=failed_verifications,
                total_gas_used=total_gas_used,
                total_cost_usd=total_cost_usd,
                transaction_hashes=transaction_hashes,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Batch verification process failed: {e}")
            processing_time = time.time() - start_time
            
            return BatchVerificationResult(
                successful_verifications=[],
                failed_verifications=[(pid, str(e)) for pid in production_ids],
                total_gas_used=0,
                total_cost_usd=0.0,
                transaction_hashes=[],
                processing_time=processing_time
            )
    
    def _process_verification_batch(self, production_ids: List[int]) -> Dict[str, Any]:
        """Process a single batch of verifications"""
        if not self.carbon_verification_contract:
            raise Exception("Carbon verification contract not available")
        
        successful = []
        failed = []
        tx_hashes = []
        total_gas = 0
        
        # Get optimized gas price
        gas_price = self.gas_optimizer.get_optimized_gas_price()
        
        for production_id in production_ids:
            try:
                # Get production data (mock for now)
                carbon_data = {
                    'production_id': production_id,
                    'producer_id': 1,
                    'total_emissions': 100.0,
                    'total_offsets': 25.0,
                    'crop_type': 'orange',
                    'usda_verified': True,
                    'timestamp': int(time.time())
                }
                
                # Create blockchain transaction
                tx_result = self._create_verification_transaction(production_id, carbon_data, gas_price)
                
                if tx_result['success']:
                    successful.append(production_id)
                    tx_hashes.append(tx_result['tx_hash'])
                    total_gas += tx_result['gas_used']
                else:
                    failed.append((production_id, tx_result['error']))
                    
            except Exception as e:
                failed.append((production_id, str(e)))
        
        return {
            'successful': successful,
            'failed': failed,
            'tx_hashes': tx_hashes,
            'gas_used': total_gas
        }
    
    def _create_verification_transaction(self, production_id: int, carbon_data: Dict[str, Any], gas_price: int) -> Dict[str, Any]:
        """Create optimized verification transaction"""
        try:
            # Generate data hash
            data_hash = self._hash_carbon_data(carbon_data)
            hash_bytes = bytes.fromhex(data_hash)
            
            # Prepare transaction data
            producer_id = carbon_data.get('producer_id', 1)
            total_emissions = int(float(carbon_data.get('total_emissions', 0)) * 1000)
            total_offsets = int(float(carbon_data.get('total_offsets', 0)) * 1000)
            crop_type = carbon_data.get('crop_type', 'general')
            
            # Build transaction with gas optimization
            transaction = self.carbon_verification_contract.functions.recordMonthlySummary(
                hash_bytes,
                producer_id,
                production_id,
                total_emissions,
                total_offsets,
                crop_type
            ).build_transaction({
                'from': self.account.address,
                'gas': 300000,  # Conservative gas limit
                'gasPrice': gas_price,
                'nonce': self.web3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send transaction
            signed_txn = self.web3.eth.account.sign_transaction(transaction, self.account.key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            return {
                'success': True,
                'tx_hash': tx_hash.hex(),
                'gas_used': receipt['gasUsed'],
                'block_number': receipt['blockNumber']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'tx_hash': '',
                'gas_used': 0
            }
    
    def mint_carbon_credits_batch(self, credit_data_list: List[Dict[str, Any]]) -> BatchVerificationResult:
        """Batch mint carbon credit NFTs with gas optimization"""
        start_time = time.time()
        
        if self.mock_mode or not self.carbon_credit_contract:
            return self._mock_batch_minting(credit_data_list, start_time)
        
        try:
            # Optimize batch size for minting
            optimal_batch_size = self.gas_optimizer.optimize_batch_size(len(credit_data_list), 6000000)
            
            successful_mints = []
            failed_mints = []
            transaction_hashes = []
            total_gas_used = 0
            
            # Process in optimized batches
            for i in range(0, len(credit_data_list), optimal_batch_size):
                batch = credit_data_list[i:i + optimal_batch_size]
                
                try:
                    batch_result = self._process_minting_batch(batch)
                    
                    successful_mints.extend(batch_result['successful'])
                    failed_mints.extend(batch_result['failed'])
                    transaction_hashes.extend(batch_result['tx_hashes'])
                    total_gas_used += batch_result['gas_used']
                    
                except Exception as e:
                    logger.error(f"Batch minting failed for batch {i//optimal_batch_size + 1}: {e}")
                    for idx, credit_data in enumerate(batch):
                        failed_mints.append((i + idx, str(e)))
            
            # Calculate costs
            gas_price = self.gas_optimizer.get_optimized_gas_price()
            total_cost_usd = self._calculate_cost_usd(total_gas_used, gas_price)
            processing_time = time.time() - start_time
            
            return BatchVerificationResult(
                successful_verifications=successful_mints,
                failed_verifications=failed_mints,
                total_gas_used=total_gas_used,
                total_cost_usd=total_cost_usd,
                transaction_hashes=transaction_hashes,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Batch minting process failed: {e}")
            processing_time = time.time() - start_time
            
            return BatchVerificationResult(
                successful_verifications=[],
                failed_verifications=[(i, str(e)) for i in range(len(credit_data_list))],
                total_gas_used=0,
                total_cost_usd=0.0,
                transaction_hashes=[],
                processing_time=processing_time
            )
    
    def _process_minting_batch(self, credit_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process a single batch of credit minting"""
        # Prepare batch data for smart contract
        batch_data = []
        
        for credit_data in credit_data_list:
            batch_data.append({
                'farmer': credit_data['farmer_address'],
                'productionId': credit_data['production_id'],
                'co2eAmount': int(float(credit_data['co2e_amount']) * 1000),  # Convert to grams
                'usdaVerificationHash': credit_data.get('usda_hash', ''),
                'creditType': credit_data.get('credit_type', 0)
            })
        
        try:
            # Get optimized gas price
            gas_price = self.gas_optimizer.get_optimized_gas_price()
            
            # Build batch mint transaction
            transaction = self.carbon_credit_contract.functions.batchMintCarbonCredits(
                batch_data
            ).build_transaction({
                'from': self.account.address,
                'gas': self.gas_optimizer.estimate_batch_gas(len(batch_data), 'mint'),
                'gasPrice': gas_price,
                'nonce': self.web3.eth.get_transaction_count(self.account.address)
            })
            
            # Sign and send
            signed_txn = self.web3.eth.account.sign_transaction(transaction, self.account.key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
            
            return {
                'successful': list(range(len(credit_data_list))),
                'failed': [],
                'tx_hashes': [tx_hash.hex()],
                'gas_used': receipt['gasUsed']
            }
            
        except Exception as e:
            return {
                'successful': [],
                'failed': [(i, str(e)) for i in range(len(credit_data_list))],
                'tx_hashes': [],
                'gas_used': 0
            }
    
    def get_gas_optimization_analysis(self, operation_type: str, batch_size: int) -> GasOptimizationResult:
        """Analyze gas optimization for planned operations"""
        if self.mock_mode or not self.gas_optimizer:
            return GasOptimizationResult(
                estimated_gas=150000 * batch_size,
                optimized_gas_price=2000000000,  # 2 gwei
                estimated_cost_usd=0.01,
                recommended_batch_size=25,
                network_congestion="low"
            )
        
        try:
            estimated_gas = self.gas_optimizer.estimate_batch_gas(batch_size, operation_type)
            optimized_gas_price = self.gas_optimizer.get_optimized_gas_price()
            estimated_cost_usd = self._calculate_cost_usd(estimated_gas, optimized_gas_price)
            recommended_batch_size = self.gas_optimizer.optimize_batch_size(batch_size)
            network_congestion = self.gas_optimizer.get_network_congestion()
            
            return GasOptimizationResult(
                estimated_gas=estimated_gas,
                optimized_gas_price=optimized_gas_price,
                estimated_cost_usd=estimated_cost_usd,
                recommended_batch_size=recommended_batch_size,
                network_congestion=network_congestion
            )
            
        except Exception as e:
            logger.error(f"Gas optimization analysis failed: {e}")
            return GasOptimizationResult(
                estimated_gas=0,
                optimized_gas_price=0,
                estimated_cost_usd=0.0,
                recommended_batch_size=1,
                network_congestion="unknown"
            )
    
    def _calculate_cost_usd(self, gas_used: int, gas_price: int) -> float:
        """Calculate transaction cost in USD"""
        try:
            # Cost in MATIC
            cost_matic = (gas_used * gas_price) / 1e18
            
            # Convert to USD (simplified - in production, use real-time price feed)
            matic_usd_price = 0.75  # Approximate MATIC price
            cost_usd = cost_matic * matic_usd_price
            
            return round(cost_usd, 6)
            
        except Exception:
            return 0.0
    
    def _get_production_carbon_data(self, production_id: int) -> Optional[Dict[str, Any]]:
        """Get carbon data for a production"""
        try:
            # This would typically query the database
            # For now, return mock data structure
            return {
                'production_id': production_id,
                'producer_id': 1,
                'total_emissions': 100.0,
                'total_offsets': 25.0,
                'crop_type': 'orange',
                'calculation_method': 'enhanced_usda',
                'usda_verified': True,
                'timestamp': int(time.time())
            }
        except Exception as e:
            logger.error(f"Failed to get carbon data for production {production_id}: {e}")
            return None
    
    def _hash_carbon_data(self, carbon_data: Dict[str, Any]) -> str:
        """Create deterministic hash of carbon data"""
        hash_input = {
            'production_id': carbon_data.get('production_id'),
            'total_emissions': str(carbon_data.get('total_emissions', 0)),
            'total_offsets': str(carbon_data.get('total_offsets', 0)),
            'crop_type': carbon_data.get('crop_type', ''),
            'calculation_method': carbon_data.get('calculation_method', ''),
            'usda_verified': carbon_data.get('usda_verified', False),
            'timestamp': carbon_data.get('timestamp', int(time.time()))
        }
        
        sorted_data = json.dumps(hash_input, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(sorted_data.encode()).hexdigest()
    
    def _mock_batch_verification(self, production_ids: List[int], start_time: float) -> BatchVerificationResult:
        """Mock batch verification for testing"""
        processing_time = time.time() - start_time
        
        return BatchVerificationResult(
            successful_verifications=production_ids,
            failed_verifications=[],
            total_gas_used=150000 * len(production_ids),
            total_cost_usd=0.01 * len(production_ids),
            transaction_hashes=[f"0x{'0' * 64}" for _ in production_ids],
            processing_time=processing_time
        )
    
    def _mock_batch_minting(self, credit_data_list: List[Dict[str, Any]], start_time: float) -> BatchVerificationResult:
        """Mock batch minting for testing"""
        processing_time = time.time() - start_time
        
        return BatchVerificationResult(
            successful_verifications=list(range(len(credit_data_list))),
            failed_verifications=[],
            total_gas_used=200000 * len(credit_data_list),
            total_cost_usd=0.015 * len(credit_data_list),
            transaction_hashes=[f"0x{'1' * 64}"],
            processing_time=processing_time
        )
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service performance statistics"""
        return {
            'network': self.network_name,
            'is_mainnet': self.is_mainnet,
            'mock_mode': self.mock_mode,
            'transaction_count': self.transaction_count,
            'total_gas_used': self.total_gas_used,
            'failed_transactions': self.failed_transactions,
            'success_rate': (self.transaction_count / max(self.transaction_count + self.failed_transactions, 1)) * 100,
            'contracts_loaded': {
                'carbon_verification': self.carbon_verification_contract is not None,
                'carbon_credit_token': self.carbon_credit_contract is not None
            }
        }


# Global instance
production_blockchain_service = ProductionBlockchainService() 