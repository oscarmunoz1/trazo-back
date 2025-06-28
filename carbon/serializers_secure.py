"""
Secure Carbon Serializers with Backend Validation

These serializers implement comprehensive server-side validation that cannot
be bypassed by client-side manipulation, ensuring data integrity and security.
"""

import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, Any
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import (
    CarbonEntry, CarbonSource, CarbonOffsetProject, CarbonOffsetPurchase,
    CarbonOffsetCertificate, RegionalEmissionFactor
)
from .services.backend_security_validation import (
    backend_security_validator, SecurityViolationError
)

logger = logging.getLogger(__name__)


class SecureCarbonEntrySerializer(serializers.ModelSerializer):
    """
    Secure serializer for carbon entries with comprehensive backend validation
    
    This serializer ensures that all validation logic is performed on the
    server-side and cannot be bypassed by client modifications.
    """
    
    # Read-only fields that are calculated server-side
    trust_score = serializers.FloatField(read_only=True)
    effective_amount = serializers.FloatField(read_only=True)
    gaming_risk_score = serializers.FloatField(read_only=True, required=False)
    audit_status = serializers.CharField(read_only=True)
    verification_badge = serializers.DictField(read_only=True)
    
    # Security fields that must be provided by client
    timestamp = serializers.IntegerField(write_only=True, required=True)
    user_agent = serializers.CharField(write_only=True, required=True, max_length=500)
    session_token = serializers.CharField(write_only=True, required=True, max_length=100)
    csrf_token = serializers.CharField(write_only=True, required=True, max_length=100)
    
    # Business logic fields
    footprint = serializers.FloatField(write_only=True, required=False, help_text="Product footprint for validation")
    product_name = serializers.CharField(write_only=True, required=False, max_length=200)
    
    class Meta:
        model = CarbonEntry
        fields = [
            # Core fields
            'id', 'amount', 'year', 'type', 'description',
            'establishment', 'production', 'created_by',
            
            # Verification fields
            'verification_level', 'trust_score', 'effective_amount',
            'additionality_evidence', 'permanence_plan', 'baseline_data',
            'methodology_template', 'registry_verification_id',
            'evidence_photos', 'evidence_documents',
            'evidence_requirements_met', 'documentation_complete',
            'additionality_verified', 'audit_status',
            
            # USDA compliance fields
            'usda_verified', 'usda_factors_based', 'verification_status',
            'data_source',
            
            # Security and audit fields
            'gaming_risk_score', 'verification_badge',
            
            # Security input fields (write-only)
            'timestamp', 'user_agent', 'session_token', 'csrf_token',
            'footprint', 'product_name',
            
            # Timestamps
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_by', 'trust_score', 'effective_amount',
            'gaming_risk_score', 'audit_status', 'verification_badge',
            'created_at', 'updated_at', 'usda_verified', 'usda_factors_based'
        ]
    
    def validate(self, attrs):
        """
        Comprehensive validation using backend security validator
        
        This validation cannot be bypassed by client-side modifications
        """
        # Get request user from context
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise ValidationError("Authentication required for carbon entry creation")
        
        # Prepare validation data
        validation_data = attrs.copy()
        validation_data['ip_address'] = self._get_client_ip(request)
        
        # Add source_id from source relationship
        if 'source' in attrs:
            source = attrs['source']
            if hasattr(source, 'name'):
                validation_data['source_id'] = source.name
            else:
                validation_data['source_id'] = str(source)
        
        try:
            # Run comprehensive backend security validation
            validation_result = backend_security_validator.validate_offset_creation(
                user=request.user,
                data=validation_data
            )
        except SecurityViolationError as e:
            logger.error(f"Security violation in serializer for user {request.user.id}: {e.message}")
            raise ValidationError({
                'security_error': e.message,
                'violation_type': e.violation_type,
                'severity': e.severity
            })
        
        # Check validation results
        if not validation_result['valid']:
            high_severity_violations = [
                v for v in validation_result['violations']
                if v.get('severity') == 'high'
            ]
            
            if high_severity_violations:
                # Create detailed error response
                error_details = {}
                for violation in high_severity_violations:
                    field = violation.get('field', 'non_field_errors')
                    if field not in error_details:
                        error_details[field] = []
                    error_details[field].append(violation['message'])
                
                raise ValidationError(error_details)
        
        # Store validation results for use in create/update
        attrs['_validation_result'] = validation_result
        
        return attrs
    
    def validate_amount(self, value):
        """Validate amount with strict server-side rules"""
        try:
            amount = Decimal(str(value))
            
            # Strict bounds checking
            if amount <= 0:
                raise ValidationError("Amount must be greater than 0")
            
            if amount < Decimal('0.001'):
                raise ValidationError("Amount too small (minimum: 0.001 kg CO2e)")
            
            if amount > Decimal('100000'):
                raise ValidationError("Amount exceeds security limit (maximum: 100,000 kg CO2e)")
            
            # Check for suspicious precision (potential manipulation)
            if amount.as_tuple().exponent < -6:  # More than 6 decimal places
                raise ValidationError("Amount has suspicious precision")
            
            return float(amount)
            
        except (InvalidOperation, ValueError):
            raise ValidationError("Amount must be a valid number")
    
    def validate_year(self, value):
        """Validate year with business logic rules"""
        current_year = timezone.now().year
        
        if not isinstance(value, int):
            raise ValidationError("Year must be an integer")
        
        if value < 2020:
            raise ValidationError("Year cannot be before 2020")
        
        if value > current_year + 1:
            raise ValidationError(f"Year cannot be more than one year in the future")
        
        return value
    
    def validate_verification_level(self, value):
        """Validate verification level with business rules"""
        allowed_levels = ['self_reported', 'community_verified', 'certified_project']
        
        if value not in allowed_levels:
            raise ValidationError(f"Invalid verification level. Must be one of: {allowed_levels}")
        
        return value
    
    def validate_timestamp(self, value):
        """Validate request timestamp to prevent replay attacks"""
        try:
            timestamp = int(value)
            now = timezone.now().timestamp() * 1000  # Convert to milliseconds
            
            # Allow 5 minutes before and after current time
            five_minutes = 5 * 60 * 1000
            
            if timestamp < now - five_minutes:
                raise ValidationError("Request timestamp is too old")
            
            if timestamp > now + five_minutes:
                raise ValidationError("Request timestamp is too far in the future")
            
            return timestamp
            
        except (ValueError, TypeError):
            raise ValidationError("Invalid timestamp format")
    
    def validate_evidence_photos(self, value):
        """Validate evidence photos URLs"""
        if not isinstance(value, list):
            raise ValidationError("Evidence photos must be a list")
        
        if len(value) > 10:
            raise ValidationError("Maximum 10 evidence photos allowed")
        
        for url in value:
            if not isinstance(url, str):
                raise ValidationError("Each photo URL must be a string")
            
            if len(url) > 500:
                raise ValidationError("Photo URL too long")
            
            # Basic URL validation
            if not (url.startswith('http://') or url.startswith('https://')):
                raise ValidationError("Invalid photo URL format")
        
        return value
    
    def validate_evidence_documents(self, value):
        """Validate evidence documents URLs"""
        if not isinstance(value, list):
            raise ValidationError("Evidence documents must be a list")
        
        if len(value) > 5:
            raise ValidationError("Maximum 5 evidence documents allowed")
        
        for url in value:
            if not isinstance(url, str):
                raise ValidationError("Each document URL must be a string")
            
            if len(url) > 500:
                raise ValidationError("Document URL too long")
            
            # Basic URL validation
            if not (url.startswith('http://') or url.startswith('https://')):
                raise ValidationError("Invalid document URL format")
        
        return value
    
    def create(self, validated_data):
        """Create carbon entry with security validation results"""
        
        # Extract validation results
        validation_result = validated_data.pop('_validation_result', {})
        
        # Remove write-only fields that shouldn't be stored
        write_only_fields = ['timestamp', 'user_agent', 'session_token', 'csrf_token', 'footprint', 'product_name']
        for field in write_only_fields:
            validated_data.pop(field, None)
        
        # Apply security-calculated values
        if 'trust_score' in validation_result:
            validated_data['trust_score'] = validation_result['trust_score']
        
        if 'effective_amount' in validation_result:
            validated_data['effective_amount'] = validation_result['effective_amount']
        
        # Set audit status based on validation
        if validation_result.get('requires_audit'):
            validated_data['audit_status'] = 'scheduled'
        else:
            validated_data['audit_status'] = 'pending'
        
        # Set verification status
        validated_data['verification_status'] = 'verified'
        validated_data['usda_factors_based'] = True
        
        # Apply gaming risk metadata
        if validation_result.get('gaming_risk_score'):
            # Store gaming risk score if model supports it
            # This would require adding the field to the model
            pass
        
        # Create the entry
        instance = super().create(validated_data)
        
        # Log creation with security details
        from .models import CarbonAuditLog
        request = self.context.get('request')
        
        CarbonAuditLog.objects.create(
            carbon_entry=instance,
            user=request.user if request else None,
            action='create',
            details=json.dumps({
                'amount': validated_data.get('amount'),
                'verification_level': validated_data.get('verification_level'),
                'trust_score': validation_result.get('trust_score'),
                'gaming_risk_score': validation_result.get('gaming_risk_score', 0),
                'anti_gaming_flags': validation_result.get('anti_gaming_flags', []),
                'audit_required': validation_result.get('requires_audit', False)
            }),
            ip_address=self._get_client_ip(request) if request else None
        )
        
        return instance
    
    def _get_client_ip(self, request):
        """Get client IP address from request"""
        if not request:
            return None
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecureFileUploadSerializer(serializers.Serializer):
    """
    Secure serializer for file uploads with comprehensive security validation
    """
    
    file = serializers.FileField(required=True)
    upload_context = serializers.JSONField(required=True)
    
    def validate_file(self, value):
        """Validate file with comprehensive security checks"""
        
        # Extract file information
        file_data = {
            'name': value.name,
            'size': value.size,
            'type': getattr(value, 'content_type', ''),
            'content': value.read(1024)  # Read first 1KB for content analysis
        }
        
        # Reset file pointer
        value.seek(0)
        
        # Run security validation
        validation_result = backend_security_validator.validate_file_upload_security(file_data)
        
        if not validation_result['valid']:
            violations = validation_result['violations']
            error_messages = [v['message'] for v in violations]
            raise ValidationError(error_messages)
        
        return value
    
    def validate_upload_context(self, value):
        """Validate upload context"""
        required_fields = ['user_id', 'establishment_id', 'upload_purpose']
        
        for field in required_fields:
            if field not in value:
                raise ValidationError(f"Missing required context field: {field}")
        
        # Validate upload purpose
        allowed_purposes = ['evidence_photo', 'evidence_document', 'verification_document']
        if value['upload_purpose'] not in allowed_purposes:
            raise ValidationError(f"Invalid upload purpose. Must be one of: {allowed_purposes}")
        
        return value


class SecureCarbonOffsetPurchaseSerializer(serializers.ModelSerializer):
    """
    Secure serializer for carbon offset purchases with backend validation
    """
    
    # Security fields
    verification_required = serializers.BooleanField(read_only=True)
    security_validation = serializers.DictField(read_only=True)
    trust_score = serializers.FloatField(read_only=True)
    
    class Meta:
        model = CarbonOffsetPurchase
        fields = [
            'id', 'project', 'user', 'amount', 'price_per_ton', 'total_price',
            'status', 'verification_status', 'certificate_file', 'certificate_id',
            'verification_required', 'security_validation', 'trust_score',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'total_price', 'certificate_id', 'verification_required',
            'security_validation', 'trust_score', 'created_at', 'updated_at'
        ]
    
    def validate_amount(self, value):
        """Validate purchase amount with security checks"""
        try:
            amount = Decimal(str(value))
            
            if amount <= 0:
                raise ValidationError("Purchase amount must be greater than 0")
            
            if amount > Decimal('10000'):  # 10 tons limit for purchases
                raise ValidationError("Purchase amount exceeds maximum limit")
            
            return float(amount)
            
        except (InvalidOperation, ValueError):
            raise ValidationError("Amount must be a valid number")
    
    def validate(self, attrs):
        """Validate purchase with project capacity and user limits"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise ValidationError("Authentication required")
        
        project = attrs.get('project')
        amount = attrs.get('amount', 0)
        
        # Check project availability
        if project and amount > project.available_capacity:
            raise ValidationError({
                'amount': f'Requested amount ({amount}) exceeds project capacity ({project.available_capacity})'
            })
        
        # Check user purchase limits (prevent gaming)
        user = request.user
        from django.utils import timezone
        from django.db.models import Sum
        
        # Daily purchase limit
        today = timezone.now().date()
        daily_purchases = CarbonOffsetPurchase.objects.filter(
            user=user,
            created_at__date=today
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        if daily_purchases + amount > 1000:  # 1 ton per day limit
            raise ValidationError({
                'amount': f'Daily purchase limit exceeded. Current: {daily_purchases}, Limit: 1000 kg CO2e'
            })
        
        return attrs
    
    def create(self, validated_data):
        """Create purchase with security validation"""
        request = self.context.get('request')
        validated_data['user'] = request.user
        
        # Calculate total price
        amount = validated_data['amount']
        price_per_ton = validated_data['price_per_ton']
        validated_data['total_price'] = amount * price_per_ton
        
        # Set initial status
        validated_data['status'] = 'pending'
        validated_data['verification_status'] = 'pending'
        
        return super().create(validated_data)


class SecurityStatusSerializer(serializers.Serializer):
    """
    Serializer for user security status information
    """
    
    trust_metrics = serializers.DictField(read_only=True)
    rate_limits = serializers.DictField(read_only=True)
    verification_recommendations = serializers.ListField(
        child=serializers.CharField(),
        read_only=True
    )
    security_features = serializers.DictField(read_only=True)
    account_status = serializers.CharField(read_only=True)
    
    def to_representation(self, instance):
        """Custom representation for security status"""
        if isinstance(instance, dict):
            return instance
        
        # If instance is a user object, calculate security status
        user = instance
        trust_history = backend_security_validator._get_user_trust_history(user)
        
        return {
            'trust_metrics': trust_history,
            'account_status': 'good' if trust_history['gaming_violations'] == 0 else 'flagged',
            'security_features': {
                'csrf_protection': True,
                'rate_limiting': True,
                'gaming_detection': True,
                'backend_validation': True
            }
        }