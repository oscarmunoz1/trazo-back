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
    CarbonOffsetCertificate
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
    establishment_id = serializers.PrimaryKeyRelatedField(queryset=CarbonEntry._meta.get_field('establishment').related_model.objects.all(), source='establishment', required=False, allow_null=True)
    production_id = serializers.PrimaryKeyRelatedField(queryset=CarbonEntry._meta.get_field('production').related_model.objects.all(), source='production', required=False, allow_null=True)
    source_id = serializers.PrimaryKeyRelatedField(queryset=CarbonSource.objects.all(), source='source')

    class Meta:
        model = CarbonEntry
        fields = [
            'id', 'establishment_id', 'production_id', 'type', 'source_id', 'amount', 'year', 'timestamp', 'description', 'cost', 'iot_device_id', 'usda_verified', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_by', 'timestamp', 'created_at', 'updated_at')

    def validate(self, data):
        establishment = data.get('establishment')
        production = data.get('production')
        if not establishment and not production:
            raise serializers.ValidationError("Either establishment or production must be set.")
        if establishment and production:
            raise serializers.ValidationError("Only one of establishment or production can be set.")
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