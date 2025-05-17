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

        total_emissions = queryset.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        total_offsets = queryset.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        net_carbon = total_emissions - total_offsets

        # Get industry average (placeholder logic, adjust based on your needs)
        industry_average = CarbonBenchmark.objects.filter(year=year).aggregate(Sum('average_emissions'))['average_emissions__sum'] or 0

        # Calculate Carbon Score (1-100, benchmarked against industry average)
        carbon_score = 100
        if industry_average > 0:
            # Simple scoring: lower net carbon relative to industry average gives higher score
            ratio = net_carbon / industry_average
            carbon_score = max(1, min(100, int(100 * (1 - ratio))))

        # Calculate year-over-year change (placeholder logic)
        previous_year = int(year) - 1
        prev_queryset = CarbonEntry.objects.all()
        if establishment_id:
            prev_queryset = prev_queryset.filter(establishment_id=establishment_id)
        if production_id:
            prev_queryset = prev_queryset.filter(production_id=production_id)
        prev_queryset = prev_queryset.filter(year=previous_year)

        prev_total_emissions = prev_queryset.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        prev_total_offsets = prev_queryset.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        prev_net_carbon = prev_total_emissions - prev_total_offsets

        year_over_year_change = 0
        if prev_net_carbon > 0:
            year_over_year_change = ((net_carbon - prev_net_carbon) / prev_net_carbon) * 100

        # Detailed recommendations based on USDA data (placeholder values for illustration)
        recommendations = []
        if net_carbon > industry_average:
            recommendations.append('Consider switching to organic fertilizers to reduce emissions by up to 20% (USDA, 2023).')
            recommendations.append('Implement drip irrigation systems to save water and reduce emissions by approximately 15% (USDA Climate-Smart Agriculture, 2024).')
            recommendations.append('Adopt cover cropping practices to sequester carbon and improve soil health, potentially offsetting 10% of emissions (USDA NRCS, 2022).')
        if total_emissions > 0:
            recommendations.append('Review fuel usage in machinery; switching to biodiesel blends can cut emissions by 10-15% (USDA Bioenergy Program, 2023).')
        if total_offsets < (total_emissions * 0.1):
            recommendations.append('Explore carbon offset programs like tree planting or renewable energy credits to balance your footprint (USDA Conservation Reserve Program, 2024).')
        if not recommendations:
            recommendations.append('Your carbon footprint is well-managed. Continue monitoring and consider sharing best practices with peers (USDA Sustainable Agriculture Network).')

        return Response({
            'total_emissions': total_emissions,
            'total_offsets': total_offsets,
            'net_carbon': net_carbon,
            'industry_average': industry_average,
            'carbon_score': carbon_score,
            'year_over_year_change': year_over_year_change,
            'recommendations': recommendations,
            'year': int(year)
        })

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
        report.save()

        serializer = CarbonReportSerializer(report)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

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
        relatable_footprint = f"{net_carbon / 0.4:.1f} miles driven"
        badges = [
            {"name": "USDA Organic", "icon": "organic", "isVerified": True, "description": "Certified organic."},
        ]
        timeline = []  # Could be filled with production events if needed
        # Placeholder farmer info
        farmer = {
            "name": "Test Farmer",
            "photo": "",
            "bio": "Committed to sustainability.",
            "generation": 3,
            "location": "California, USA",
            "certifications": ["USDA Organic"],
            "sustainabilityInitiatives": ["Drip irrigation", "Cover cropping"],
            "carbonReduction": 20,
            "yearsOfPractice": 10
        }
        return Response({
            "carbonScore": carbon_score,
            "netFootprint": net_carbon,
            "relatableFootprint": relatable_footprint,
            "badges": badges,
            "farmer": farmer,
            "timeline": timeline,
            "isUsdaVerified": True,
            "verificationDate": str(timezone.now().date()),
            "socialProof": {"totalScans": 100, "totalOffsets": 10, "averageRating": 4.8}
        })

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
