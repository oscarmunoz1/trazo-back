from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Q
from django.utils import timezone
from django.utils.timezone import make_aware

from rest_framework import filters, status, viewsets
from rest_framework.decorators import action, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from company.models import Company
from product.models import Product, Parcel

from common.models import Gallery
from backend.permissions import CompanyNestedViewSet

from .models import CommonEvent, History, HistoryScan
from .serializers import (
    EventSerializer,
    HistorySerializer,
    ListHistoryClassSerializer,
    PublicHistorySerializer,
)

import hashlib
from datetime import datetime, timedelta
from dateutil import parser as date_parser

from rest_framework import viewsets, filters, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action, permission_classes
from .models import (
    WeatherEvent,
    ChemicalEvent,
    ProductionEvent,
    GeneralEvent,
    EquipmentEvent,
    SoilManagementEvent,
    PestManagementEvent,
    HistoryScan,
)
from reviews.models import Review
from .serializers import (
    HistorySerializer,
    WeatherEventSerializer,
    ProductionEventSerializer,
    ChemicalEventSerializer,
    GeneralEventSerializer,
    EquipmentEventSerializer,
    SoilManagementEventSerializer,
    PestManagementEventSerializer,
    PublicHistorySerializer,
    ListHistoryClassSerializer,
    UpdateChemicalEventSerializer,
    UpdateWeatherEventSerializer,
    UpdateProductionEventSerializer,
    UpdateGeneralEventSerializer,
    UpdateEquipmentEventSerializer,
    UpdateSoilManagementEventSerializer,
    UpdatePestManagementEventSerializer,
)
from .constants import (
    WEATHER_EVENT_TYPE,
    PRODUCTION_EVENT_TYPE,
    CHEMICAL_EVENT_TYPE,
    GENERAL_EVENT_TYPE,
    EQUIPMENT_EVENT_TYPE,
    SOIL_MANAGEMENT_EVENT_TYPE,
    PEST_MANAGEMENT_EVENT_TYPE,
    EVENT_TYPE_TO_MODEL,
    ALLOWED_PERIODS,
)

from django.db.models import Q


class HistoryViewSet(viewsets.ModelViewSet):
    serializer_class = HistorySerializer
    filter_backends = [filters.OrderingFilter]

    def get_serializer_class(self):
        if (
            self.action == "create"
            or self.action == "update"
            or self.action == "partial_update"
        ):
            return HistorySerializer
        elif self.action == "list":
            return ListHistoryClassSerializer
        else:
            return HistorySerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def get_queryset(self):
        if self.action == "public_history":
            return History.objects.filter(published=True)
        elif self.action == "my_scans":
            return History.objects.filter(
                history_scans__user=self.request.user
            ).select_related(
                'product',
                'parcel__establishment'
            ).order_by('id', '-history_scans__date').distinct('id')
        elif self.action == "my_reviews":
            return Review.objects.filter(
                user=self.request.user
            ).select_related(
                'production',
                'production__product',
                'production__parcel__establishment'
            ).order_by('-date')
        else:
            return History.objects.all()

    def create(self, request):
        data = request.data
        parcel = Parcel.objects.get(id=data["parcel"])
        product = data["product"]
        obj, created = Product.objects.get_or_create(name=product["name"])
        type = data["type"]
        age_of_plants = data["age_of_plants"]
        number_of_plants = data["number_of_plants"]
        soil_ph = data["soil_ph"]
        is_outdoor = data["is_outdoor"]
        extra_data = {
            "age_of_plants": age_of_plants,
            "number_of_plants": number_of_plants,
            "soil_ph": soil_ph,
            "is_outdoor": is_outdoor,
        }
        history = History.objects.create(
            start_date=data["start_date"],
            parcel=parcel,
            product=obj,
            extra_data=extra_data,
            type=type,
        )
        parcel.current_history = history
        parcel.save()
        serializer = HistorySerializer(history)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='start-production', permission_classes=[IsAuthenticated])
    def start_production(self, request):
        """
        Enhanced production creation endpoint with crop selection and blockchain integration.
        Supports Step 7 implementation from TRAZO_FOCUSED_IMPLEMENTATION_PLAN_FINAL.md
        """
        try:
            data = request.data
            
            # Validate required fields
            required_fields = ['name', 'parcel_id', 'crop_type', 'start_date']
            for field in required_fields:
                if field not in data:
                    return Response(
                        {'error': f'Missing required field: {field}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Get parcel and validate ownership
            try:
                parcel = Parcel.objects.get(id=data['parcel_id'])
                # Add permission check here if needed
                # if not user has access to this parcel...
            except Parcel.DoesNotExist:
                return Response(
                    {'error': 'Parcel not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Create or get product based on crop type
            crop_type = data['crop_type']
            product, created = Product.objects.get_or_create(name=crop_type)
            
            # Parse dates with timezone awareness
            start_date_str = data['start_date'].replace('Z', '+00:00')
            start_date = datetime.fromisoformat(start_date_str)
            if start_date.tzinfo is None:
                start_date = timezone.make_aware(start_date)
            
            expected_harvest = None
            if data.get('expected_harvest'):
                expected_harvest_str = data['expected_harvest'].replace('Z', '+00:00')
                expected_harvest = datetime.fromisoformat(expected_harvest_str)
                if expected_harvest.tzinfo is None:
                    expected_harvest = timezone.make_aware(expected_harvest)
            
            # Create production with enhanced data
            extra_data = {
                'crop_category': self._categorize_crop(crop_type),
                'production_method': data.get('production_method', 'conventional'),
                'estimated_yield': data.get('estimated_yield'),
                'irrigation_method': data.get('irrigation_method'),
                'created_via': 'production_start_form',
                'blockchain_enabled': True,  # Enable blockchain for new productions
            }
            
            # Add optional fields to extra_data
            optional_fields = ['age_of_plants', 'number_of_plants', 'soil_ph', 'is_outdoor', 'notes']
            for field in optional_fields:
                if data.get(field):
                    extra_data[field] = data[field]
            
            history = History.objects.create(
                name=data['name'],
                start_date=start_date,
                finish_date=expected_harvest,
                parcel=parcel,
                product=product,
                extra_data=extra_data,
                type=data.get('type', 'OR'),  # Default to Orchard
                description=data.get('description', ''),
                operator=request.user if request.user.is_authenticated else None
            )
            
            # Update parcel's current history
            parcel.current_history = history
            parcel.save()
            
            # Create initial blockchain record for this production
            try:
                from carbon.services.blockchain import blockchain_service
                
                initial_carbon_data = {
                    'production_id': history.id,
                    'total_emissions': 0.0,
                    'total_offsets': 0.0,
                    'crop_type': crop_type,
                    'calculation_method': 'initial_production_setup',
                    'usda_verified': False,
                    'timestamp': int(start_date.timestamp()),
                    'carbon_score': 50,  # Initial neutral score
                    'industry_percentile': 50
                }
                
                blockchain_result = blockchain_service.create_carbon_record(history.id, initial_carbon_data)
                
                # Store blockchain reference in extra_data
                history.extra_data['blockchain_transaction'] = blockchain_result.get('transaction_hash')
                history.extra_data['blockchain_verified'] = blockchain_result.get('blockchain_verified', False)
                history.save()
                
            except Exception as e:
                print(f"Error creating initial blockchain record: {e}")
                # Continue without blockchain - not critical for production creation
            
            # Serialize and return the created production
            serializer = HistorySerializer(history)
            response_data = serializer.data
            
            # Add additional metadata for the frontend
            response_data.update({
                'crop_category': extra_data.get('crop_category'),
                'blockchain_enabled': extra_data.get('blockchain_enabled', False),
                'blockchain_transaction': extra_data.get('blockchain_transaction'),
                'qr_code_url': history.qr_code.url if history.qr_code else None,
                'establishment': {
                    'id': parcel.establishment.id,
                    'name': parcel.establishment.name,
                    'location': parcel.establishment.get_location()
                },
                'parcel': {
                    'id': parcel.id,
                    'name': parcel.name,
                    'area': parcel.area
                }
            })
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response(
                {'error': f'Invalid date format: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            print(f"Error creating production: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': 'Failed to create production'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _categorize_crop(self, crop_name: str) -> str:
        """Helper method to categorize crops for the production start form"""
        crop_lower = crop_name.lower()
        
        fruit_keywords = ['orange', 'apple', 'grape', 'lemon', 'lime', 'strawberry', 'blueberry', 'avocado']
        vegetable_keywords = ['tomato', 'lettuce', 'carrot', 'broccoli', 'spinach', 'cucumber', 'pepper', 'onion']
        grain_keywords = ['corn', 'wheat', 'rice', 'barley', 'oats', 'soybean']
        herb_keywords = ['basil', 'oregano', 'thyme', 'rosemary', 'mint']
        legume_keywords = ['bean', 'chickpea', 'lentil', 'pea']
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
                
        return 'other'

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def public_history(self, request, pk=None):
        queryset = self.get_queryset()
        history = get_object_or_404(queryset, pk=pk)
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(",")[0]
        else:
            ip_address = request.META.get("HTTP_X_REAL_IP")

        city = None
        country = None

        # Get city and country from IP using free API (no GDAL required)
        if ip_address:
            try:
                import requests
                # Using ipapi.co - free tier allows 1000 requests/day
                response = requests.get(f'https://ipapi.co/{ip_address}/json/', timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    city = data.get('city')
                    country = data.get('country_name')
            except Exception as e:
                # If geolocation fails, continue without it
                print(f"IP geolocation failed: {e}")
                pass

        history_scan = HistoryScan.objects.create(
            history=history,
            user=request.user if request.user.is_authenticated else None,
            ip_address=ip_address,
            city=city,
            country=country,
        )
        similar_histories = History.objects.filter(
            parcel__establishment__company=history.parcel.establishment.company,
            published=True,
        ).exclude(id=history.id).select_related(
            'product', 
            'parcel__establishment'
        ).order_by('-id')[:5]
        serializer = PublicHistorySerializer(
            history, context={"history_scan": history_scan.id, "similar_histories": similar_histories, "request": request}
        )
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_scans(self, request):
        queryset = self.get_queryset()
        scans_data = []
        for history in queryset:
            latest_scan = history.history_scans.filter(user=request.user).order_by('-date').first()
            if latest_scan:
                scans_data.append(
                    PublicHistorySerializer(
                        history, 
                        context={"history_scan": latest_scan.id}
                    ).data
                )
        return Response(scans_data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_reviews(self, request):
        queryset = self.get_queryset()
        reviews_data = []
        for review in queryset:
            reviews_data.append({
                'id': review.id,
                'headline': review.headline,
                'written_review': review.written_review,
                'date': review.date,
                'rating': review.rating,
                'history': HistorySerializer(review.production).data
            })
        return Response(reviews_data)


class PublicHistoryScanViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=["post"])
    @permission_classes([AllowAny])
    def comment(self, request, pk=None):
        history_scan = get_object_or_404(HistoryScan, pk=pk)
        comment = request.data.get("comment", None)
        if comment is None:
            return Response(
                {"error": "Comment is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        history_scan.comment = comment
        history_scan.save()
        return Response(status=status.HTTP_200_OK)


class HistoryScanViewSet(CompanyNestedViewSet, viewsets.ModelViewSet):
    queryset = HistoryScan.objects.all()
    serializer_class = ListHistoryClassSerializer

    @action(detail=False, methods=["get"])
    def list_scans_by_establishment(
        self, request, parcel_pk=None, company_pk=None, establishment_pk=None
    ):
        parcel = request.query_params.get("parcel", None)
        product = request.query_params.get("product", None)
        period = request.query_params.get("period", None)
        production = request.query_params.get("production", None)
        if period is None or period not in ALLOWED_PERIODS:
            return Response(
                {"error": "Period is required and must be week, month or year"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if self.establishment is None:
            return Response(
                {"error": "Establishment is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get date kwargs for filter by period
        date_kwargs = {}
        if period == "week":
            date_kwargs["date__gte"] = datetime.now() - timedelta(days=7)
        elif period == "month":
            date_kwargs["date__gte"] = datetime.now() - timedelta(days=30)
        elif period == "year":
            date_kwargs["date__gte"] = datetime.now() - timedelta(days=365)

        # Get last 9 scans from the establishment
        history_scans = HistoryScan.objects.filter(
            history__parcel__establishment=self.establishment,
            **date_kwargs,
        ).order_by("-date")
        if parcel is not None:
            history_scans = history_scans.filter(history__parcel__id=parcel)
        if product is not None:
            history_scans = history_scans.filter(history__product__id=product)
        if production is not None:
            history_scans = history_scans.filter(history__id=production)
        return Response(
            ListHistoryClassSerializer(
                history_scans[0:9], many=True, context={"history_scan": True}
            ).data
        )


class EventViewSet(CompanyNestedViewSet, viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated,)
    filter_backends = [filters.OrderingFilter]

    def get_serializer_class(self):
        event_type = (
            self.request.data.get("event_type")
            if "event_type" in self.request.data
            else self.request.query_params.get("event_type", None)
        )
        
        # For retrieve actions without event_type, we'll determine it in get_object
        # and store it for later use
        if event_type is None and self.action == "retrieve":
            # Check if we've already determined the event type
            if hasattr(self, '_determined_event_type'):
                event_type = self._determined_event_type
            else:
                # Default to general for now, will be corrected in retrieve method
                event_type = GENERAL_EVENT_TYPE
        
        if event_type is None:
            raise Exception("Event type is required")
        event_type = int(event_type)
        
        is_mutation = self.action in ["create", "update", "partial_update"]
        
        if event_type == WEATHER_EVENT_TYPE:
            return UpdateWeatherEventSerializer if is_mutation else WeatherEventSerializer
        elif event_type == PRODUCTION_EVENT_TYPE:
            return UpdateProductionEventSerializer if is_mutation else ProductionEventSerializer
        elif event_type == CHEMICAL_EVENT_TYPE:
            return UpdateChemicalEventSerializer if is_mutation else ChemicalEventSerializer
        elif event_type == EQUIPMENT_EVENT_TYPE:
            return UpdateEquipmentEventSerializer if is_mutation else EquipmentEventSerializer
        elif event_type == SOIL_MANAGEMENT_EVENT_TYPE:
            return UpdateSoilManagementEventSerializer if is_mutation else SoilManagementEventSerializer
        elif event_type == PEST_MANAGEMENT_EVENT_TYPE:
            return UpdatePestManagementEventSerializer if is_mutation else PestManagementEventSerializer
        else:  # GENERAL_EVENT_TYPE
            return UpdateGeneralEventSerializer if is_mutation else GeneralEventSerializer

    def get_queryset(self):
        event_type = (
            self.request.data.get("event_type")
            if "event_type" in self.request.data
            else self.request.query_params.get("event_type", None)
        )
        
        # For retrieve actions without event_type, return a special marker
        if event_type is None and self.action == "retrieve":
            # We'll handle this in get_object method
            return None
        
        if event_type is not None:
            event_type = int(event_type)
            
        event_model = EVENT_TYPE_TO_MODEL.get(event_type)
        if event_model:
            queryset = event_model.objects.all()
        else:
            queryset = GeneralEvent.objects.all()
        
        # Filter by company and establishment if they are set
        # Events are connected through: Event -> History -> Parcel -> Establishment -> Company
        if hasattr(self, 'company') and self.company is not None:
            queryset = queryset.filter(history__parcel__establishment__company=self.company)
        
        if hasattr(self, 'establishment') and self.establishment is not None:
            queryset = queryset.filter(history__parcel__establishment=self.establishment)
            
        return queryset

    def get_object(self):
        """
        Override get_object to handle cross-model lookups when event_type is not specified
        """
        event_type = self.request.query_params.get("event_type", None)
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        event_id = self.kwargs[lookup_url_kwarg]

        # If event_type is specified, only search in that specific event type
        if event_type is not None:
            try:
                event_type = int(event_type)
                event_model = EVENT_TYPE_TO_MODEL.get(event_type)
                
                if event_model:
                    queryset = event_model.objects.all()
                    
                    # Apply the same filtering as in get_queryset
                    if hasattr(self, 'company') and self.company is not None:
                        queryset = queryset.filter(history__parcel__establishment__company=self.company)
                    
                    if hasattr(self, 'establishment') and self.establishment is not None:
                        queryset = queryset.filter(history__parcel__establishment=self.establishment)
                    
                    obj = queryset.get(pk=event_id)
                    # Check permissions
                    self.check_object_permissions(self.request, obj)
                    # Store the determined event type for serializer selection
                    self._determined_event_type = event_type
                    return obj
                    
            except (ValueError, event_model.DoesNotExist):
                # If the specified event_type doesn't contain this event, raise 404
                from django.http import Http404
                raise Http404(f"Event with ID {event_id} not found in event type {event_type}")

        # For actions without event_type parameter, search across all event types
        if self.action in ["update", "partial_update", "retrieve"]:
            # Try to find the event across all event types
            
            # Apply company/establishment filtering to each model
            for event_type_id, event_model in EVENT_TYPE_TO_MODEL.items():
                try:
                    queryset = event_model.objects.all()
                    
                    # Apply the same filtering as in get_queryset
                    if hasattr(self, 'company') and self.company is not None:
                        queryset = queryset.filter(history__parcel__establishment__company=self.company)
                    
                    if hasattr(self, 'establishment') and self.establishment is not None:
                        queryset = queryset.filter(history__parcel__establishment=self.establishment)
                    
                    obj = queryset.get(pk=event_id)
                    # Check permissions
                    self.check_object_permissions(self.request, obj)
                    # Store the determined event type for serializer selection
                    self._determined_event_type = event_type_id
                    return obj
                except event_model.DoesNotExist:
                    continue
            
            # If not found in any event type, raise 404
            from django.http import Http404
            raise Http404("Event not found")
        
        # Use default behavior for other cases
        return super().get_object()

    def retrieve(self, request, *args, **kwargs):
        """
        Override retrieve to handle event_type determination
        """
        instance = self.get_object()
        
        # If we determined the event type during get_object, update the serializer
        if hasattr(self, '_determined_event_type'):
            # Force re-evaluation of serializer class with correct event type
            event_type = self._determined_event_type
            
            # Get the correct serializer class
            if event_type == WEATHER_EVENT_TYPE:
                serializer_class = WeatherEventSerializer
            elif event_type == PRODUCTION_EVENT_TYPE:
                serializer_class = ProductionEventSerializer
            elif event_type == CHEMICAL_EVENT_TYPE:
                serializer_class = ChemicalEventSerializer
            elif event_type == EQUIPMENT_EVENT_TYPE:
                serializer_class = EquipmentEventSerializer
            elif event_type == SOIL_MANAGEMENT_EVENT_TYPE:
                serializer_class = SoilManagementEventSerializer
            elif event_type == PEST_MANAGEMENT_EVENT_TYPE:
                serializer_class = PestManagementEventSerializer
            else:  # GENERAL_EVENT_TYPE
                serializer_class = GeneralEventSerializer
            
            serializer = serializer_class(instance)
            return Response(serializer.data)
        
        # Default behavior
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def perform_create(self, serializer):
        parcels = self.request.POST.getlist("parcels", None)
        event_type = self.request.data.get("event_type", None)
        if event_type is None:
            raise Exception("Event type is required")
        if parcels is None or parcels is []:
            raise Exception("Parcel is required")
        parcels = Parcel.objects.filter(
            id__in=[int(parcel) for parcel in parcels]
        ).select_related("current_history")

        for parcel in parcels:
            if parcel.current_history is not None:
                history = parcel.current_history
                index = (
                    history.history_weatherevent_events.count()
                    + history.history_chemicalevent_events.count()
                    + history.history_generalevent_events.count()
                    + history.history_productionevent_events.count()
                ) + 1

                event_model = EVENT_TYPE_TO_MODEL.get(int(event_type), GeneralEvent)
                event = event_model.objects.create(
                    history=history,
                    index=index,
                    created_by=self.request.user,
                    **serializer.validated_data,
                )
                event.save()

    def update(self, request, *args, **kwargs):
        """
        Override update to prevent changing event types after creation
        """
        # Get the current instance first to determine its type
        instance = self.get_object()
        
        # Determine the current event type based on the model
        current_event_type = None
        for event_type_id, event_model in EVENT_TYPE_TO_MODEL.items():
            if isinstance(instance, event_model):
                current_event_type = event_type_id
                break
        
        # Get the requested event type
        requested_event_type = (
            self.request.data.get("event_type")
            if "event_type" in self.request.data
            else self.request.query_params.get("event_type", None)
        )
        
        if requested_event_type is not None:
            requested_event_type = int(requested_event_type)
            
            # Check if user is trying to change the event type
            if current_event_type != requested_event_type:
                return Response(
                    {
                        "error": "Cannot change event type after creation",
                        "detail": f"This event is a {instance.__class__.__name__} and cannot be changed to event type {requested_event_type}",
                        "current_event_type": current_event_type,
                        "requested_event_type": requested_event_type
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # If event types match, proceed with normal update
        return super().update(request, *args, **kwargs)
