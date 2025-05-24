from rest_framework import serializers
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

class CarbonSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonSource
        fields = '__all__'

class CarbonOffsetActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CarbonOffsetAction
        fields = '__all__'

class CarbonEntrySerializer(serializers.ModelSerializer):
    establishment_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    production_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    source_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = CarbonEntry
        fields = ['id', 'establishment', 'production', 'type', 'amount', 'year', 
                  'description', 'source', 'source_id', 'created_at', 'created_by',
                  'usda_verified', 'establishment_id', 'production_id']
        read_only_fields = ['created_at', 'created_by', 'usda_verified']

    def validate(self, data):
        # Handle both establishment and establishment_id
        establishment = data.get('establishment')
        establishment_id = data.pop('establishment_id', None)
        
        if establishment_id and not establishment:
            try:
                data['establishment'] = Establishment.objects.get(id=establishment_id)
            except Establishment.DoesNotExist:
                raise serializers.ValidationError(f"Establishment with ID {establishment_id} not found")
        
        # Handle both production and production_id
        production = data.get('production')
        production_id = data.pop('production_id', None)
        
        if production_id and not production:
            try:
                data['production'] = History.objects.get(id=production_id)
            except History.DoesNotExist:
                raise serializers.ValidationError(f"Production with ID {production_id} not found")
        
        # Handle both source and source_id  
        source = data.get('source')
        source_id = data.pop('source_id', None)
        
        if source_id and not source:
            try:
                data['source'] = CarbonSource.objects.get(id=source_id)
            except CarbonSource.DoesNotExist:
                raise serializers.ValidationError(f"Carbon source with ID {source_id} not found")
        
        # Validate that either establishment or production is provided
        if not data.get('establishment') and not data.get('production'):
            raise serializers.ValidationError("Either establishment or production must be set.")
            
        return data

    def create(self, validated_data):
        # Set the created_by field to the current user
        validated_data['created_by'] = self.context['request'].user
        # Template logic: auto-calculate amount if source has default_emission_factor and 'raw_amount' is provided
        source = validated_data.get('source')
        raw_amount = self.initial_data.get('raw_amount')
        if source and raw_amount is not None:
            try:
                raw_amount = float(raw_amount)
                validated_data['amount'] = raw_amount * source.default_emission_factor
            except Exception:
                pass  # fallback to provided amount
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