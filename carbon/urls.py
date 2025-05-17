from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import CarbonEstablishmentSummaryViewSet, CarbonProductionSummaryViewSet, PublicProductionViewSet, CarbonOffsetViewSet, CarbonProductionViewSet

router = DefaultRouter()
router.register(r'sources', views.CarbonSourceViewSet)
router.register(r'offset-actions', views.CarbonOffsetActionViewSet)
router.register(r'entries', views.CarbonEntryViewSet)
router.register(r'certifications', views.CarbonCertificationViewSet)
router.register(r'benchmarks', views.CarbonBenchmarkViewSet)
router.register(r'reports', views.CarbonReportViewSet)
router.register(r'badges', views.SustainabilityBadgeViewSet)
router.register(r'micro-offsets', views.MicroOffsetViewSet)
router.register(r'green-points', views.GreenPointsViewSet)
router.register(r'audit-logs', views.CarbonAuditLogViewSet)
router.register(r'offset-projects', views.CarbonOffsetProjectViewSet)
router.register(r'offset-purchases', views.CarbonOffsetPurchaseViewSet)
router.register(r'offset-certificates', views.CarbonOffsetCertificateViewSet)
router.register(r'calculator', views.CarbonFootprintCalculatorViewSet, basename='calculator')
router.register(r'establishments', CarbonEstablishmentSummaryViewSet, basename='carbon-establishment-summary')
router.register(r'productions', CarbonProductionSummaryViewSet, basename='carbon-production-summary')
router.register(r'public/productions', PublicProductionViewSet, basename='public-production')
router.register(r'offsets', CarbonOffsetViewSet, basename='carbon-offset')
router.register(r'productions-flat', CarbonProductionViewSet, basename='carbon-production-flat')

urlpatterns = [
    path('', include(router.urls)),
] 