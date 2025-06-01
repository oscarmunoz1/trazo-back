from django.urls import path, include, re_path

from rest_framework_nested import routers
from .views import CompanyViewSet, EstablishmentViewSet, PublicEstablishmentViewSet
from history.views import HistoryViewSet, HistoryScanViewSet, EventViewSet
from product.views import ParcelViewSet, ProductsViewSet
from reviews.views import ReviewsViewSet


router = routers.DefaultRouter()

router.register(r"companies", CompanyViewSet, basename="companies")

# Public routes (no authentication required)
router.register(r"companies/public/establishments", PublicEstablishmentViewSet, basename="public-establishments")

# Company routes
company_router = routers.NestedDefaultRouter(router, r"companies", lookup="company")
company_router.register(
    r"establishments", EstablishmentViewSet, basename="company-establishments"
)


# Establishment routes
establishment_router = routers.NestedDefaultRouter(
    company_router, r"establishments", lookup="establishment"
)

establishment_router.register(
    r"scans", HistoryScanViewSet, basename="establishment-scans"
)
establishment_router.register(r"events", EventViewSet, basename="establishment-events")
establishment_router.register(
    r"parcels", ParcelViewSet, basename="establishment-parcels"
)
establishment_router.register(
    r"products", ProductsViewSet, basename="establishment-products"
)

# Parcels routes
parcel_router = routers.NestedDefaultRouter(
    establishment_router, r"parcels", lookup="parcel"
)

parcel_router.register(
    r"histories",
    HistoryViewSet,
    basename="parcel-histories",
)

# History routes
history_router = routers.NestedDefaultRouter(
    parcel_router, r"histories", lookup="history"
)
history_router.register(r"reviews", ReviewsViewSet, basename="history-reviews")


urlpatterns = [
    re_path(r"^", include(router.urls)),
    re_path(r"^", include(company_router.urls)),
    re_path(r"^", include(establishment_router.urls)),
    re_path(r"^", include(parcel_router.urls)),
    re_path(r"^", include(history_router.urls)),
    path("", include("history.urls")),
]
