from django.shortcuts import render
from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
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
    Establishment,
    History
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
from .services.certificate import certificate_generator
from .services.report_generator import report_generator
from rest_framework import serializers

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
        print("bulk_create")
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
        print("perform_create")
        print(serializer.validated_data)
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
                print(f"Error calculating emissions: {e}")

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
        target_entity = None
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
                    benchmark = CarbonBenchmark.objects.filter(
                        industry=industry,
                        year=year
                    ).first()
                    if benchmark:
                        industry_benchmark = benchmark.average_emissions
                target_entity = establishment
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

class CarbonCertificationViewSet(viewsets.ModelViewSet):
    queryset = CarbonCertification.objects.all()
    serializer_class = CarbonCertificationSerializer

    def get_queryset(self):
        user = self.request.user
        establishment_id = self.request.query_params.get('establishment')
        
        if not user.is_authenticated:
            return CarbonCertification.objects.none()
        
        queryset = CarbonCertification.objects.all()
        
        # Filter by establishment if specified
        if establishment_id:
            try:
                establishment_id = int(establishment_id)
                queryset = queryset.filter(establishment_id=establishment_id)
            except (ValueError, TypeError):
                # Handle non-integer establishment_id
                pass
                
        return queryset

    @action(detail=False, methods=['get'])
    def by_entity(self, request):
        entity_type = request.query_params.get('entity_type')
        entity_id = request.query_params.get('entity_id')
        if entity_type not in ['establishment', 'production'] or not entity_id:
            return Response({'error': 'Invalid entity type or ID'}, status=status.HTTP_400_BAD_REQUEST)

        if entity_type == 'establishment':
            certifications = CarbonCertification.objects.filter(establishment_id=entity_id)
        else:  # production
            certifications = CarbonCertification.objects.filter(production_id=entity_id)

        page = self.paginate_queryset(certifications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(certifications, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save()
        CarbonAuditLog.objects.create(
            certification=serializer.instance,
            user=self.request.user,
            action='create',
            details=f'Created certification {serializer.instance.name}'
        )

    def perform_update(self, serializer):
        serializer.save()
        CarbonAuditLog.objects.create(
            certification=serializer.instance,
            user=self.request.user,
            action='update',
            details=f'Updated certification {serializer.instance.name}'
        )

    def perform_destroy(self, instance):
        CarbonAuditLog.objects.create(
            certification=instance,
            user=self.request.user,
            action='delete',
            details=f'Deleted certification {instance.name}'
        )
        instance.delete()

class CarbonBenchmarkViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CarbonBenchmark.objects.all()
    serializer_class = CarbonBenchmarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        industry = self.request.query_params.get('industry')
        year = self.request.query_params.get('year')
        queryset = CarbonBenchmark.objects.all()
        if industry:
            queryset = queryset.filter(industry=industry)
        if year:
            queryset = queryset.filter(year=year)
        return queryset

class ConsumerCarbonSummaryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for consumer-facing carbon summary data accessible via QR code.
    No authentication required for public transparency.
    """
    queryset = CarbonEntry.objects.all()
    serializer_class = CarbonFootprintSummarySerializer
    permission_classes = []  # No authentication required
    lookup_field = 'qr_code_id'  # Placeholder for QR code identifier

    def get_queryset(self):
        qr_code_id = self.kwargs.get('qr_code_id')
        # Logic to map QR code ID to establishment or production
        # Placeholder: Assume qr_code_id maps to establishment_id for now
        return CarbonEntry.objects.filter(establishment_id=qr_code_id)

    @action(detail=False, methods=['get'])
    def qr_summary(self, request, qr_code_id=None):
        year = request.query_params.get('year', timezone.now().year)
        queryset = self.get_queryset().filter(year=year)

        total_emissions = queryset.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        total_offsets = queryset.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        net_carbon = total_emissions - total_offsets

        # Industry average and carbon score
        industry_average = CarbonBenchmark.objects.filter(year=year).aggregate(Sum('average_emissions'))['average_emissions__sum'] or 0
        carbon_score = 100
        if industry_average > 0:
            ratio = net_carbon / industry_average
            carbon_score = max(1, min(100, int(100 * (1 - ratio))))

        # Relatable footprint (e.g., equivalent to driving miles)
        relatable_footprint = f"{net_carbon / 0.4:.1f} miles driven"  # Assuming 0.4 kg CO2e per mile (placeholder)

        # Placeholder for badges (e.g., certifications)
        badges = [
            {"name": "USDA Organic", "icon": "organic"},
            {"name": "Carbon-Neutral", "icon": "neutral"} if net_carbon <= 0 else {"name": "Sustainable", "icon": "sustainable"}
        ]

        # Placeholder for timeline/storytelling data
        timeline = [
            {"stage": "Planted", "description": "Organic seeds in California", "date": "2023-01-15"},
            {"stage": "Harvested", "description": "Using low-emission tools", "date": "2023-06-20"},
            {"stage": "Transported", "description": "Via electric truck", "date": "2023-07-01"}
        ]

        # Placeholder for farmer story
        farmer_story = "Grown by Sunny Farms, a 3rd-generation family business committed to sustainability."

        # Calculate industry percentile (placeholder logic)
        industry_percentile = carbon_score  # Simplified, assuming score reflects percentile

        # Emissions breakdown by category (placeholder data)
        emissions_by_category = {
            "Fertilizer": total_emissions * 0.4,
            "Fuel": total_emissions * 0.3,
            "Irrigation": total_emissions * 0.2,
            "Other": total_emissions * 0.1
        }

        # Emissions by source (placeholder data)
        emissions_by_source = {
            "Nitrogen Fertilizer": total_emissions * 0.3,
            "Diesel": total_emissions * 0.25,
            "Electricity": total_emissions * 0.15,
            "Other Sources": total_emissions * 0.3
        }

        # Offsets by action (placeholder data)
        offsets_by_action = {
            "Tree Planting": total_offsets * 0.6,
            "Renewable Energy": total_offsets * 0.4
        }

        return Response({
            'total_emissions': total_emissions,
            'total_offsets': total_offsets,
            'net_carbon': net_carbon,
            'carbon_score': carbon_score,
            'relatable_footprint': relatable_footprint,
            'industry_percentile': industry_percentile,
            'badges': badges,
            'timeline': timeline,
            'farmer_story': farmer_story,
            'emissions_by_category': emissions_by_category,
            'emissions_by_source': emissions_by_source,
            'offsets_by_action': offsets_by_action,
            'year': int(year)
        })

class CarbonReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CarbonReport.objects.all()
    serializer_class = CarbonReportSerializer

    def get_queryset(self):
        user = self.request.user
        establishment_id = self.request.query_params.get('establishment')
        
        if not user.is_authenticated:
            return CarbonReport.objects.none()
        
        queryset = CarbonReport.objects.all()
        
        # Filter by establishment if specified
        if establishment_id:
            try:
                establishment_id = int(establishment_id)
                queryset = queryset.filter(establishment_id=establishment_id)
            except (ValueError, TypeError):
                # Handle non-integer establishment_id
                pass
                
        return queryset

    @action(detail=False, methods=['get'])
    def by_entity(self, request):
        entity_type = request.query_params.get('entity_type')
        entity_id = request.query_params.get('entity_id')
        if entity_type not in ['establishment', 'production'] or not entity_id:
            return Response({'error': 'Invalid entity type or ID'}, status=status.HTTP_400_BAD_REQUEST)

        if entity_type == 'establishment':
            reports = CarbonReport.objects.filter(establishment_id=entity_id)
        else:  # production
            reports = CarbonReport.objects.filter(production_id=entity_id)

        page = self.paginate_queryset(reports)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(reports, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def generate(self, request):
        entity_type = request.data.get('entity_type')
        entity_id = request.data.get('entity_id')
        period_start = request.data.get('period_start')
        period_end = request.data.get('period_end')

        # Check if we're getting data from the new frontend format
        establishment_id = request.data.get('establishment')
        if establishment_id and not entity_type:
            entity_type = 'establishment'
            entity_id = establishment_id

        # Handle year and report type for period calculation
        year = request.data.get('year')
        report_type = request.data.get('reportType')
        quarter = request.data.get('quarter')
        
        if year and report_type and not period_start:
            # Calculate period_start and period_end based on year and report_type
            if report_type == 'annual':
                period_start = f"{year}-01-01"
                period_end = f"{year}-12-31"
            elif report_type == 'quarterly' and quarter:
                # Calculate dates for the specified quarter
                quarter_months = {
                    1: (1, 3),  # Q1: Jan-Mar
                    2: (4, 6),  # Q2: Apr-Jun
                    3: (7, 9),  # Q3: Jul-Sep
                    4: (10, 12)  # Q4: Oct-Dec
                }
                start_month, end_month = quarter_months.get(int(quarter), (1, 3))
                period_start = f"{year}-{start_month:02d}-01"
                
                # Calculate end date (last day of end month)
                if end_month in [4, 6, 9, 11]:
                    end_day = 30
                elif end_month == 2:
                    # Simple leap year check
                    end_day = 29 if (int(year) % 4 == 0 and int(year) % 100 != 0) or (int(year) % 400 == 0) else 28
                else:
                    end_day = 31
                
                period_end = f"{year}-{end_month:02d}-{end_day}"

        if entity_type not in ['establishment', 'production'] or not entity_id:
            return Response({'error': 'Invalid entity type or ID'}, status=status.HTTP_400_BAD_REQUEST)

        if entity_type == 'establishment':
            try:
                entity = Establishment.objects.get(id=entity_id)
                entries = CarbonEntry.objects.filter(establishment=entity)
            except Establishment.DoesNotExist:
                return Response({'error': 'Establishment not found'}, status=status.HTTP_404_NOT_FOUND)
        else:  # production
            try:
                entity = History.objects.get(id=entity_id)
                entries = CarbonEntry.objects.filter(production=entity)
            except History.DoesNotExist:
                return Response({'error': 'Production not found'}, status=status.HTTP_404_NOT_FOUND)

        if period_start:
            entries = entries.filter(timestamp__gte=period_start)
        if period_end:
            entries = entries.filter(timestamp__lte=period_end)

        total_emissions = sum(entry.amount for entry in entries if entry.type == 'emission')
        total_offsets = sum(entry.amount for entry in entries if entry.type == 'offset')
        net_footprint = total_emissions - total_offsets
        carbon_score = max(0, min(100, int(100 - (net_footprint / max(total_emissions, 1)) * 100)))

        # Create the report object
        try:
            report = CarbonReport(
                establishment=entity if entity_type == 'establishment' else None,
                production=entity if entity_type == 'production' else None,
                period_start=period_start if period_start else timezone.now().date(),
                period_end=period_end if period_end else timezone.now().date(),
                total_emissions=total_emissions,
                total_offsets=total_offsets,
                net_footprint=net_footprint,
                carbon_score=carbon_score,
                generated_at=timezone.now()
            )
            
            # Handle document upload if provided
            document = request.data.get('document')
            if document and hasattr(document, 'file'):
                report.document = document
                document_source = 'uploaded'
            else:
                # Generate a PDF report when no document is uploaded
                report.save()  # Save first to get an ID
                try:
                    # Generate PDF using the report generator
                    document_url = report_generator.generate_report(report)
                    report.document = document_url
                    document_source = 'generated'
                except Exception as e:
                    # Log the PDF generation error but continue
                    print(f"Error generating PDF: {str(e)}")
                    document_source = 'none'
            
            report.save()
            
            # Add additional logging
            log_details = f'Generated {report_type} report for {entity_type} {entity_id}'
            if document_source != 'none':
                log_details += f' with {document_source} document'
                
            CarbonAuditLog.objects.create(
                report=report,
                user=request.user,
                action='create',
                details=log_details
            )

            serializer = CarbonReportSerializer(report)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        year = request.query_params.get('year', timezone.now().year)
        establishment_id = pk
        queryset = CarbonEntry.objects.filter(establishment_id=establishment_id, year=year)
        total_emissions = queryset.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        total_offsets = queryset.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        net_carbon = total_emissions - total_offsets
        industry_average = CarbonBenchmark.objects.filter(year=year).aggregate(Sum('average_emissions'))['average_emissions__sum'] or 0
        carbon_score = 100
        if industry_average > 0:
            ratio = net_carbon / industry_average
            carbon_score = max(1, min(100, int(100 * (1 - ratio))))
        recommendations = []
        if net_carbon > industry_average:
            recommendations.append('Consider switching to organic fertilizers to reduce emissions by up to 20%.')
        if total_emissions > 0:
            recommendations.append('Review fuel usage in machinery; switching to biodiesel blends can cut emissions by 10-15%.')
        if total_offsets < (total_emissions * 0.1):
            recommendations.append('Explore carbon offset programs like tree planting or renewable energy credits.')
        if not recommendations:
            recommendations.append('Your carbon footprint is well-managed. Continue monitoring and consider sharing best practices with peers.')
        return Response({
            'total_emissions': total_emissions,
            'total_offsets': total_offsets,
            'net_footprint': net_carbon,
            'carbon_score': carbon_score,
            'recommendations': recommendations,
            'year': int(year)
        })

class SustainabilityBadgeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SustainabilityBadge.objects.all()
    serializer_class = SustainabilityBadgeSerializer

class MicroOffsetViewSet(viewsets.ModelViewSet):
    queryset = MicroOffset.objects.all()
    serializer_class = MicroOffsetSerializer

class GreenPointsViewSet(viewsets.ModelViewSet):
    queryset = GreenPoints.objects.all()
    serializer_class = GreenPointsSerializer

class CarbonAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CarbonAuditLog.objects.all()
    serializer_class = CarbonAuditLogSerializer

class CarbonOffsetProjectViewSet(viewsets.ModelViewSet):
    queryset = CarbonOffsetProject.objects.all()
    serializer_class = CarbonOffsetProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = CarbonOffsetProject.objects.all()
        project_type = self.request.query_params.get('project_type')
        certification = self.request.query_params.get('certification')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        min_capacity = self.request.query_params.get('min_capacity')

        if project_type:
            queryset = queryset.filter(project_type=project_type)
        if certification:
            queryset = queryset.filter(certification_standard=certification)
        if min_price:
            queryset = queryset.filter(price_per_ton__gte=min_price)
        if max_price:
            queryset = queryset.filter(price_per_ton__lte=max_price)
        if min_capacity:
            queryset = queryset.filter(available_capacity__gte=min_capacity)

        return queryset

    @action(detail=True, methods=['post'])
    def purchase(self, request, pk=None):
        """
        Purchase carbon offsets from a project
        """
        project = self.get_object()
        amount = request.data.get('amount')
        
        if not amount:
            return Response(
                {'error': 'Amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            amount = float(amount)
        except ValueError:
            return Response(
                {'error': 'Invalid amount'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount > project.available_capacity:
            return Response(
                {'error': f'Requested amount exceeds available capacity. Available: {project.available_capacity} tons'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create purchase record
        purchase = CarbonOffsetPurchase.objects.create(
            project=project,
            buyer=request.user,
            amount=amount,
            price_per_ton=project.price_per_ton,
            status='pending',
            transaction_id=f"TXN-{timezone.now().timestamp()}"
        )
        
        # Update project capacity
        project.available_capacity -= amount
        project.save()
        
        # TODO: Integrate with payment gateway
        # For now, mark as completed
        purchase.status = 'completed'
        purchase.save()
        
        # Generate certificate
        certificate = CarbonOffsetCertificate.objects.create(
            purchase=purchase,
            certificate_number=f"CERT-{purchase.transaction_id}",
            verification_code=f"VER-{purchase.transaction_id}",
            certificate_url=f"https://trazo.com/certificates/{purchase.transaction_id}",
            metadata={
                'project_name': project.name,
                'project_type': project.project_type,
                'certification_standard': project.certification_standard
            }
        )
        
        # Update purchase with certificate URL
        purchase.certificate_url = certificate.certificate_url
        purchase.save()
        
        return Response({
            'purchase': CarbonOffsetPurchaseSerializer(purchase).data,
            'certificate': CarbonOffsetCertificateSerializer(certificate).data
        })

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Verify a carbon offset project
        """
        project = self.get_object()
        
        try:
            verification_results = verification_service.verify_project(project)
            return Response(verification_results)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CarbonOffsetPurchaseViewSet(viewsets.ModelViewSet):
    queryset = CarbonOffsetPurchase.objects.all()
    serializer_class = CarbonOffsetPurchaseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CarbonOffsetPurchase.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def generate_certificate(self, request, pk=None):
        purchase = self.get_object()
        if not purchase.is_verified:
            return Response(
                {'error': 'Purchase must be verified before generating certificate'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            certificate = certificate_generator.generate_certificate(purchase)
            return Response({
                'message': 'Certificate generated successfully',
                'certificate_url': certificate
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def verify_certificate(self, request):
        certificate_id = request.query_params.get('certificate_id')
        if not certificate_id:
            return Response(
                {'error': 'certificate_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = certificate_generator.verify_certificate(certificate_id)
        return Response(result)

    @action(detail=True, methods=['get'])
    def certificate_status(self, request, pk=None):
        purchase = self.get_object()
        return Response({
            'is_verified': purchase.is_verified,
            'has_certificate': bool(purchase.certificate_file),
            'certificate_url': purchase.certificate_file.url if purchase.certificate_file else None
        })

class CarbonOffsetCertificateViewSet(viewsets.ModelViewSet):
    queryset = CarbonOffsetCertificate.objects.all()
    serializer_class = CarbonOffsetCertificateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CarbonOffsetCertificate.objects.filter(purchase__user=self.request.user)

class CarbonFootprintCalculatorViewSet(viewsets.ViewSet):
    """
    ViewSet for calculating carbon footprints
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'])
    def calculate(self, request):
        """
        Calculate carbon footprint based on input data
        """
        try:
            # Validate required fields
            required_fields = ['crop_type', 'area', 'inputs']
            for field in required_fields:
                if field not in request.data:
                    return Response(
                        {'error': f'Missing required field: {field}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Extract and validate data
            crop_type = request.data['crop_type']
            area = float(request.data['area'])
            inputs = request.data['inputs']
            region = request.data.get('region')

            if area <= 0:
                return Response(
                    {'error': 'Area must be greater than 0'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculate footprint
            result = calculator.calculate_farm_footprint(
                inputs=inputs,
                crop_type=crop_type,
                area=area,
                region=region
            )

            # Log the calculation
            CarbonAuditLog.objects.create(
                user=request.user,
                action='calculate',
                details=f'Calculated carbon footprint for {crop_type} on {area} acres'
            )

            return Response(result)

        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error calculating carbon footprint: {str(e)}")
            return Response(
                {'error': 'Failed to calculate carbon footprint'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CarbonProductionSummaryViewSet(viewsets.ViewSet):
    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        year = request.query_params.get('year', timezone.now().year)
        production_id = pk
        queryset = CarbonEntry.objects.filter(production_id=production_id, year=year)
        total_emissions = queryset.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        total_offsets = queryset.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        net_carbon = total_emissions - total_offsets
        industry_average = CarbonBenchmark.objects.filter(year=year).aggregate(Sum('average_emissions'))['average_emissions__sum'] or 0
        carbon_score = 100
        if industry_average > 0:
            ratio = net_carbon / industry_average
            carbon_score = max(1, min(100, int(100 * (1 - ratio))))
        recommendations = []
        if net_carbon > industry_average:
            recommendations.append('Consider switching to organic fertilizers to reduce emissions by up to 20%.')
        if total_emissions > 0:
            recommendations.append('Review fuel usage in machinery; switching to biodiesel blends can cut emissions by 10-15%.')
        if total_offsets < (total_emissions * 0.1):
            recommendations.append('Explore carbon offset programs like tree planting or renewable energy credits.')
        if not recommendations:
            recommendations.append('Your carbon footprint is well-managed. Continue monitoring and consider sharing best practices with peers.')
        return Response({
            'total_emissions': total_emissions,
            'total_offsets': total_offsets,
            'net_footprint': net_carbon,
            'carbon_score': carbon_score,
            'recommendations': recommendations,
            'year': int(year)
        })

    @action(detail=True, methods=['get'], url_path='timeline')
    def timeline(self, request, pk=None):
        production_id = pk
        # Gather all event types for this production (History)
        events = []
        for model, event_type in [
            (WeatherEvent, 'weather'),
            (ChemicalEvent, 'chemical'),
            (ProductionEvent, 'production'),
            (GeneralEvent, 'general')
        ]:
            for event in model.objects.filter(history_id=production_id):
                events.append({
                    'id': event.id,
                    'date': getattr(event, 'date', getattr(event, 'timestamp', None)),
                    'title': getattr(event, 'description', str(event)),
                    'type': event_type,
                    'details': event.__dict__
                })
        # Sort by date
        events = [e for e in events if e['date'] is not None]
        events.sort(key=lambda x: x['date'])
        return Response({'timeline': events})

class CarbonEstablishmentSummaryViewSet(viewsets.ViewSet):
    @action(detail=True, methods=['get'], url_path='recommendations')
    def recommendations(self, request, pk=None):
        year = request.query_params.get('year', timezone.now().year)
        establishment_id = pk
        queryset = CarbonEntry.objects.filter(establishment_id=establishment_id, year=year)
        total_emissions = queryset.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        total_offsets = queryset.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        net_carbon = total_emissions - total_offsets
        industry_average = CarbonBenchmark.objects.filter(year=year).aggregate(Sum('average_emissions'))['average_emissions__sum'] or 0
        recommendations = []
        if net_carbon > industry_average:
            recommendations.append('Consider switching to organic fertilizers to reduce emissions by up to 20%.')
            recommendations.append('Implement drip irrigation systems to save water and reduce emissions by approximately 15%.')
            recommendations.append('Adopt cover cropping practices to sequester carbon and improve soil health, potentially offsetting 10% of emissions.')
        if total_emissions > 0:
            recommendations.append('Review fuel usage in machinery; switching to biodiesel blends can cut emissions by 10-15%.')
        if total_offsets < (total_emissions * 0.1):
            recommendations.append('Explore carbon offset programs like tree planting or renewable energy credits.')
        if not recommendations:
            recommendations.append('Your carbon footprint is well-managed. Continue monitoring and consider sharing best practices with peers.')
        return Response({'recommendations': recommendations, 'year': int(year)})

    @action(detail=True, methods=['get'], url_path='iot-data')
    def iot_data(self, request, pk=None):
        # Mock IoT data (replace with real sensor integration as needed)
        import random
        data = {
            'soilMoisture': round(random.uniform(20, 40), 2),
            'temperature': round(random.uniform(15, 35), 2),
            'humidity': round(random.uniform(40, 80), 2),
            'solarRadiation': round(random.uniform(200, 800), 2),
            'waterUsage': round(random.uniform(100, 500), 2),
            'energyConsumption': round(random.uniform(50, 200), 2)
        }
        return Response(data)

    @action(detail=True, methods=['get'], url_path='historical-data')
    def historical_data(self, request, pk=None):
        establishment_id = pk
        time_range = request.query_params.get('timeRange', 'month')
        now = timezone.now()
        labels = []
        emissions = []
        offsets = []
        queryset = CarbonEntry.objects.filter(establishment_id=establishment_id)
        if time_range == 'week':
            for i in range(6, -1, -1):
                day = now - timedelta(days=i)
                label = day.strftime('%a')
                day_entries = queryset.filter(timestamp__date=day.date())
                emissions.append(day_entries.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0)
                offsets.append(day_entries.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0)
                labels.append(label)
        elif time_range == 'year':
            for i in range(1, 13):
                label = datetime(now.year, i, 1).strftime('%b')
                month_entries = queryset.filter(timestamp__year=now.year, timestamp__month=i)
                emissions.append(month_entries.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0)
                offsets.append(month_entries.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0)
                labels.append(label)
        else:  # month
            for i in range(29, -1, -1):
                day = now - timedelta(days=i)
                label = day.strftime('%d %b')
                day_entries = queryset.filter(timestamp__date=day.date())
                emissions.append(day_entries.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0)
                offsets.append(day_entries.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0)
                labels.append(label)
        return Response({'labels': labels, 'emissions': emissions, 'offsets': offsets})

    @action(detail=True, methods=['get'], url_path='emissions-breakdown')
    def emissions_breakdown(self, request, pk=None):
        establishment_id = pk
        year = request.query_params.get('year', timezone.now().year)
        queryset = CarbonEntry.objects.filter(establishment_id=establishment_id, year=year, type='emission')
        
        # Get all categories in use
        categories = CarbonSource.objects.values_list('category', flat=True).distinct()
        
        # Categorize emissions based on actual categories in data
        direct = {
            'fertilizer': queryset.filter(source__category='fertilizer').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0,
            'fuel': queryset.filter(source__category='fuel').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0,
            'equipment': queryset.filter(source__category='equipment').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        }
        
        indirect = {
            'energy': queryset.filter(source__category='energy').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0,
            'transportation': queryset.filter(source__category='transportation').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0,
            'waste': queryset.filter(source__category='waste').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        }
        
        # Total emissions
        total = sum(direct.values()) + sum(indirect.values())
        
        return Response({
            'direct': direct,
            'indirect': indirect,
            'total': total
        })

class PublicProductionViewSet(viewsets.ViewSet):
    permission_classes = []  # No authentication required

    @action(detail=True, methods=['get'], url_path='qr-summary')
    def qr_summary(self, request, pk=None):
        """
        Get comprehensive consumer-facing summary for a production, accessed via QR code scan
        """
        try:
            production = History.objects.get(id=pk)
            
            # Get carbon report for this production
            carbon_report = CarbonReport.objects.filter(production=production).first()
            
            # Get badges assigned to this production
            badges_data = []
            for badge in production.badges.all():
                badges_data.append({
                    'id': str(badge.id),
                    'name': badge.name,
                    'icon': badge.icon.url if badge.icon else None,
                    'description': badge.description,
                    'isVerified': badge.usda_verified,
                    'level': 'gold' if 'Gold' in badge.name else 
                             'silver' if 'Silver' in badge.name else
                             'bronze' if 'Bronze' in badge.name else 'platinum',
                    'dateAchieved': timezone.now().strftime('%Y-%m-%d')
                })
            
            # Get carbon entries for this production
            carbon_entries = CarbonEntry.objects.filter(production=production)
            
            # Calculate emissions by category
            emissions_by_category = {}
            emissions_by_source = {}
            offsets_by_action = {}
            total_emissions = 0
            total_offsets = 0
            
            for entry in carbon_entries:
                if entry.type == 'emission':
                    total_emissions += entry.co2e_amount
                    
                    # Group by category
                    category = entry.source.category if hasattr(entry.source, 'category') and entry.source.category else 'other'
                    if category in emissions_by_category:
                        emissions_by_category[category] += entry.co2e_amount
                    else:
                        emissions_by_category[category] = entry.co2e_amount
                        
                    # Group by source
                    source = entry.source.name if hasattr(entry.source, 'name') and entry.source.name else 'unknown'
                    if source in emissions_by_source:
                        emissions_by_source[source] += entry.co2e_amount
                    else:
                        emissions_by_source[source] = entry.co2e_amount
                        
                elif entry.type == 'offset':
                    total_offsets += entry.co2e_amount
                    
                    # Group by source (action)
                    action = entry.source.name if hasattr(entry.source, 'name') and entry.source.name else 'other offsets'
                    if action in offsets_by_action:
                        offsets_by_action[action] += entry.co2e_amount
                    else:
                        offsets_by_action[action] = entry.co2e_amount
            
            # Get benchmark for this product type to calculate industry percentile
            benchmarks = CarbonBenchmark.objects.filter(
                crop_type__icontains=production.product.name,
                year=carbon_entries.first().year if carbon_entries.exists() else timezone.now().year
            ).first()
            
            industry_average = benchmarks.average_emissions if benchmarks else 0.5  # Default if no benchmark
            
            # Calculate net footprint
            net_footprint = total_emissions - total_offsets
            
            # Calculate carbon score (1-100)
            carbon_score = CarbonEntry.calculate_carbon_score(
                total_emissions, 
                total_offsets,
                industry_average * production.production_amount if hasattr(production, 'production_amount') and production.production_amount else total_emissions
            )
            
            # Calculate industry percentile (if better than average, higher percentile)
            if benchmarks:
                # Convert to per kg for comparison
                net_per_kg = net_footprint / production.production_amount if hasattr(production, 'production_amount') and production.production_amount else 0
                if net_per_kg < benchmarks.min_emissions:
                    industry_percentile = 95  # Top 5%
                elif net_per_kg < benchmarks.average_emissions:
                    # Linear scale between min and average
                    industry_percentile = 50 + 45 * ((benchmarks.average_emissions - net_per_kg) / (benchmarks.average_emissions - benchmarks.min_emissions))
                else:
                    # Linear scale between average and max
                    industry_percentile = max(5, 50 * ((benchmarks.max_emissions - net_per_kg) / (benchmarks.max_emissions - benchmarks.average_emissions)))
            else:
                industry_percentile = 50  # Default to average
            
            # Get relatable footprint
            if net_footprint < 1:
                relatable_footprint = f"like driving {round(net_footprint * 4, 1)} miles"
            elif net_footprint < 10:
                relatable_footprint = f"like {round(net_footprint / 8, 1)} gallons of gasoline"
            else:
                relatable_footprint = f"like {round(net_footprint / 1000, 2)} metric tons of CO2"
            
            # Get USDA verification status
            is_usda_verified = carbon_report.usda_verified if carbon_report else False
            
            # Get social proof metrics
            # For this demo, we're using dummy data but this could be real data in production
            social_proof = {
                'totalScans': 532,
                'totalOffsets': 230,
                'totalUsers': 180,
                'averageRating': 4.2
            }
            
            # Get timeline events from production events
            timeline_events = []
            
            # Add weather events
            from history.models import WeatherEvent
            weather_events = WeatherEvent.objects.filter(history=production).order_by('date')
            for event in weather_events:
                timeline_events.append({
                    'id': str(event.id),
                    'date': event.date.strftime('%Y-%m-%d'),
                    'title': event.get_type_display(),
                    'description': event.description or event.observation,
                    'type': 'weather',
                    'carbonImpact': 0,  # Can be calculated if data is available
                })
            
            # Add chemical events
            from history.models import ChemicalEvent
            chemical_events = ChemicalEvent.objects.filter(history=production).order_by('date')
            for event in chemical_events:
                timeline_events.append({
                    'id': str(event.id),
                    'date': event.date.strftime('%Y-%m-%d'),
                    'title': f"{event.get_type_display()} Application",
                    'description': event.description or f"{event.commercial_name} ({event.volume})",
                    'type': 'chemical',
                    'carbonImpact': 0.2,  # Example impact
                })
            
            # Add production events
            from history.models import ProductionEvent
            production_events = ProductionEvent.objects.filter(history=production).order_by('date')
            for event in production_events:
                timeline_events.append({
                    'id': str(event.id),
                    'date': event.date.strftime('%Y-%m-%d'),
                    'title': event.get_type_display(),
                    'description': event.description or event.observation,
                    'type': 'production',
                    'carbonImpact': 0.1 if event.type == 'HA' else -0.1,  # Example: harvesting has positive impact, other activities might reduce emissions
                })
            
            # Sort timeline by date
            timeline_events.sort(key=lambda x: x['date'])
            
            # Get farmer data (using production attributes if available)
            farmer_data = {
                'name': getattr(production, 'farmer_name', production.operator.get_full_name() if production.operator else 'Farmer'),
                'photo': getattr(production, 'farmer_photo', ''),
                'bio': getattr(production, 'farmer_bio', ''),
                'generation': getattr(production, 'farmer_generation', 3),
                'location': getattr(production, 'farmer_location', production.parcel.establishment.city if production.parcel and production.parcel.establishment else 'California'),
                'certifications': getattr(production, 'farmer_certifications', ['Organic']),
                'sustainabilityInitiatives': getattr(production, 'sustainability_initiatives', [
                    'Water conservation',
                    'Renewable energy',
                    'Soil health practices'
                ]),
                'carbonReduction': getattr(production, 'carbon_reduction', 15000),
                'yearsOfPractice': getattr(production, 'years_of_practice', 10)
            }
            
            # Get recommendations from carbon report or use default
            recommendations = []
            if carbon_report and carbon_report.recommendations:
                for rec in carbon_report.recommendations:
                    if isinstance(rec, dict) and 'title' in rec:
                        recommendations.append(rec['title'])
            
            # If we don't have enough recommendations, add default ones
            default_recs = [
                'Efficient water irrigation',
                'Organic fertilizers',
                'Solar power utilization',
                'Reduced pesticide usage'
            ]
            
            for rec in default_recs:
                if rec not in recommendations and len(recommendations) < 4:
                    recommendations.append(rec)
            
            # Build the response
            response_data = {
                'carbonScore': carbon_score,
                'totalEmissions': total_emissions,
                'totalOffsets': total_offsets,
                'netFootprint': net_footprint,
                'relatableFootprint': relatable_footprint,
                'industryPercentile': round(industry_percentile),
                'industryAverage': industry_average,
                'badges': badges_data,
                'farmer': farmer_data,
                'farmerStory': getattr(production, 'farmer_story', "Our farm has been in the family for generations, and we're committed to sustainable practices that preserve the land for future generations."),
                'timeline': timeline_events,
                'isUsdaVerified': is_usda_verified,
                'verificationDate': timezone.now().strftime('%Y-%m-%d') if is_usda_verified else None,
                'socialProof': social_proof,
                'emissionsByCategory': emissions_by_category,
                'emissionsBySource': emissions_by_source,
                'offsetsByAction': offsets_by_action,
                'recommendations': recommendations
            }
            
            return Response(response_data)
            
        except History.DoesNotExist:
            return Response(
                {"error": "Production not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        production_id = pk
        year = request.query_params.get('year', timezone.now().year)
        entries = CarbonEntry.objects.filter(production_id=production_id, year=year)
        total_emissions = entries.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        total_offsets = entries.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        net_carbon = total_emissions - total_offsets
        carbon_score = 100
        industry_average = CarbonBenchmark.objects.filter(year=year).aggregate(Sum('average_emissions'))['average_emissions__sum'] or 0
        if industry_average > 0:
            ratio = net_carbon / industry_average
            carbon_score = max(1, min(100, int(100 * (1 - ratio))))
        return Response({
            "totalEmissions": total_emissions,
            "totalOffsets": total_offsets,
            "netFootprint": net_carbon,
            "carbonScore": carbon_score,
            "year": int(year)
        })

    @action(detail=True, methods=['get'], url_path='recommendations')
    def recommendations(self, request, pk=None):
        """
        Get sustainability recommendations for a production based on carbon footprint.
        Adapted to be more consumer-friendly, focusing on what's already being done
        rather than suggestions for the producer.
        """
        production_id = pk
        year = request.query_params.get('year', timezone.now().year)
        
        try:
            production = History.objects.get(id=production_id)
            
            # Get the carbon data for this production
            carbon_entries = CarbonEntry.objects.filter(
                production_id=production_id, 
                year=year
            )
            
            # Get the practices applied
            sustainable_practices = []
            
            # Water conservation
            if CarbonEntry.objects.filter(
                production_id=production_id,
                source__name__icontains='irrigation'
            ).exists():
                sustainable_practices.append({
                    "id": "water-conservation",
                    "title": "Efficient Irrigation",
                    "description": "This producer uses water-saving irrigation techniques",
                    "impact": "Reduces water usage by up to 30% compared to conventional methods",
                    "costSavings": "Saves approximately $500 per acre annually",
                    "implementation": "Drip irrigation and soil moisture monitoring",
                    "category": "water"
                })
            
            # Organic fertilizers
            if CarbonEntry.objects.filter(
                production_id=production_id,
                source__name__icontains='organic fertilizer'
            ).exists():
                sustainable_practices.append({
                    "id": "organic-fertilizer",
                    "title": "Organic Fertilizers",
                    "description": "This product is grown with natural fertilizers",
                    "impact": "Reduces chemical runoff and builds soil health",
                    "costSavings": "Improves soil quality over time",
                    "implementation": "Compost and natural nutrient sources",
                    "category": "soil"
                })
            
            # Renewable energy
            if CarbonEntry.objects.filter(
                production_id=production_id,
                source__name__icontains='solar' 
            ).exists():
                sustainable_practices.append({
                    "id": "renewable-energy",
                    "title": "Solar Powered",
                    "description": "This farm uses solar energy in its operations",
                    "impact": "Reduces fossil fuel emissions by up to 40%",
                    "costSavings": "Saves approximately $2,000 annually in energy costs",
                    "implementation": "Solar panels power farm operations",
                    "category": "energy"
                })
                
            # Add some default practices if none found
            if not sustainable_practices:
                sustainable_practices = [
                    {
                        "id": "crop-rotation",
                        "title": "Crop Rotation",
                        "description": "This farm practices crop rotation to maintain soil health",
                        "impact": "Reduces pest problems and improves soil fertility",
                        "costSavings": "Reduces fertilizer needs by 20%",
                        "implementation": "Systematically changes crops in the same area",
                        "category": "soil"
                    },
                    {
                        "id": "integrated-pest-management",
                        "title": "Reduced Pesticide Use",
                        "description": "Uses integrated pest management to minimize chemical use",
                        "impact": "Reduces harmful chemical runoff by up to 50%",
                        "costSavings": "Saves on expensive pesticides",
                        "implementation": "Natural predators and targeted treatments",
                        "category": "biodiversity"
                    }
                ]
            
            # Get actual emissions data for context
            emissions_by_category = {}
            total_emissions = 0
            total_offsets = 0
            
            for entry in carbon_entries:
                if entry.type == 'emission':
                    total_emissions += entry.amount
                    category = entry.source.category if hasattr(entry.source, 'category') else 'other'
                    if category in emissions_by_category:
                        emissions_by_category[category] += entry.amount
                    else:
                        emissions_by_category[category] = entry.amount
                elif entry.type == 'offset':
                    total_offsets += entry.amount
            
            # Calculate net footprint
            net_footprint = total_emissions - total_offsets
                
            return Response({
                "recommendations": sustainable_practices,
                "emissionsByCategory": emissions_by_category,
                "totalEmissions": total_emissions,
                "totalOffsets": total_offsets,
                "netFootprint": net_footprint
            })
        except History.DoesNotExist:
            return Response(
                {"error": "Production not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CarbonOffsetViewSet(viewsets.ViewSet):
    permission_classes = []  # No authentication required (adjust as needed)

    def create(self, request):
        production_id = request.data.get('productionId')
        amount = request.data.get('amount')
        if not production_id or not amount:
            return Response({'error': 'productionId and amount are required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            amount = float(amount)
        except ValueError:
            return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)
        # Create the offset entry
        entry = CarbonEntry.objects.create(
            production_id=production_id,
            type='offset',
            amount=amount,
            co2e_amount=amount,  # Assuming amount is in CO2e
            description='Offset created via public API',
            year=timezone.now().year
        )
        return Response({'success': True, 'transactionId': entry.id})

class ProductionSerializer(serializers.ModelSerializer):
    class Meta:
        model = History
        fields = ['id', 'name', 'start_date', 'finish_date', 'published', 'parcel_id', 'product_id', 'description']

class CarbonProductionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = History.objects.all()
    serializer_class = ProductionSerializer
    permission_classes = []  # Public


# Real-time Carbon Calculation API
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from carbon.services.event_carbon_calculator import EventCarbonCalculator


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
        
        calculator = EventCarbonCalculator()
        
        # Create a mock event object for calculation
        class MockEvent:
            def __init__(self, data):
                for key, value in data.items():
                    setattr(self, key, value)
                # Set defaults if not provided
                if not hasattr(self, 'type'):
                    self.type = 'FE'  # Default fertilizer
                if not hasattr(self, 'volume'):
                    self.volume = '10'
                if not hasattr(self, 'concentration'):
                    self.concentration = '10-10-10'
                if not hasattr(self, 'area'):
                    self.area = '1'
                if not hasattr(self, 'way_of_application'):
                    self.way_of_application = 'broadcast'
                if not hasattr(self, 'observation'):
                    self.observation = ''
                if not hasattr(self, 'description'):
                    self.description = 'Event preview'
        
        mock_event = MockEvent(event_data)
        
        # Calculate based on event type
        if event_type == 'chemical':
            calculation_result = calculator.calculate_chemical_event_impact(mock_event)
        elif event_type == 'production':
            calculation_result = calculator.calculate_production_event_impact(mock_event)
        elif event_type == 'weather':
            calculation_result = calculator.calculate_weather_event_impact(mock_event)
        elif event_type == 'equipment':
            calculation_result = calculator.calculate_equipment_event_impact(mock_event)
        elif event_type == 'soil_management':
            calculation_result = calculator.calculate_soil_management_event_impact(mock_event)
        elif event_type == 'business':
            calculation_result = calculator.calculate_business_event_impact(mock_event)
        elif event_type == 'pest_management':
            calculation_result = calculator.calculate_pest_management_event_impact(mock_event)
        else:
            # General or unknown event type
            calculation_result = {
                'co2e': 0.1,
                'efficiency_score': 50.0,
                'usda_verified': False,
                'calculation_method': 'general_event',
                'recommendations': []
            }
        
        # Add helpful metadata for the frontend
        calculation_result['event_type'] = event_type
        calculation_result['timestamp'] = timezone.now().isoformat()
        
        return Response(calculation_result, status=status.HTTP_200_OK)
        
    except Exception as e:
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
