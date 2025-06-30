"""
Enhanced Carbon Views with Backend Security Validation

This module provides enhanced API endpoints with comprehensive backend security
validation that cannot be bypassed by client-side manipulation.
"""

import logging
from decimal import Decimal
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_ratelimit.decorators import ratelimit
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator

from .models import (
    CarbonEntry, CarbonSource, CarbonAuditLog, CarbonOffsetProject,
    CarbonOffsetPurchase, CarbonOffsetCertificate
)
from .services.backend_security_validation import (
    backend_security_validator, SecurityViolationError
)
from .services.verification import verification_service
from .services.certificate import certificate_generator
from company.models import Establishment
from history.models import History

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='10/m', method='POST', block=True)
def create_secure_carbon_offset(request):
    """
    Create a carbon offset with comprehensive backend security validation.
    
    This endpoint implements server-side validation that cannot be bypassed
    by client-side manipulation, including anti-gaming protection and 
    progressive verification requirements.
    
    Expected payload: {
        "amount": 12.5,
        "source_id": "reforestation_project_001",
        "offset_project_type": "certified_marketplace",
        "verification_level": "certified_project",
        "productName": "Organic Almonds",
        "footprint": 25.0,
        "establishmentId": "uuid",
        "userId": "uuid",
        "timestamp": 1640995200000,
        "userAgent": "Mozilla/5.0...",
        "sessionToken": "session_token",
        "csrfToken": "csrf_token",
        "additionality_evidence": "Evidence text...",
        "permanence_plan": "Plan details...",
        "evidence_photos": ["url1", "url2"],
        "evidence_documents": ["url1"]
    }
    """
    try:
        # Extract and prepare validation data
        request_data = request.data.copy()
        request_data['ip_address'] = get_client_ip(request)
        request_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
        
        # CRITICAL: Comprehensive backend security validation
        try:
            validation_result = backend_security_validator.validate_offset_creation(
                user=request.user,
                data=request_data
            )
        except SecurityViolationError as e:
            # Critical security violation detected
            logger.error(f"Critical security violation from user {request.user.id}: {e.message}")
            
            return Response({
                'error': 'Security validation failed',
                'message': 'Your request has been blocked due to security policy violations.',
                'violation_type': e.violation_type,
                'support_contact': 'security@trazo.com',
                'request_id': f"SEC_{timezone.now().timestamp()}"
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Check if validation passed
        if not validation_result['valid']:
            high_severity_violations = [
                v for v in validation_result['violations'] 
                if v.get('severity') == 'high'
            ]
            
            if high_severity_violations:
                return Response({
                    'error': 'Validation failed',
                    'violations': high_severity_violations,
                    'warnings': validation_result.get('warnings', []),
                    'anti_gaming_flags': validation_result.get('anti_gaming_flags', []),
                    'gaming_risk_score': validation_result.get('gaming_risk_score', 0),
                    'requires_upgrade': any(
                        v.get('type') == 'verification_level_required' 
                        for v in high_severity_violations
                    )
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract validated data
        amount = Decimal(str(request_data['amount']))
        source_id = request_data['source_id']
        verification_level = request_data.get('verification_level', 'self_reported')
        year = int(request_data.get('year', timezone.now().year))
        establishment_id = request_data.get('establishmentId')
        user_id = request_data.get('userId')
        
        # Validate user authorization
        if user_id and str(request.user.id) != str(user_id):
            return Response({
                'error': 'Authorization failed',
                'message': 'User ID mismatch'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Determine establishment and production context
        establishment = None
        production = None
        
        production_id = request_data.get('production')
        if production_id:
            try:
                production = History.objects.get(id=production_id)
                establishment = production.establishment
                # Verify user has access to this production
                if establishment.company not in request.user.companies.all():
                    return Response({
                        'error': 'Access denied to production'
                    }, status=status.HTTP_403_FORBIDDEN)
            except History.DoesNotExist:
                return Response({
                    'error': 'Production not found'
                }, status=status.HTTP_404_NOT_FOUND)
        elif establishment_id:
            try:
                establishment = Establishment.objects.get(id=establishment_id)
                # Verify user has access to this establishment
                if establishment.company not in request.user.companies.all():
                    return Response({
                        'error': 'Access denied to establishment'
                    }, status=status.HTTP_403_FORBIDDEN)
            except Establishment.DoesNotExist:
                return Response({
                    'error': 'Establishment not found'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # Auto-determine establishment from user
            user_companies = request.user.companies.all()
            if user_companies.exists():
                establishment = user_companies.first().establishments.first()
            
            if not establishment:
                return Response({
                    'error': 'No valid establishment found'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create offset source with enhanced validation
        offset_source, created = CarbonSource.objects.get_or_create(
            name=source_id,
            defaults={
                'category': 'offset',
                'default_emission_factor': -1.0,  # Negative for offset
                'unit': 'kg CO2e',
                'description': f'Carbon offset project: {source_id}',
                'usda_verified': source_id in [
                    'reforestation', 'no_till', 'cover_crop', 'solar', 'wind'
                ],
                'verification_status': 'verified' if verification_level == 'certified_project' else 'estimated'
            }
        )
        
        # Create carbon entry with enhanced security fields
        carbon_entry = CarbonEntry.objects.create(
            establishment=establishment,
            production=production,
            created_by=request.user,
            type='offset',
            source=offset_source,
            amount=float(amount),
            year=year,
            description=f'Secure carbon offset: {source_id} - {amount} kg CO₂e',
            
            # USDA and verification fields
            usda_verified=offset_source.usda_verified,
            usda_factors_based=True,
            verification_status='verified',
            data_source=f'Secure offset creation: {source_id}',
            
            # Enhanced verification system fields
            verification_level=verification_level,
            trust_score=validation_result.get('trust_score', 0.5),
            effective_amount=validation_result.get('effective_amount', float(amount)),
            
            # Evidence and documentation
            additionality_evidence=request_data.get('additionality_evidence', ''),
            permanence_plan=request_data.get('permanence_plan', ''),
            baseline_data=request_data.get('baseline_data', {}),
            methodology_template=request_data.get('methodology_template', ''),
            registry_verification_id=request_data.get('registry_verification_id', ''),
            evidence_photos=request_data.get('evidence_photos', []),
            evidence_documents=request_data.get('evidence_documents', []),
            
            # Audit and compliance
            audit_status='scheduled' if validation_result.get('requires_audit') else 'pending',
            additionality_verified=verification_level == 'certified_project',
            evidence_requirements_met=bool(request_data.get('additionality_evidence')),
            documentation_complete=bool(request_data.get('registry_verification_id'))
        )
        
        # Apply security adjustments
        gaming_risk_score = validation_result.get('gaming_risk_score', 0)
        if gaming_risk_score > 0.3:
            # Apply additional buffer for suspicious submissions
            additional_buffer = min(0.2, gaming_risk_score * 0.3)
            carbon_entry.effective_amount *= (1 - additional_buffer)
            carbon_entry.save()
        
        # Enhanced verification check with blockchain integration
        verification_result_detailed = verification_service.verify_carbon_entry(
            carbon_entry  # Now uses the correct method for CarbonEntry
        )
        
        # Handle blockchain verification if required
        if validation_result.get('blockchain_verification_required'):
            try:
                from .services.blockchain import blockchain_service
                blockchain_result = blockchain_service.record_carbon_offset(
                    carbon_entry.id,
                    float(amount),
                    source_id,
                    request.user.id
                )
                
                if blockchain_result.get('success'):
                    carbon_entry.registry_verification_id = blockchain_result.get('transaction_hash', '')
                    carbon_entry.verification_status = 'blockchain_verified'
                    carbon_entry.save()
                else:
                    logger.warning(f"Blockchain verification failed for offset {carbon_entry.id}")
                    
            except Exception as e:
                logger.error(f"Blockchain verification error: {str(e)}")
                # Continue without blockchain if it fails (log for investigation)
        
        # Create comprehensive audit log
        CarbonAuditLog.objects.create(
            carbon_entry=carbon_entry,
            user=request.user,
            action='create',
            details=json.dumps({
                'amount': float(amount),
                'source_id': source_id,
                'verification_level': verification_level,
                'trust_score': validation_result.get('trust_score'),
                'effective_amount': validation_result.get('effective_amount'),
                'gaming_risk_score': gaming_risk_score,
                'anti_gaming_flags': validation_result.get('anti_gaming_flags', []),
                'blockchain_verified': validation_result.get('blockchain_verification_required', False),
                'audit_required': validation_result.get('requires_audit', False)
            }),
            ip_address=get_client_ip(request)
        )
        
        # Generate certificate if applicable
        certificate_url = None
        if (verification_level == 'certified_project' and 
            float(amount) >= 100 and 
            verification_result_detailed.get('status') == 'verified'):
            
            try:
                # Create a CarbonOffsetPurchase for certificate generation
                purchase = CarbonOffsetPurchase.objects.create(
                    user=request.user,
                    project=CarbonOffsetProject.objects.get_or_create(
                        name=f"Project {source_id}",
                        defaults={
                            'description': f'Carbon offset project: {source_id}',
                            'project_type': 'reforestation',
                            'certification_standard': 'VCS',
                            'location': 'Global',
                            'price_per_ton': Decimal('15.00'),
                            'available_capacity': Decimal('1000000.00')
                        }
                    )[0],
                    amount=amount,
                    price_per_ton=Decimal('15.00'),
                    total_price=amount * Decimal('15.00'),
                    status='completed',
                    verification_status='verified'
                )
                
                certificate_file = certificate_generator.generate_certificate(purchase)
                certificate_url = f"/media/{certificate_file}"
                
            except Exception as e:
                logger.error(f"Certificate generation failed: {str(e)}")
                # Continue without certificate
        
        # Prepare comprehensive response
        response_data = {
            'success': True,
            'carbon_entry_id': carbon_entry.id,
            'amount': float(amount),
            'effective_amount': validation_result.get('effective_amount'),
            'source': source_id,
            'establishment_id': establishment.id,
            'production_id': production.id if production else None,
            
            # Security and verification information
            'security_validation': {
                'trust_score': validation_result.get('trust_score'),
                'gaming_risk_score': gaming_risk_score,
                'anti_gaming_flags': validation_result.get('anti_gaming_flags', []),
                'blockchain_verified': validation_result.get('blockchain_verification_required', False),
                'audit_required': validation_result.get('requires_audit', False)
            },
            
            # Verification details
            'verification': {
                'level': verification_level,
                'status': carbon_entry.verification_status,
                'audit_status': carbon_entry.audit_status,
                'badge': carbon_entry.verification_badge
            },
            
            # Warnings and recommendations
            'warnings': validation_result.get('warnings', []),
            'recommendations': [],
            
            # Certificate information
            'certificate_url': certificate_url,
            
            # Trust and adjustment details
            'trust_adjustments': validation_result.get('trust_adjustments', {}),
            
            # Compliance information
            'compliance': {
                'usda_verified': carbon_entry.usda_verified,
                'verification_complete': carbon_entry.documentation_complete,
                'evidence_provided': carbon_entry.evidence_requirements_met
            }
        }
        
        # Add recommendations based on validation results
        if gaming_risk_score > 0.5:
            response_data['recommendations'].append(
                'Consider upgrading to certified verification for better trust scores'
            )
        
        if float(amount) >= 100 and verification_level == 'self_reported':
            response_data['recommendations'].append(
                'High-value offsets benefit from certified project verification'
            )
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error in secure offset creation for user {request.user.id}: {str(e)}")
        
        # Create error audit log
        CarbonAuditLog.objects.create(
            user=request.user,
            action='create',
            details=f'Secure offset creation failed: {str(e)}',
            ip_address=get_client_ip(request)
        )
        
        return Response({
            'error': 'Offset creation failed',
            'message': 'An error occurred while processing your request. Please try again.',
            'support_contact': 'support@trazo.com',
            'error_id': f"ERR_{timezone.now().timestamp()}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@method_decorator(csrf_protect)
@ratelimit(key='user', rate='5/m', method='POST', block=True)
def validate_file_upload_security(request):
    """
    Validate file upload security before allowing upload.
    
    This endpoint provides comprehensive server-side file validation
    to prevent malicious file uploads and ensure compliance with
    security policies.
    """
    try:
        file_data = request.data
        
        # Validate file security
        validation_result = backend_security_validator.validate_file_upload_security(file_data)
        
        if not validation_result['valid']:
            return Response({
                'error': 'File validation failed',
                'violations': validation_result['violations'],
                'warnings': validation_result.get('warnings', [])
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': True,
            'message': 'File passed security validation',
            'file_info': {
                'name': file_data.get('name'),
                'type': file_data.get('type'),
                'size': file_data.get('size')
            },
            'warnings': validation_result.get('warnings', [])
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"File upload validation error: {str(e)}")
        return Response({
            'error': 'File validation failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='60/m', method='GET', block=True)
def get_user_security_status(request):
    """
    Get current user's security status and trust metrics.
    
    This endpoint provides transparency about the user's trust score,
    gaming detection status, and verification recommendations.
    """
    try:
        user = request.user
        
        # Get user trust history
        trust_history = backend_security_validator._get_user_trust_history(user)
        
        # Calculate overall trust score using the same logic as offset validation
        # but without specific offset data
        base_score = 0.5  # Default for self-reported level
        
        # Adjust based on user history
        history_adjustment = 0
        if trust_history['total_verified_offsets'] > 10:
            history_adjustment += 0.1
        if trust_history['audit_pass_rate'] > 0.9:
            history_adjustment += 0.1
        if trust_history['gaming_violations'] == 0:
            history_adjustment += 0.05
        else:
            history_adjustment -= 0.1 * trust_history['gaming_violations']
        
        # Calculate overall trust score (without current submission adjustments)
        overall_trust_score = max(0.1, min(1.0, base_score + history_adjustment))
        
        # Get recent security events
        recent_violations = CarbonAuditLog.objects.filter(
            user=user,
            action='gaming_detected',
            timestamp__gte=timezone.now() - timezone.timedelta(days=30)
        ).count()
        
        # Get rate limit status
        rapid_key = f"rapid_submissions:{user.id}"
        rapid_count = cache.get(rapid_key, 0)
        
        security_status = {
            'trust_metrics': {
                'total_verified_offsets': trust_history['total_verified_offsets'],
                'audit_pass_rate': trust_history['audit_pass_rate'],
                'recent_violations': recent_violations,
                'account_standing': 'good' if recent_violations == 0 else 'flagged'
            },
            'overall_trust_score': overall_trust_score,
            'gaming_detection': {
                'risk_level': 'low' if recent_violations == 0 else 'high',
                'recent_violations': recent_violations,
                'gaming_score': min(recent_violations * 0.2, 1.0),  # 0-1 scale
                'last_violation': None  # Could add timestamp if needed
            },
            'rate_limits': {
                'rapid_submissions_remaining': max(0, 
                    backend_security_validator.SECURITY_LIMITS['MAX_RAPID_SUBMISSIONS'] - rapid_count
                ),
                'daily_self_reported_used': cache.get(
                    f"daily_self_reported:{user.id}:{timezone.now().date()}", 0
                ),
                'daily_self_reported_limit': backend_security_validator.SECURITY_LIMITS['MAX_DAILY_SELF_REPORTED']
            },
            'security_flags': [
                {
                    'type': 'account_flagged',
                    'severity': 'high',
                    'message': 'Account flagged due to recent gaming violations'
                }
            ] if recent_violations > 0 else [],
            'verification_recommendations': [],
            'security_features': {
                'csrf_protection': True,
                'rate_limiting': True,
                'gaming_detection': True,
                'blockchain_verification': True,
                'audit_trail': True
            }
        }
        
        # Add personalized recommendations based on trust score and metrics
        recommendations = []
        
        if overall_trust_score < 0.6:
            recommendations.append('Focus on improving your overall trust score to access more features')
        
        if trust_history['total_verified_offsets'] < 5:
            recommendations.append('Consider using certified projects to build trust score')
        elif trust_history['total_verified_offsets'] < 10:
            recommendations.append('Continue building trust with more verified offset projects')
        
        if trust_history['audit_pass_rate'] < 0.8:
            recommendations.append('Improve audit pass rate by providing better documentation')
        elif trust_history['audit_pass_rate'] < 0.9:
            recommendations.append('Enhance documentation quality to achieve excellent audit rates')
        
        if recent_violations > 0:
            recommendations.append('Address recent violations to restore account standing')
            recommendations.append('Follow platform guidelines to avoid future flagging')
        
        if overall_trust_score >= 0.8:
            recommendations.append('Excellent trust score! You have access to all platform features')
        
        # Add recommendations for improving trust score
        if overall_trust_score < 0.8:
            recommendations.append('Add evidence photos and documents to increase trust')
            recommendations.append('Participate in community verification to build credibility')
        
        security_status['verification_recommendations'] = recommendations
        
        return Response(security_status, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error getting security status for user {request.user.id}: {str(e)}")
        return Response({
            'error': 'Failed to get security status'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


import json
from django.core.cache import cache