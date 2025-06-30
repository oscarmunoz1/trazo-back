from datetime import datetime, timedelta
from rest_framework import viewsets, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg, Q, ExpressionWrapper
from django.db.models.functions import ExtractWeekDay, ExtractDay, ExtractMonth

from .serializers import (
    RetrieveCompanySerializer,
    CreateCompanySerializer,
    UpdateEstablishmentSerializer,
    RetrieveEstablishmentSerializer,
    EstablishmentChartSerializer,
    EstablishmentProductsReputationSerializer,
    EstablishmentSerializer,
)
from .models import Company, Establishment
from .constants import ALLOWED_PERIODS
from users.models import WorksIn
from users.serializers import WorksInSerializer
from product.models import Parcel, Product
from product.serializers import ProductListOptionsSerializer
from history.models import History, HistoryScan
from history.serializers import HistoryListOptionsSerializer
from reviews.models import Review
from reviews.serializers import ListReviewSerializer
from backend.permissions import CompanyNestedViewSet
from subscriptions.permissions import HasEstablishmentCreationPermission


class CompanyViewSet(CompanyNestedViewSet, viewsets.ModelViewSet):
    queryset = Company.objects.all()
    filter_backends = [filters.OrderingFilter]

    def get_serializer_class(self):
        if self.action == "create":
            return CreateCompanySerializer
        return RetrieveCompanySerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company = serializer.save()
        WorksIn.objects.create(
            user=request.user, company=company, role=WorksIn.COMPANY_ADMIN
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None, company_pk=None):
        company = get_object_or_404(Company, pk=pk)
        members = WorksIn.objects.filter(company=company)
        return Response(
            WorksInSerializer(members, many=True).data,
            status=status.HTTP_200_OK,
        )


class EstablishmentViewSet(CompanyNestedViewSet, viewsets.ModelViewSet):
    queryset = Establishment.objects.all()
    filter_backends = [filters.OrderingFilter]
    serializer_class = UpdateEstablishmentSerializer
    permission_classes = [IsAuthenticated, HasEstablishmentCreationPermission]

    def get_serializer_class(self):
        if (
            self.action == "create"
            or self.action == "update"
            or self.action == "partial_update"
        ):
            return UpdateEstablishmentSerializer
        return RetrieveEstablishmentSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def _generate_filter_kwargs(
        self, period: str, production: str = "", period_filter: str = ""
    ) -> dict:
        filter_kwargs = {}
        if period == "week":
            filter_kwargs[f"{period_filter}date__gte"] = datetime.now() - timedelta(
                days=7
            )
        elif period == "month":
            filter_kwargs[f"{period_filter}date__gte"] = datetime.now() - timedelta(
                days=31
            )
        elif period == "year":
            filter_kwargs[f"{period_filter}date__gte"] = datetime.now() - timedelta(
                days=365
            )

        if production is not None:
            production = get_object_or_404(History, pk=production)
            filter_kwargs["history__id"] = production.id

        return filter_kwargs

    @action(detail=True, methods=["get"])
    def products(
        self, request, pk=None, company_pk=None, establishment_pk=None
    ) -> Response:
        establishment = get_object_or_404(Establishment, pk=pk)
        products = Product.objects.filter(
            histories__parcel__establishment=establishment,
            histories__published=True,
        )
        parcel = request.query_params.get("parcel", None)
        if parcel is not None:
            parcel = get_object_or_404(Parcel, pk=parcel)
            products = products.filter(histories__parcel__id=parcel.id)

        return Response(
            ProductListOptionsSerializer(products.distinct(), many=True).data
        )

    @action(detail=True, methods=["get"])
    def histories(
        self, request, pk=None, company_pk=None, establishment_pk=None
    ) -> Response:
        establishment = get_object_or_404(Establishment, pk=pk)
        parcel = request.query_params.get("parcel", None)
        product = request.query_params.get("product", None)
        period = request.query_params.get("period", None)
        if period is None or period not in ALLOWED_PERIODS:
            return Response(
                {"error": "Period is required and must be week, month or year"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get date kwargs for filter by period
        filter_kwargs = self._generate_filter_kwargs(period, None, "history_scans__")

        if parcel is not None:
            parcel = get_object_or_404(Parcel, pk=parcel)
            filter_kwargs["parcel__id"] = parcel.id

        if product is not None:
            product = get_object_or_404(Product, pk=product)
            filter_kwargs["product__id"] = product.id

        histories = History.objects.filter(
            parcel__establishment=establishment,
            published=True,
            **filter_kwargs,
        ).distinct()

        return Response(HistoryListOptionsSerializer(histories, many=True).data)

    @action(detail=True, methods=["get"])
    def get_charts_data(self, request, pk=None, company_pk=None) -> Response:
        establishment = get_object_or_404(Establishment, pk=pk)
        parcel = request.query_params.get("parcel", None)
        product = request.query_params.get("product", None)
        period = request.query_params.get("period", None)
        production = request.query_params.get("production", None)

        if period is None or period not in ALLOWED_PERIODS:
            return Response(
                {"error": "Period is required and must be week, month or year"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get date kwargs for filter by period
        filter_kwargs = self._generate_filter_kwargs(
            period, production, "history__history_scans__"
        )

        if parcel is not None:
            parcel = get_object_or_404(Parcel, pk=parcel)
            filter_kwargs["history__parcel__id"] = parcel.id

        if product is not None:
            product = get_object_or_404(Product, pk=product)
            filter_kwargs["history__product__id"] = product.id

        series_result = []
        if period == "week":
            histories = HistoryScan.objects.filter(
                history__parcel__establishment=establishment,
                history__published=True,
                **filter_kwargs,
            ).distinct()
            total_histories = histories.annotate(day_of_week=ExtractWeekDay("date"))
            total_histories = total_histories.values("day_of_week").annotate(
                count=Count("id", distinct=True)
            )

            histories_with_review = histories.exclude(reviews__isnull=True)
            histories_with_review = histories_with_review.annotate(
                day_of_week=ExtractWeekDay("date")
            )
            histories_with_review = histories_with_review.values(
                "day_of_week"
            ).annotate(count=Count("id", distinct=True))

            result_dict = {}
            for history in total_histories:
                if history["day_of_week"] not in result_dict:
                    result_dict[history["day_of_week"]] = {}
                result_dict[history["day_of_week"]]["scans"] = history["count"]
            for history in histories_with_review:
                if history["day_of_week"] not in result_dict:
                    result_dict[history["day_of_week"]] = {}
                result_dict[history["day_of_week"]]["reviews"] = history["count"]
            today = datetime.now()
            one_week_ago = today - timedelta(days=6)
            date_range = [
                one_week_ago + timedelta(days=i)
                for i in range((today - one_week_ago).days + 1)
            ]

            series_result = []
            series_result_reviews = []
            days_range = []
            for date in date_range:
                day = date.isoweekday() % 7 + 1
                days_range.append(day)
                if day in result_dict:
                    series_result.append(
                        result_dict[day]["scans"]
                    ) if "scans" in result_dict[day] else series_result.append(0)
                    series_result_reviews.append(
                        result_dict[day]["reviews"]
                    ) if "reviews" in result_dict[
                        day
                    ] else series_result_reviews.append(
                        0
                    )
                else:
                    series_result.append(0)
                    series_result_reviews.append(0)

        elif period == "month":
            histories = HistoryScan.objects.filter(
                history__parcel__establishment=establishment,
                history__published=True,
                **filter_kwargs,
            ).distinct()
            total_histories = histories.annotate(
                day_of_month=ExtractDay("date"), month=ExtractMonth("date")
            )
            total_histories = total_histories.values("day_of_month", "month")
            total_histories = total_histories.annotate(count=Count("id", distinct=True))

            histories_with_review = histories.exclude(reviews__isnull=True)
            histories_with_review = histories_with_review.annotate(
                day_of_month=ExtractDay("date"), month=ExtractMonth("date")
            )
            histories_with_review = histories_with_review.values(
                "day_of_month", "month"
            ).annotate(count=Count("id", distinct=True))

            result_dict = {}
            for history in total_histories:
                month = history["month"]
                day_of_month = history["day_of_month"]
                if month not in result_dict:
                    result_dict[month] = {}
                if day_of_month not in result_dict[month]:
                    result_dict[month][day_of_month] = {}
                result_dict[month][day_of_month]["scans"] = history["count"]
            for history in histories_with_review:
                month = history["month"]
                day_of_month = history["day_of_month"]
                if month not in result_dict:
                    result_dict[month] = {}
                if day_of_month not in result_dict[month]:
                    result_dict[month][day_of_month] = {}
                result_dict[month][day_of_month]["reviews"] = history["count"]
            today = datetime.now()
            one_month_ago = today - timedelta(days=31)
            date_range = [
                one_month_ago + timedelta(days=i)
                for i in range((today - one_month_ago).days + 1)
            ]

            series_result = []
            series_result_reviews = []
            days_range = []
            for date in date_range:
                day = date.day
                month = date.month
                days_range.append(day)
                if month in result_dict and day in result_dict[month]:
                    series_result.append(
                        result_dict[month][day]["scans"]
                    ) if "scans" in result_dict[month][day] else series_result.append(0)
                    series_result_reviews.append(
                        result_dict[month][day]["reviews"]
                    ) if "reviews" in result_dict[month][
                        day
                    ] else series_result_reviews.append(
                        0
                    )
                else:
                    series_result.append(0)
                    series_result_reviews.append(0)
        elif period == "year":
            histories = HistoryScan.objects.filter(
                history__parcel__establishment=establishment,
                history__published=True,
                **filter_kwargs,
            ).distinct()
            total_histories = histories.annotate(month=ExtractMonth("date"))
            total_histories = total_histories.values("month")
            total_histories = total_histories.annotate(count=Count("id", distinct=True))

            histories_with_review = histories.exclude(reviews__isnull=True)
            histories_with_review = histories_with_review.annotate(
                month=ExtractMonth("date")
            )
            histories_with_review = histories_with_review.values("month")
            histories_with_review = histories_with_review.annotate(
                count=Count("id", distinct=True)
            )

            result_dict = {}
            for history in total_histories:
                month = history["month"]
                if month not in result_dict:
                    result_dict[month] = {}
                result_dict[month]["scans"] = history["count"]
            for history in histories_with_review:
                month = history["month"]
                if month not in result_dict:
                    result_dict[month] = {}
                result_dict[month]["reviews"] = history["count"]

            series_result = []
            series_result_reviews = []
            for month in range(1, 13):
                if month in result_dict:
                    series_result.append(
                        result_dict[month]["scans"]
                    ) if "scans" in result_dict[month] else series_result.append(0)
                    series_result_reviews.append(
                        result_dict[month]["reviews"]
                    ) if "reviews" in result_dict[
                        month
                    ] else series_result_reviews.append(
                        0
                    )
                else:
                    series_result.append(0)
                    series_result_reviews.append(0)

        result = {
            "scans_vs_sales": EstablishmentChartSerializer(
                {"series": {"scans": series_result, "sales": series_result_reviews}},
                context={
                    "month_length": len(series_result) if period == "month" else None,
                    "period": period,
                    "days": days_range
                    if period == "month" or period == "week"
                    else None,
                },
            ).data
        }

        return Response(
            result,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def products_reputation(
        self, request, pk=None, company_pk=None, establishment_pk=None
    ) -> Response:
        establishment = get_object_or_404(Establishment, pk=pk)
        parcel = request.query_params.get("parcel", None)
        product = request.query_params.get("product", None)
        period = request.query_params.get("period", None)
        production = request.query_params.get("production", None)
        if period is None or period not in ALLOWED_PERIODS:
            return Response(
                {"error": "Period is required and must be week, month or year"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get date kwargs for filter by period
        filter_kwargs = self._generate_filter_kwargs(
            period, None, "production__history_scans__"
        )

        if parcel is not None:
            parcel = get_object_or_404(Parcel, pk=parcel)
            filter_kwargs["production__parcel__id"] = parcel.id

        if product is not None:
            product = get_object_or_404(Product, pk=product)
            filter_kwargs["production__product__id"] = product.id

        if production is not None:
            production = get_object_or_404(History, pk=production)
            filter_kwargs["production__id"] = production.id

        series_result = []
        options_result = []
        reviews = Review.objects.filter(
            production__parcel__establishment=establishment,
            **filter_kwargs,
        ).distinct()

        reviews = reviews.values("production__product__name")
        reviews = reviews.annotate(avg_rating=Avg("rating"))

        for review in reviews:
            series_result.append(round(review["avg_rating"], 1))
            options_result.append(review["production__product__name"])

        result = {
            "products_reputation": EstablishmentProductsReputationSerializer(
                {"series": series_result, "options": options_result},
            ).data
        }

        return Response(
            result,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def last_reviews(
        self, request, pk=None, company_pk=None, establishment_pk=None
    ) -> Response:
        establishment = get_object_or_404(Establishment, pk=pk)
        reviews = Review.objects.filter(
            production__parcel__establishment=establishment,
        ).order_by("-date")[:3]
        return Response(
            ListReviewSerializer(reviews, many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def rating_reviews_percentage(
        self, request, pk=None, company_pk=None, establishment_pk=None
    ) -> Response:
        establishment = get_object_or_404(Establishment, pk=pk)
        # Return percentage of positive, neutral and negative reviews for the establishment

        reviews = Review.objects.filter(
            production__parcel__establishment=establishment,
        )
        total_reviews = reviews.count()

        reviews = reviews.aggregate(
            positive=Count("rating", filter=Q(rating__gte=3)),
            neutral=Count("rating", filter=Q(rating=2)),
            negative=Count("rating", filter=Q(rating__lte=1)),
        )

        result = {
            "positive": int(reviews["positive"] / total_reviews * 100)
            if total_reviews > 0
            else 0,
            "neutral": int(reviews["neutral"] / total_reviews * 100)
            if total_reviews > 0
            else 0,
            "negative": int(reviews["negative"] / total_reviews * 100)
            if total_reviews > 0
            else 0,
        }

        return Response(
            result,
            status=status.HTTP_200_OK,
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class PublicEstablishmentViewSet(viewsets.ViewSet):
    """
    Public endpoint for consumer-facing establishment views.
    No authentication required.
    """
    permission_classes = []

    def retrieve(self, request, pk=None):
        """Get public establishment data by ID"""
        try:
            # Only show active establishments
            establishment = get_object_or_404(
                Establishment.objects.select_related('company'), 
                pk=pk, 
                is_active=True
            )
            
            # Use EstablishmentSerializer but filter sensitive data
            serializer = EstablishmentSerializer(establishment, context={'request': request})
            data = serializer.data
            
            # Remove sensitive fields for public view
            public_fields = [
                'id', 'name', 'description', 'address', 'city', 'state', 'country',
                'location', 'latitude', 'longitude', 'certifications', 'about', 
                'main_activities', 'location_highlights', 'custom_message', 'images', 
                'email', 'phone', 'zip_code', 'crops_grown', 'sustainability_practices', 
                'employee_count', 'total_acreage', 'year_established', 'establishment_type',
                'farming_method', 'image', 'water_sources', 'climate_zone', 'soil_types',
                'conservation_practices', 'irrigation_methods'
            ]
            
            public_data = {key: data[key] for key in public_fields if key in data}
            
            return Response(public_data, status=status.HTTP_200_OK)
            
        except Establishment.DoesNotExist:
            return Response({
                'error': 'Establishment not found or not available publicly'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'error': f'An error occurred: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
