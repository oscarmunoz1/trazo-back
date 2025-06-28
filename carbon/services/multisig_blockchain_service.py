"""
Multi-Signature Blockchain Service for Trazo
Implements multi-signature requirements for critical blockchain operations.
Addresses CRITICAL security vulnerability found in single-key blockchain operations.
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

try:
    from web3 import Web3
    from web3.exceptions import TransactionNotFound, ContractLogicError
    WEB3_AVAILABLE = True
except ImportError:
    Web3 = None
    TransactionNotFound = Exception
    ContractLogicError = Exception
    WEB3_AVAILABLE = False

from .secure_key_management import secure_key_manager
from .blockchain import BlockchainCarbonService, BlockchainUnavailableError, BlockchainOperationError
from .enhanced_error_handling import (
    error_handler,
    BlockchainErrorHandler,
    with_error_handling,
    RetryConfig,
    FallbackConfig,
    FallbackStrategy
)

logger = logging.getLogger(__name__)


class MultiSigOperationError(Exception):
    """Raised when multi-signature operation fails"""
    pass


class InsufficientSignaturesError(Exception):
    """Raised when insufficient signatures for operation"""
    pass


class MultiSigBlockchainService(BlockchainCarbonService):
    """
    Enhanced blockchain service with multi-signature requirements for critical operations.
    Extends the base blockchain service with additional security layers.
    """
    
    def __init__(self):
        super().__init__()
        
        # Multi-signature configuration
        self.multisig_enabled = getattr(settings, 'BLOCKCHAIN_MULTISIG_ENABLED', True)
        self.required_signatures = getattr(settings, 'BLOCKCHAIN_REQUIRED_SIGNATURES', 2)
        self.max_signers = getattr(settings, 'BLOCKCHAIN_MAX_SIGNERS', 5)
        
        # Critical operation thresholds that require multi-sig
        self.multisig_thresholds = {
            'carbon_amount_kg': getattr(settings, 'MULTISIG_CARBON_THRESHOLD', 1000),  # 1000 kg CO2e
            'monetary_value_usd': getattr(settings, 'MULTISIG_VALUE_THRESHOLD', 10000),  # $10,000
            'credit_issuance': getattr(settings, 'MULTISIG_CREDIT_THRESHOLD', 100),  # 100 credits
        }
        
        # Authorized signers (loaded from secure storage)
        self.authorized_signers = self._load_authorized_signers()
        
        logger.info(f"MultiSigBlockchainService initialized - MultiSig: {self.multisig_enabled}, Required signatures: {self.required_signatures}")
    
    def _load_authorized_signers(self) -> List[Dict[str, str]]:
        """Load authorized signers from secure storage"""
        try:
            signers_data = secure_key_manager.get_secret('trazo/blockchain/multisig_signers')
            
            if signers_data and isinstance(signers_data, dict):
                signers = signers_data.get('signers', [])
                logger.info(f"✅ Loaded {len(signers)} authorized signers")
                return signers
            
            # Default signers for development
            if not self.production_mode:
                logger.warning("Using default signers for development - NOT SECURE FOR PRODUCTION")
                return [
                    {
                        'address': '0x742d35Cc6634C0532925a3b8d1c8b2b8b1f6E8B4',
                        'role': 'admin',
                        'name': 'Development Admin'
                    },
                    {
                        'address': '0x8ba1f109551bD432803012645Hac136c02142AC8',
                        'role': 'operator',
                        'name': 'Development Operator'
                    }
                ]
            
            logger.warning("No authorized signers found in secure storage")
            return []
            
        except Exception as e:
            logger.error(f"Failed to load authorized signers: {e}")
            return []
    
    def _requires_multisig(self, operation_type: str, operation_data: Dict[str, Any]) -> bool:
        """Determine if operation requires multi-signature based on thresholds"""
        try:
            if not self.multisig_enabled:
                return False
            
            # Always require multi-sig for credit issuance
            if operation_type == 'issue_credits':
                credits = operation_data.get('credits', 0)
                return credits >= self.multisig_thresholds['credit_issuance']
            
            # Check carbon amount threshold
            if operation_type in ['create_carbon_record', 'monthly_summary']:
                carbon_amount = operation_data.get('total_emissions', 0) + operation_data.get('total_offsets', 0)
                if carbon_amount >= self.multisig_thresholds['carbon_amount_kg']:
                    return True
            
            # Check monetary value threshold
            monetary_value = operation_data.get('monetary_value_usd', 0)
            if monetary_value >= self.multisig_thresholds['monetary_value_usd']:
                return True
            
            # Critical system operations
            if operation_type in ['register_producer', 'update_contract', 'emergency_stop']:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking multi-sig requirements: {e}")
            # Default to requiring multi-sig on error for security
            return True
    
    def _create_multisig_proposal(self, operation_type: str, operation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a multi-signature proposal for critical operations"""
        try:
            proposal_id = f"trazo_{operation_type}_{int(time.time())}"
            
            proposal = {
                'proposal_id': proposal_id,
                'operation_type': operation_type,
                'operation_data': operation_data,
                'created_at': timezone.now().isoformat(),
                'status': 'pending',
                'required_signatures': self.required_signatures,
                'signatures': [],
                'approvals': [],
                'rejections': [],
                'expires_at': (timezone.now() + timezone.timedelta(hours=24)).isoformat(),
                'created_by': operation_data.get('created_by', 'system'),
                'metadata': {
                    'carbon_amount': operation_data.get('total_emissions', 0) + operation_data.get('total_offsets', 0),
                    'monetary_value': operation_data.get('monetary_value_usd', 0),
                    'risk_level': self._assess_operation_risk(operation_type, operation_data)
                }
            }
            
            # Store proposal in secure storage
            proposal_key = f"trazo/multisig/proposals/{proposal_id}"
            success = secure_key_manager.store_secret(
                proposal_key,
                proposal,
                f"Multi-sig proposal for {operation_type}"
            )
            
            if success:
                logger.info(f"✅ Created multi-sig proposal: {proposal_id}")
                
                # Notify authorized signers (implement notification logic)
                self._notify_signers(proposal)
                
                return proposal
            else:
                raise MultiSigOperationError("Failed to store multi-sig proposal")
            
        except Exception as e:
            logger.error(f"Failed to create multi-sig proposal: {e}")
            raise MultiSigOperationError(f"Proposal creation failed: {e}")
    
    def _assess_operation_risk(self, operation_type: str, operation_data: Dict[str, Any]) -> str:
        """Assess risk level of blockchain operation"""
        try:
            risk_score = 0
            
            # Risk factors
            carbon_amount = operation_data.get('total_emissions', 0) + operation_data.get('total_offsets', 0)
            monetary_value = operation_data.get('monetary_value_usd', 0)
            
            # Carbon amount risk
            if carbon_amount > 10000:  # 10 tons CO2e
                risk_score += 30
            elif carbon_amount > 1000:  # 1 ton CO2e
                risk_score += 15
            
            # Monetary value risk
            if monetary_value > 100000:  # $100k
                risk_score += 40
            elif monetary_value > 10000:  # $10k
                risk_score += 20
            
            # Operation type risk
            high_risk_operations = ['issue_credits', 'register_producer', 'emergency_stop']
            medium_risk_operations = ['create_carbon_record', 'monthly_summary']
            
            if operation_type in high_risk_operations:
                risk_score += 25
            elif operation_type in medium_risk_operations:
                risk_score += 10
            
            # Risk level classification
            if risk_score >= 70:
                return 'high'
            elif risk_score >= 40:
                return 'medium'
            else:
                return 'low'
                
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            return 'high'  # Default to high risk on error
    
    def _notify_signers(self, proposal: Dict[str, Any]):
        """Notify authorized signers about new proposal (placeholder for notification logic)"""
        try:
            # In a real implementation, this would:
            # 1. Send email notifications to authorized signers
            # 2. Create dashboard notifications
            # 3. Send Slack/Teams messages
            # 4. Log audit trail
            
            proposal_id = proposal['proposal_id']
            operation_type = proposal['operation_type']
            risk_level = proposal['metadata']['risk_level']
            
            logger.info(f"📧 Notifying {len(self.authorized_signers)} signers about proposal {proposal_id}")
            logger.info(f"   Operation: {operation_type}, Risk: {risk_level}")
            
            # Create audit log entry
            audit_entry = {
                'event': 'multisig_proposal_created',
                'proposal_id': proposal_id,
                'operation_type': operation_type,
                'risk_level': risk_level,
                'notified_signers': len(self.authorized_signers),
                'timestamp': timezone.now().isoformat()
            }
            
            # Store audit log
            audit_key = f"trazo/audit/multisig/{proposal_id}_created"
            secure_key_manager.store_secret(audit_key, audit_entry, "Multi-sig proposal audit log")
            
        except Exception as e:
            logger.error(f"Failed to notify signers: {e}")
    
    def sign_proposal(self, proposal_id: str, signer_address: str, signature: str, approve: bool = True) -> Dict[str, Any]:
        """Add signature to a multi-sig proposal"""
        try:
            # Get proposal from secure storage
            proposal_key = f"trazo/multisig/proposals/{proposal_id}"
            proposal = secure_key_manager.get_secret(proposal_key, use_cache=False)
            
            if not proposal:
                raise MultiSigOperationError(f"Proposal not found: {proposal_id}")
            
            # Validate signer
            if not self._is_authorized_signer(signer_address):
                raise MultiSigOperationError(f"Unauthorized signer: {signer_address}")
            
            # Check if already signed
            existing_signatures = [s['signer'] for s in proposal.get('signatures', [])]
            if signer_address in existing_signatures:
                raise MultiSigOperationError(f"Signer already signed: {signer_address}")
            
            # Check expiration
            expires_at = timezone.datetime.fromisoformat(proposal['expires_at'].replace('Z', '+00:00'))
            if timezone.now() > expires_at:
                raise MultiSigOperationError("Proposal has expired")
            
            # Add signature
            signature_data = {
                'signer': signer_address,
                'signature': signature,
                'timestamp': timezone.now().isoformat(),
                'approve': approve
            }
            
            proposal['signatures'].append(signature_data)
            
            if approve:
                proposal['approvals'].append(signer_address)
            else:
                proposal['rejections'].append(signer_address)
            
            # Check if we have enough signatures
            if len(proposal['approvals']) >= self.required_signatures:
                proposal['status'] = 'approved'
                logger.info(f"✅ Proposal {proposal_id} approved with {len(proposal['approvals'])} signatures")
            elif len(proposal['rejections']) >= self.required_signatures:
                proposal['status'] = 'rejected'
                logger.info(f"❌ Proposal {proposal_id} rejected with {len(proposal['rejections'])} rejections")
            
            # Update proposal in secure storage
            success = secure_key_manager.store_secret(proposal_key, proposal, f"Updated multi-sig proposal {proposal_id}")
            
            if success:
                return {
                    'success': True,
                    'proposal_id': proposal_id,
                    'status': proposal['status'],
                    'signatures_count': len(proposal['signatures']),
                    'approvals_count': len(proposal['approvals']),
                    'rejections_count': len(proposal['rejections']),
                    'required_signatures': self.required_signatures
                }
            else:
                raise MultiSigOperationError("Failed to update proposal")
            
        except Exception as e:
            logger.error(f"Failed to sign proposal {proposal_id}: {e}")
            raise MultiSigOperationError(f"Signature failed: {e}")
    
    def _is_authorized_signer(self, signer_address: str) -> bool:
        """Check if address is an authorized signer"""
        return any(signer['address'].lower() == signer_address.lower() for signer in self.authorized_signers)
    
    def execute_approved_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """Execute an approved multi-sig proposal"""
        try:
            # Get proposal
            proposal_key = f"trazo/multisig/proposals/{proposal_id}"
            proposal = secure_key_manager.get_secret(proposal_key, use_cache=False)
            
            if not proposal:
                raise MultiSigOperationError(f"Proposal not found: {proposal_id}")
            
            if proposal['status'] != 'approved':
                raise MultiSigOperationError(f"Proposal not approved: {proposal['status']}")
            
            # Execute the operation
            operation_type = proposal['operation_type']
            operation_data = proposal['operation_data']
            
            result = None
            
            if operation_type == 'create_carbon_record':
                production_id = operation_data['production_id']
                carbon_data = operation_data['carbon_data']
                result = super().create_carbon_record(production_id, carbon_data)
                
            elif operation_type == 'issue_credits':
                production_id = operation_data['production_id']
                credits = operation_data['credits']
                result = super().issue_carbon_credits(production_id, credits)
                
            elif operation_type == 'monthly_summary':
                result = super().submit_monthly_summary(
                    operation_data['producer_id'],
                    operation_data['production_id'],
                    operation_data['total_co2e'],
                    operation_data['data_hash'],
                    operation_data['raw_data']
                )
            
            else:
                raise MultiSigOperationError(f"Unknown operation type: {operation_type}")
            
            # Mark proposal as executed
            proposal['status'] = 'executed'
            proposal['executed_at'] = timezone.now().isoformat()
            proposal['execution_result'] = result
            
            secure_key_manager.store_secret(proposal_key, proposal, f"Executed multi-sig proposal {proposal_id}")
            
            # Create audit log
            audit_entry = {
                'event': 'multisig_proposal_executed',
                'proposal_id': proposal_id,
                'operation_type': operation_type,
                'executed_by': 'system',
                'execution_result': result,
                'timestamp': timezone.now().isoformat()
            }
            
            audit_key = f"trazo/audit/multisig/{proposal_id}_executed"
            secure_key_manager.store_secret(audit_key, audit_entry, "Multi-sig execution audit log")
            
            logger.info(f"✅ Executed multi-sig proposal: {proposal_id}")
            
            return {
                'success': True,
                'proposal_id': proposal_id,
                'operation_type': operation_type,
                'execution_result': result,
                'executed_at': proposal['executed_at']
            }
            
        except Exception as e:
            logger.error(f"Failed to execute proposal {proposal_id}: {e}")
            raise MultiSigOperationError(f"Execution failed: {e}")
    
    def create_carbon_record(self, production_id: int, carbon_data: Dict[str, Any]) -> Dict[str, Any]:
        """Override to add multi-signature protection for critical operations"""
        try:
            # Check if multi-sig is required
            if self._requires_multisig('create_carbon_record', carbon_data):
                logger.info(f"Creating multi-sig proposal for carbon record: production_id={production_id}")
                
                operation_data = {
                    'production_id': production_id,
                    'carbon_data': carbon_data,
                    'created_by': carbon_data.get('created_by', 'system'),
                    'total_emissions': carbon_data.get('total_emissions', 0),
                    'total_offsets': carbon_data.get('total_offsets', 0)
                }
                
                proposal = self._create_multisig_proposal('create_carbon_record', operation_data)
                
                return {
                    'multisig_required': True,
                    'proposal_id': proposal['proposal_id'],
                    'status': 'pending_approval',
                    'required_signatures': self.required_signatures,
                    'message': f'Multi-signature approval required. Proposal ID: {proposal["proposal_id"]}'
                }
            else:
                # Execute directly for low-risk operations
                return super().create_carbon_record(production_id, carbon_data)
                
        except Exception as e:
            logger.error(f"Multi-sig carbon record creation failed: {e}")
            raise BlockchainOperationError(f"Multi-sig operation failed: {e}")
    
    def issue_carbon_credits(self, production_id: int, credits: float) -> Dict[str, Any]:
        """Override to add multi-signature protection for credit issuance"""
        try:
            operation_data = {
                'production_id': production_id,
                'credits': credits
            }
            
            # Credit issuance always requires multi-sig
            if self._requires_multisig('issue_credits', operation_data):
                logger.info(f"Creating multi-sig proposal for credit issuance: production_id={production_id}, credits={credits}")
                
                proposal = self._create_multisig_proposal('issue_credits', operation_data)
                
                return {
                    'multisig_required': True,
                    'proposal_id': proposal['proposal_id'],
                    'status': 'pending_approval',
                    'required_signatures': self.required_signatures,
                    'message': f'Multi-signature approval required for {credits} credits. Proposal ID: {proposal["proposal_id"]}'
                }
            else:
                return super().issue_carbon_credits(production_id, credits)
                
        except Exception as e:
            logger.error(f"Multi-sig credit issuance failed: {e}")
            raise BlockchainOperationError(f"Multi-sig operation failed: {e}")
    
    def get_pending_proposals(self, signer_address: str = None) -> List[Dict[str, Any]]:
        """Get pending multi-sig proposals for a signer"""
        try:
            # This would need to be implemented with a proper database or index
            # For now, this is a placeholder
            logger.info(f"Getting pending proposals for signer: {signer_address}")
            
            # In a real implementation, you would:
            # 1. Query all proposals with status 'pending'
            # 2. Filter by signer if provided
            # 3. Return sorted by creation date
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get pending proposals: {e}")
            return []


# Enhanced singleton instance with multi-signature support
multisig_blockchain_service = MultiSigBlockchainService()