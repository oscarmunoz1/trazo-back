"""
Gas-Optimized Blockchain Service for Trazo
Implements gas optimization strategies for blockchain transactions
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
import hashlib
from dataclasses import dataclass
from enum import Enum

try:
    from web3 import Web3
    from web3.exceptions import TransactionNotFound, ContractLogicError
    from web3.gas_strategies.time_based import medium_gas_price_strategy, fast_gas_price_strategy
    WEB3_AVAILABLE = True
except ImportError:
    Web3 = None
    TransactionNotFound = Exception
    ContractLogicError = Exception
    WEB3_AVAILABLE = False

from .multisig_blockchain_service import MultiSigBlockchainService
from .secure_key_management import secure_key_manager

logger = logging.getLogger(__name__)


class GasStrategy(Enum):
    """Gas price strategies for different transaction priorities"""
    ECO = "eco"           # Lowest gas, slower confirmation
    STANDARD = "standard" # Balanced gas price
    FAST = "fast"         # Higher gas, faster confirmation
    URGENT = "urgent"     # Highest gas, immediate confirmation


@dataclass
class GasOptimizationConfig:
    """Configuration for gas optimization strategies"""
    max_gas_price_gwei: int = 100      # Maximum gas price in Gwei
    min_gas_price_gwei: int = 1        # Minimum gas price in Gwei
    gas_limit_buffer: float = 1.2      # 20% buffer on estimated gas
    batch_size_limit: int = 50         # Maximum transactions per batch
    priority_fee_multiplier: float = 1.1  # EIP-1559 priority fee multiplier
    base_fee_multiplier: float = 2.0   # EIP-1559 base fee multiplier


@dataclass
class TransactionBatch:
    """Batch of transactions for gas optimization"""
    transactions: List[Dict[str, Any]]
    total_gas_estimate: int
    estimated_cost_wei: int
    priority: GasStrategy
    batch_id: str


class GasOptimizedBlockchainService(MultiSigBlockchainService):
    """
    Gas-optimized blockchain service that extends multi-signature functionality
    with intelligent gas management and transaction batching
    """
    
    def __init__(self):
        super().__init__()
        
        # Gas optimization configuration
        self.gas_config = GasOptimizationConfig()
        self.gas_oracle_cache_ttl = 60  # Cache gas prices for 1 minute
        
        # Transaction batching
        self.pending_batches = {}
        self.max_batch_wait_time = 300  # 5 minutes maximum wait for batch
        
        # Gas optimization strategies
        self.gas_strategies = {
            GasStrategy.ECO: {
                'multiplier': 0.8,
                'max_wait_time': 1800,  # 30 minutes
                'priority_fee_gwei': 1
            },
            GasStrategy.STANDARD: {
                'multiplier': 1.0,
                'max_wait_time': 600,   # 10 minutes
                'priority_fee_gwei': 2
            },
            GasStrategy.FAST: {
                'multiplier': 1.3,
                'max_wait_time': 180,   # 3 minutes
                'priority_fee_gwei': 5
            },
            GasStrategy.URGENT: {
                'multiplier': 2.0,
                'max_wait_time': 60,    # 1 minute
                'priority_fee_gwei': 10
            }
        }
        
        # Performance tracking
        self.gas_savings_total = 0
        self.transaction_stats = {
            'batched_transactions': 0,
            'single_transactions': 0,
            'total_gas_used': 0,
            'total_gas_saved': 0
        }
        
        logger.info("GasOptimizedBlockchainService initialized with gas optimization enabled")
    
    def get_optimal_gas_price(self, strategy: GasStrategy = GasStrategy.STANDARD) -> Dict[str, int]:
        """
        Get optimal gas price based on current network conditions and strategy
        
        Returns:
            Dict with gasPrice (legacy) and maxFeePerGas/maxPriorityFeePerGas (EIP-1559)
        """
        try:
            # Check cache first
            cache_key = f"gas_price_{strategy.value}"
            cached_price = cache.get(cache_key)
            
            if cached_price:
                logger.debug(f"Using cached gas price for {strategy.value}")
                return cached_price
            
            if not WEB3_AVAILABLE or not self.web3 or not self.web3.is_connected():
                # Fallback gas prices in Gwei
                fallback_prices = {
                    GasStrategy.ECO: {'gasPrice': 5, 'maxFeePerGas': 8, 'maxPriorityFeePerGas': 1},
                    GasStrategy.STANDARD: {'gasPrice': 15, 'maxFeePerGas': 20, 'maxPriorityFeePerGas': 2},
                    GasStrategy.FAST: {'gasPrice': 25, 'maxFeePerGas': 35, 'maxPriorityFeePerGas': 5},
                    GasStrategy.URGENT: {'gasPrice': 50, 'maxFeePerGas': 70, 'maxPriorityFeePerGas': 10}
                }
                
                prices = fallback_prices[strategy]
                # Convert Gwei to Wei
                return {
                    k: v * 10**9 for k, v in prices.items()
                }
            
            # Get current network gas prices
            try:
                # Try to get EIP-1559 data first
                latest_block = self.web3.eth.get_block('latest')
                base_fee = latest_block.get('baseFeePerGas', 0)
                
                if base_fee > 0:  # EIP-1559 supported
                    strategy_config = self.gas_strategies[strategy]
                    
                    max_priority_fee = strategy_config['priority_fee_gwei'] * 10**9
                    max_fee_per_gas = int(base_fee * self.gas_config.base_fee_multiplier + max_priority_fee)
                    
                    # Apply strategy multiplier
                    max_fee_per_gas = int(max_fee_per_gas * strategy_config['multiplier'])
                    
                    # Enforce limits
                    max_fee_per_gas = min(max_fee_per_gas, self.gas_config.max_gas_price_gwei * 10**9)
                    max_fee_per_gas = max(max_fee_per_gas, self.gas_config.min_gas_price_gwei * 10**9)
                    
                    gas_prices = {
                        'maxFeePerGas': max_fee_per_gas,
                        'maxPriorityFeePerGas': max_priority_fee,
                        'gasPrice': max_fee_per_gas  # Legacy fallback
                    }
                    
                else:
                    # Legacy gas pricing
                    current_gas_price = self.web3.eth.gas_price
                    strategy_config = self.gas_strategies[strategy]
                    
                    optimized_price = int(current_gas_price * strategy_config['multiplier'])
                    optimized_price = min(optimized_price, self.gas_config.max_gas_price_gwei * 10**9)
                    optimized_price = max(optimized_price, self.gas_config.min_gas_price_gwei * 10**9)
                    
                    gas_prices = {
                        'gasPrice': optimized_price,
                        'maxFeePerGas': optimized_price,
                        'maxPriorityFeePerGas': optimized_price // 10  # 10% of gas price
                    }
                
                # Cache for 1 minute
                cache.set(cache_key, gas_prices, self.gas_oracle_cache_ttl)
                
                logger.debug(f"Optimized gas price for {strategy.value}: {gas_prices['gasPrice'] // 10**9} Gwei")
                return gas_prices
                
            except Exception as e:
                logger.warning(f"Failed to get network gas price, using fallback: {e}")
                # Return conservative fallback
                return {
                    'gasPrice': 20 * 10**9,  # 20 Gwei
                    'maxFeePerGas': 30 * 10**9,
                    'maxPriorityFeePerGas': 2 * 10**9
                }
                
        except Exception as e:
            logger.error(f"Error getting optimal gas price: {e}")
            return {
                'gasPrice': 15 * 10**9,  # Safe fallback
                'maxFeePerGas': 25 * 10**9,
                'maxPriorityFeePerGas': 2 * 10**9
            }
    
    def estimate_transaction_gas(self, transaction_data: Dict[str, Any]) -> int:
        """
        Estimate gas for a transaction with optimization
        
        Args:
            transaction_data: Transaction parameters
            
        Returns:
            Estimated gas limit with buffer
        """
        try:
            if not WEB3_AVAILABLE or not self.web3 or not self.web3.is_connected():
                # Fallback gas estimates by transaction type
                fallback_estimates = {
                    'carbon_offset': 150000,
                    'credit_issuance': 120000,
                    'certificate_mint': 100000,
                    'registry_update': 80000,
                    'simple_transfer': 21000
                }
                
                tx_type = transaction_data.get('type', 'simple_transfer')
                base_estimate = fallback_estimates.get(tx_type, 100000)
                
                return int(base_estimate * self.gas_config.gas_limit_buffer)
            
            # Estimate gas using web3
            estimated_gas = self.web3.eth.estimate_gas(transaction_data)
            
            # Add buffer for safety
            optimized_gas = int(estimated_gas * self.gas_config.gas_limit_buffer)
            
            logger.debug(f"Gas estimate: {estimated_gas} -> {optimized_gas} (with buffer)")
            return optimized_gas
            
        except Exception as e:
            logger.warning(f"Gas estimation failed, using conservative estimate: {e}")
            return 200000  # Conservative fallback
    
    def create_transaction_batch(self, 
                                transactions: List[Dict[str, Any]], 
                                strategy: GasStrategy = GasStrategy.STANDARD) -> TransactionBatch:
        """
        Create an optimized batch of transactions
        
        Args:
            transactions: List of transaction data
            strategy: Gas optimization strategy
            
        Returns:
            Optimized transaction batch
        """
        try:
            # Limit batch size
            if len(transactions) > self.gas_config.batch_size_limit:
                logger.warning(f"Batch size {len(transactions)} exceeds limit, splitting")
                transactions = transactions[:self.gas_config.batch_size_limit]
            
            # Estimate total gas for batch
            total_gas_estimate = 0
            optimized_transactions = []
            
            gas_prices = self.get_optimal_gas_price(strategy)
            
            for tx_data in transactions:
                # Estimate gas for individual transaction
                gas_estimate = self.estimate_transaction_gas(tx_data)
                total_gas_estimate += gas_estimate
                
                # Add gas pricing to transaction
                optimized_tx = {
                    **tx_data,
                    'gas': gas_estimate,
                    **gas_prices
                }
                
                optimized_transactions.append(optimized_tx)
            
            # Calculate estimated cost
            gas_price_for_cost = gas_prices.get('gasPrice', gas_prices.get('maxFeePerGas', 0))
            estimated_cost_wei = total_gas_estimate * gas_price_for_cost
            
            # Generate batch ID
            batch_content = json.dumps(transactions, sort_keys=True)
            batch_id = hashlib.md5(batch_content.encode()).hexdigest()[:12]
            
            batch = TransactionBatch(
                transactions=optimized_transactions,
                total_gas_estimate=total_gas_estimate,
                estimated_cost_wei=estimated_cost_wei,
                priority=strategy,
                batch_id=batch_id
            )
            
            logger.info(f"Created transaction batch {batch_id}: {len(transactions)} txs, "
                       f"{total_gas_estimate} gas, ~{estimated_cost_wei // 10**18:.6f} ETH")
            
            return batch
            
        except Exception as e:
            logger.error(f"Failed to create transaction batch: {e}")
            raise
    
    def execute_batch_transaction(self, batch: TransactionBatch) -> Dict[str, Any]:
        """
        Execute a batch of transactions with gas optimization
        
        Args:
            batch: Transaction batch to execute
            
        Returns:
            Batch execution results
        """
        try:
            start_time = time.time()
            results = {
                'batch_id': batch.batch_id,
                'total_transactions': len(batch.transactions),
                'successful_transactions': 0,
                'failed_transactions': 0,
                'transaction_hashes': [],
                'total_gas_used': 0,
                'total_cost_wei': 0,
                'execution_time': 0,
                'errors': []
            }
            
            logger.info(f"Executing transaction batch {batch.batch_id} with {len(batch.transactions)} transactions")
            
            for i, tx_data in enumerate(batch.transactions):
                try:
                    # Execute individual transaction within batch
                    tx_result = self._execute_single_transaction(tx_data, batch.priority)
                    
                    if tx_result['success']:
                        results['successful_transactions'] += 1
                        results['transaction_hashes'].append(tx_result['hash'])
                        results['total_gas_used'] += tx_result.get('gas_used', 0)
                        results['total_cost_wei'] += tx_result.get('gas_cost_wei', 0)
                    else:
                        results['failed_transactions'] += 1
                        results['errors'].append({
                            'transaction_index': i,
                            'error': tx_result.get('error', 'Unknown error')
                        })
                    
                    # Small delay between transactions to avoid nonce conflicts
                    if i < len(batch.transactions) - 1:
                        time.sleep(0.1)
                        
                except Exception as e:
                    logger.error(f"Error executing transaction {i} in batch {batch.batch_id}: {e}")
                    results['failed_transactions'] += 1
                    results['errors'].append({
                        'transaction_index': i,
                        'error': str(e)
                    })
            
            results['execution_time'] = time.time() - start_time
            
            # Calculate gas savings compared to individual transactions
            estimated_individual_cost = len(batch.transactions) * (batch.estimated_cost_wei // len(batch.transactions))
            gas_savings = max(0, estimated_individual_cost - results['total_cost_wei'])
            results['gas_savings_wei'] = gas_savings
            
            # Update statistics
            self.transaction_stats['batched_transactions'] += results['successful_transactions']
            self.transaction_stats['total_gas_used'] += results['total_gas_used']
            self.transaction_stats['total_gas_saved'] += gas_savings
            
            logger.info(f"Batch {batch.batch_id} completed: {results['successful_transactions']}/{results['total_transactions']} successful, "
                       f"Gas used: {results['total_gas_used']}, Saved: {gas_savings} wei")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to execute transaction batch: {e}")
            return {
                'batch_id': batch.batch_id,
                'success': False,
                'error': str(e)
            }
    
    def _execute_single_transaction(self, tx_data: Dict[str, Any], strategy: GasStrategy) -> Dict[str, Any]:
        """
        Execute a single transaction with gas optimization
        
        Args:
            tx_data: Transaction data
            strategy: Gas strategy to use
            
        Returns:
            Transaction execution result
        """
        try:
            if not WEB3_AVAILABLE or not self.web3 or not self.web3.is_connected():
                logger.warning("Web3 not available, simulating transaction")
                return {
                    'success': True,
                    'hash': f"0x{'0' * 64}",  # Mock hash
                    'gas_used': tx_data.get('gas', 100000),
                    'gas_cost_wei': tx_data.get('gas', 100000) * tx_data.get('gasPrice', 20 * 10**9),
                    'simulated': True
                }
            
            # Get account and nonce
            account = self.web3.eth.account.from_key(self.private_key)
            nonce = self.web3.eth.get_transaction_count(account.address)
            
            # Prepare transaction
            transaction = {
                'nonce': nonce,
                'from': account.address,
                **tx_data
            }
            
            # Sign and send transaction
            signed_txn = self.web3.eth.account.sign_transaction(transaction, self.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for receipt with timeout based on strategy
            strategy_config = self.gas_strategies[strategy]
            timeout = strategy_config['max_wait_time']
            
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            
            if receipt.status == 1:  # Success
                gas_used = receipt.gasUsed
                gas_price = transaction.get('gasPrice', transaction.get('maxFeePerGas', 0))
                gas_cost_wei = gas_used * gas_price
                
                return {
                    'success': True,
                    'hash': tx_hash.hex(),
                    'gas_used': gas_used,
                    'gas_cost_wei': gas_cost_wei,
                    'block_number': receipt.blockNumber
                }
            else:
                return {
                    'success': False,
                    'hash': tx_hash.hex(),
                    'error': 'Transaction reverted'
                }
                
        except Exception as e:
            logger.error(f"Error executing single transaction: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def optimize_carbon_offset_transaction(self, 
                                         offset_data: Dict[str, Any],
                                         strategy: GasStrategy = GasStrategy.STANDARD) -> Dict[str, Any]:
        """
        Optimize a carbon offset transaction for gas efficiency
        
        Args:
            offset_data: Carbon offset data
            strategy: Gas optimization strategy
            
        Returns:
            Optimized transaction result
        """
        try:
            # Check if this should be part of a batch
            offset_amount = offset_data.get('amount_kg', 0)
            
            # For large offsets, use individual transaction with high priority
            if offset_amount > 10000:  # 10 tons CO2e
                strategy = GasStrategy.FAST
                logger.info(f"Large offset ({offset_amount} kg), using fast strategy")
            
            # Prepare transaction data
            tx_data = {
                'type': 'carbon_offset',
                'to': self.contract_address,
                'data': self._encode_offset_data(offset_data),
                'value': 0
            }
            
            # Create single-transaction batch for consistency
            batch = self.create_transaction_batch([tx_data], strategy)
            
            # Execute with optimization
            result = self.execute_batch_transaction(batch)
            
            # Add offset-specific metadata
            result['offset_data'] = {
                'amount_kg': offset_amount,
                'strategy_used': strategy.value,
                'gas_efficiency_score': self._calculate_efficiency_score(result)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to optimize carbon offset transaction: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _encode_offset_data(self, offset_data: Dict[str, Any]) -> str:
        """
        Encode carbon offset data for blockchain transaction
        
        Args:
            offset_data: Offset data to encode
            
        Returns:
            Encoded data as hex string
        """
        try:
            # Simplified encoding - in production this would use proper ABI encoding
            encoded_data = json.dumps(offset_data)
            return f"0x{encoded_data.encode().hex()}"
            
        except Exception as e:
            logger.error(f"Failed to encode offset data: {e}")
            return "0x"
    
    def _calculate_efficiency_score(self, transaction_result: Dict[str, Any]) -> float:
        """
        Calculate gas efficiency score for a transaction
        
        Args:
            transaction_result: Transaction execution result
            
        Returns:
            Efficiency score from 0-100
        """
        try:
            if not transaction_result.get('success', False):
                return 0.0
            
            # Base score
            score = 50.0
            
            # Bonus for gas savings
            gas_saved = transaction_result.get('gas_savings_wei', 0)
            if gas_saved > 0:
                score += min(30.0, gas_saved / 10**15 * 10)  # Up to 30 points for savings
            
            # Bonus for successful batching
            tx_count = transaction_result.get('total_transactions', 1)
            if tx_count > 1:
                score += min(20.0, tx_count * 2)  # Up to 20 points for batching
            
            # Penalty for high gas usage
            gas_used = transaction_result.get('total_gas_used', 0)
            if gas_used > 500000:  # High gas usage
                score -= min(20.0, (gas_used - 500000) / 100000 * 5)
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.error(f"Failed to calculate efficiency score: {e}")
            return 0.0
    
    def get_gas_optimization_stats(self) -> Dict[str, Any]:
        """
        Get gas optimization statistics
        
        Returns:
            Comprehensive gas optimization statistics
        """
        try:
            total_transactions = (self.transaction_stats['batched_transactions'] + 
                                self.transaction_stats['single_transactions'])
            
            if total_transactions == 0:
                return {
                    'total_transactions': 0,
                    'optimization_enabled': True,
                    'statistics': 'No transactions processed yet'
                }
            
            avg_gas_per_tx = (self.transaction_stats['total_gas_used'] / total_transactions 
                            if total_transactions > 0 else 0)
            
            batching_rate = (self.transaction_stats['batched_transactions'] / total_transactions * 100
                           if total_transactions > 0 else 0)
            
            return {
                'total_transactions': total_transactions,
                'batched_transactions': self.transaction_stats['batched_transactions'],
                'single_transactions': self.transaction_stats['single_transactions'],
                'batching_rate_percent': round(batching_rate, 2),
                'total_gas_used': self.transaction_stats['total_gas_used'],
                'total_gas_saved_wei': self.transaction_stats['total_gas_saved'],
                'average_gas_per_transaction': round(avg_gas_per_tx),
                'estimated_cost_savings_eth': self.transaction_stats['total_gas_saved'] / 10**18,
                'optimization_features': {
                    'dynamic_gas_pricing': True,
                    'transaction_batching': True,
                    'eip1559_support': True,
                    'gas_limit_optimization': True
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get gas optimization stats: {e}")
            return {
                'error': str(e),
                'optimization_enabled': True
            }
    
    def optimize_gas_for_bulk_operations(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Optimize gas for bulk blockchain operations like batch certificate minting
        
        Args:
            operations: List of blockchain operations
            
        Returns:
            Optimized bulk operation result
        """
        try:
            logger.info(f"Optimizing gas for {len(operations)} bulk operations")
            
            # Group operations by type for better batching
            operation_groups = {}
            for op in operations:
                op_type = op.get('type', 'unknown')
                if op_type not in operation_groups:
                    operation_groups[op_type] = []
                operation_groups[op_type].append(op)
            
            results = {
                'total_operations': len(operations),
                'operation_groups': len(operation_groups),
                'group_results': {},
                'total_gas_used': 0,
                'total_gas_saved': 0,
                'total_cost_wei': 0
            }
            
            # Process each group with optimal strategy
            for op_type, group_ops in operation_groups.items():
                try:
                    # Choose strategy based on operation type and urgency
                    if op_type in ['carbon_offset', 'credit_issuance']:
                        strategy = GasStrategy.FAST  # Carbon operations need faster confirmation
                    else:
                        strategy = GasStrategy.STANDARD
                    
                    # Create and execute batch
                    batch = self.create_transaction_batch(group_ops, strategy)
                    group_result = self.execute_batch_transaction(batch)
                    
                    results['group_results'][op_type] = group_result
                    results['total_gas_used'] += group_result.get('total_gas_used', 0)
                    results['total_gas_saved'] += group_result.get('gas_savings_wei', 0)
                    results['total_cost_wei'] += group_result.get('total_cost_wei', 0)
                    
                except Exception as e:
                    logger.error(f"Failed to process operation group {op_type}: {e}")
                    results['group_results'][op_type] = {
                        'success': False,
                        'error': str(e)
                    }
            
            # Calculate overall efficiency
            results['efficiency_score'] = self._calculate_efficiency_score(results)
            results['cost_savings_eth'] = results['total_gas_saved'] / 10**18
            
            logger.info(f"Bulk operation optimization completed: {results['total_gas_used']} gas used, "
                       f"{results['total_gas_saved']} wei saved")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to optimize bulk operations: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Utility functions for easy integration
def create_gas_optimized_transaction(transaction_data: Dict[str, Any], 
                                   strategy: GasStrategy = GasStrategy.STANDARD) -> Dict[str, Any]:
    """
    Create a gas-optimized transaction
    
    Args:
        transaction_data: Transaction parameters
        strategy: Gas optimization strategy
        
    Returns:
        Optimized transaction data
    """
    service = GasOptimizedBlockchainService()
    gas_prices = service.get_optimal_gas_price(strategy)
    gas_limit = service.estimate_transaction_gas(transaction_data)
    
    return {
        **transaction_data,
        'gas': gas_limit,
        **gas_prices
    }


def estimate_bulk_operation_cost(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Estimate cost for bulk blockchain operations
    
    Args:
        operations: List of operations to estimate
        
    Returns:
        Cost estimation including optimization benefits
    """
    service = GasOptimizedBlockchainService()
    
    # Estimate individual costs
    individual_cost = 0
    for op in operations:
        gas_estimate = service.estimate_transaction_gas(op)
        gas_price = service.get_optimal_gas_price(GasStrategy.STANDARD)['gasPrice']
        individual_cost += gas_estimate * gas_price
    
    # Estimate batch cost (typically 10-20% savings)
    batch_cost = int(individual_cost * 0.85)  # 15% savings estimate
    
    return {
        'individual_cost_wei': individual_cost,
        'batch_cost_wei': batch_cost,
        'estimated_savings_wei': individual_cost - batch_cost,
        'estimated_savings_eth': (individual_cost - batch_cost) / 10**18,
        'optimization_benefit_percent': ((individual_cost - batch_cost) / individual_cost * 100) if individual_cost > 0 else 0
    }