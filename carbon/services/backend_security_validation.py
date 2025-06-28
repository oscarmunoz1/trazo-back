"""
Enhanced Backend Security Validation Service

This service provides comprehensive server-side validation that cannot be bypassed
by client-side manipulation. All critical business logic validation is performed
on the backend to prevent security vulnerabilities.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation

from ..models import (
    CarbonEntry, CarbonAuditLog, CarbonOffsetProject, CarbonOffsetPurchase,
    RegionalEmissionFactor, USDAComplianceRecord, VerificationAudit
)

logger = logging.getLogger(__name__)
User = get_user_model()


class SecurityViolationError(Exception):
    """Raised when a security violation is detected"""
    def __init__(self, message: str, violation_type: str, severity: str = 'high'):
        self.message = message
        self.violation_type = violation_type
        self.severity = severity
        super().__init__(self.message)


class BackendSecurityValidator:
    """
    Comprehensive backend security validation service
    
    This service validates all critical operations on the server-side to prevent
    client-side bypasses and ensures data integrity.
    """
    
    # Security limits that MUST be enforced on backend
    SECURITY_LIMITS = {
        'MAX_OFFSET_AMOUNT': 100000,  # kg CO2e per single transaction
        'MIN_OFFSET_AMOUNT': 0.001,   # kg CO2e minimum
        'MAX_DAILY_SELF_REPORTED': 500,  # kg CO2e per user per day
        'MAX_MONTHLY_SELF_REPORTED': 10000,  # kg CO2e per user per month
        'MAX_RAPID_SUBMISSIONS': 5,   # Max submissions per 10 minutes
        'MAX_FOOTPRINT_MULTIPLIER': 2.0,  # Max offset as % of footprint
        'GAMING_DETECTION_THRESHOLD': 0.75,  # Risk score threshold
        'BLOCKCHAIN_REQUIRED_AMOUNT': 1000,  # kg CO2e requiring blockchain verification
    }
    
    def __init__(self):
        self.production_mode = getattr(settings, 'DEBUG', True) == False
        self.strict_validation = self.production_mode or getattr(settings, 'FORCE_STRICT_VALIDATION', False)
    
    def validate_offset_creation(self, user: User, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive validation for offset creation with anti-gaming protection
        
        Args:
            user: User creating the offset
            data: Offset creation data
            
        Returns:
            Dict containing validation results and any violations
            
        Raises:
            SecurityViolationError: If critical security violations are detected
        """
        validation_result = {
            'valid': True,
            'violations': [],
            'warnings': [],
            'anti_gaming_flags': [],
            'trust_adjustments': {},
            'effective_amount': None,
            'requires_audit': False,
            'blockchain_verification_required': False
        }
        
        try:
            # 1. CRITICAL INPUT VALIDATION (Server-side only)
            self._validate_critical_inputs(data, validation_result)
            
            # 2. RATE LIMITING VALIDATION
            self._validate_rate_limits(user, data, validation_result)
            
            # 3. BUSINESS LOGIC VALIDATION
            self._validate_business_logic(user, data, validation_result)
            
            # 4. ANTI-GAMING DETECTION
            self._detect_gaming_patterns(user, data, validation_result)
            
            # 5. VERIFICATION LEVEL REQUIREMENTS
            self._validate_verification_requirements(data, validation_result)
            
            # 6. PROGRESSIVE TRUST SCORING
            self._calculate_trust_score(user, data, validation_result)
            
            # 7. BLOCKCHAIN VERIFICATION REQUIREMENTS
            self._check_blockchain_requirements(data, validation_result)
            
            # 8. FINAL SECURITY CHECKS
            self._perform_final_security_checks(user, data, validation_result)
            
            # If we have high-severity violations, mark as invalid
            high_severity_violations = [v for v in validation_result['violations'] if v.get('severity') == 'high']
            if high_severity_violations:
                validation_result['valid'] = False
                
                # Log critical security violation
                self._log_security_violation(user, data, high_severity_violations)
                
                # Raise exception for critical violations
                if any(v.get('type') in ['amount_manipulation', 'rate_limit_exceeded', 'gaming_detected'] 
                       for v in high_severity_violations):
                    raise SecurityViolationError(
                        f"Critical security violation detected: {high_severity_violations[0]['message']}",
                        violation_type=high_severity_violations[0]['type'],
                        severity='high'
                    )
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Security validation error for user {user.id}: {str(e)}")
            validation_result['valid'] = False
            validation_result['violations'].append({
                'type': 'validation_error',
                'severity': 'high',
                'message': 'Security validation failed',
                'details': str(e)
            })
            return validation_result
    
    def _validate_critical_inputs(self, data: Dict[str, Any], validation_result: Dict[str, Any]):
        """Validate critical inputs that must never be bypassed"""
        
        # Amount validation with strict bounds
        try:
            amount = Decimal(str(data.get('amount', 0)))
            if amount <= 0:
                validation_result['violations'].append({
                    'type': 'invalid_amount',
                    'severity': 'high',
                    'message': 'Offset amount must be greater than 0',
                    'field': 'amount'
                })
            elif amount < Decimal(str(self.SECURITY_LIMITS['MIN_OFFSET_AMOUNT'])):
                validation_result['violations'].append({
                    'type': 'amount_too_small',
                    'severity': 'medium',
                    'message': f'Amount below minimum threshold: {self.SECURITY_LIMITS["MIN_OFFSET_AMOUNT"]} kg CO2e',
                    'field': 'amount'
                })
            elif amount > Decimal(str(self.SECURITY_LIMITS['MAX_OFFSET_AMOUNT'])):
                validation_result['violations'].append({
                    'type': 'amount_manipulation',
                    'severity': 'high',
                    'message': f'Amount exceeds maximum security limit: {self.SECURITY_LIMITS["MAX_OFFSET_AMOUNT"]} kg CO2e',
                    'field': 'amount'
                })
                
        except (InvalidOperation, ValueError, TypeError):
            validation_result['violations'].append({
                'type': 'invalid_amount_format',
                'severity': 'high',
                'message': 'Invalid amount format - must be a valid number',
                'field': 'amount'
            })
        
        # Required fields validation
        required_fields = ['amount', 'source_id', 'type', 'year']
        for field in required_fields:
            if field not in data or data[field] is None or str(data[field]).strip() == '':
                validation_result['violations'].append({
                    'type': 'missing_required_field',
                    'severity': 'high',
                    'message': f'Required field missing: {field}',
                    'field': field
                })
        
        # Year validation
        try:
            year = int(data.get('year', 0))
            current_year = datetime.now().year
            if year < 2020 or year > current_year + 1:
                validation_result['violations'].append({
                    'type': 'invalid_year',
                    'severity': 'medium',
                    'message': f'Year must be between 2020 and {current_year + 1}',
                    'field': 'year'
                })
        except (ValueError, TypeError):
            validation_result['violations'].append({
                'type': 'invalid_year_format',
                'severity': 'high',
                'message': 'Year must be a valid integer',
                'field': 'year'
            })
        
        # Source ID validation
        source_id = data.get('source_id', '').strip()
        if source_id:
            # Validate against known project types or allow custom with restrictions
            allowed_sources = [
                'no_till', 'cover_crop', 'reforestation', 'solar', 'wind', 
                'methane_capture', 'composting', 'biochar', 'mangrove'
            ]
            if source_id not in allowed_sources and len(source_id) < 3:
                validation_result['violations'].append({
                    'type': 'invalid_source',
                    'severity': 'medium',
                    'message': 'Invalid or unrecognized offset source',
                    'field': 'source_id'
                })
    
    def _validate_rate_limits(self, user: User, data: Dict[str, Any], validation_result: Dict[str, Any]):
        """Validate rate limits to prevent rapid-fire gaming"""
        
        user_id = user.id
        now = timezone.now()
        
        # Check rapid submissions (10 minutes)
        rapid_key = f"rapid_submissions:{user_id}"
        rapid_count = cache.get(rapid_key, 0)
        
        if rapid_count >= self.SECURITY_LIMITS['MAX_RAPID_SUBMISSIONS']:
            validation_result['violations'].append({
                'type': 'rate_limit_exceeded',
                'severity': 'high',
                'message': 'Too many submissions in a short period. Please wait before submitting again.',
                'cooldown_seconds': 600  # 10 minutes
            })
        else:
            # Increment rapid submission counter
            cache.set(rapid_key, rapid_count + 1, 600)  # 10 minutes
        
        # Check daily self-reported limits
        daily_key = f"daily_self_reported:{user_id}:{now.date()}"
        daily_amount = cache.get(daily_key, 0)
        amount = float(data.get('amount', 0))
        verification_level = data.get('verification_level', 'self_reported')
        
        if verification_level == 'self_reported':
            if daily_amount + amount > self.SECURITY_LIMITS['MAX_DAILY_SELF_REPORTED']:
                validation_result['violations'].append({
                    'type': 'daily_limit_exceeded',
                    'severity': 'high',
                    'message': f'Daily self-reported limit exceeded. Maximum: {self.SECURITY_LIMITS["MAX_DAILY_SELF_REPORTED"]} kg CO2e',
                    'current_daily_total': daily_amount,
                    'attempted_amount': amount
                })
            else:
                # Update daily counter
                cache.set(daily_key, daily_amount + amount, 86400)  # 24 hours
        
        # Check monthly limits for self-reported
        monthly_key = f"monthly_self_reported:{user_id}:{now.year}-{now.month:02d}"
        monthly_amount = cache.get(monthly_key, 0)
        
        if verification_level == 'self_reported':
            if monthly_amount + amount > self.SECURITY_LIMITS['MAX_MONTHLY_SELF_REPORTED']:
                validation_result['violations'].append({
                    'type': 'monthly_limit_exceeded',
                    'severity': 'high',
                    'message': f'Monthly self-reported limit exceeded. Consider upgrading to certified verification.',
                    'current_monthly_total': monthly_amount,
                    'monthly_limit': self.SECURITY_LIMITS['MAX_MONTHLY_SELF_REPORTED']
                })
            else:
                # Update monthly counter
                days_in_month = 31  # Simplified for cache expiry
                cache.set(monthly_key, monthly_amount + amount, days_in_month * 86400)
    
    def _validate_business_logic(self, user: User, data: Dict[str, Any], validation_result: Dict[str, Any]):
        """Validate core business logic rules"""
        
        amount = float(data.get('amount', 0))
        footprint = data.get('footprint', 0)
        
        # Footprint ratio validation
        if footprint and amount > footprint * self.SECURITY_LIMITS['MAX_FOOTPRINT_MULTIPLIER']:
            validation_result['violations'].append({
                'type': 'excessive_offset_ratio',
                'severity': 'high',
                'message': f'Offset amount cannot exceed {int(self.SECURITY_LIMITS["MAX_FOOTPRINT_MULTIPLIER"] * 100)}% of footprint',
                'footprint': footprint,
                'attempted_amount': amount,
                'max_allowed': footprint * self.SECURITY_LIMITS['MAX_FOOTPRINT_MULTIPLIER']
            })
        
        # Verification level business rules
        verification_level = data.get('verification_level', 'self_reported')
        
        # High-value offsets require certified verification
        if amount >= 1000 and verification_level != 'certified_project':
            validation_result['violations'].append({
                'type': 'verification_level_required',
                'severity': 'high',
                'message': 'High-value offsets (≥1000 kg CO₂e) require certified project verification',
                'required_verification_level': 'certified_project',
                'amount_threshold': 1000
            })
        
        # Medium-value offsets require additionality evidence
        if amount >= 100 and not data.get('additionality_evidence'):
            validation_result['violations'].append({
                'type': 'additionality_evidence_required',
                'severity': 'medium',
                'message': 'Medium-value offsets (≥100 kg CO₂e) require additionality evidence',
                'required_fields': ['additionality_evidence'],
                'amount_threshold': 100
            })
        
        # Project capacity validation
        source_id = data.get('source_id')
        if source_id:
            try:
                project = CarbonOffsetProject.objects.get(id=source_id)
                if amount > project.available_capacity:
                    validation_result['violations'].append({
                        'type': 'insufficient_project_capacity',
                        'severity': 'high',
                        'message': 'Requested amount exceeds project available capacity',
                        'available_capacity': float(project.available_capacity),
                        'requested_amount': amount
                    })
            except CarbonOffsetProject.DoesNotExist:
                # Project doesn't exist as a formal project - allow but flag for review
                validation_result['warnings'].append({
                    'type': 'unregistered_project',
                    'severity': 'low',
                    'message': 'Offset source is not a registered project',
                    'source_id': source_id
                })
    
    def _detect_gaming_patterns(self, user: User, data: Dict[str, Any], validation_result: Dict[str, Any]):
        """Advanced anti-gaming pattern detection"""
        
        amount = float(data.get('amount', 0))
        user_id = user.id
        now = timezone.now()
        
        gaming_flags = []
        risk_score = 0
        
        # 1. Round number detection for large amounts
        if amount >= 100 and amount % 50 == 0:
            gaming_flags.append('suspicious_round_number')
            risk_score += 0.2
        
        # 2. Submission timing patterns
        recent_submissions = CarbonEntry.objects.filter(
            created_by=user,
            type='offset',
            created_at__gte=now - timedelta(hours=24)
        ).count()
        
        if recent_submissions >= 10:
            gaming_flags.append('high_frequency_submissions')
            risk_score += 0.3
        
        # 3. Amount progression analysis
        recent_amounts = list(CarbonEntry.objects.filter(
            created_by=user,
            type='offset',
            created_at__gte=now - timedelta(days=7)
        ).values_list('amount', flat=True))
        
        if len(recent_amounts) >= 3:
            # Check for suspiciously linear progression
            differences = [recent_amounts[i+1] - recent_amounts[i] for i in range(len(recent_amounts)-1)]
            if len(set(differences)) == 1 and differences[0] > 0:
                gaming_flags.append('linear_amount_progression')
                risk_score += 0.25
        
        # 4. Verification level gaming
        verification_level = data.get('verification_level', 'self_reported')
        if verification_level == 'self_reported' and amount >= 500:
            recent_high_self_reported = CarbonEntry.objects.filter(
                created_by=user,
                type='offset',
                verification_level='self_reported',
                amount__gte=500,
                created_at__gte=now - timedelta(days=30)
            ).count()
            
            if recent_high_self_reported >= 3:
                gaming_flags.append('avoiding_verification_requirements')
                risk_score += 0.4
        
        # 5. Establishment/production switching patterns
        establishment_id = data.get('establishment')
        production_id = data.get('production')
        
        if establishment_id or production_id:
            recent_context_switches = CarbonEntry.objects.filter(
                created_by=user,
                type='offset',
                created_at__gte=now - timedelta(days=7)
            ).values('establishment_id', 'production_id').distinct().count()
            
            if recent_context_switches >= 5:
                gaming_flags.append('frequent_context_switching')
                risk_score += 0.2
        
        # Store gaming analysis results
        if gaming_flags:
            validation_result['anti_gaming_flags'] = gaming_flags
            
        # Calculate final risk score
        validation_result['gaming_risk_score'] = min(risk_score, 1.0)
        
        # Flag for review if risk score is high
        if risk_score >= self.SECURITY_LIMITS['GAMING_DETECTION_THRESHOLD']:
            validation_result['violations'].append({
                'type': 'gaming_detected',
                'severity': 'high',
                'message': 'Suspicious gaming patterns detected',
                'gaming_flags': gaming_flags,
                'risk_score': risk_score,
                'requires_manual_review': True
            })
            validation_result['requires_audit'] = True
    
    def _validate_verification_requirements(self, data: Dict[str, Any], validation_result: Dict[str, Any]):
        """Validate verification requirements based on amount and level"""
        
        amount = float(data.get('amount', 0))
        verification_level = data.get('verification_level', 'self_reported')
        
        # Critical verification requirements
        if amount >= 1000:
            if verification_level != 'certified_project':
                validation_result['violations'].append({
                    'type': 'verification_upgrade_required',
                    'severity': 'high',
                    'message': 'Amounts ≥1000 kg CO₂e require certified project verification',
                    'required_verification': 'certified_project',
                    'current_verification': verification_level
                })
            
            if not data.get('permanence_plan'):
                validation_result['violations'].append({
                    'type': 'permanence_plan_required',
                    'severity': 'high',
                    'message': 'Permanence plan required for high-value offsets',
                    'amount_threshold': 1000
                })
        
        if amount >= 100 and not data.get('additionality_evidence'):
            validation_result['violations'].append({
                'type': 'additionality_evidence_required',
                'severity': 'medium',
                'message': 'Additionality evidence required for medium-value offsets',
                'amount_threshold': 100
            })
        
        # Certified project requirements
        if verification_level == 'certified_project':
            if not data.get('registry_verification_id'):
                validation_result['violations'].append({
                    'type': 'registry_verification_required',
                    'severity': 'high',
                    'message': 'Registry verification ID required for certified projects',
                    'required_field': 'registry_verification_id'
                })
    
    def _calculate_trust_score(self, user: User, data: Dict[str, Any], validation_result: Dict[str, Any]):
        """Calculate dynamic trust score based on user history and current submission"""
        
        # Base trust scores by verification level
        base_trust_scores = {
            'self_reported': 0.5,
            'community_verified': 0.75,
            'certified_project': 1.0
        }
        
        verification_level = data.get('verification_level', 'self_reported')
        base_score = base_trust_scores.get(verification_level, 0.5)
        
        # Adjust based on user history
        user_history = self._get_user_trust_history(user)
        history_adjustment = 0
        
        if user_history['total_verified_offsets'] > 10:
            history_adjustment += 0.1
        if user_history['audit_pass_rate'] > 0.9:
            history_adjustment += 0.1
        if user_history['gaming_violations'] == 0:
            history_adjustment += 0.05
        else:
            history_adjustment -= 0.1 * user_history['gaming_violations']
        
        # Adjust based on current submission quality
        quality_adjustment = 0
        amount = float(data.get('amount', 0))
        
        if data.get('additionality_evidence'):
            quality_adjustment += 0.05
        if data.get('permanence_plan'):
            quality_adjustment += 0.05
        if data.get('evidence_photos'):
            quality_adjustment += 0.03
        if data.get('evidence_documents'):
            quality_adjustment += 0.03
        
        # Gaming penalty
        gaming_penalty = validation_result.get('gaming_risk_score', 0) * 0.3
        
        # Calculate final trust score
        final_trust_score = max(0.1, min(1.0, base_score + history_adjustment + quality_adjustment - gaming_penalty))
        
        # Calculate effective amount with trust score applied
        effective_amount = amount * final_trust_score
        
        validation_result['trust_score'] = final_trust_score
        validation_result['effective_amount'] = effective_amount
        validation_result['trust_adjustments'] = {
            'base_score': base_score,
            'history_adjustment': history_adjustment,
            'quality_adjustment': quality_adjustment,
            'gaming_penalty': gaming_penalty,
            'final_score': final_trust_score
        }
    
    def _check_blockchain_requirements(self, data: Dict[str, Any], validation_result: Dict[str, Any]):
        """Check if blockchain verification is required"""
        
        amount = float(data.get('amount', 0))
        verification_level = data.get('verification_level', 'self_reported')
        
        # Blockchain required for high-value transactions in production
        if (amount >= self.SECURITY_LIMITS['BLOCKCHAIN_REQUIRED_AMOUNT'] and 
            self.production_mode and verification_level == 'certified_project'):
            
            validation_result['blockchain_verification_required'] = True
            validation_result['warnings'].append({
                'type': 'blockchain_verification_required',
                'severity': 'medium',
                'message': f'Blockchain verification required for amounts ≥{self.SECURITY_LIMITS["BLOCKCHAIN_REQUIRED_AMOUNT"]} kg CO₂e',
                'amount_threshold': self.SECURITY_LIMITS['BLOCKCHAIN_REQUIRED_AMOUNT']
            })
    
    def _perform_final_security_checks(self, user: User, data: Dict[str, Any], validation_result: Dict[str, Any]):
        """Perform final security checks before allowing creation"""
        
        # Check if user is in good standing
        recent_violations = CarbonAuditLog.objects.filter(
            user=user,
            action='gaming_detected',
            timestamp__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        if recent_violations >= 3:
            validation_result['violations'].append({
                'type': 'user_on_probation',
                'severity': 'high',
                'message': 'Account flagged for multiple recent violations. Contact support.',
                'recent_violations': recent_violations,
                'requires_manual_review': True
            })
        
        # Production-specific checks
        if self.production_mode:
            # Ensure CSRF token validation in production
            if not data.get('csrfToken'):
                validation_result['violations'].append({
                    'type': 'missing_csrf_token',
                    'severity': 'high',
                    'message': 'CSRF protection required',
                    'field': 'csrfToken'
                })
            
            # Session validation
            if not data.get('sessionToken'):
                validation_result['violations'].append({
                    'type': 'missing_session_token',
                    'severity': 'high',
                    'message': 'Valid session required',
                    'field': 'sessionToken'
                })
        
        # Audit requirement determination
        amount = float(data.get('amount', 0))
        if (amount >= 500 or 
            validation_result.get('gaming_risk_score', 0) >= 0.5 or 
            validation_result.get('anti_gaming_flags')):
            validation_result['requires_audit'] = True
    
    def _get_user_trust_history(self, user: User) -> Dict[str, Any]:
        """Get user's trust history metrics"""
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Count verified offsets
        total_verified_offsets = CarbonEntry.objects.filter(
            created_by=user,
            type='offset',
            verification_level__in=['community_verified', 'certified_project']
        ).count()
        
        # Calculate audit pass rate
        recent_audits = VerificationAudit.objects.filter(
            carbon_entry__created_by=user,
            audit_date__gte=thirty_days_ago
        )
        audit_pass_rate = (recent_audits.filter(result='passed').count() / 
                          max(recent_audits.count(), 1))
        
        # Count gaming violations
        gaming_violations = CarbonAuditLog.objects.filter(
            user=user,
            action='gaming_detected',
            timestamp__gte=thirty_days_ago
        ).count()
        
        return {
            'total_verified_offsets': total_verified_offsets,
            'audit_pass_rate': audit_pass_rate,
            'gaming_violations': gaming_violations
        }
    
    def _log_security_violation(self, user: User, data: Dict[str, Any], violations: List[Dict[str, Any]]):
        """Log security violations for monitoring and analysis"""
        
        violation_details = {
            'user_id': user.id,
            'submission_data': {
                'amount': data.get('amount'),
                'source_id': data.get('source_id'),
                'verification_level': data.get('verification_level')
            },
            'violations': violations,
            'timestamp': timezone.now().isoformat(),
            'ip_address': data.get('ip_address'),
            'user_agent': data.get('user_agent', '')[:200]
        }
        
        # Create audit log entry
        CarbonAuditLog.objects.create(
            user=user,
            action='gaming_detected',
            details=f'Security violations detected: {", ".join([v["type"] for v in violations])}',
            ip_address=data.get('ip_address')
        )
        
        # Log to security monitoring system
        logger.warning(f"Security violation detected for user {user.id}: {violation_details}")
        
        # Cache violation for rate limiting
        violation_key = f"security_violations:{user.id}"
        current_count = cache.get(violation_key, 0)
        cache.set(violation_key, current_count + 1, 3600)  # 1 hour
    
    def validate_file_upload_security(self, file_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate file upload security requirements"""
        
        validation_result = {
            'valid': True,
            'violations': [],
            'warnings': []
        }
        
        # File size validation
        file_size = file_data.get('size', 0)
        max_size = 10 * 1024 * 1024  # 10MB
        
        if file_size > max_size:
            validation_result['violations'].append({
                'type': 'file_too_large',
                'severity': 'high',
                'message': f'File size exceeds maximum allowed: {max_size / (1024*1024):.1f}MB',
                'file_size': file_size,
                'max_size': max_size
            })
        
        # File type validation
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'application/pdf', 'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain', 'text/rtf'
        ]
        
        file_type = file_data.get('type', '')
        if file_type not in allowed_types:
            validation_result['violations'].append({
                'type': 'invalid_file_type',
                'severity': 'high',
                'message': 'File type not allowed for security reasons',
                'file_type': file_type,
                'allowed_types': allowed_types
            })
        
        # Malicious filename detection
        filename = file_data.get('name', '')
        dangerous_patterns = [
            '.exe', '.bat', '.cmd', '.scr', '.com', '.pif', '.vbs', 
            '.js', '.jar', '.php', '.py', '.sh', '.ps1'
        ]
        
        if any(pattern in filename.lower() for pattern in dangerous_patterns):
            validation_result['violations'].append({
                'type': 'malicious_filename',
                'severity': 'high',
                'message': 'Filename contains potentially dangerous patterns',
                'filename': filename
            })
        
        # Path traversal detection
        if '..' in filename or '/' in filename or '\\' in filename:
            validation_result['violations'].append({
                'type': 'path_traversal_attempt',
                'severity': 'high',
                'message': 'Filename contains path traversal characters',
                'filename': filename
            })
        
        if validation_result['violations']:
            validation_result['valid'] = False
        
        return validation_result


# Create singleton instance
backend_security_validator = BackendSecurityValidator()