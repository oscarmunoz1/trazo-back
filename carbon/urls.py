from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import CarbonEstablishmentSummaryViewSet, CarbonProductionSummaryViewSet, PublicProductionViewSet, CarbonOffsetViewSet, CarbonProductionViewSet, calculate_event_carbon_impact, AutomationRuleViewSet, BlockchainVerificationViewSet

router = DefaultRouter()
# Database-driven Crop Template System
router.register(r'crop-types', views.CropTypeViewSet)
router.register(r'event-templates', views.EventTemplateViewSet)
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
router.register(r'blockchain', BlockchainVerificationViewSet, basename='blockchain-verification')

urlpatterns = [
    path('', include(router.urls)),
    path('calculate-event-impact/', calculate_event_carbon_impact, name='calculate-event-carbon-impact'),
    
    # Enhanced USDA Integration Endpoints
    path('enhanced-event-impact/', views.calculate_event_impact, name='enhanced-event-impact'),
    path('usda-credibility/<int:establishment_id>/', views.get_usda_credibility_info, name='usda-credibility'),
    path('regional-benchmark/<int:establishment_id>/', views.get_regional_benchmark, name='regional-benchmark'),
    
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
    # Carbon Cost Intelligence endpoints (simplified, carbon-focused only)
    path('productions/<int:production_id>/economics/', views.get_production_carbon_economics, name='production_carbon_economics'),
    path('productions/<int:production_id>/carbon-credits/', views.get_carbon_credit_potential, name='carbon_credit_potential'),
    path('establishments/<int:establishment_id>/carbon-summary/', views.get_establishment_carbon_summary, name='establishment_carbon_summary'),
    # Crop Templates API
    path('crop-templates/', views.get_crop_templates, name='crop-templates'),
    path('crop-templates/<str:template_id>/', views.get_crop_template_detail, name='crop-template-detail'),
    # Educational content endpoints (Week 2)
    path('education/usda-methodology/', views.get_usda_methodology_content, name='usda-methodology-content'),
    path('education/regional-practices/<str:state>/<str:crop_type>/', views.get_regional_farming_practices, name='regional-farming-practices'),
    path('education/carbon-examples/<str:carbon_value>/', views.get_carbon_impact_examples, name='carbon-impact-examples'),
    path('education/trust-comparison/', views.get_trust_comparison_data, name='trust-comparison-data'),
    # Generic educational content endpoint
    path('education/<str:topic>/', views.get_education_content, name='education-content'),
] 