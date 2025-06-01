from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import CarbonEstablishmentSummaryViewSet, CarbonProductionSummaryViewSet, PublicProductionViewSet, CarbonOffsetViewSet, CarbonProductionViewSet, calculate_event_carbon_impact, AutomationRuleViewSet

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
router.register(r'iot-devices', views.IoTDeviceViewSet, basename='iot-devices')
router.register(r'automation-rules', AutomationRuleViewSet, basename='automation-rules')

urlpatterns = [
    path('', include(router.urls)),
    path('calculate-event-impact/', calculate_event_carbon_impact, name='calculate-event-carbon-impact'),
    path('webhooks/john-deere/', views.john_deere_webhook, name='john_deere_webhook'),
    path('webhooks/weather-station/', views.weather_station_webhook, name='weather_station_webhook'),
    # IoT Device Management
    path('iot-devices/', views.IoTDeviceViewSet.as_view({'get': 'list', 'post': 'create'}), name='iot-devices'),
    path('iot-devices/<int:pk>/', views.IoTDeviceViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='iot-device-detail'),
    path('iot-devices/status/', views.IoTDeviceViewSet.as_view({'get': 'device_status'}), name='iot-device-status'),
    path('iot-devices/simulate_data/', views.IoTDeviceViewSet.as_view({'post': 'simulate_data'}), name='iot-simulate-data'),
    path('iot-devices/pending_events/', views.IoTDeviceViewSet.as_view({'get': 'pending_events'}), name='iot-pending-events'),
    path('iot-devices/approve_event/', views.IoTDeviceViewSet.as_view({'post': 'approve_event'}), name='iot-approve-event'),
    path('iot-devices/reject_event/', views.IoTDeviceViewSet.as_view({'post': 'reject_event'}), name='iot-reject-event'),
    
    # John Deere API Integration
    path('john-deere/auth/', views.john_deere_auth_start, name='john_deere_auth_start'),
    path('john-deere/callback/', views.john_deere_auth_callback, name='john_deere_auth_callback'),
    path('john-deere/sync-devices/', views.john_deere_sync_devices, name='john_deere_sync_devices'),
    path('john-deere/webhook/', views.john_deere_webhook, name='john_deere_webhook'),
    
    # Weather API endpoints
    path('weather/current/', views.weather_current_conditions, name='weather_current_conditions'),
    path('weather/alerts/', views.weather_alerts, name='weather_alerts'),
    path('weather/recommendations/', views.weather_recommendations, name='weather_recommendations'),
    path('weather/forecast/', views.weather_forecast, name='weather_forecast'),
    path('weather/create-alert-event/', views.weather_create_alert_event, name='weather_create_alert_event'),
] 