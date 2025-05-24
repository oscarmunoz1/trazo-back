from datetime import datetime, timedelta

from django.shortcuts import render
from django.contrib.gis.geoip2 import GeoIP2
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, filters, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action, permission_classes
from .models import (
    History,
    ProductionEvent,
    WeatherEvent,
    ChemicalEvent,
    GeneralEvent,
    EquipmentEvent,
    SoilManagementEvent,
    BusinessEvent,
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
    BusinessEventSerializer,
    PestManagementEventSerializer,
    PublicHistorySerializer,
    ListHistoryClassSerializer,
    UpdateChemicalEventSerializer,
    UpdateWeatherEventSerializer,
    UpdateProductionEventSerializer,
    UpdateGeneralEventSerializer,
    UpdateEquipmentEventSerializer,
    UpdateSoilManagementEventSerializer,
    UpdateBusinessEventSerializer,
    UpdatePestManagementEventSerializer,
)
from .constants import (
    WEATHER_EVENT_TYPE,
    PRODUCTION_EVENT_TYPE,
    CHEMICAL_EVENT_TYPE,
    GENERAL_EVENT_TYPE,
    EQUIPMENT_EVENT_TYPE,
    SOIL_MANAGEMENT_EVENT_TYPE,
    BUSINESS_EVENT_TYPE,
    PEST_MANAGEMENT_EVENT_TYPE,
    event_map,
    ALLOWED_PERIODS,
)

from product.models import Parcel, Product
from backend.permissions import CompanyNestedViewSet
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
            start_date=data["date"],
            parcel=parcel,
            product=obj,
            extra_data=extra_data,
            type=type,
        )
        parcel.current_history = history
        parcel.save()
        serializer = HistorySerializer(history)
        return Response(serializer.data)

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

        if ip_address:
            try:
                g = GeoIP2()
                city = g.city(ip_address).get("city")
                country = g.country(ip_address).get("country_name")
            except Exception as e:
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
        elif event_type == BUSINESS_EVENT_TYPE:
            return UpdateBusinessEventSerializer if is_mutation else BusinessEventSerializer
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
        if event_type is not None:
            event_type = int(event_type)
            
        event_model = event_map.get(event_type)
        if event_model:
            return event_model.objects.all()
        else:
            return GeneralEvent.objects.all()

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

                event_model = event_map.get(int(event_type), GeneralEvent)
                event = event_model.objects.create(
                    history=history,
                    index=index,
                    created_by=self.request.user,
                    **serializer.validated_data,
                )
                event.save()
