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
from .services.cost_optimizer import CostOptimizer
from django.contrib.auth import get_user_model
from company.models import Establishment
from history.models import History
from .services.calculator import calculator
from .services.verification import verification_service
from .services.certificate import certificate_generator
from .services.report_generator import report_generator
from rest_framework import serializers
import logging

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


# ROI Calculation and Cost Optimization Endpoints
class CostOptimizationViewSet(viewsets.ViewSet):
    """
    ViewSet for cost optimization and ROI calculation services.
    Provides savings analysis and recommendations for agricultural operations.
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='calculate-savings')
    def calculate_savings(self, request):
        """
        Calculate comprehensive savings potential for an establishment.
        Expected payload: {'establishment_id': int}
        """
        try:
            establishment_id = request.data.get('establishment_id')
            
            if not establishment_id:
                return Response(
                    {'error': 'establishment_id is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify establishment exists
            try:
                establishment = Establishment.objects.get(id=establishment_id)
            except Establishment.DoesNotExist:
                return Response(
                    {'error': 'Establishment not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Initialize cost optimizer and calculate savings
            optimizer = CostOptimizer()
            savings_analysis = optimizer.calculate_savings_potential(establishment_id)
            
            # Log the analysis for audit trail
            CarbonAuditLog.objects.create(
                user=request.user,
                action='create',
                details=f'Generated savings analysis for establishment {establishment_id}'
            )
            
            return Response(savings_analysis, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error calculating savings potential: {str(e)}")
            return Response(
                {
                    'error': 'Failed to calculate savings potential',
                    'details': str(e),
                    'total_annual_savings': 0,
                    'recommendations': []
                }, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='equipment-marketplace')
    def equipment_marketplace(self, request):
        """
        Get equipment marketplace recommendations based on current usage patterns.
        Query params: establishment_id (required)
        """
        try:
            establishment_id = request.query_params.get('establishment_id')
            
            if not establishment_id:
                return Response(
                    {'error': 'establishment_id query parameter is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                establishment = Establishment.objects.get(id=establishment_id)
            except Establishment.DoesNotExist:
                return Response(
                    {'error': 'Establishment not found'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Mock equipment marketplace data (replace with real marketplace integration)
            equipment_recommendations = [
                {
                    'id': 'tractor_upgrade_2024',
                    'category': 'tractor',
                    'title': 'Fuel-Efficient Compact Tractor',
                    'brand': 'John Deere 3038E',
                    'description': 'Modern compact tractor with 30% better fuel efficiency',
                    'current_cost': 18000,
                    'annual_savings': 1200,
                    'payback_months': 18,
                    'efficiency_improvement': '30%',
                    'features': [
                        'Advanced fuel injection system',
                        'Precision steering and GPS ready',
                        'Reduced maintenance requirements',
                        'IoT connectivity for tracking'
                    ],
                    'financing_options': [
                        {'type': 'lease', 'monthly_payment': 320, 'term_months': 60},
                        {'type': 'loan', 'monthly_payment': 285, 'term_months': 72, 'interest_rate': 4.5}
                    ],
                    'carbon_impact': {
                        'co2_reduction_annually': 2.4,  # tons
                        'efficiency_score_improvement': 25
                    }
                },
                {
                    'id': 'irrigation_system_2024',
                    'category': 'irrigation',
                    'title': 'Smart Drip Irrigation System',
                    'brand': 'Rain Bird XFS Subsurface',
                    'description': 'Precision irrigation with soil moisture sensors',
                    'current_cost': 8500,
                    'annual_savings': 800,
                    'payback_months': 13,
                    'efficiency_improvement': '40%',
                    'features': [
                        'Soil moisture monitoring',
                        'Weather-based scheduling',
                        'Mobile app control',
                        'Water usage analytics'
                    ],
                    'financing_options': [
                        {'type': 'rebate', 'discount_amount': 2000, 'program': 'USDA Water Conservation'},
                        {'type': 'loan', 'monthly_payment': 180, 'term_months': 48, 'interest_rate': 3.9}
                    ],
                    'carbon_impact': {
                        'co2_reduction_annually': 1.8,
                        'efficiency_score_improvement': 20
                    }
                },
                {
                    'id': 'sprayer_upgrade_2024',
                    'category': 'sprayer',
                    'title': 'Precision Chemical Applicator',
                    'brand': 'Apache AS1240',
                    'description': 'Variable rate technology for reduced chemical waste',
                    'current_cost': 45000,
                    'annual_savings': 3500,
                    'payback_months': 15,
                    'efficiency_improvement': '35%',
                    'features': [
                        'Variable rate technology',
                        'GPS section control',
                        'Real-time application monitoring',
                        'Reduced chemical waste'
                    ],
                    'financing_options': [
                        {'type': 'lease', 'monthly_payment': 850, 'term_months': 60},
                        {'type': 'trade_in', 'trade_value': 12000, 'net_cost': 33000}
                    ],
                    'carbon_impact': {
                        'co2_reduction_annually': 4.2,
                        'efficiency_score_improvement': 30
                    }
                }
            ]
            
            return Response({
                'establishment_id': establishment_id,
                'marketplace_updated': timezone.now().isoformat(),
                'equipment_recommendations': equipment_recommendations,
                'financing_programs': [
                    {
                        'name': 'USDA Rural Development Loan',
                        'description': 'Low-interest loans for agricultural equipment',
                        'max_amount': 100000,
                        'interest_rate': 3.5,
                        'term_years': 10
                    },
                    {
                        'name': 'Farm Service Agency Equipment Loan',
                        'description': 'Government-backed loans for qualifying farmers',
                        'max_amount': 200000,
                        'interest_rate': 4.0,
                        'term_years': 15
                    }
                ],
                'rebate_programs': [
                    {
                        'name': 'Environmental Quality Incentives Program (EQIP)',
                        'description': 'Cost-share assistance for conservation practices',
                        'max_rebate': 0.75,  # 75% cost share
                        'eligible_categories': ['irrigation', 'conservation_tillage', 'nutrient_management']
                    }
                ]
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching equipment marketplace: {str(e)}")
            return Response(
                {
                    'error': 'Failed to fetch equipment marketplace data',
                    'details': str(e),
                    'equipment_recommendations': []
                }, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='bulk-purchasing')
    def bulk_purchasing_opportunities(self, request):
        """
        Analyze bulk purchasing opportunities for chemical inputs.
        Expected payload: {'establishment_ids': [int], 'chemical_types': [str]}
        """
        try:
            establishment_ids = request.data.get('establishment_ids', [])
            chemical_types = request.data.get('chemical_types', ['FE', 'PE', 'HE', 'FU'])
            
            if not establishment_ids:
                return Response(
                    {'error': 'establishment_ids is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Aggregate chemical usage across establishments
            total_usage = {}
            total_cost = 0
            
            for establishment_id in establishment_ids:
                try:
                    establishment = Establishment.objects.get(id=establishment_id)
                    productions = History.objects.filter(parcel__establishment=establishment)
                    
                    for production in productions:
                        chemical_events = ChemicalEvent.objects.filter(
                            history=production,
                            type__in=chemical_types
                        )
                        
                        for event in chemical_events:
                            chemical_type = event.type
                            if chemical_type not in total_usage:
                                total_usage[chemical_type] = {
                                    'volume': 0,
                                    'estimated_cost': 0,
                                    'events_count': 0
                                }
                            
                            # Extract volume and estimate cost
                            optimizer = CostOptimizer()
                            volume = optimizer._extract_numeric_value(event.volume or "0")
                            cost = optimizer._estimate_chemical_cost_from_event(event)
                            
                            total_usage[chemical_type]['volume'] += volume
                            total_usage[chemical_type]['estimated_cost'] += cost
                            total_usage[chemical_type]['events_count'] += 1
                            total_cost += cost
                            
                except Establishment.DoesNotExist:
                    continue
            
            # Calculate bulk discounts and savings opportunities
            bulk_opportunities = []
            total_potential_savings = 0
            
            for chemical_type, usage_data in total_usage.items():
                if usage_data['estimated_cost'] > 1000:  # Minimum threshold for bulk pricing
                    chemical_name = dict(ChemicalEvent.CHEMICAL_EVENTS)[chemical_type]
                    
                    # Calculate bulk discount (15-20% for large orders)
                    bulk_discount = 0.18 if usage_data['estimated_cost'] > 5000 else 0.12
                    potential_savings = usage_data['estimated_cost'] * bulk_discount
                    total_potential_savings += potential_savings
                    
                    bulk_opportunities.append({
                        'chemical_type': chemical_type,
                        'chemical_name': chemical_name,
                        'total_volume': usage_data['volume'],
                        'total_cost': usage_data['estimated_cost'],
                        'events_count': usage_data['events_count'],
                        'bulk_discount_percentage': bulk_discount * 100,
                        'potential_savings': potential_savings,
                        'recommended_suppliers': [
                            {
                                'name': 'AgriSupply Co-op',
                                'discount': bulk_discount,
                                'minimum_order': 5000,
                                'delivery_included': True,
                                'contact': 'bulk@agrisupply.com'
                            },
                            {
                                'name': 'Farm Chemical Direct',
                                'discount': bulk_discount - 0.02,
                                'minimum_order': 3000,
                                'delivery_included': False,
                                'contact': '1-800-FARM-CHEM'
                            }
                        ]
                    })

                return Response({
                'analysis_date': timezone.now().isoformat(),
                'establishments_analyzed': len(establishment_ids),
                'total_annual_cost': total_cost,
                'total_potential_savings': total_potential_savings,
                'savings_percentage': (total_potential_savings / max(total_cost, 1)) * 100,
                'bulk_opportunities': bulk_opportunities,
                'coordination_tips': [
                    'Contact neighboring farms to increase order volumes',
                    'Plan seasonal chemical needs 3-6 months in advance',
                    'Ensure proper storage facilities for bulk orders',
                    'Consider shared storage and delivery arrangements'
                ]
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error analyzing bulk purchasing: {str(e)}")
            return Response(
                {
                    'error': 'Failed to analyze bulk purchasing opportunities',
                    'details': str(e),
                    'bulk_opportunities': []
                }, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'], url_path='government-incentives')
    def government_incentives(self, request):
        """
        Get available government incentives and grants for sustainability practices.
        Query params: establishment_id, location (optional)
        """
        try:
            establishment_id = request.query_params.get('establishment_id')
            location = request.query_params.get('location', 'US')  # Default to US
            
            # Mock government incentives data (replace with real government API integration)
            incentives = [
                {
                    'id': 'eqip_2024',
                    'program': 'Environmental Quality Incentives Program (EQIP)',
                    'agency': 'USDA NRCS',
                    'type': 'cost_share',
                    'max_payment': 200000,
                    'cost_share_percentage': 75,
                    'eligible_practices': [
                        'Cover crop',
                        'Nutrient management',
                        'Integrated pest management',
                        'Conservation tillage',
                        'Irrigation water management'
                    ],
                    'application_deadline': '2024-03-15',
                    'application_status': 'open',
                    'estimated_approval_time': '90 days',
                    'contact_info': {
                        'office': 'Local NRCS Office',
                        'phone': '1-800-NRCS-HELP',
                        'website': 'https://www.nrcs.usda.gov/programs-initiatives/eqip'
                    }
                },
                {
                    'id': 'csp_2024',
                    'program': 'Conservation Stewardship Program (CSP)',
                    'agency': 'USDA NRCS',
                    'type': 'annual_payment',
                    'max_payment': 40000,
                    'payment_structure': 'per_acre_per_year',
                    'eligible_practices': [
                        'Carbon sequestration',
                        'Soil health improvement',
                        'Water quality protection',
                        'Wildlife habitat enhancement'
                    ],
                    'contract_length': '5 years',
                    'application_deadline': '2024-02-28',
                    'application_status': 'open',
                    'estimated_approval_time': '120 days',
                    'contact_info': {
                        'office': 'Local NRCS Office',
                        'phone': '1-800-NRCS-HELP',
                        'website': 'https://www.nrcs.usda.gov/programs-initiatives/csp'
                    }
                },
                {
                    'id': 'carbon_credit_2024',
                    'program': 'Climate Smart Agriculture Carbon Credits',
                    'agency': 'Private Market / USDA Partnership',
                    'type': 'market_payment',
                    'payment_rate': '15-30 per ton CO2e',
                    'eligible_practices': [
                        'No-till farming',
                        'Cover crops',
                        'Rotational grazing',
                        'Agroforestry'
                    ],
                    'contract_length': '10 years',
                    'verification_required': True,
                    'application_status': 'continuous',
                    'estimated_approval_time': '60 days',
                    'contact_info': {
                        'program': 'Nori Carbon Markets',
                        'website': 'https://nori.com',
                        'email': 'farmers@nori.com'
                    }
                },
                {
                    'id': 'reap_2024',
                    'program': 'Rural Energy for America Program (REAP)',
                    'agency': 'USDA Rural Development',
                    'type': 'grant_loan',
                    'max_grant': 500000,
                    'max_loan': 25000000,
                    'grant_percentage': 25,
                    'eligible_technologies': [
                        'Solar panels',
                        'Wind turbines',
                        'Biomass systems',
                        'Energy efficiency improvements'
                    ],
                    'application_deadline': '2024-04-30',
                    'application_status': 'open',
                    'estimated_approval_time': '180 days',
                    'contact_info': {
                        'office': 'USDA Rural Development',
                        'phone': '1-800-RD-APPLY',
                        'website': 'https://www.rd.usda.gov/programs-services/energy-programs/rural-energy-america-program-renewable-energy-systems-energy-efficiency-improvement-grants'
                    }
                }
            ]
            
            # Filter incentives based on establishment characteristics if available
            if establishment_id:
                try:
                    establishment = Establishment.objects.get(id=establishment_id)
                    # Add establishment-specific filtering logic here
                except Establishment.DoesNotExist:
                    pass
            
            return Response({
                'location': location,
                'last_updated': timezone.now().isoformat(),
                'available_incentives': incentives,
                'application_tips': [
                    'Contact local NRCS office for personalized guidance',
                    'Prepare detailed conservation plans before applying',
                    'Apply early as funding is limited and competitive',
                    'Consider combining multiple programs for maximum benefit',
                    'Keep detailed records of current practices for baseline'
                ],
                'total_potential_value': sum(
                    incentive.get('max_payment', 0) for incentive in incentives 
                    if incentive.get('type') in ['cost_share', 'grant_loan']
                )
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching government incentives: {str(e)}")
            return Response(
                {
                    'error': 'Failed to fetch government incentives',
                    'details': str(e),
                    'available_incentives': []
                }, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
        return Response({'message': 'QR summary'}, status=status.HTTP_200_OK)


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