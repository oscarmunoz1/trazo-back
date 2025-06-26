from rest_framework import serializers
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
    Establishment,
    History
)

# Database-driven Crop Template System Serializers

class CropTypeDropdownSerializer(serializers.ModelSerializer):
    """Lightweight serializer for crop type dropdowns - only essential fields"""
    
    class Meta:
        model = CropType
        fields = ['id', 'name', 'category', 'slug']


class CropTypeSerializer(serializers.ModelSerializer):
    """Serializer for CropType model"""
    
    total_events_count = serializers.ReadOnlyField()
    carbon_benchmark_range = serializers.ReadOnlyField()
    
    class Meta:
        model = CropType
        fields = [
            'id', 'name', 'slug', 'category', 'description',
            'typical_farm_size', 'growing_season', 'harvest_season',
            'emissions_per_hectare', 'industry_average', 'best_practice', 
            'carbon_credit_potential', 'typical_cost_per_hectare',
            'fertilizer_cost_per_hectare', 'fuel_cost_per_hectare',
            'irrigation_cost_per_hectare', 'labor_cost_per_hectare',
            'organic_premium', 'sustainable_premium', 'local_premium',
            'sustainability_opportunities', 'usda_verified', 'data_source',
            'is_active', 'created_at', 'updated_at', 'total_events_count',
            'carbon_benchmark_range'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']


class ProductionTemplateSerializer(serializers.ModelSerializer):
    """Serializer for ProductionTemplate model"""
    
    crop_type_name = serializers.CharField(source='crop_type.name', read_only=True)
    events_count = serializers.ReadOnlyField()
    total_carbon_impact = serializers.ReadOnlyField()
    total_cost_estimate = serializers.ReadOnlyField()
    
    class Meta:
        model = ProductionTemplate
        fields = [
            'id', 'crop_type', 'crop_type_name', 'name', 'slug', 'farming_approach',
            'description', 'complexity_level', 'estimated_setup_time',
            'projected_emissions_reduction', 'projected_cost_change', 'projected_yield_impact',
            'premium_pricing_potential', 'market_demand', 'certification_requirements',
            'compliance_notes', 'is_active', 'is_recommended', 'usage_count',
            'success_rate', 'usda_reviewed', 'usda_compliant', 'events_count',
            'total_carbon_impact', 'total_cost_estimate', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'usage_count', 'success_rate', 'events_count', 
                           'total_carbon_impact', 'total_cost_estimate', 'created_at', 'updated_at']


class EventTemplateSerializer(serializers.ModelSerializer):
    """Serializer for EventTemplate model"""
    
    crop_type_name = serializers.CharField(source='production_template.crop_type.name', read_only=True)
    production_template_name = serializers.CharField(source='production_template.name', read_only=True)
    formatted_carbon_impact = serializers.ReadOnlyField()
    carbon_impact_color = serializers.ReadOnlyField()
    
    class Meta:
        model = EventTemplate
        fields = [
            'id', 'production_template', 'production_template_name', 'crop_type_name', 
            'name', 'event_type', 'description', 'timing', 'frequency', 'typical_duration', 
            'order_sequence', 'carbon_impact', 'carbon_category', 'carbon_sources', 
            'typical_amounts', 'cost_estimate', 'labor_hours', 'efficiency_tips', 
            'sustainability_score', 'alternative_methods', 'qr_visibility', 'consumer_message',
            'backend_event_type', 'backend_event_fields', 'usda_practice_code', 'usda_compliant',
            'emission_factor_source', 'is_active', 'is_default_enabled', 'is_required',
            'usage_count', 'created_at', 'updated_at', 'formatted_carbon_impact',
            'carbon_impact_color'
        ]
        read_only_fields = ['id', 'usage_count', 'created_at', 'updated_at']


class EventTemplateCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating events from templates"""
    
    template_id = serializers.IntegerField(write_only=True)
    enabled = serializers.BooleanField(default=True, write_only=True)
    custom_amounts = serializers.JSONField(required=False, write_only=True)
    custom_notes = serializers.CharField(max_length=500, required=False, write_only=True)
    
    class Meta:
        model = EventTemplate
        fields = [
            'template_id', 'enabled', 'custom_amounts', 'custom_notes'
        ]


class CropTemplateDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for crop type with all production templates and event templates"""
    
    production_templates = ProductionTemplateSerializer(many=True, read_only=True)
    total_templates_count = serializers.ReadOnlyField()
    total_events_count = serializers.ReadOnlyField()
    
    class Meta:
        model = CropType
        fields = [
            'id', 'name', 'slug', 'category', 'description',
            'typical_farm_size', 'growing_season', 'harvest_season',
            'emissions_per_hectare', 'industry_average', 'best_practice',
            'carbon_credit_potential', 'typical_cost_per_hectare',
            'fertilizer_cost_per_hectare', 'fuel_cost_per_hectare',
            'irrigation_cost_per_hectare', 'labor_cost_per_hectare',
            'organic_premium', 'sustainable_premium', 'local_premium',
            'sustainability_opportunities', 'usda_verified', 'data_source',
            'is_active', 'production_templates', 'total_templates_count', 'total_events_count'
        ]


class QuickEventTemplateSerializer(serializers.ModelSerializer):
    """Lightweight serializer for quick event selection"""
    
    crop_type_name = serializers.CharField(source='production_template.crop_type.name', read_only=True)
    production_template_name = serializers.CharField(source='production_template.name', read_only=True)
    type = serializers.SerializerMethodField()
    
    def get_type(self, obj):
        """Generate the translation key based on event name and type"""
        # Convert event name to a translation key format
        name_lower = obj.name.lower()
        
        # Map common event names to translation keys
        name_mappings = {
            'high-density site design': 'event.high_density.site_design',
            'diseño de sitio de alta densidad': 'event.high_density.site_design',
            'site preparation': 'event.site.preparation',
            'preparación del sitio': 'event.site.preparation',
            'tree planting': 'event.tree.planting',
            'plantación de árboles': 'event.tree.planting',
            'fertilization': 'event.fertilization.application',
            'fertilización': 'event.fertilization.application',
            'cover crop establishment': 'event.cover_crop.establishment',
            'establecimiento de cultivo de cobertura': 'event.cover_crop.establishment',
            'organic soil preparation': 'event.organic.soil_preparation',
            'preparación orgánica del suelo': 'event.organic.soil_preparation',
            'orchard establishment': 'event.orchard.establishment',
            'establecimiento de huerto': 'event.orchard.establishment',
            'irrigation management': 'event.irrigation.management',
            'manejo de riego': 'event.irrigation.management',
            'cover crop system': 'event.cover_crop.system',
            'sistema de cultivo de cobertura': 'event.cover_crop.system',
            'beneficial insect release': 'event.beneficial.insect_release',
            'liberación de insectos benéficos': 'event.beneficial.insect_release',
            'planting': 'event.production.planting',
            'plantación': 'event.production.planting',
            'cover crop termination': 'event.cover_crop.termination',
            'terminación de cultivo de cobertura': 'event.cover_crop.termination',
            'certification inspection': 'event.certification.inspection',
            'inspección de certificación': 'event.certification.inspection',
            'wheat seeding': 'event.seeding.wheat',
            'siembra de trigo': 'event.seeding.wheat',
            'spring nitrogen application': 'event.nitrogen.application',
            'aplicación de nitrógeno primaveral': 'event.nitrogen.application',
            'cotton planting': 'event.seeding.cotton',
            'plantación de algodón': 'event.seeding.cotton',
            'winter cover crop': 'event.winter.cover_crop',
            'cultivo de cobertura invernal': 'event.winter.cover_crop',
            'soil test': 'event.soil.soil_test',
            'prueba de suelo': 'event.soil.soil_test',
        }
        
        # Check for exact matches first
        if name_lower in name_mappings:
            return name_mappings[name_lower]
        
        # Fallback: generate based on event_type and simplified name
        event_type_lower = obj.event_type.lower()
        simplified_name = name_lower.replace(' ', '_').replace('-', '_')
        
        # Map event types to categories
        if 'fertiliz' in name_lower or 'fertiliz' in event_type_lower:
            return 'event.fertilization.application'
        elif 'irrigation' in name_lower or 'riego' in name_lower:
            return 'event.irrigation.management'
        elif 'plant' in name_lower and ('tree' in name_lower or 'árbol' in name_lower):
            return 'event.tree.planting'
        elif 'plant' in name_lower:
            return 'event.production.planting'
        elif 'soil' in name_lower or 'suelo' in name_lower:
            if 'test' in name_lower or 'prueba' in name_lower:
                return 'event.soil.soil_test'
            elif 'preparation' in name_lower or 'preparación' in name_lower:
                return 'event.soil.preparation'
            else:
                return 'event.soil.management'
        elif 'cover crop' in name_lower or 'cultivo de cobertura' in name_lower:
            if 'establishment' in name_lower or 'establecimiento' in name_lower:
                return 'event.cover_crop.establishment'
            elif 'termination' in name_lower or 'terminación' in name_lower:
                return 'event.cover_crop.termination'
            else:
                return 'event.cover_crop.system'
        elif 'pest' in name_lower or 'plaga' in name_lower:
            return 'event.pest.control'
        elif 'harvest' in name_lower or 'cosecha' in name_lower:
            return 'event.production.harvest'
        elif 'pruning' in name_lower or 'poda' in name_lower:
            return 'event.production.pruning'
        else:
            # Generic fallback based on event type
            return f'event.{event_type_lower.replace(" ", "_")}.{simplified_name}'
    
    class Meta:
        model = EventTemplate
        fields = [
            'id', 'name', 'event_type', 'description', 'timing',
            'carbon_impact', 'carbon_category', 'cost_estimate',
            'sustainability_score', 'qr_visibility', 'crop_type_name',
            'production_template_name', 'backend_event_type', 'backend_event_fields', 'typical_amounts', 'type'
        ]


class CarbonSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonSource
        fields = ['id', 'name', 'description', 'unit', 'category', 'usda_verified']

class CarbonOffsetActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonOffsetAction
        fields = '__all__'

class CarbonEntrySerializer(serializers.ModelSerializer):
    establishment_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    production_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    source_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    source = CarbonSourceSerializer(read_only=True)

    class Meta:
        model = CarbonEntry
        fields = ['id', 'establishment', 'production', 'type', 'amount', 'year', 
                  'description', 'source', 'source_id', 'created_at', 'created_by',
                  'usda_verified', 'establishment_id', 'production_id',
                  'verification_level', 'trust_score', 'effective_amount',
                  'additionality_verified', 'audit_status', 'registry_verification_id']
        read_only_fields = ['created_at', 'created_by', 'usda_verified', 'effective_amount']

    def validate(self, data):
        # Handle both establishment and establishment_id
        establishment_id = data.pop('establishment_id', None)
        if establishment_id:
            try:
                data['establishment'] = Establishment.objects.get(id=establishment_id)
            except Establishment.DoesNotExist:
                raise serializers.ValidationError('Invalid establishment ID')
        
        # Handle both production and production_id
        production_id = data.pop('production_id', None)
        if production_id:
            try:
                data['production'] = History.objects.get(id=production_id)
            except History.DoesNotExist:
                raise serializers.ValidationError('Invalid production ID')
        
        # Handle source_id
        source_id = data.pop('source_id', None)
        if source_id:
            try:
                data['source'] = CarbonSource.objects.get(id=source_id)
            except CarbonSource.DoesNotExist:
                raise serializers.ValidationError('Invalid source ID')
            
        return data

    def create(self, validated_data):
        # Set the created_by field to the current user
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

class CarbonCertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonCertification
        fields = '__all__'

class CarbonBenchmarkSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonBenchmark
        fields = '__all__'

class CarbonReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonReport
        fields = '__all__'
        read_only_fields = ('generated_at',)

class CarbonAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonAuditLog
        fields = '__all__'
        read_only_fields = ('timestamp',)

class SustainabilityBadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SustainabilityBadge
        fields = '__all__'

class MicroOffsetSerializer(serializers.ModelSerializer):
    class Meta:
        model = MicroOffset
        fields = '__all__'

class GreenPointsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GreenPoints
        fields = '__all__'

class CarbonFootprintSummarySerializer(serializers.Serializer):
    total_emissions = serializers.FloatField()
    total_offsets = serializers.FloatField()
    net_footprint = serializers.FloatField()
    carbon_score = serializers.IntegerField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()

    class Meta:
        fields = ('total_emissions', 'total_offsets', 'net_footprint', 'carbon_score', 'period_start', 'period_end')

class CarbonOffsetProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonOffsetProject
        fields = [
            'id', 'name', 'description', 'project_type', 'location',
            'total_capacity', 'available_capacity', 'price_per_ton',
            'certification_standard', 'verification_status', 'start_date',
            'end_date', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')

class CarbonOffsetPurchaseSerializer(serializers.ModelSerializer):
    project_details = CarbonOffsetProjectSerializer(source='project', read_only=True)
    
    class Meta:
        model = CarbonOffsetPurchase
        fields = [
            'id', 'project', 'project_details', 'amount', 'price_per_ton',
            'total_price', 'status', 'transaction_id', 'purchase_date',
            'certificate_url', 'notes'
        ]
        read_only_fields = ('total_price', 'transaction_id', 'purchase_date', 'certificate_url')

    def validate(self, data):
        project = data.get('project')
        amount = data.get('amount')
        
        if project and amount:
            if amount > project.available_capacity:
                raise serializers.ValidationError(
                    f"Requested amount exceeds available capacity. Available: {project.available_capacity} tons"
                )
            if amount <= 0:
                raise serializers.ValidationError("Amount must be greater than 0")
        
        return data

class CarbonOffsetCertificateSerializer(serializers.ModelSerializer):
    purchase_details = CarbonOffsetPurchaseSerializer(source='purchase', read_only=True)
    
    class Meta:
        model = CarbonOffsetCertificate
        fields = [
            'id', 'purchase', 'purchase_details', 'certificate_number',
            'issue_date', 'expiry_date', 'verification_code',
            'certificate_url', 'metadata'
        ]
        read_only_fields = ('certificate_number', 'issue_date', 'verification_code') 