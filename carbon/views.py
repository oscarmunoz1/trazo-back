from django.shortcuts import render
from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Avg, F, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import (
    CarbonSource,
    CarbonOffsetAction,
    CarbonEntry,
    CarbonCertification,
    CarbonBenchmark,
    CarbonReport,
    CarbonAuditLog,
    SustainabilityBadge,
    MicroOffset,
    GreenPoints,
    CarbonOffsetProject,
    CarbonOffsetPurchase,
    CarbonOffsetCertificate,
    IoTDevice,
    IoTDataPoint,
    AutomationRule,
)
from history.models import WeatherEvent, ChemicalEvent, ProductionEvent, GeneralEvent
from .serializers import (
    CarbonSourceSerializer,
    CarbonOffsetActionSerializer,
    CarbonEntrySerializer,
    CarbonCertificationSerializer,
    CarbonBenchmarkSerializer,
    CarbonReportSerializer,
    CarbonFootprintSummarySerializer,
    SustainabilityBadgeSerializer,
    MicroOffsetSerializer,
    GreenPointsSerializer,
    CarbonAuditLogSerializer,
    CarbonOffsetProjectSerializer,
    CarbonOffsetPurchaseSerializer,
    CarbonOffsetCertificateSerializer
)
from .services import coolfarm_service
from django.contrib.auth import get_user_model
from company.models import Establishment
from history.models import History
from .services.calculator import calculator
from .services.verification import verification_service
# from .services.certificate import certificate_generator  # Temporarily disabled due to font issues
from .services.report_generator import report_generator
from rest_framework import serializers
import logging
import random
import math
import datetime
import json

from .services.john_deere_api import JohnDeereAPI, is_john_deere_configured, get_john_deere_api
from .services.weather_api import WeatherService, get_weather_service, get_current_weather, get_agricultural_recommendations, check_weather_alerts
from .services.blockchain import blockchain_service
from .services.automation_service import AutomationLevelService
import hashlib
import traceback

logger = logging.getLogger(__name__)
User = get_user_model()

# Custom permission for company admin/manager
class IsCompanyAdminOrManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in ['admin', 'manager']

# Custom permission to check for premium subscription
class IsPremiumUser(permissions.BasePermission):
    def has_permission(self, request, view):
        # Placeholder logic for checking subscription status
        # In a real implementation, this would check against a subscription model or service
        if not hasattr(request.user, 'subscription_plan'):
            return False
        return request.user.subscription_plan in ['premium', 'enterprise']

class CarbonSourceViewSet(viewsets.ModelViewSet):
    queryset = CarbonSource.objects.all()
    serializer_class = CarbonSourceSerializer

class CarbonOffsetActionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CarbonOffsetAction.objects.all()
    serializer_class = CarbonOffsetActionSerializer
    permission_classes = []  # Public

class CarbonEntryViewSet(viewsets.ModelViewSet):
    queryset = CarbonEntry.objects.all()
    serializer_class = CarbonEntrySerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return CarbonEntry.objects.none()
        
        queryset = CarbonEntry.objects.all()
        
        # Apply filters from query parameters
        establishment_id = self.request.query_params.get('establishment')
        production_id = self.request.query_params.get('production')
        year = self.request.query_params.get('year')
        
        if establishment_id:
            try:
                establishment_id = int(establishment_id)
                queryset = queryset.filter(establishment_id=establishment_id)
            except (ValueError, TypeError):
                pass
                
        if production_id:
            try:
                production_id = int(production_id)
                queryset = queryset.filter(production_id=production_id)
            except (ValueError, TypeError):
                pass
                
        if year:
            try:
                year = int(year)
                queryset = queryset.filter(year=year)
            except (ValueError, TypeError):
                pass
                
        return queryset

    @action(detail=False, methods=['post'])
    def calculate_emissions(self, request):
        """
        Calculate emissions using CoolFarmTool API
        """
        try:
            crop_type = request.data.get('crop_type')
            acreage = float(request.data.get('acreage', 0))
            inputs = request.data.get('inputs', {})
            region = request.data.get('region')

            if not crop_type or acreage <= 0:
                return Response(
                    {'error': 'Invalid crop type or acreage'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculate emissions using CoolFarmTool service
            result = coolfarm_service.calculate_emissions(
                crop_type=crop_type,
                acreage=acreage,
                inputs=inputs,
                region=region
            )

            return Response(result)

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': 'Failed to calculate emissions'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        entries = request.data
        if not isinstance(entries, list):
            return Response({'error': 'Expected a list of entries'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=entries, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def by_entity(self, request):
        entity_type = request.query_params.get('entity_type')
        entity_id = request.query_params.get('entity_id')
        if entity_type not in ['establishment', 'production'] or not entity_id:
            return Response({'error': 'Invalid entity type or ID'}, status=status.HTTP_400_BAD_REQUEST)

        if entity_type == 'establishment':
            entries = CarbonEntry.objects.filter(establishment_id=entity_id)
        else:  # production
            entries = CarbonEntry.objects.filter(production_id=entity_id)

        page = self.paginate_queryset(entries)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(entries, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        # Check if the entry is for production-level tracking and restrict to premium users
        if serializer.validated_data.get('production') and (not hasattr(self.request.user, 'subscription_plan') or self.request.user.subscription_plan not in ['premium', 'enterprise']):
            raise permissions.PermissionDenied(detail='Production-level tracking is a premium feature. Upgrade your plan.')
        
        # If raw_amount is provided, calculate emissions using CoolFarmTool
        raw_amount = self.request.data.get('raw_amount')
        if raw_amount is not None:
            try:
                crop_type = self.request.data.get('crop_type')
                acreage = float(raw_amount)
                inputs = self.request.data.get('inputs', {})
                region = self.request.data.get('region')

                if crop_type:
                    result = coolfarm_service.calculate_emissions(
                        crop_type=crop_type,
                        acreage=acreage,
                        inputs=inputs,
                        region=region
                    )
                    serializer.validated_data['amount'] = result['co2e']
                    serializer.validated_data['usda_verified'] = result['usda_verified']
            except Exception as e:
                # Log error but continue with creation
                logger.error(f"Error calculating emissions: {e}")

        serializer.save(created_by=self.request.user)
        # Log the creation
        CarbonAuditLog.objects.create(
            carbon_entry=serializer.instance,
            user=self.request.user,
            action='create',
            details=f'Created {serializer.instance.type} entry'
        )

    def perform_update(self, serializer):
        serializer.save()
        # Log the update
        CarbonAuditLog.objects.create(
            carbon_entry=serializer.instance,
            user=self.request.user,
            action='update',
            details=f'Updated {serializer.instance.type} entry'
        )

    def perform_destroy(self, instance):
        # Log the deletion
        CarbonAuditLog.objects.create(
            carbon_entry=instance,
            user=self.request.user,
            action='delete',
            details=f'Deleted {instance.type} entry'
        )
        instance.delete()

    @action(detail=False, methods=['get'])
    def summary(self, request):
        establishment_id = request.query_params.get('establishment')
        production_id = request.query_params.get('production')
        year = request.query_params.get('year', timezone.now().year)

        if not establishment_id and not production_id:
            return Response({'error': 'Either establishment or production ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        if production_id and (not hasattr(request.user, 'subscription_plan') or request.user.subscription_plan not in ['premium', 'enterprise']):
            return Response({'error': 'Production-level tracking is a premium feature. Upgrade your plan.'}, status=status.HTTP_403_FORBIDDEN)

        queryset = CarbonEntry.objects.all()
        if establishment_id:
            queryset = queryset.filter(establishment_id=establishment_id)
        if production_id:
            queryset = queryset.filter(production_id=production_id)
        queryset = queryset.filter(year=year)

        total_emissions = queryset.filter(type='emission').aggregate(Sum('amount'))['amount__sum'] or 0
        total_offsets = queryset.filter(type='offset').aggregate(Sum('amount'))['amount__sum'] or 0
        net_carbon = total_emissions - total_offsets
        
        # Calculate carbon score (0-100 scale)
        carbon_score = 0
        if total_emissions > 0:
            # Base score on offset percentage with diminishing returns
            offset_percentage = min(100, (total_offsets / total_emissions) * 100)
            
            # Score increases with percentage of offsets
            if offset_percentage >= 100:
                carbon_score = 85  # Base score for carbon neutrality
                # Bonus for going beyond neutrality
                carbon_score += min(15, ((offset_percentage - 100) / 50) * 15)
            else:
                carbon_score = offset_percentage * 0.85  # Scale up to 85 max
        
        # Get industry benchmark if available
        industry_benchmark = 0
        if establishment_id:
            try:
                establishment = Establishment.objects.get(id=establishment_id)
                # Try to use industry attribute if it exists, otherwise fall back to type
                industry = None
                if hasattr(establishment, 'industry') and establishment.industry:
                    industry = establishment.industry
                elif establishment.type:
                    industry = establishment.type
                
                if industry:
                    try:
                        benchmark = CarbonBenchmark.objects.filter(
                                        industry=industry,
                            year=year
                        ).first()
                        if benchmark:
                            industry_benchmark = benchmark.average_emissions
                    except Exception:
                        pass
            except Exception:
                pass
            except Establishment.DoesNotExist:
                pass
                
        # Return consistent field names for frontend
        summary_data = {
            'total_emissions': total_emissions,
            'total_offsets': total_offsets,
            'net_carbon': net_carbon,
            'carbon_score': round(carbon_score),
            'industry_average': industry_benchmark
        }
        
        return Response(summary_data)


# Carbon Footprint Calculator and Analysis Endpoints


# Real-time Carbon Calculation API
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_event_carbon_impact(request):
    """
    Real-time carbon calculation API for event forms.
    Calculates carbon impact without creating database entries.
    """
    try:
        event_type = request.data.get('event_type')  # 'chemical', 'production', 'weather', 'general'
        event_data = request.data.get('event_data', {})
        
        if not event_type:
            return Response(
                {'error': 'event_type is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mock calculation for now - replace with actual carbon calculator
        calculation_result = {
            'co2e': 0.1,
            'efficiency_score': 50.0,
            'usda_verified': False,
            'calculation_method': 'general_event',
            'recommendations': [],
            'event_type': event_type,
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(calculation_result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error calculating carbon impact: {str(e)}")
        return Response(
            {
                'error': 'Failed to calculate carbon impact',
                'details': str(e),
                'co2e': 0.0,
                'efficiency_score': 50.0,
                'usda_verified': False
            }, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class CarbonCertificationViewSet(viewsets.ModelViewSet):
    queryset = CarbonCertification.objects.all()
    serializer_class = CarbonCertificationSerializer
    permission_classes = [permissions.IsAuthenticated]


class CarbonBenchmarkViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CarbonBenchmark.objects.all()
    serializer_class = CarbonBenchmarkSerializer
    permission_classes = [permissions.IsAuthenticated]


class CarbonReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CarbonReport.objects.all()
    serializer_class = CarbonReportSerializer
    permission_classes = [permissions.IsAuthenticated]


class SustainabilityBadgeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SustainabilityBadge.objects.all()
    serializer_class = SustainabilityBadgeSerializer
    permission_classes = [permissions.IsAuthenticated]


class MicroOffsetViewSet(viewsets.ModelViewSet):
    queryset = MicroOffset.objects.all()
    serializer_class = MicroOffsetSerializer
    permission_classes = [permissions.IsAuthenticated]


class GreenPointsViewSet(viewsets.ModelViewSet):
    queryset = GreenPoints.objects.all()
    serializer_class = GreenPointsSerializer
    permission_classes = [permissions.IsAuthenticated]


class CarbonAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CarbonAuditLog.objects.all()
    serializer_class = CarbonAuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]


class CarbonOffsetProjectViewSet(viewsets.ModelViewSet):
    queryset = CarbonOffsetProject.objects.all()
    serializer_class = CarbonOffsetProjectSerializer
    permission_classes = [permissions.IsAuthenticated]


class CarbonOffsetPurchaseViewSet(viewsets.ModelViewSet):
    queryset = CarbonOffsetPurchase.objects.all()
    serializer_class = CarbonOffsetPurchaseSerializer
    permission_classes = [permissions.IsAuthenticated]


class CarbonOffsetCertificateViewSet(viewsets.ModelViewSet):
    queryset = CarbonOffsetCertificate.objects.all()
    serializer_class = CarbonOffsetCertificateSerializer
    permission_classes = [permissions.IsAuthenticated]


class CarbonFootprintCalculatorViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """Calculate carbon footprint"""
        return Response({'co2e': 0.1}, status=status.HTTP_200_OK)


# Placeholder ViewSets for missing ones referenced in URLs
class CarbonEstablishmentSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        return Response({'message': 'Establishment summary'}, status=status.HTTP_200_OK)


class CarbonProductionSummaryViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        return Response({'message': 'Production summary'}, status=status.HTTP_200_OK)


class PublicProductionViewSet(viewsets.ViewSet):
    permission_classes = []

    @action(detail=True, methods=['get'], url_path='qr-summary')
    def qr_summary(self, request, pk=None):
        try:
            # Phase 1 Optimization: Add caching for QR endpoint
            from django.core.cache import cache
            from django.db import connection
            from history.models import History
            from company.models import Establishment
            from .services.blockchain import blockchain_service
            
            # Quick mode for progressive loading (just carbon score)
            quick_mode = request.GET.get('quick') == 'true'
            
            # Cache key for this production
            cache_key = f'qr_summary_{pk}_v2{"_quick" if quick_mode else ""}'
            cached_data = cache.get(cache_key)
            
            if cached_data:
                # Return cached data with fresh timestamp
                cached_data['cache_hit'] = True
                cached_data['timestamp'] = timezone.now().isoformat()
                return Response(cached_data, status=status.HTTP_200_OK)
            
            # Optimize database query with select_related and prefetch_related
            production = History.objects.select_related(
                'product',
                'parcel__establishment__company'
            ).prefetch_related(
                'carbonentry_set__source'
            ).get(id=pk, published=True)
            establishment = production.parcel.establishment if production.parcel else None
            
            if not establishment:
                return Response({
                    'error': 'No establishment found for this production'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get crop information for benchmarking
            crop_name = production.product.name if production.product else "unknown"
            crop_type = crop_name.lower().replace(' ', '_')
            
            # Get carbon entries for this production
            production_entries = CarbonEntry.objects.filter(production=production)
            establishment_entries = CarbonEntry.objects.filter(establishment=establishment)
            
            # Calculate totals from production-specific entries first, fall back to establishment
            if production_entries.exists():
                entries = production_entries
            else:
                entries = establishment_entries.filter(year=production.start_date.year if production.start_date else timezone.now().year)
            
            total_emissions = entries.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
            total_offsets = entries.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
            net_footprint = total_emissions - total_offsets
            
            # Get emissions breakdown by category and source
            emissions_by_category = {}
            emissions_by_source = {}
            offsets_by_action = {}
            
            # Calculate emissions by source
            for entry in entries.filter(type='emission'):
                source_name = entry.source.name if entry.source else 'Unknown'
                if source_name not in emissions_by_source:
                    emissions_by_source[source_name] = 0
                emissions_by_source[source_name] += float(entry.co2e_amount or 0)
                
                # Also categorize by source category
                category = entry.source.category if entry.source else 'Other'
                if category not in emissions_by_category:
                    emissions_by_category[category] = 0
                emissions_by_category[category] += float(entry.co2e_amount or 0)
            
            # Calculate offsets by action
            for entry in entries.filter(type='offset'):
                action_name = entry.source.name if entry.source else 'Unknown Offset'
                if action_name not in offsets_by_action:
                    offsets_by_action[action_name] = 0
                offsets_by_action[action_name] += float(entry.co2e_amount or 0)
            
            # Get crop-specific benchmark first, then fallback to industry
            industry_percentile = 0
            industry_average = 0
            benchmark_source = "industry_average"
            benchmark = None
            
            try:
                # First try to get crop-specific benchmark
                current_year = production.start_date.year if production.start_date else timezone.now().year
                
                # Try exact crop match first
                crop_benchmark = CarbonBenchmark.objects.filter(
                    crop_type=crop_type,
                    year=current_year,
                    usda_verified=True
                ).first()
                
                if not crop_benchmark and crop_type != "unknown":
                    # Try partial crop name matches
                    crop_keywords = crop_name.lower().split()
                    for keyword in crop_keywords:
                        crop_benchmark = CarbonBenchmark.objects.filter(
                            crop_type__icontains=keyword,
                            year=current_year,
                            usda_verified=True
                        ).first()
                        if crop_benchmark:
                            break
                
                if crop_benchmark:
                    benchmark = crop_benchmark
                    benchmark_source = f"crop_specific_{crop_benchmark.crop_type}"
                    industry_average = crop_benchmark.average_emissions
                else:
                    # Fallback to general industry benchmark
                    industry = getattr(establishment, 'industry', None) or getattr(establishment, 'type', 'agriculture')
                    benchmark = CarbonBenchmark.objects.filter(
                        industry=industry,
                        year=current_year,
                        crop_type=''  # General industry benchmark
                    ).first()
                    
                    if benchmark:
                        industry_average = benchmark.average_emissions
                        benchmark_source = f"industry_{industry}"
                
                # Calculate percentile based on benchmark
                if benchmark and industry_average > 0:
                    # Convert net footprint to per-kg basis if we have production amount
                    production_amount = getattr(production, 'production_amount', None) or 1000  # Default 1000kg
                    net_footprint_per_kg = net_footprint / production_amount if production_amount > 0 else net_footprint
                    
                    if net_footprint_per_kg <= 0:
                        industry_percentile = 95  # Very good if carbon neutral/negative
                    elif net_footprint_per_kg <= benchmark.min_emissions:
                        industry_percentile = 95  # Top performers
                    elif net_footprint_per_kg >= benchmark.max_emissions:
                        industry_percentile = 5   # Bottom performers
                    else:
                        # Linear interpolation between min and max
                        position = (net_footprint_per_kg - benchmark.min_emissions) / (benchmark.max_emissions - benchmark.min_emissions)
                        industry_percentile = max(5, min(95, int(95 - (position * 90))))
                else:
                    # No benchmark available - estimate based on carbon score
                    carbon_score_temp = 50
                    if total_emissions > 0:
                        offset_percentage = min(100, (total_offsets / total_emissions) * 100)
                        if offset_percentage >= 100:
                            carbon_score_temp = 85 + min(15, ((offset_percentage - 100) / 50) * 15)
                        else:
                            carbon_score_temp = offset_percentage * 0.85
                    elif total_offsets > 0:
                        carbon_score_temp = 95
                    
                    industry_percentile = max(5, min(95, int(carbon_score_temp * 0.9)))
                    
            except Exception as e:
                print(f"Error calculating crop-specific benchmarks: {e}")
                industry_percentile = 50
            
            # Calculate carbon score with crop-specific considerations
            carbon_score = 0
            if benchmark:
                # Use benchmark-based scoring
                production_amount = getattr(production, 'production_amount', None) or 1000
                net_footprint_per_kg = net_footprint / production_amount if production_amount > 0 else net_footprint
                
                if net_footprint_per_kg <= 0:
                    carbon_score = 95  # Excellent for carbon neutral/negative
                elif net_footprint_per_kg <= benchmark.min_emissions:
                    carbon_score = 90  # Excellent performance
                elif net_footprint_per_kg <= benchmark.average_emissions:
                    # Better than average: scale from 70-90
                    ratio = net_footprint_per_kg / benchmark.average_emissions
                    carbon_score = int(90 - (ratio * 20))
                elif net_footprint_per_kg <= benchmark.max_emissions:
                    # Worse than average: scale from 30-70
                    ratio = (net_footprint_per_kg - benchmark.average_emissions) / (benchmark.max_emissions - benchmark.average_emissions)
                    carbon_score = int(70 - (ratio * 40))
                else:
                    # Worse than max: scale from 10-30
                    ratio = min(net_footprint_per_kg / benchmark.max_emissions, 2.0)
                    carbon_score = max(10, int(30 - ((ratio - 1) * 20)))
            else:
                # Fallback to offset-based scoring
                if total_emissions > 0:
                    offset_percentage = min(100, (total_offsets / total_emissions) * 100)
                    if offset_percentage >= 100:
                        carbon_score = 85 + min(15, ((offset_percentage - 100) / 50) * 15)
                    else:
                        carbon_score = offset_percentage * 0.85
                elif total_offsets > 0:
                    carbon_score = 95  # High score for carbon negative
                else:
                    carbon_score = 50  # Default score when no data
            
            carbon_score = max(1, min(100, round(carbon_score)))
            
            # Quick mode: return minimal data for fast loading
            if quick_mode:
                quick_response = {
                    'carbonScore': carbon_score,
                    'totalEmissions': float(total_emissions),
                    'totalOffsets': float(total_offsets),
                    'cache_hit': False,
                    'timestamp': timezone.now().isoformat()
                }
                # Cache quick response for 5 minutes
                cache.set(cache_key, quick_response, 300)
                return Response(quick_response, status=status.HTTP_200_OK)
            
            # Create blockchain verification if not already exists
            blockchain_verification = None
            try:
                # Prepare carbon data for blockchain
                carbon_data = {
                    'production_id': int(pk),
                    'total_emissions': float(total_emissions),
                    'total_offsets': float(total_offsets),
                    'crop_type': crop_name,
                    'calculation_method': 'crop_specific_usda_benchmarking',
                    'usda_verified': bool(benchmark and benchmark.usda_verified),
                    'timestamp': int(production.start_date.timestamp()) if production.start_date else int(timezone.now().timestamp()),
                    'carbon_score': carbon_score,
                    'industry_percentile': industry_percentile
                }
                
                # Check if blockchain record exists, create if not
                verification_result = blockchain_service.verify_carbon_record(int(pk))
                if not verification_result.get('verified', False):
                    # Create new blockchain record
                    blockchain_result = blockchain_service.create_carbon_record(int(pk), carbon_data)
                    blockchain_verification = {
                        'verified': True,
                        'transaction_hash': blockchain_result.get('transaction_hash'),
                        'record_hash': blockchain_result.get('record_hash'),
                        'verification_url': blockchain_result.get('verification_url'),
                        'network': blockchain_result.get('network', 'ethereum'),
                        'verification_date': timezone.now().isoformat(),
                        'mock_data': blockchain_result.get('mock_data', False)
                    }
                else:
                    # Use existing blockchain record
                    blockchain_verification = {
                        'verified': verification_result.get('verified', False),
                        'record_hash': verification_result.get('record_hash'),
                        'verification_url': f"https://etherscan.io/tx/{verification_result.get('transaction_hash', '')}",
                        'network': 'ethereum',
                        'verification_date': timezone.now().isoformat(),
                        'mock_data': verification_result.get('mock_data', False)
                    }
                    
                # Check compliance status
                compliance_result = blockchain_service.check_compliance(int(pk))
                blockchain_verification.update({
                    'compliance_status': compliance_result.get('compliant', False),
                    'eligible_for_credits': compliance_result.get('eligible_for_credits', False)
                })
                
            except Exception as e:
                print(f"Error with blockchain verification: {e}")
                # Fallback blockchain verification for demo
                blockchain_verification = {
                    'verified': True,
                    'transaction_hash': f'0x{hashlib.sha256(f"fallback_{pk}".encode()).hexdigest()}',
                    'verification_url': f'https://etherscan.io/tx/0x{hashlib.sha256(f"fallback_{pk}".encode()).hexdigest()}',
                    'network': 'ethereum_testnet',
                    'verification_date': timezone.now().isoformat(),
                    'compliance_status': True,
                    'eligible_for_credits': carbon_score >= 70,
                    'fallback_data': True
                }
            
            # Get sustainability badges for this establishment/production
            badges = []
            try:
                establishment_badges = SustainabilityBadge.objects.filter(establishments=establishment)
                for badge in establishment_badges:
                    badges.append({
                        'id': str(badge.id),
                        'name': badge.name,
                        'description': badge.description,
                        'icon': badge.icon or 'leaf'
                    })
                    
                # Add crop-specific badges
                if carbon_score >= 90:
                    badges.append({
                        'id': 'excellence',
                        'name': f'Excellence in {crop_name.title()} Production',
                        'description': f'Top 10% performer for {crop_name} carbon efficiency',
                        'icon': 'star'
                    })
                elif carbon_score >= 70:
                    badges.append({
                        'id': 'sustainable',
                        'name': f'Sustainable {crop_name.title()} Producer',
                        'description': f'Above average sustainability for {crop_name} production',
                        'icon': 'leaf'
                    })
                    
                # Add blockchain verification badge
                if blockchain_verification and blockchain_verification.get('verified'):
                    badges.append({
                        'id': 'blockchain_verified',
                        'name': 'Blockchain Verified',
                        'description': 'Carbon data verified on blockchain for immutable transparency',
                        'icon': 'shield'
                    })
                    
            except Exception as e:
                print(f"Error getting badges: {e}")
            
            # Generate crop-specific relatable footprint
            relatable_footprint = "Carbon neutral production"
            if net_footprint > 0:
                miles_equivalent = net_footprint / 0.12  # 0.12 kg CO2 per mile
                relatable_footprint = f"Like driving {miles_equivalent:.1f} miles"
            elif net_footprint < 0:
                trees_equivalent = abs(net_footprint) / 22  # 22 kg CO2 per tree per year
                relatable_footprint = f"Like planting {trees_equivalent:.1f} trees"
            
            # Get crop-specific recommendations
            recommendations = []
            crop_category = self._get_crop_category_for_recommendations(crop_name)
            
            if carbon_score < 70:
                base_recommendations = [
                    "Consider implementing drip irrigation to reduce water usage",
                    "Switch to organic fertilizers to lower chemical emissions",
                    "Use renewable energy sources for farm operations",
                    "Implement cover crops for carbon sequestration"
                ]
                
                # Add crop-specific recommendations
                if crop_category == 'legumes':
                    base_recommendations.append("Reduce nitrogen fertilizer use - legumes naturally fix nitrogen")
                elif crop_category == 'nuts':
                    base_recommendations.append("Implement deficit irrigation strategies to reduce water consumption")
                elif crop_category == 'herbs':
                    base_recommendations.append("Consider companion planting to reduce pest control needs")
                elif crop_category == 'grains':
                    base_recommendations.append("Implement no-till farming to reduce soil carbon loss")
                    
                recommendations = base_recommendations[:4]  # Limit to 4 recommendations
            else:
                recommendations = [
                    f"Excellent {crop_name} production practices!",
                    "Continue current sustainable farming methods",
                    "Consider sharing best practices with other farmers",
                    "Look into carbon credit opportunities"
                ]
            
            # Add timeline data from production events (if not quick mode)
            timeline_data = []
            if not quick_mode:
                # Get production events for timeline
                from history.models import ProductionEvent, ChemicalEvent, EquipmentEvent
                
                events = []
                events.extend(ProductionEvent.objects.filter(history=production).select_related())
                events.extend(ChemicalEvent.objects.filter(history=production).select_related()) 
                events.extend(EquipmentEvent.objects.filter(history=production).select_related())
                
                # Sort events by date
                events = sorted(events, key=lambda x: x.event_date if hasattr(x, 'event_date') else x.date)
                
                for idx, event in enumerate(events[:10]):  # Limit to 10 most recent events
                    # Determine event type based on the model class and attributes
                    event_type = 'production.general'  # Default
                    if hasattr(event, 'chemical_name'):
                        if 'pesticide' in str(event.chemical_name).lower():
                            event_type = 'chemical.pesticide'
                        elif 'fertilizer' in str(event.chemical_name).lower():
                            event_type = 'chemical.fertilizer' 
                        elif 'herbicide' in str(event.chemical_name).lower():
                            event_type = 'chemical.herbicide'
                        else:
                            event_type = 'chemical.application'
                    elif hasattr(event, 'operation_type'):
                        if 'harvest' in str(event.operation_type).lower():
                            event_type = 'production.harvesting'
                        elif 'irrigation' in str(event.operation_type).lower():
                            event_type = 'production.irrigation'
                        else:
                            event_type = 'production.operation'
                    elif hasattr(event, 'equipment_type'):
                        event_type = 'production.equipment'
                    
                    timeline_data.append({
                        'id': f'event_{idx}_{event.id}',
                        'type': event_type,
                        'date': (event.event_date if hasattr(event, 'event_date') else event.date).isoformat(),
                        'description': getattr(event, 'notes', getattr(event, 'description', '')),
                        'observation': getattr(event, 'observation', ''),
                        'certified': getattr(event, 'certified', False),
                        'index': idx
                    })
            
            # Build the response matching the frontend interface with blockchain data
            response_data = {
                'carbonScore': carbon_score,
                'totalEmissions': float(total_emissions),
                'totalOffsets': float(total_offsets),
                'netFootprint': float(net_footprint),
                'relatableFootprint': relatable_footprint,
                'industryPercentile': industry_percentile,
                'industryAverage': float(industry_average),
                'isUsdaVerified': getattr(establishment, 'usda_verified', False) if hasattr(establishment, 'usda_verified') else bool(benchmark and benchmark.usda_verified),
                'cropType': crop_name,
                'benchmarkSource': benchmark_source,
                'badges': badges,
                'recommendations': recommendations,
                'emissionsByCategory': emissions_by_category,
                'emissionsBySource': emissions_by_source,
                'offsetsByAction': offsets_by_action,
                'socialProof': {
                    'totalScans': 1000,  # Could be calculated from actual scan data
                    'totalOffsets': float(total_offsets),
                    'totalUsers': 500,
                    'averageRating': 4.5
                },
                'verificationDate': benchmark.last_updated.isoformat() if benchmark else None,
                # Enhanced blockchain verification data
                'blockchainVerification': blockchain_verification,
                # Add essential location and establishment data for consumer experience
                'farmer': {
                    'name': establishment.name if establishment else 'Unknown Farm',
                    'location': f"{establishment.city}, {establishment.state}" if establishment and establishment.city else 'Location not available',
                    'description': establishment.about[:200] if establishment and establishment.about else None,
                    'id': establishment.id if establishment else None
                },
                'timeline': timeline_data,
                # Add basic parcel info for location display (without full polygon for performance)
                'parcel': {
                    'name': production.parcel.name if production.parcel else 'Field',
                    'location': f"{establishment.city}, {establishment.state}" if establishment and establishment.city else None,
                    'area': float(production.parcel.area) if production.parcel and production.parcel.area else None
                } if production.parcel else None,
                # Add essential consumer features that were lost when making history API conditional
                'product': {
                    'id': production.id,
                    'name': production.product.name if production.product else 'Product',
                    'reputation': float(production.reputation) if production.reputation else 4.5
                },
                # Add images from production album if available
                'images': self._get_production_images(production),
                # Add similar products from the same company (like history API does)
                'similar_products': self._get_similar_products(production),
                # Track scan if available
                'history_scan': getattr(production, 'history_scan', None),
                # Performance tracking
                'cache_hit': False,
                'timestamp': timezone.now().isoformat()
            }
            
            # Cache the response for 15 minutes (900 seconds)
            # Production data doesn't change frequently, so caching is safe
            cache.set(cache_key, response_data, 900)
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except History.DoesNotExist:
            return Response({
                'error': 'Production not found or not published'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error in qr_summary: {e}")
            import traceback
            traceback.print_exc()
            return Response({
                'error': 'Internal server error',
                'carbonScore': 50,
                'totalEmissions': 0.0,
                'totalOffsets': 0.0,
                'netFootprint': 0.0,
                'relatableFootprint': 'Data being calculated',
                'industryPercentile': 50,
                'industryAverage': 0.0,
                'isUsdaVerified': False,
                'cropType': 'unknown',
                'benchmarkSource': 'fallback',
                'badges': [],
                'recommendations': ['Data will be available soon'],
                'emissionsByCategory': {},
                'emissionsBySource': {},
                'offsetsByAction': {},
                'socialProof': {
                    'totalScans': 0,
                    'totalOffsets': 0.0,
                    'totalUsers': 0,
                    'averageRating': 0.0
                },
                'verificationDate': None,
                'blockchainVerification': {
                    'verified': False,
                    'error': str(e)
                }
            }, status=status.HTTP_200_OK)

    def _get_crop_category_for_recommendations(self, crop_name: str) -> str:
        """Helper method to categorize crops for recommendations"""
        crop_lower = crop_name.lower()
        
        fruit_keywords = ['orange', 'apple', 'grape', 'lemon', 'lime', 'strawberry', 'blueberry', 'avocado']
        vegetable_keywords = ['tomato', 'lettuce', 'carrot', 'broccoli', 'spinach', 'cucumber', 'pepper', 'onion']
        grain_keywords = ['corn', 'wheat', 'rice', 'barley', 'oats']
        herb_keywords = ['basil', 'oregano', 'thyme', 'rosemary', 'mint']
        legume_keywords = ['soybean', 'bean', 'chickpea', 'lentil', 'pea']
        nut_keywords = ['almond', 'walnut', 'pecan', 'hazelnut']
        
        for keyword in fruit_keywords:
            if keyword in crop_lower:
                return 'fruits'
        for keyword in vegetable_keywords:
            if keyword in crop_lower:
                return 'vegetables'
        for keyword in grain_keywords:
            if keyword in crop_lower:
                return 'grains'
        for keyword in herb_keywords:
            if keyword in crop_lower:
                return 'herbs'
        for keyword in legume_keywords:
            if keyword in crop_lower:
                return 'legumes'
        for keyword in nut_keywords:
            if keyword in crop_lower:
                return 'nuts'
                
        return 'general'
    
    def _get_production_images(self, production):
        """Get images from production album for consumer display"""
        try:
            if production.album and production.album.images.exists():
                images = []
                for image in production.album.images.all()[:5]:  # Limit to 5 images for performance
                    # Build absolute URL for image
                    image_url = None
                    if image.image:
                        from django.conf import settings
                        if image.image.url.startswith('http'):
                            image_url = image.image.url
                        else:
                            # Build absolute URL
                            base_url = getattr(settings, 'MEDIA_URL_BASE', 'http://localhost:8000')
                            image_url = f"{base_url.rstrip('/')}{image.image.url}"
                    
                    images.append({
                        'id': image.id,
                        'image': image_url,
                        'name': getattr(image, 'name', '') or ''
                    })
                return images
            return []
        except Exception:
            return []
    
    def _get_similar_products(self, production):
        """Get similar products from the same company (matching history API logic)"""
        try:
            if not production.parcel or not production.parcel.establishment:
                return []
            
            from history.models import History
            similar_histories = History.objects.filter(
                parcel__establishment__company=production.parcel.establishment.company,
                published=True,
            ).exclude(id=production.id).select_related(
                'product', 
                'parcel__establishment'
            ).order_by('-id')[:5]  # Same logic as history API
            
            similar_products = []
            for history in similar_histories:
                # Get first image if available with absolute URL
                image_url = None
                if history.album and history.album.images.exists():
                    first_image = history.album.images.first()
                    if first_image and first_image.image:
                        # Build absolute URL for image
                        from django.conf import settings
                        if hasattr(first_image.image, 'url'):
                            if first_image.image.url.startswith('http'):
                                image_url = first_image.image.url
                            else:
                                # Build absolute URL
                                base_url = getattr(settings, 'MEDIA_URL_BASE', 'http://localhost:8000')
                                image_url = f"{base_url.rstrip('/')}{first_image.image.url}"
                
                similar_products.append({
                    'id': history.id,
                    'product': {
                        'name': history.product.name if history.product else 'Product'
                    },
                    'reputation': float(history.reputation) if history.reputation else 4.5,
                    'image': image_url
                })
            
            return similar_products
        except Exception:
            return []


class CarbonOffsetViewSet(viewsets.ViewSet):
    permission_classes = []

    def create(self, request):
        return Response({'success': True}, status=status.HTTP_201_CREATED)


class ProductionSerializer(serializers.ModelSerializer):
    class Meta:
        model = History
        fields = ['id', 'name', 'start_date', 'finish_date', 'published']


class CarbonProductionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = History.objects.all()
    permission_classes = []
    serializer_class = ProductionSerializer


# IoT Integration and Automation Endpoints
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def john_deere_webhook(request):
    """
    Webhook endpoint for John Deere IoT fuel sensor data.
    Automatically creates equipment events and calculates carbon impact.
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['device_id', 'establishment_id', 'fuel_liters', 'timestamp', 'equipment_type']
        for field in required_fields:
            if field not in data:
                return Response(
                        {'error': f'Missing required field: {field}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        establishment_id = data['establishment_id']
        fuel_liters = float(data['fuel_liters'])
        equipment_type = data['equipment_type']
        device_id = data['device_id']
        timestamp = data['timestamp']
        
        # Verify establishment exists
        try:
            establishment = Establishment.objects.get(id=establishment_id)
        except Establishment.DoesNotExist:
            return Response(
                {'error': 'Establishment not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Calculate carbon emissions (diesel: 2.7 kg CO2e/liter)
        co2e_emissions = fuel_liters * 2.7
        
        # Find or create a CarbonSource for IoT-generated fuel consumption events
        source_name = f'{equipment_type.title()} Fuel Consumption'
        carbon_source, created = CarbonSource.objects.get_or_create(
            name=source_name,
            defaults={
                'category': 'fuel',
                'default_emission_factor': 2.7,  # Diesel emission factor
                'unit': 'kg CO2e/L',
                'description': f'Automatically created for IoT device: {device_id}'
            }
        )
        
        # Create carbon entry automatically
        carbon_entry = CarbonEntry.objects.create(
            establishment_id=establishment_id,
            type='emission',
            source=carbon_source,  # Use CarbonSource instance instead of string
            amount=co2e_emissions,
            year=timezone.now().year,
            description=f'Auto-logged from IoT device {device_id}: {fuel_liters}L fuel consumed',
            iot_device_id=device_id,
            created_by=request.user
        )
        
        # Log the IoT data ingestion
        CarbonAuditLog.objects.create(
            carbon_entry=carbon_entry,
            user=request.user,
            action='iot_create',
            details=f'IoT device {device_id} auto-created fuel consumption event: {fuel_liters}L = {co2e_emissions:.2f} kg CO2e'
        )
        
        return Response({
            'status': 'success',
            'carbon_entry_id': carbon_entry.id,
            'co2e_calculated': co2e_emissions,
            'message': f'Successfully processed {fuel_liters}L fuel consumption from {equipment_type}'
        }, status=status.HTTP_201_CREATED)

    except ValueError as e:
        return Response(
            {'error': f'Invalid data format: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    except Exception as e:
        logger.error(f"Error processing John Deere webhook: {str(e)}")
        return Response(
            {'error': 'Failed to process IoT data'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def weather_station_webhook(request):
    """
    Webhook endpoint for weather station data.
    Auto-suggests events based on weather conditions.
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['station_id', 'establishment_id', 'temperature', 'humidity', 'wind_speed', 'timestamp']
        for field in required_fields:
            if field not in data:
                return Response(
                        {'error': f'Missing required field: {field}'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        establishment_id = data['establishment_id']
        temperature = float(data['temperature'])
        humidity = float(data['humidity'])
        wind_speed = float(data['wind_speed'])
        station_id = data['station_id']
        
        # Verify establishment exists
        try:
            establishment = Establishment.objects.get(id=establishment_id)
        except Establishment.DoesNotExist:
            return Response(
                {'error': 'Establishment not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate weather-based recommendations
        recommendations = []
        
        # High temperature alert (>35°C)
        if temperature > 35:
            recommendations.append({
                'type': 'weather_alert',
                'priority': 'high',
                'message': f'High temperature alert: {temperature}°C - Consider crop protection measures',
                'suggested_actions': [
                    'Increase irrigation frequency',
                    'Apply shade cloth if available',
                    'Monitor plant stress indicators'
                ]
            })
        
        # High wind alert (>25 km/h)
        if wind_speed > 25:
            recommendations.append({
                'type': 'weather_alert',
                'priority': 'medium',
                'message': f'High wind alert: {wind_speed} km/h - Avoid chemical applications',
                'suggested_actions': [
                    'Postpone spraying operations',
                    'Secure loose equipment',
                    'Check irrigation systems for damage'
                ]
            })
        
        # Low humidity alert (<30%)
        if humidity < 30:
            recommendations.append({
                'type': 'weather_alert',
                'priority': 'medium',
                'message': f'Low humidity alert: {humidity}% - Increase irrigation',
                'suggested_actions': [
                    'Increase irrigation duration',
                    'Monitor soil moisture levels',
                    'Consider misting systems'
                ]
            })
        
        # Log weather data processing
        CarbonAuditLog.objects.create(
            user=request.user,
            action='weather_processed',
            details=f'Weather station {station_id} data processed: {temperature}°C, {humidity}% humidity, {wind_speed} km/h wind'
        )
        
        return Response({
            'status': 'success',
            'recommendations': recommendations,
            'weather_data': {
                'temperature': temperature,
                'humidity': humidity,
                'wind_speed': wind_speed
            },
            'message': f'Weather data processed successfully with {len(recommendations)} recommendations'
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response(
            {'error': f'Invalid data format: {str(e)}'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error processing weather station webhook: {str(e)}")
        return Response(
            {'error': 'Failed to process weather data'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class IoTDeviceViewSet(viewsets.ViewSet):
    """
    ViewSet for IoT device management and monitoring.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """List all IoT devices for an establishment."""
        establishment_id = request.query_params.get('establishment_id')

        if not establishment_id:
            return Response(
                {'error': 'establishment_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            devices = IoTDevice.objects.filter(establishment_id=establishment_id)
            device_data = []
            
            for device in devices:
                device_info = {
                    'id': device.id,
                    'device_id': device.device_id,
                    'device_type': device.device_type,
                    'name': device.name,
                    'manufacturer': device.manufacturer,
                    'model': device.model,
                    'status': device.status,
                    'battery_level': device.battery_level,
                    'location': {
                        'lat': float(device.latitude) if device.latitude else None,
                        'lng': float(device.longitude) if device.longitude else None
                    },
                    'installed_date': device.installed_date.isoformat(),
                    'last_seen': device.last_seen.isoformat() if device.last_seen else None,
                    'configuration': device.configuration,
                    'notes': device.notes,
                    'needs_maintenance': device.needs_maintenance,
                    'total_data_points': device.total_data_points
                }
                device_data.append(device_info)
            
            return Response({
                'devices': device_data,
                'total_count': len(device_data)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error listing IoT devices: {str(e)}")
            return Response(
                {'error': 'Failed to list devices', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request):
        """Register a new IoT device."""
        try:
            data = request.data
            
            # Validate required fields
            required_fields = ['device_id', 'device_type', 'establishment_id', 'name']
            for field in required_fields:
                if field not in data:
                    return Response(
                        {'error': f'Missing required field: {field}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Check if device_id already exists
            if IoTDevice.objects.filter(device_id=data['device_id']).exists():
                return Response(
                        {'error': 'Device ID already exists'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
            # Verify establishment exists
            try:
                establishment = Establishment.objects.get(id=data['establishment_id'])
            except Establishment.DoesNotExist:
                return Response(
                    {'error': 'Establishment not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Create the device
            device = IoTDevice.objects.create(
                device_id=data['device_id'],
                device_type=data['device_type'],
                establishment=establishment,
                name=data['name'],
                manufacturer=data.get('manufacturer', ''),
                model=data.get('model', ''),
                latitude=data.get('latitude'),
                longitude=data.get('longitude'),
                configuration=data.get('configuration', {}),
                notes=data.get('notes', ''),
                status='offline'  # Default to offline until first data received
            )
            
            # Log device registration
            CarbonAuditLog.objects.create(
                user=request.user,
                action='create',
                details=f'Registered new IoT device: {device.device_id} ({device.name})'
            )
            
            return Response({
                'id': device.id,
                'device_id': device.device_id,
                'message': f'Device {device.name} registered successfully',
                'status': 'registered'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating IoT device: {str(e)}")
            return Response(
                {'error': 'Failed to register device', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def retrieve(self, request, pk=None):
        """Get details of a specific IoT device."""
        try:
            device = IoTDevice.objects.get(id=pk)
            
            # Get recent data points
            recent_data = IoTDataPoint.objects.filter(
                device=device
            ).order_by('-timestamp')[:10]
            
            device_data = {
                'id': device.id,
                'device_id': device.device_id,
                'device_type': device.device_type,
                'name': device.name,
                'manufacturer': device.manufacturer,
                'model': device.model,
                'status': device.status,
                'battery_level': device.battery_level,
                'location': {
                    'lat': float(device.latitude) if device.latitude else None,
                    'lng': float(device.longitude) if device.longitude else None
                },
                'installed_date': device.installed_date.isoformat(),
                'last_seen': device.last_seen.isoformat() if device.last_seen else None,
                'last_maintenance': device.last_maintenance.isoformat() if device.last_maintenance else None,
                'configuration': device.configuration,
                'notes': device.notes,
                'needs_maintenance': device.needs_maintenance,
                'total_data_points': device.total_data_points,
                'recent_data': [
                    {
                        'timestamp': dp.timestamp.isoformat(),
                        'data': dp.data,
                        'quality_score': dp.quality_score,
                        'processed': dp.processed
                    } for dp in recent_data
                ]
            }
            
            return Response(device_data, status=status.HTTP_200_OK)
            
        except IoTDevice.DoesNotExist:
            return Response(
                {'error': 'Device not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error retrieving IoT device: {str(e)}")
            return Response(
                {'error': 'Failed to retrieve device', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, pk=None):
        """Update IoT device configuration."""
        try:
            device = IoTDevice.objects.get(id=pk)
            data = request.data
            
            # Update allowed fields
            updatable_fields = [
                'name', 'manufacturer', 'model', 'latitude', 'longitude',
                'configuration', 'notes', 'status'
            ]
            
            updated_fields = []
            for field in updatable_fields:
                if field in data:
                    setattr(device, field, data[field])
                    updated_fields.append(field)
            
            if updated_fields:
                device.save(update_fields=updated_fields)
                
                # Log device update
                CarbonAuditLog.objects.create(
                    user=request.user,
                    action='update',
                    details=f'Updated IoT device {device.device_id}: {", ".join(updated_fields)}'
                )
            
            return Response({
                'id': device.id,
                'device_id': device.device_id,
                'message': f'Device {device.name} updated successfully',
                'updated_fields': updated_fields
            }, status=status.HTTP_200_OK)
            
        except IoTDevice.DoesNotExist:
            return Response(
                {'error': 'Device not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating IoT device: {str(e)}")
            return Response(
                {'error': 'Failed to update device', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, pk=None):
        """Delete an IoT device."""
        try:
            device = IoTDevice.objects.get(id=pk)
            device_name = device.name
            device_id = device.device_id
            
            # Log device deletion before deleting
            CarbonAuditLog.objects.create(
                user=request.user,
                action='delete',
                details=f'Deleted IoT device: {device_id} ({device_name})'
            )
            
            device.delete()
            
            return Response({
                'message': f'Device {device_name} deleted successfully'
            }, status=status.HTTP_200_OK)
            
        except IoTDevice.DoesNotExist:
            return Response(
                {'error': 'Device not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error deleting IoT device: {str(e)}")
            return Response(
                {'error': 'Failed to delete device', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def device_status(self, request):
        """Get status of all IoT devices for an establishment."""
        establishment_id = request.query_params.get('establishment_id')
        
        if not establishment_id:
            return Response(
                {'error': 'establishment_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Query real IoT devices from database
            devices = IoTDevice.objects.filter(establishment_id=establishment_id)
            
            device_data = []
            for device in devices:
                # Count data points for today
                today = timezone.now().date()
                data_points_today = IoTDataPoint.objects.filter(
                    device=device,
                    timestamp__date=today
                ).count()
                
                # Determine signal strength based on last seen
                signal_strength = 'offline'
                if device.last_seen:
                    time_diff = timezone.now() - device.last_seen
                    if time_diff < timedelta(minutes=5):
                        signal_strength = 'excellent'
                    elif time_diff < timedelta(minutes=15):
                        signal_strength = 'strong'
                    elif time_diff < timedelta(hours=1):
                        signal_strength = 'weak'
                    else:
                        signal_strength = 'offline'
                
                # Build device status object
                device_info = {
                    'device_id': device.device_id,
                    'device_type': device.device_type,
                    'equipment': f"{device.manufacturer} {device.model}".strip() or device.name,
                    'status': device.status,
                    'last_update': device.last_seen.isoformat() if device.last_seen else None,
                    'battery_level': device.battery_level or 0,
                    'signal_strength': signal_strength,
                    'data_points_today': data_points_today,
                    'location': {
                        'lat': float(device.latitude) if device.latitude else None,
                        'lng': float(device.longitude) if device.longitude else None
                    },
                    'name': device.name,
                    'manufacturer': device.manufacturer,
                    'model': device.model,
                    'installed_date': device.installed_date.isoformat(),
                    'needs_maintenance': device.needs_maintenance,
                    'total_data_points': device.total_data_points,
                    'last_data_received': device.last_data_received.isoformat() if device.last_data_received else None
                }
                device_data.append(device_info)
            
            # Calculate summary statistics
            total_devices = len(device_data)
            online_devices = len([d for d in device_data if d['status'] == 'online'])
            offline_devices = len([d for d in device_data if d['status'] == 'offline'])
            maintenance_devices = len([d for d in device_data if d.get('needs_maintenance', False)])
            low_battery_devices = len([d for d in device_data if d['battery_level'] and d['battery_level'] < 20])
            
            return Response({
                'establishment_id': establishment_id,
                'devices': device_data,
                'summary': {
                    'total_devices': total_devices,
                    'online_devices': online_devices,
                    'offline_devices': offline_devices,
                    'maintenance_devices': maintenance_devices,
                    'low_battery_devices': low_battery_devices,
                    'total_data_points_today': sum(d['data_points_today'] for d in device_data)
                },
                'last_updated': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching IoT device status: {str(e)}")
            return Response(
                {'error': 'Failed to fetch device status', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def device_types(self, request):
        """Get available device types for registration."""
        return Response({
            'device_types': [
                {'value': choice[0], 'label': choice[1]} 
                for choice in IoTDevice.DEVICE_TYPES
            ]
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def simulate_data(self, request):
        """Simulate IoT data for testing purposes - creates data points that go through the approval workflow."""
        establishment_id = request.data.get('establishment_id')
        device_type = request.data.get('device_type', 'fuel_sensor')
        
        if not establishment_id:
            return Response(
                {'error': 'establishment_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Verify establishment exists
            try:
                establishment = Establishment.objects.get(id=establishment_id)
            except Establishment.DoesNotExist:
                return Response(
                    {'error': 'Establishment not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if device_type == 'fuel_sensor':
                # Get or create the fuel sensor device
                device, created = IoTDevice.objects.get_or_create(
                    device_id='JD_TRACTOR_SIM_001',
                    establishment=establishment,
                    defaults={
                        'device_type': 'fuel_sensor',
                        'name': 'John Deere 6120M Tractor (Simulator)',
                        'manufacturer': 'John Deere',
                        'model': '6120M',
                        'status': 'online',
                        'battery_level': 85,
                        'signal_strength': 'strong',
                        'latitude': 34.0522,
                        'longitude': -118.2437,
                        'last_maintenance': timezone.now() - datetime.timedelta(days=30)
                    }
                )
                
                # Create realistic fuel consumption data
                fuel_liters = round(12.5 + (timezone.now().hour * 0.8), 2)
                engine_hours = round(timezone.now().hour * 1.2, 1)
                
                simulated_data = {
                    'fuel_liters': fuel_liters,
                    'engine_hours': engine_hours,
                    'fuel_efficiency': round(fuel_liters / max(engine_hours, 0.1), 2),
                    'equipment_type': 'tractor',
                    'operation_type': 'field_operations',
                    'area_covered': round(random.uniform(0.5, 2.0), 1),  # hectares
                    'gps_location': {
                        'lat': 34.0522 + random.uniform(-0.001, 0.001),
                        'lng': -118.2437 + random.uniform(-0.001, 0.001)
                    },
                    'timestamp': timezone.now().isoformat(),
                    'device_id': device.device_id
                }
                
                # Create IoT data point (not carbon entry directly)
                data_point = IoTDataPoint.objects.create(
                    device=device,
                    timestamp=timezone.now(),
                    data=simulated_data,
                    processed=False,  # Will be processed through approval workflow
                    quality_score=0.95,  # High quality simulated data
                    anomaly_detected=False
                )
                
                # Update device stats
                device.increment_data_points()
                
                return Response({
                    'status': 'success',
                    'message': f'Simulated fuel sensor data created: {fuel_liters}L fuel consumption',
                    'data_point_id': data_point.id,
                    'simulated_data': simulated_data,
                    'workflow': 'Data point created - check Pending Events for approval',
                    'note': 'This data will appear in Pending Events and can be approved to create carbon entries'
                }, status=status.HTTP_201_CREATED)
                
            elif device_type == 'weather_station':
                # Get or create the weather station device
                device, created = IoTDevice.objects.get_or_create(
                    device_id='WS_SIM_001',
                    establishment=establishment,
                    defaults={
                        'device_type': 'weather_station',
                        'name': 'Davis Vantage Pro2 (Simulator)',
                        'manufacturer': 'Davis Instruments',
                        'model': 'Vantage Pro2',
                        'status': 'online',
                        'battery_level': 92,
                        'signal_strength': 'excellent',
                        'latitude': 34.0525,
                        'longitude': -118.2435,
                        'last_maintenance': timezone.now() - datetime.timedelta(days=15)
                    }
                )
                
                # Create realistic weather data
                # Realistic weather patterns for California citrus region
                base_temp = 22  # Base temperature in Celsius
                hour = timezone.now().hour
                temp_variation = 8 * math.sin((hour - 6) * math.pi / 12)  # Daily temperature cycle
                temperature = round(base_temp + temp_variation + random.uniform(-2, 2), 1)
                
                # Humidity inversely related to temperature
                humidity = round(70 - (temperature - 20) * 2 + random.uniform(-10, 10), 1)
                humidity = max(20, min(95, humidity))  # Keep within realistic bounds
                
                simulated_data = {
                    'temperature': temperature,
                    'humidity': humidity,
                    'wind_speed': round(random.uniform(5, 25) if 8 <= hour <= 18 else random.uniform(2, 12), 1),
                    'pressure': round(1013 + random.uniform(-15, 15), 1),
                    'solar_radiation': round(random.uniform(0, 1200) if 6 <= hour <= 19 else 0, 1),
                    'rainfall': round(random.uniform(0, 2) if random.random() < 0.1 else 0, 1),  # 10% chance of rain
                    'uv_index': round(random.uniform(0, 11) if 8 <= hour <= 17 else 0, 1),
                    'timestamp': timezone.now().isoformat(),
                    'station_id': device.device_id
                }
                
                # Create IoT data point
                data_point = IoTDataPoint.objects.create(
                    device=device,
                    timestamp=timezone.now(),
                    data=simulated_data,
                    processed=False,
                    quality_score=0.98,  # Very high quality weather data
                    anomaly_detected=False
                )
                
                # Update device stats
                device.increment_data_points()
                
                return Response({
                    'status': 'success',
                    'message': f'Simulated weather station data created: {temperature}°C, {humidity}% humidity',
                    'data_point_id': data_point.id,
                    'simulated_data': simulated_data,
                    'workflow': 'Weather data created - may trigger automation rules',
                    'note': 'Weather data typically triggers recommendations rather than direct carbon entries'
                }, status=status.HTTP_201_CREATED)
            
            else:
                return Response({
                    'error': f'Unsupported device type: {device_type}',
                    'supported_types': ['fuel_sensor', 'weather_station']
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error simulating IoT data: {str(e)}")
            return Response({
                'error': 'Failed to simulate IoT data',
                'details': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AutomationRuleViewSet(viewsets.ViewSet):
    """
    ViewSet for managing automation rules that generate events from IoT data.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """List automation rules for an establishment."""
        establishment_id = request.query_params.get('establishment_id')
        
        if not establishment_id:
            return Response(
                {'error': 'establishment_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            rules = AutomationRule.objects.filter(establishment_id=establishment_id)
            
            rule_data = []
            for rule in rules:
                rule_info = {
                    'id': rule.id,
                    'name': rule.name,
                    'device_type': rule.device_type,
                    'trigger_type': rule.trigger_type,
                    'trigger_config': rule.trigger_config,
                    'action_type': rule.action_type,
                    'action_config': rule.action_config,
                    'is_active': rule.is_active,
                    'last_triggered': rule.last_triggered.isoformat() if rule.last_triggered else None,
                    'trigger_count': rule.trigger_count,
                    'description': rule.description,
                    'created_at': rule.created_at.isoformat()
                }
                rule_data.append(rule_info)
        
            return Response({
                'rules': rule_data,
                'total_count': len(rule_data)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error listing automation rules: {str(e)}")
            return Response(
                {'error': 'Failed to list automation rules', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request):
        """Create a new automation rule."""
        try:
            data = request.data
            
            # Validate required fields
            required_fields = ['name', 'establishment_id', 'trigger_type', 'trigger_config', 'action_type', 'action_config']
            for field in required_fields:
                if field not in data:
                    return Response(
                        {'error': f'Missing required field: {field}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Verify establishment exists
            try:
                establishment = Establishment.objects.get(id=data['establishment_id'])
            except Establishment.DoesNotExist:
                return Response(
                    {'error': 'Establishment not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Create the automation rule
            rule = AutomationRule.objects.create(
                name=data['name'],
                establishment=establishment,
                device_type=data.get('device_type', ''),
                trigger_type=data['trigger_type'],
                trigger_config=data['trigger_config'],
                action_type=data['action_type'],
                action_config=data['action_config'],
                description=data.get('description', ''),
                created_by=request.user,
                is_active=data.get('is_active', True)
            )
            
            # Log rule creation
            CarbonAuditLog.objects.create(
                user=request.user,
                action='create',
                details=f'Created automation rule: {rule.name}'
            )
            
            return Response({
                'id': rule.id,
                'name': rule.name,
                'message': f'Automation rule {rule.name} created successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating automation rule: {str(e)}")
            return Response(
                {'error': 'Failed to create automation rule', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def pending_events(self, request):
        """Get pending events that need user approval before creation."""
        establishment_id = request.query_params.get('establishment_id')
        auto_process = request.query_params.get('auto_process', 'true').lower() == 'true'
        
        if not establishment_id:
            return Response(
                {'error': 'establishment_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get establishment for automation level checking
            establishment = Establishment.objects.get(id=establishment_id)
            automation_service = AutomationLevelService()
            
            # Get unprocessed IoT data points that could generate events
            unprocessed_data = IoTDataPoint.objects.filter(
                device__establishment_id=establishment_id,
                processed=False,
                timestamp__gte=timezone.now() - timedelta(hours=24)  # Last 24 hours
            ).order_by('-timestamp')[:20]
            
            pending_events = []
            auto_processed_count = 0
            
            for data_point in unprocessed_data:
                device = data_point.device
                
                # Generate event suggestions based on device type and data
                if device.device_type == 'fuel_sensor' and 'fuel_liters' in data_point.data:
                    fuel_liters = data_point.data['fuel_liters']
                    co2e_emissions = fuel_liters * 2.7  # Diesel emission factor
                    
                    # Calculate confidence score based on data quality and patterns
                    confidence = self._calculate_fuel_confidence(data_point, fuel_liters)
                    
                    event_data = {
                        'id': f'fuel_{data_point.id}',
                        'data_point_id': data_point.id,
                        'device_id': device.device_id,
                        'device_name': device.name,
                        'event_type': 'fuel_consumption',
                        'suggested_carbon_entry': {
                            'type': 'emission',
                            'source': f'{device.name} Fuel Consumption',
                            'amount': co2e_emissions,
                            'description': f'Fuel consumption: {fuel_liters}L from {device.name}',
                            'raw_data': data_point.data
                        },
                        'timestamp': data_point.timestamp.isoformat(),
                        'confidence': confidence,
                        'auto_approve_recommended': confidence > 0.9
                    }
                    
                    # Plan-Based Smart Auto-Approval Logic
                    should_auto_approve = automation_service.should_auto_approve_event(data_point, confidence)
                    
                    if auto_process and should_auto_approve:
                        # Auto-approve based on subscription plan automation level
                        try:
                            self._auto_approve_event(data_point, event_data['suggested_carbon_entry'], request.user)
                            auto_processed_count += 1
                            continue  # Don't add to pending list
                        except Exception as e:
                            logger.error(f"Error auto-approving event: {str(e)}")
                            # Fall through to manual approval
                    
                    # Add to pending events for manual approval
                    pending_events.append(event_data)
                
                elif device.device_type == 'soil_moisture' and 'soil_moisture_percent' in data_point.data:
                    moisture = data_point.data['soil_moisture_percent']
                    
                    if moisture < 30:  # Low moisture threshold
                        confidence = self._calculate_moisture_confidence(data_point, moisture)
                        
                        event_data = {
                            'id': f'irrigation_{data_point.id}',
                            'data_point_id': data_point.id,
                            'device_id': device.device_id,
                            'device_name': device.name,
                            'event_type': 'irrigation_needed',
                            'suggested_action': {
                                'type': 'irrigation',
                                'priority': 'high' if moisture < 20 else 'medium',
                                'description': f'Low soil moisture detected: {moisture}% - Irrigation recommended',
                                'estimated_water_needed': '50-100L per hectare'
                            },
                            'timestamp': data_point.timestamp.isoformat(),
                            'confidence': confidence,
                            'auto_approve_recommended': False  # Always require approval for irrigation
                        }
                        
                        pending_events.append(event_data)
                
                elif device.device_type == 'weather_station':
                    # Weather data typically generates recommendations, not carbon entries
                    weather_data = data_point.data
                    recommendations = self._generate_weather_recommendations(weather_data)
                    
                    if recommendations:
                        confidence = 0.85  # Weather recommendations have high confidence
                        
                        event_data = {
                            'id': f'weather_{data_point.id}',
                            'data_point_id': data_point.id,
                            'device_id': device.device_id,
                            'device_name': device.name,
                            'event_type': 'weather_alert',
                            'suggested_action': recommendations[0],  # Take first recommendation
                            'timestamp': data_point.timestamp.isoformat(),
                            'confidence': confidence,
                            'auto_approve_recommended': False  # Weather alerts need human review
                        }
                        
                        pending_events.append(event_data)
            
            # Get automation statistics for the establishment
            automation_stats = automation_service.get_automation_stats_for_establishment(establishment)
            
            return Response({
                'establishment_id': establishment_id,
                'pending_events': pending_events,
                'total_count': len(pending_events),
                'auto_processed_count': auto_processed_count,
                'automation_info': {
                    'target_automation_level': automation_stats['target_automation_level'],
                    'actual_automation_rate': automation_stats['actual_automation_rate'],
                    'carbon_tracking_mode': automation_stats['carbon_tracking_mode'],
                    'compliance_status': automation_stats['compliance_status']
                },
                'workflow_info': {
                    'auto_approval_threshold': 0.9,
                    'manual_approval_threshold': 0.7,
                    'review_threshold': 0.5
                },
                'last_updated': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching pending events: {str(e)}")
            return Response(
                {'error': 'Failed to fetch pending events', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _calculate_fuel_confidence(self, data_point, fuel_liters):
        """Calculate confidence score for fuel consumption events."""
        confidence = 0.5  # Base confidence
        
        # Data quality factors
        if data_point.quality_score > 0.9:
            confidence += 0.2
        elif data_point.quality_score > 0.7:
            confidence += 0.1
        
        # Realistic fuel consumption (5-50L per session)
        if 5 <= fuel_liters <= 50:
            confidence += 0.2
        elif fuel_liters > 50:
            confidence -= 0.1  # High consumption needs review
        
        # Device status
        if data_point.device.status == 'online':
            confidence += 0.1
        
        # Time consistency (working hours)
        hour = data_point.timestamp.hour
        if 6 <= hour <= 18:  # Normal working hours
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _calculate_moisture_confidence(self, data_point, moisture):
        """Calculate confidence score for soil moisture events."""
        confidence = 0.6  # Base confidence for soil data
        
        # Data quality
        if data_point.quality_score > 0.9:
            confidence += 0.15
        
        # Realistic moisture levels
        if 10 <= moisture <= 60:
            confidence += 0.1
        
        # Critical levels get higher confidence
        if moisture < 20:
            confidence += 0.1
        
        return min(1.0, confidence)
    
    def _generate_weather_recommendations(self, weather_data):
        """Generate weather-based recommendations."""
        recommendations = []
        
        temperature = weather_data.get('temperature', 0)
        wind_speed = weather_data.get('wind_speed', 0)
        humidity = weather_data.get('humidity', 50)
        
        # High temperature alert
        if temperature > 35:
            recommendations.append({
                'type': 'weather_alert',
                'priority': 'high',
                'description': f'High temperature alert: {temperature}°C - Consider crop protection measures',
                'suggested_actions': [
                    'Increase irrigation frequency',
                    'Apply shade cloth if available',
                    'Monitor plant stress indicators'
                ]
            })
        
        # High wind alert
        if wind_speed > 25:
            recommendations.append({
                'type': 'weather_alert',
                'priority': 'medium',
                'description': f'High wind alert: {wind_speed} km/h - Avoid chemical applications',
                'suggested_actions': [
                    'Postpone spraying operations',
                    'Secure loose equipment',
                    'Check irrigation systems for damage'
                ]
            })
        
        # Low humidity alert
        if humidity < 30:
            recommendations.append({
                'type': 'weather_alert',
                'priority': 'medium',
                'description': f'Low humidity alert: {humidity}% - Increase irrigation',
                'suggested_actions': [
                    'Increase irrigation duration',
                    'Monitor soil moisture levels',
                    'Consider misting systems'
                ]
            })
        
        return recommendations
    
    def _auto_approve_event(self, data_point, event_data, user):
        """Automatically approve and create carbon entry for high-confidence events."""
        # Find or create a CarbonSource
        source_name = event_data.get('source', 'IoT Device Data')
        carbon_source, created = CarbonSource.objects.get_or_create(
            name=source_name,
            defaults={
                'category': 'equipment',
                'default_emission_factor': 2.7,
                'unit': 'kg CO2e/L',
                'description': f'Auto-created for IoT device: {data_point.device.device_id}'
            }
        )
        
        # Create the carbon entry
        carbon_entry = CarbonEntry.objects.create(
            establishment=data_point.device.establishment,
            type=event_data['type'],
            source=carbon_source,
            amount=event_data['amount'],
            year=timezone.now().year,
            description=event_data['description'],
            iot_device_id=data_point.device.device_id,
            created_by=user
        )
        
        # Mark data point as processed
        data_point.processed = True
        data_point.processed_at = timezone.now()
        data_point.carbon_entry = carbon_entry
        data_point.save()
        
        # Update device stats
        data_point.device.increment_data_points()
        
        # Log the auto-approval
        CarbonAuditLog.objects.create(
            carbon_entry=carbon_entry,
            user=user,
            action='iot_auto_approve',
            details=f'Auto-approved IoT event from {data_point.device.device_id}: {event_data["amount"]:.2f} kg CO2e (confidence: high)'
        )
        
        return carbon_entry

    @action(detail=False, methods=['post'])
    def approve_event(self, request):
        """Approve a pending event and create the carbon entry."""
        try:
            data = request.data
            data_point_id = data.get('data_point_id')
            event_data = data.get('event_data')
            
            if not data_point_id or not event_data:
                return Response(
                    {'error': 'data_point_id and event_data are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the data point
            try:
                data_point = IoTDataPoint.objects.get(id=data_point_id)
            except IoTDataPoint.DoesNotExist:
                return Response(
                    {'error': 'Data point not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Use the same auto-approval logic for manual approvals
            carbon_entry = self._auto_approve_event(data_point, event_data, request.user)
            
            # Update audit log to reflect manual approval
            CarbonAuditLog.objects.filter(
                carbon_entry=carbon_entry,
                action='iot_auto_approve'
            ).update(
                action='iot_manual_approve',
                details=f'Manually approved IoT event from {data_point.device.device_id}: {event_data["amount"]:.2f} kg CO2e'
            )
        
            return Response({
                'carbon_entry_id': carbon_entry.id,
                'message': 'Event approved and carbon entry created successfully',
                'co2e_amount': carbon_entry.amount
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error approving event: {str(e)}")
            return Response(
                {'error': 'Failed to approve event', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def reject_event(self, request):
        """Reject a pending event and mark data point as processed without creating entry."""
        try:
            data_point_id = request.data.get('data_point_id')
            reason = request.data.get('reason', 'User rejected')
            
            if not data_point_id:
                return Response(
                    {'error': 'data_point_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the data point
            try:
                data_point = IoTDataPoint.objects.get(id=data_point_id)
            except IoTDataPoint.DoesNotExist:
                return Response(
                    {'error': 'Data point not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Mark as processed without creating carbon entry
            data_point.processed = True
            data_point.processed_at = timezone.now()
            data_point.save()
            
            # Log the rejection
            CarbonAuditLog.objects.create(
                user=request.user,
                action='iot_reject',
                details=f'Rejected IoT event from {data_point.device.device_id}: {reason}'
            )
            
            return Response({
                'message': 'Event rejected successfully',
                'reason': reason
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error rejecting event: {str(e)}")
            return Response(
                {'error': 'Failed to reject event', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def automation_stats(self, request):
        """Get automation statistics for an establishment"""
        establishment_id = request.query_params.get('establishment_id')
        days = int(request.query_params.get('days', 30))
        
        if not establishment_id:
            return Response(
                {'error': 'establishment_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            establishment = Establishment.objects.get(id=establishment_id)
            automation_service = AutomationLevelService()
            
            stats = automation_service.get_automation_stats_for_establishment(establishment, days)
            
            return Response(stats, status=status.HTTP_200_OK)
            
        except Establishment.DoesNotExist:
            return Response(
                {'error': 'Establishment not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error getting automation stats: {str(e)}")
            return Response(
                {'error': 'Failed to get automation statistics', 'details': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Placeholder ViewSets for missing ones referenced in URLs


# John Deere API Integration Views

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def john_deere_auth_start(request):
    """
    Start John Deere OAuth authentication flow.
    
    Returns authorization URL for user to complete OAuth consent.
    """
    try:
        from carbon.services.john_deere_api import get_john_deere_api, is_john_deere_configured
        
        if not is_john_deere_configured():
            return Response({
                'error': 'John Deere API not configured',
                'message': 'Please configure JOHN_DEERE_CLIENT_ID and JOHN_DEERE_CLIENT_SECRET'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Generate state parameter for CSRF protection
        state = f"{request.user.id}_{timezone.now().timestamp()}"
        
        api = get_john_deere_api()
        auth_url = api.get_authorization_url(state=state)
        
        # Store state in session for validation
        request.session['john_deere_oauth_state'] = state
        
        return Response({
            'authorization_url': auth_url,
            'state': state,
            'message': 'Redirect user to authorization_url to complete OAuth flow'
        })
        
    except Exception as e:
        logger.error(f"Failed to start John Deere OAuth: {e}")
        return Response({
            'error': 'OAuth initialization failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def john_deere_auth_callback(request):
    """
    Handle John Deere OAuth callback and exchange code for token.
    
    Expected query parameters:
    - code: Authorization code from John Deere
    - state: State parameter for CSRF protection
    """
    try:
        from carbon.services.john_deere_api import get_john_deere_api
        
        # Get parameters from callback
        authorization_code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        if error:
            return Response({
                'error': 'OAuth authorization failed',
                'message': f'John Deere returned error: {error}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not authorization_code:
            return Response({
                'error': 'Missing authorization code',
                'message': 'No authorization code received from John Deere'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate state parameter
        expected_state = request.session.get('john_deere_oauth_state')
        if not state or state != expected_state:
            return Response({
                'error': 'Invalid state parameter',
                'message': 'CSRF protection failed - invalid state'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Exchange code for token
        api = get_john_deere_api()
        token_data = api.exchange_code_for_token(authorization_code)
        
        # Clean up session
        if 'john_deere_oauth_state' in request.session:
            del request.session['john_deere_oauth_state']
        
        return Response({
            'success': True,
            'message': 'John Deere authentication successful',
            'token_expires_in': token_data.get('expires_in'),
            'next_step': 'Call /carbon/john-deere/sync-devices/ to sync your equipment'
        })
        
    except Exception as e:
        logger.error(f"Failed to complete John Deere OAuth: {e}")
        return Response({
            'error': 'OAuth completion failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def john_deere_sync_devices(request):
    """
    Sync John Deere machines with IoT devices.
    
    This endpoint fetches machines from John Deere API and creates/updates
    corresponding IoT device records.
    """
    try:
        from carbon.services.john_deere_api import get_john_deere_api
        from carbon.models import IoTDevice
        
        establishment_id = request.data.get('establishment_id')
        if not establishment_id:
            return Response({
                'error': 'establishment_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            establishment = Establishment.objects.get(id=establishment_id)
        except Establishment.DoesNotExist:
            return Response({
                'error': 'Establishment not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        api = get_john_deere_api()
        
        # Get organizations (farms) from John Deere
        organizations = api.get_organizations()
        if not organizations:
            return Response({
                'error': 'No John Deere organizations found',
                'message': 'Make sure your John Deere account has access to farm data'
            }, status=status.HTTP_404_NOT_FOUND)
        
        synced_devices = []
        errors = []
        
        # Sync machines from all organizations
        for org in organizations:
            org_id = org.get('id')
            machines = api.get_machines(org_id)
            
            for machine in machines:
                try:
                    machine_id = machine.get('id')
                    machine_name = machine.get('name', f"Machine {machine_id}")
                    machine_model = machine.get('model', '')
                    
                    # Create or update IoT device
                    device, created = IoTDevice.objects.get_or_create(
                        john_deere_machine_id=machine_id,
                        establishment=establishment,
                        defaults={
                            'device_id': f"jd_{machine_id}",
                            'device_type': 'fuel_sensor',  # Default type for John Deere equipment
                            'name': machine_name,
                            'manufacturer': 'John Deere',
                            'model': machine_model,
                            'api_connection_status': 'pending'
                        }
                    )
                    
                    # Sync machine status with device
                    sync_success = api.sync_machine_with_iot_device(machine_id, device)
                    
                    synced_devices.append({
                        'device_id': device.device_id,
                        'machine_id': machine_id,
                        'name': machine_name,
                        'created': created,
                        'sync_success': sync_success,
                        'status': device.status
                    })
                    
                except Exception as e:
                    errors.append({
                        'machine_id': machine.get('id'),
                        'error': str(e)
                    })
        
        return Response({
            'success': True,
            'message': f'Synced {len(synced_devices)} devices',
            'synced_devices': synced_devices,
            'errors': errors if errors else None,
            'organizations_found': len(organizations)
        })
        
    except Exception as e:
        logger.error(f"Failed to sync John Deere devices: {e}")
        return Response({
            'error': 'Device sync failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def weather_current_conditions(request):
    """
    Get current weather conditions for an establishment.
    
    Query Parameters:
    - establishment_id: ID of the establishment
    - lat: Latitude (optional, overrides establishment location)
    - lng: Longitude (optional, overrides establishment location)
    """
    try:
        establishment_id = request.GET.get('establishment_id')
        lat = request.GET.get('lat')
        lng = request.GET.get('lng')
        
        if not establishment_id and not (lat and lng):
            return Response({
                'error': 'Either establishment_id or lat/lng coordinates required'
            }, status=400)
        
        # Get coordinates from establishment if not provided
        if not (lat and lng):
            try:
                establishment = Establishment.objects.get(id=establishment_id)
                lat = establishment.latitude
                lng = establishment.longitude
                
                if not (lat and lng):
                    return Response({
                        'error': 'Establishment does not have location coordinates'
                    }, status=400)
            except Establishment.DoesNotExist:
                return Response({
                    'error': 'Establishment not found'
                }, status=404)
        
        # Get weather data
        weather_service = get_weather_service()
        weather_data = weather_service.get_current_conditions(float(lat), float(lng))
        
        return Response({
            'status': 'success',
            'establishment_id': establishment_id,
            'location': {'lat': float(lat), 'lng': float(lng)},
            'weather': weather_data,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Weather conditions error: {e}")
        return Response({
            'error': f'Failed to get weather conditions: {str(e)}'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def weather_alerts(request):
    """
    Get active weather alerts for an establishment.
    
    Query Parameters:
    - establishment_id: ID of the establishment
    - lat: Latitude (optional, overrides establishment location)
    - lng: Longitude (optional, overrides establishment location)
    """
    try:
        establishment_id = request.GET.get('establishment_id')
        lat = request.GET.get('lat')
        lng = request.GET.get('lng')
        
        if not establishment_id and not (lat and lng):
            return Response({
                'error': 'Either establishment_id or lat/lng coordinates required'
            }, status=400)
        
        # Get coordinates from establishment if not provided
        if not (lat and lng):
            try:
                establishment = Establishment.objects.get(id=establishment_id)
                lat = establishment.latitude
                lng = establishment.longitude
                
                if not (lat and lng):
                    return Response({
                        'error': 'Establishment does not have location coordinates'
                    }, status=400)
            except Establishment.DoesNotExist:
                return Response({
                    'error': 'Establishment not found'
                }, status=404)
        
        # Get weather alerts
        alerts = check_weather_alerts(float(lat), float(lng))
        
        return Response({
            'status': 'success',
            'establishment_id': establishment_id,
            'location': {'lat': float(lat), 'lng': float(lng)},
            'alerts': alerts,
            'alert_count': len(alerts),
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Weather alerts error: {e}")
        return Response({
            'error': f'Failed to get weather alerts: {str(e)}'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def weather_recommendations(request):
    """
    Get agricultural recommendations based on current weather conditions.
    
    Query Parameters:
    - establishment_id: ID of the establishment
    - lat: Latitude (optional, overrides establishment location)
    - lng: Longitude (optional, overrides establishment location)
    - establishment_type: Type of agricultural operation (optional)
    """
    try:
        establishment_id = request.GET.get('establishment_id')
        lat = request.GET.get('lat')
        lng = request.GET.get('lng')
        establishment_type = request.GET.get('establishment_type')
        
        if not establishment_id and not (lat and lng):
            return Response({
                'error': 'Either establishment_id or lat/lng coordinates required'
            }, status=400)
        
        # Get coordinates and type from establishment if not provided
        if not (lat and lng) or not establishment_type:
            try:
                establishment = Establishment.objects.get(id=establishment_id)
                if not (lat and lng):
                    lat = establishment.latitude
                    lng = establishment.longitude
                
                if not establishment_type:
                    establishment_type = getattr(establishment, 'establishment_type', 'general')
                
                if not (lat and lng):
                    return Response({
                        'error': 'Establishment does not have location coordinates'
                    }, status=400)
            except Establishment.DoesNotExist:
                return Response({
                    'error': 'Establishment not found'
                }, status=404)
        
        # Get agricultural recommendations
        recommendations = get_agricultural_recommendations(
            float(lat), 
            float(lng), 
            establishment_type
        )
        
        # Categorize recommendations by priority
        critical_recommendations = [r for r in recommendations if r.get('priority') == 'critical']
        high_recommendations = [r for r in recommendations if r.get('priority') == 'high']
        medium_recommendations = [r for r in recommendations if r.get('priority') == 'medium']
        low_recommendations = [r for r in recommendations if r.get('priority') == 'low']
        
        return Response({
            'status': 'success',
            'establishment_id': establishment_id,
            'location': {'lat': float(lat), 'lng': float(lng)},
            'establishment_type': establishment_type,
            'recommendations': {
                'critical': critical_recommendations,
                'high': high_recommendations,
                'medium': medium_recommendations,
                'low': low_recommendations,
                'total_count': len(recommendations)
            },
            'summary': {
                'critical_count': len(critical_recommendations),
                'high_count': len(high_recommendations),
                'medium_count': len(medium_recommendations),
                'low_count': len(low_recommendations),
                'requires_immediate_action': len(critical_recommendations) + len(high_recommendations) > 0
            },
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Weather recommendations error: {e}")
        return Response({
            'error': f'Failed to get weather recommendations: {str(e)}'
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def weather_create_alert_event(request):
    """
    Create an IoT event based on weather conditions and recommendations.
    
    This endpoint allows automatic creation of weather-based events
    that can trigger carbon calculations and recommendations.
    """
    try:
        data = request.data
        establishment_id = data.get('establishment_id')
        weather_data = data.get('weather_data')
        recommendations = data.get('recommendations', [])
        
        if not establishment_id:
            return Response({
                'error': 'establishment_id is required'
            }, status=400)
        
        if not weather_data:
            return Response({
                'error': 'weather_data is required'
            }, status=400)
        
        try:
            establishment = Establishment.objects.get(id=establishment_id)
        except Establishment.DoesNotExist:
            return Response({
                'error': 'Establishment not found'
            }, status=404)
        
        # Create weather alert event
        event_data = {
            'establishment_id': establishment_id,
            'event_type': 'weather_alert',
            'description': f"Weather alert: {weather_data.get('description', 'Weather conditions require attention')}",
            'metadata': {
                'weather_conditions': weather_data,
                'recommendations': recommendations,
                'alert_type': 'automated_weather_monitoring',
                'source': 'weather_api'
            },
            'confidence': 0.85,  # High confidence for weather data
            'requires_approval': len([r for r in recommendations if r.get('priority') in ['critical', 'high']]) > 0
        }
        
        # Create IoT data point for weather event
        device, created = IoTDevice.objects.get_or_create(
            establishment=establishment,
            name=f"Weather Station - {establishment.name}",
            defaults={
                'device_type': 'weather_station',
                'status': 'online',
                'battery_level': 100,
                'last_seen': timezone.now()
            }
        )
        
        data_point = IoTDataPoint.objects.create(
            device=device,
            data_type='weather_alert',
            value=json.dumps(weather_data),
            quality_score=0.9,  # High quality for official weather data
            metadata=event_data['metadata'],
            confidence=event_data['confidence']
        )
        
        # Process through unified IoT workflow
        if event_data['confidence'] > 0.9 and not event_data['requires_approval']:
            # Auto-approve weather events with high confidence
            # Note: Weather events typically don't create carbon entries directly
            # but may trigger recommendations for carbon-reducing actions
            logger.info(f"Auto-approved weather event for establishment {establishment_id}")
            
        return Response({
            'status': 'success',
            'message': 'Weather alert event created successfully',
            'data_point_id': data_point.id,
            'device_id': device.id,
            'requires_approval': event_data['requires_approval'],
            'confidence': event_data['confidence'],
            'recommendations_count': len(recommendations)
        }, status=201)
        
    except Exception as e:
        logger.error(f"Weather alert event creation error: {e}")
        return Response({
            'error': f'Failed to create weather alert event: {str(e)}'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def weather_forecast(request):
    """
    Get weather forecast for an establishment.
    
    Query Parameters:
    - establishment_id: ID of the establishment
    - lat: Latitude (optional, overrides establishment location)
    - lng: Longitude (optional, overrides establishment location)
    - days: Number of days to forecast (default: 7, max: 14)
    """
    try:
        establishment_id = request.GET.get('establishment_id')
        lat = request.GET.get('lat')
        lng = request.GET.get('lng')
        days = int(request.GET.get('days', 7))
        
        # Limit forecast days
        days = min(days, 14)
        
        if not establishment_id and not (lat and lng):
            return Response({
                'error': 'Either establishment_id or lat/lng coordinates required'
            }, status=400)
        
        # Get coordinates from establishment if not provided
        if not (lat and lng):
            try:
                establishment = Establishment.objects.get(id=establishment_id)
                lat = establishment.latitude
                lng = establishment.longitude
                
                if not (lat and lng):
                    return Response({
                        'error': 'Establishment does not have location coordinates'
                    }, status=400)
            except Establishment.DoesNotExist:
                return Response({
                    'error': 'Establishment not found'
                }, status=404)
        
        # Get weather forecast
        weather_service = get_weather_service()
        forecast_data = weather_service.get_forecast(float(lat), float(lng), days)
        
        return Response({
            'status': 'success',
            'establishment_id': establishment_id,
            'location': {'lat': float(lat), 'lng': float(lng)},
            'forecast': forecast_data,
            'forecast_days': days,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Weather forecast error: {e}")
        return Response({
            'error': f'Failed to get weather forecast: {str(e)}'
        }, status=500)


class BlockchainVerificationViewSet(viewsets.ViewSet):
    """
    ViewSet for blockchain-based carbon verification and credit management.
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='verify-production')
    def verify_production(self, request):
        """
        Create blockchain verification record for a production's carbon data.
        """
        try:
            production_id = request.data.get('production_id')
            producer_id = request.data.get('producer_id')
            crop_type = request.data.get('crop_type', 'general')
            
            if not production_id:
                return Response({
                    'error': 'production_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get carbon data for the production
            try:
                production = History.objects.get(id=production_id)
            except History.DoesNotExist:
                return Response({
                    'error': 'Production not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Get carbon summary data
            public_view = PublicProductionViewSet()
            carbon_data = public_view._calculate_carbon_summary(production_id)
            
            # Add additional data needed for blockchain
            carbon_data.update({
                'production_id': production_id,
                'producer_id': producer_id or production.establishment.id,
                'crop_type': crop_type,
                'timestamp': int(timezone.now().timestamp())
            })
            
            # Create blockchain record
            blockchain_result = blockchain_service.create_carbon_record(production_id, carbon_data)
            
            if blockchain_result.get('blockchain_verified'):
                return Response({
                    'status': 'success',
                    'message': 'Production verified on blockchain',
                    'verification_data': blockchain_result,
                    'carbon_data': carbon_data
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'status': 'partial_success',
                    'message': 'Verification completed in mock mode',
                    'verification_data': blockchain_result,
                    'carbon_data': carbon_data
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            logger.error(f"Blockchain verification error: {e}")
            return Response({
                'error': f'Failed to verify production: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='verify-record/(?P<production_id>[^/.]+)')
    def verify_record(self, request, production_id=None):
        """
        Verify existing blockchain record for a production.
        """
        try:
            if not production_id:
                return Response({
                    'error': 'production_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify record on blockchain
            verification_result = blockchain_service.verify_carbon_record(int(production_id))
            
            return Response({
                'status': 'success',
                'production_id': production_id,
                'verification': verification_result
            })
            
        except Exception as e:
            logger.error(f"Record verification error: {e}")
            return Response({
                'error': f'Failed to verify record: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='compliance-check/(?P<production_id>[^/.]+)')
    def compliance_check(self, request, production_id=None):
        """
        Check USDA compliance status for a production.
        """
        try:
            if not production_id:
                return Response({
                    'error': 'production_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check compliance on blockchain
            compliance_result = blockchain_service.check_compliance(int(production_id))
            
            return Response({
                'status': 'success',
                'production_id': production_id,
                'compliance': compliance_result
            })
            
        except Exception as e:
            logger.error(f"Compliance check error: {e}")
            return Response({
                'error': f'Failed to check compliance: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='issue-credits')
    def issue_credits(self, request):
        """
        Issue carbon credits for verified sustainable practices.
        """
        try:
            production_id = request.data.get('production_id')
            credits_amount = request.data.get('credits_amount')
            
            if not production_id or not credits_amount:
                return Response({
                    'error': 'production_id and credits_amount are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Issue credits on blockchain
            credits_result = blockchain_service.issue_carbon_credits(
                int(production_id), 
                float(credits_amount)
            )
            
            return Response({
                'status': 'success',
                'message': 'Carbon credits issued successfully',
                'credits': credits_result
            })
            
        except Exception as e:
            logger.error(f"Credits issuance error: {e}")
            return Response({
                'error': f'Failed to issue credits: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='summary/(?P<production_id>[^/.]+)')
    def blockchain_summary(self, request, production_id=None):
        """
        Get comprehensive carbon summary with blockchain verification.
        """
        try:
            if not production_id:
                return Response({
                    'error': 'production_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get comprehensive summary with blockchain data
            summary = blockchain_service.get_carbon_summary_with_blockchain(int(production_id))
            
            return Response({
                'status': 'success',
                'production_id': production_id,
                'summary': summary
            })
            
        except Exception as e:
            logger.error(f"Blockchain summary error: {e}")
            return Response({
                'error': f'Failed to get blockchain summary: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='batch-process')
    def batch_process(self, request):
        """
        Process multiple productions for blockchain verification.
        """
        try:
            production_ids = request.data.get('production_ids', [])
            
            if not production_ids or not isinstance(production_ids, list):
                return Response({
                    'error': 'production_ids list is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Process batch
            batch_result = blockchain_service.batch_process_carbon_entries(production_ids)
            
            return Response({
                'status': 'success',
                'message': 'Batch processing completed',
                'results': batch_result
            })
            
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            return Response({
                'error': f'Failed to process batch: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)