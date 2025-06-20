from django.contrib import admin
from .models import (
    CropType, ProductionTemplate, EventTemplate,
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
    IoTDevice,
    IoTDataPoint,
    AutomationRule,
)
from django.utils.html import format_html
from django.db.models import Count

# Register your models here.
admin.site.register(CarbonSource)
admin.site.register(CarbonOffsetAction)
admin.site.register(CarbonEntry)
admin.site.register(CarbonCertification)
admin.site.register(CarbonBenchmark)
admin.site.register(CarbonReport)
admin.site.register(CarbonAuditLog)

# Database-driven Crop Template System Admin

@admin.register(CropType)
class CropTypeAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'category', 'emissions_per_hectare', 
        'total_templates_count', 'total_events_count', 'usda_verified', 'is_active', 'created_at'
    )
    list_filter = ('category', 'usda_verified', 'is_active', 'created_at')
    search_fields = ('name', 'description', 'data_source')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at', 'total_templates_count', 'total_events_count')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'category', 'description', 'is_active')
        }),
        ('Agricultural Characteristics', {
            'fields': (
                'typical_farm_size', 'growing_season', 'harvest_season'
            )
        }),
        ('USDA Carbon Benchmarks', {
            'fields': (
                'emissions_per_hectare', 'industry_average', 
                'best_practice', 'carbon_credit_potential'
            )
        }),
        ('Economic Data (per hectare)', {
            'fields': (
                'typical_cost_per_hectare', 'fertilizer_cost_per_hectare',
                'fuel_cost_per_hectare', 'irrigation_cost_per_hectare', 
                'labor_cost_per_hectare'
            )
        }),
        ('Premium Pricing Potential', {
            'fields': ('organic_premium', 'sustainable_premium', 'local_premium')
        }),
        ('Sustainability', {
            'fields': ('sustainability_opportunities',)
        }),
        ('Meta Information', {
            'fields': ('usda_verified', 'data_source', 'created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('production_templates')


@admin.register(ProductionTemplate)
class ProductionTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'crop_type', 'farming_approach', 'complexity_level',
        'events_count', 'total_carbon_impact', 'usage_count', 
        'is_recommended', 'usda_compliant', 'is_active'
    )
    list_filter = (
        'crop_type', 'farming_approach', 'complexity_level', 'market_demand',
        'is_recommended', 'usda_reviewed', 'usda_compliant', 'is_active', 'created_at'
    )
    search_fields = ('name', 'description', 'crop_type__name', 'compliance_notes')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = (
        'created_at', 'last_updated', 'usage_count', 'events_count',
        'total_carbon_impact', 'total_cost_estimate'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('crop_type', 'name', 'slug', 'farming_approach', 'description', 'is_active')
        }),
        ('Template Characteristics', {
            'fields': ('complexity_level', 'estimated_setup_time')
        }),
        ('Carbon and Economic Projections', {
            'fields': (
                'projected_emissions_reduction', 'projected_cost_change', 'projected_yield_impact'
            )
        }),
        ('Market Data', {
            'fields': ('premium_pricing_potential', 'market_demand')
        }),
        ('Certification and Compliance', {
            'fields': ('certification_requirements', 'compliance_notes')
        }),
        ('Template Status', {
            'fields': ('is_recommended', 'usage_count', 'success_rate')
        }),
        ('USDA Verification', {
            'fields': ('usda_reviewed', 'usda_compliant')
        }),
        ('Template Metrics', {
            'fields': ('events_count', 'total_carbon_impact', 'total_cost_estimate'),
            'classes': ('collapse',)
        }),
        ('Meta Information', {
            'fields': ('created_at', 'last_updated')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('event_templates').select_related('crop_type')


class EventTemplateInline(admin.TabularInline):
    model = EventTemplate
    extra = 0
    fields = (
        'name', 'event_type', 'timing', 'carbon_impact', 
        'carbon_category', 'cost_estimate', 'is_default_enabled', 'order_sequence'
    )
    readonly_fields = ('usage_count',)


@admin.register(EventTemplate)
class EventTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'production_template', 'crop_type_display', 'event_type', 'carbon_impact_display',
        'carbon_category', 'cost_estimate', 'qr_visibility', 
        'is_default_enabled', 'is_required', 'usage_count', 'is_active'
    )
    list_filter = (
        'production_template__crop_type', 'production_template__farming_approach', 
        'event_type', 'carbon_category', 'frequency',
        'qr_visibility', 'is_default_enabled', 'is_required', 'usda_compliant', 'is_active', 'created_at'
    )
    search_fields = (
        'name', 'description', 'production_template__name', 
        'production_template__crop_type__name', 'efficiency_tips', 'consumer_message'
    )
    readonly_fields = (
        'created_at', 'updated_at', 'usage_count', 'formatted_carbon_impact', 'crop_type_display'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('production_template', 'name', 'event_type', 'description', 'is_active')
        }),
        ('Timing and Scheduling', {
            'fields': ('timing', 'frequency', 'typical_duration', 'order_sequence')
        }),
        ('Carbon and Environmental Impact', {
            'fields': (
                'carbon_impact', 'carbon_category', 'formatted_carbon_impact',
                'carbon_sources', 'typical_amounts'
            )
        }),
        ('Economic Impact', {
            'fields': ('cost_estimate', 'labor_hours')
        }),
        ('Sustainability and Efficiency', {
            'fields': ('efficiency_tips', 'sustainability_score', 'alternative_methods')
        }),
        ('Consumer Visibility', {
            'fields': ('qr_visibility', 'consumer_message')
        }),
        ('Backend Event Mapping', {
            'fields': ('backend_event_type', 'backend_event_fields'),
            'classes': ('collapse',)
        }),
        ('USDA Compliance', {
            'fields': ('usda_practice_code', 'usda_compliant', 'emission_factor_source'),
            'classes': ('collapse',)
        }),
        ('Meta Information', {
            'fields': (
                'is_default_enabled', 'is_required', 'usage_count', 'created_at', 'updated_at'
            )
        }),
    )
    
    def crop_type_display(self, obj):
        """Display crop type through production template"""
        return obj.crop_type.name
    crop_type_display.short_description = 'Crop Type'
    crop_type_display.admin_order_field = 'production_template__crop_type__name'
    
    def carbon_impact_display(self, obj):
        """Display carbon impact with color coding"""
        color = obj.carbon_impact_color
        impact = obj.formatted_carbon_impact
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, impact
        )
    carbon_impact_display.short_description = 'Carbon Impact'
    carbon_impact_display.admin_order_field = 'carbon_impact'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('production_template__crop_type')
