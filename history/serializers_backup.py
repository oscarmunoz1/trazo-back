from rest_framework import serializers
from django.utils import timezone

from .models import (
    History,
    CommonEvent,
    ChemicalEvent,
    WeatherEvent,
    GeneralEvent,
    HistoryScan,
    ProductionEvent,
    EquipmentEvent,
    SoilManagementEvent,
    PestManagementEvent,
)
from .constants import (
    WEATHER_EVENT_TYPE,
    PRODUCTION_EVENT_TYPE,
    CHEMICAL_EVENT_TYPE,
    GENERAL_EVENT_TYPE,
    EQUIPMENT_EVENT_TYPE,
    SOIL_MANAGEMENT_EVENT_TYPE,
    PEST_MANAGEMENT_EVENT_TYPE,
)
from common.models import Gallery
from product.models import Product, Parcel
from company.models import Establishment
from users.models import User
from users.serializers import BasicUserSerializer


class EventSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    carbon_data = serializers.SerializerMethodField()

    class Meta:
        model = CommonEvent
        fields = "__all__"

    def get_image(self, event):
        if event.album is not None:
            return event.album.images.first().image.url
        return None

    def get_carbon_data(self, event):
        """
        Get carbon calculation data for the event.
        First check if it's stored in extra_data, otherwise calculate it.
        OPTIMIZATION: Skip expensive calculations for list views.
        """
        try:
            # Check if carbon calculation is already stored in extra_data
            if hasattr(event, 'extra_data') and event.extra_data and 'carbon_calculation' in event.extra_data:
                return event.extra_data['carbon_calculation']
            
            # OPTIMIZATION: Check if this is being called from a list view context
            # If so, return minimal data to avoid expensive USDA API calls
            request = self.context.get('request')
            if request and hasattr(request, 'resolver_match'):
                view_name = getattr(request.resolver_match, 'url_name', '')
                if 'list' in view_name or request.method == 'GET' and '/history/' in request.path:
                    # Return minimal carbon data for list views
                    return {
                        'co2e': 0.0,
                        'efficiency_score': 50.0,
                        'usda_factors_based': False,
                        'verification_status': 'not_calculated',
                        'calculation_method': 'list_view_minimal',
                        'data_source': 'Cached',
                        'recommendations': [],
                        'event_type': event.__class__.__name__.lower().replace('event', ''),
                        'timestamp': event.date.isoformat() if event.date else None,
                        'note': 'Full calculation available in detail view'
                    }
            
            # Full calculation only for detail views or when explicitly requested
            from carbon.services.event_carbon_calculator import EventCarbonCalculator
            
            calculator = EventCarbonCalculator()
            
            # Determine event type and calculate accordingly
            if isinstance(event, ChemicalEvent):
                result = calculator.calculate_chemical_event_impact(event)
            elif isinstance(event, ProductionEvent):
                result = calculator.calculate_production_event_impact(event)
            elif isinstance(event, WeatherEvent):
                result = calculator.calculate_weather_event_impact(event)
            elif isinstance(event, EquipmentEvent):
                result = calculator.calculate_equipment_event_impact(event)
            elif isinstance(event, SoilManagementEvent):
                result = calculator.calculate_soil_management_event_impact(event)
            elif isinstance(event, PestManagementEvent):
                result = calculator.calculate_pest_management_event_impact(event)
            elif isinstance(event, GeneralEvent):
                # For general events, use standard minimal calculation
                result = {
                    'co2e': 0.1,
                    'efficiency_score': 50.0,
                    'usda_factors_based': False,
                    'verification_status': 'estimated',
                    'calculation_method': 'general_event_standard',
                    'data_source': 'Industry Standards',
                    'recommendations': [],
                    'event_type': 'general',
                    'timestamp': event.date.isoformat() if event.date else None
                }
            else:
                # Fallback for unknown event types
                result = {
                    'co2e': 0.0,
                    'efficiency_score': 50.0,
                    'usda_factors_based': False,
                    'verification_status': 'unknown',
                    'calculation_method': 'unknown_event_type',
                    'data_source': 'Unknown',
                    'recommendations': [],
                    'event_type': 'unknown',
                    'timestamp': event.date.isoformat() if event.date else None
                }
            
            return result
            
        except Exception as e:
            # Return fallback data if calculation fails
            return {
                'co2e': 0.0,
                'efficiency_score': 50.0,
                'usda_factors_based': False,
                'verification_status': 'calculation_error',
                'calculation_method': 'calculation_error',
                'data_source': 'Error',
                'recommendations': [],
                'event_type': 'error',
                'timestamp': event.date.isoformat() if event.date else None,
                'error': str(e)
            }


class UpdateChemicalEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChemicalEvent
        fields = "__all__"


class ChemicalEventSerializer(EventSerializer):
    type = serializers.SerializerMethodField()
    event_type = serializers.SerializerMethodField()

    class Meta:
        model = ChemicalEvent
        fields = "__all__"

    def get_type(self, chemical_event):
        type_display = chemical_event.get_type_display()
        if type_display is None:
            return "event.chemical.unknown"
        return f"event.chemical.{type_display.lower().replace(' ', '_')}"

    def get_event_type(self, chemical_event):
        return CHEMICAL_EVENT_TYPE


class UpdateWeatherEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeatherEvent
        fields = "__all__"

    def to_internal_value(self, data):
        type = data.get("type", None)
        if type is None:
            raise serializers.ValidationError(
                {"type": ["This field is required."]}, code="required"
            )
        data = data.copy()
        extra_data = {}
        if type == WeatherEvent.FROST:
            extra_data["lower_temperature"] = data.pop("lower_temperature", None)
            extra_data["way_of_protection"] = data.pop("way_of_protection", None)
        elif type == WeatherEvent.DROUGHT:
            extra_data["water_deficit"] = data.pop("water_deficit", None)
        elif type == WeatherEvent.HAILSTORM:
            extra_data["weight"] = data.pop("weight", None)
            extra_data["diameter"] = data.pop("diameter", None)
            extra_data["duration"] = data.pop("duration", None)
            extra_data["way_of_protection"] = data.pop("way_of_protection", None)
        elif type == WeatherEvent.HIGH_TEMPERATURE:
            extra_data["highest_temperature"] = data.pop("highest_temperature", None)
            extra_data["start_date"] = data.pop("start_date", None)
            extra_data["end_date"] = data.pop("end_date", None)
        internal_value = super().to_internal_value(data)
        internal_value.extra_data = extra_data

        return internal_value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        type = data.get("type", None)
        
        # Ensure extra_data is not None before accessing it
        if instance.extra_data is None:
            instance.extra_data = {}
        
        if type == WeatherEvent.FROST:
            data["lower_temperature"] = instance.extra_data.get("lower_temperature", 0)
            data["way_of_protection"] = instance.extra_data.get("way_of_protection", "")
        elif type == WeatherEvent.DROUGHT:
            data["water_deficit"] = instance.extra_data.get("water_deficit", 0)
        elif type == WeatherEvent.HAILSTORM:
            data["weight"] = instance.extra_data.get("weight", 0)
            data["diameter"] = instance.extra_data.get("diameter", 0)
            data["duration"] = instance.extra_data.get("duration", 0)
            data["way_of_protection"] = instance.extra_data.get("way_of_protection", "")
        elif type == WeatherEvent.HIGH_TEMPERATURE:
            data["highest_temperature"] = instance.extra_data.get("highest_temperature", 0)
            data["start_date"] = instance.extra_data.get("start_date", "")
            data["end_date"] = instance.extra_data.get("end_date", "")
        
        data.pop("extra_data", None)  # Use pop with default to avoid KeyError if key doesn't exist

        # Calculate production-level USDA verification status
        try:
            from carbon.models import CarbonEntry
            
            carbon_entries = CarbonEntry.objects.filter(production=instance)
            total_entries = carbon_entries.count()
            
            if total_entries > 0:
                usda_verified_entries = carbon_entries.filter(usda_verified=True).count()
                usda_factors_based_entries = carbon_entries.filter(usda_factors_based=True).count()
                
                # Production is USDA verified if majority of entries are USDA verified or factors-based
                production_usda_verified = (
                    usda_verified_entries > 0 or 
                    usda_factors_based_entries >= (total_entries * 0.5)
                )
                
                # Add to extra_data for frontend
                if data.get('extra_data') is None:
                    data['extra_data'] = {}
                
                data['extra_data']['usda_verified'] = production_usda_verified
                data['extra_data']['usda_verification_details'] = {
                    'total_entries': total_entries,
                    'usda_verified_entries': usda_verified_entries,
                    'usda_factors_based_entries': usda_factors_based_entries,
                    'verification_percentage': round((usda_verified_entries / total_entries * 100), 1) if total_entries > 0 else 0
                }
                
                # Calculate and add carbon totals for dashboard display
                from django.db.models import Sum
                total_emissions = carbon_entries.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
                total_offsets = carbon_entries.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
                carbon_score = 50  # Default score
                
                # Calculate carbon score using the model method with industry benchmark
                if total_emissions > 0 or total_offsets > 0:
                    from carbon.models import CarbonEntry, CarbonBenchmark
                    
                    # Get industry benchmark for the production
                    industry_benchmark = None
                    try:
                        # Get crop type from product name
                        product_name = instance.product.name.lower() if instance.product else None
                        crop_type = None
                        
                        if product_name:
                            # Map product names to benchmark crop types
                            crop_mapping = {
                                'citrus (oranges)': 'orange',
                                'citrus (lemons)': 'lemon', 
                                'strawberries': 'strawberry',
                                'almonds': 'almond',
                                'grapes': 'grape',
                                'apples': 'apple',
                                'avocados': 'avocado',
                                'tomatoes': 'tomato',
                                'corn': 'corn',
                                'soybeans': 'soybean'
                            }
                            
                            crop_type = crop_mapping.get(product_name, product_name.split()[0])
                        
                        # Look for crop-specific benchmark
                        if crop_type:
                            benchmark = CarbonBenchmark.objects.filter(
                                crop_type=crop_type,
                                year=instance.start_date.year if instance.start_date else 2025,
                                usda_verified=True
                            ).first()
                            
                            if benchmark:
                                # Convert per-kg benchmark to total production benchmark
                                # Estimate production weight (default 1000kg if unknown)
                                estimated_production_kg = 1000  # Default estimate
                                industry_benchmark = benchmark.average_emissions * estimated_production_kg
                    
                    except Exception as e:
                        print(f"Error getting benchmark for production {instance.id}: {e}")
                    
                    carbon_score = CarbonEntry.calculate_carbon_score(total_emissions, total_offsets, industry_benchmark)
                
                data['extra_data']['total_emissions'] = float(total_emissions)
                data['extra_data']['total_offsets'] = float(total_offsets)
                data['extra_data']['carbon_score'] = carbon_score
            else:
                # No carbon entries, so not USDA verified
                if data.get('extra_data') is None:
                    data['extra_data'] = {}
                data['extra_data']['usda_verified'] = False
                data['extra_data']['total_emissions'] = 0.0
                data['extra_data']['total_offsets'] = 0.0
                data['extra_data']['carbon_score'] = 50
                
        except Exception as e:
            print(f"Error calculating USDA verification for production {instance.id}: {e}")
            # Fallback to existing logic
            if data.get('extra_data') is None:
                data['extra_data'] = {}
            data['extra_data']['usda_verified'] = False
            data['extra_data']['total_emissions'] = 0.0
            data['extra_data']['total_offsets'] = 0.0
            data['extra_data']['carbon_score'] = 50
        
        return data

    def update(self, instance, validated_data):
        album_data = self.context.get("request").FILES
        if album_data:
            gallery = instance.album
            if gallery is None:
                gallery = Gallery.objects.create()
            for image_data in album_data.getlist("album[images]"):
                gallery_image = gallery.images.create(image=image_data)
                gallery_image.save()
            validated_data["album"] = gallery
        return super().update(instance, validated_data)

    def create(self, validated_data):
        album_data = self.context.get("request").FILES
        if album_data:
            gallery = Gallery.objects.create()
            for image_data in album_data.getlist("album[images]"):
                gallery_image = gallery.images.create(image=image_data)
                gallery_image.save()
            validated_data["album"] = gallery
        return super().create(validated_data)


class WeatherEventSerializer(EventSerializer):
    type = serializers.SerializerMethodField()
    event_type = serializers.SerializerMethodField()

    class Meta:
        model = WeatherEvent
        fields = "__all__"

    def get_type(self, weather_event):
        type_display = weather_event.get_type_display()
        if type_display is None:
            return "event.weather.unknown"
        return f"event.weather.{type_display.lower().replace(' ', '_')}"

    def get_event_type(self, weather_event):
        return WEATHER_EVENT_TYPE


class UpdateProductionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionEvent
        fields = "__all__"


class ProductionEventSerializer(EventSerializer):
    type = serializers.SerializerMethodField()
    event_type = serializers.SerializerMethodField()

    class Meta:
        model = ProductionEvent
        fields = "__all__"

    def get_type(self, production_event):
        type_display = production_event.get_type_display()
        if type_display is None:
            return "event.production.unknown"
        return f"event.production.{type_display.lower().replace(' ', '_')}"

    def get_event_type(self, production_event):
        return PRODUCTION_EVENT_TYPE


class UpdateGeneralEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneralEvent
        fields = "__all__"


class GeneralEventSerializer(EventSerializer):
    type = serializers.SerializerMethodField()
    event_type = serializers.SerializerMethodField()

    class Meta:
        model = GeneralEvent
        fields = "__all__"

    def get_type(self, general_event):
        return f"event.general.{general_event.name.lower().replace(' ', '_')}"

    def get_event_type(self, general_event):
        return GENERAL_EVENT_TYPE


class OptimizedHistoryListSerializer(serializers.ModelSerializer):
    """
    Optimized serializer for dashboard list view that avoids expensive operations
    like get_events() and get_members() that cause N+1 queries.
    """
    product = serializers.SerializerMethodField()
    parcel = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    crop_type = serializers.SerializerMethodField()
    
    class Meta:
        model = History
        fields = [
            "id",
            "start_date", 
            "finish_date",
            "name",
            "published",
            "earning",
            "parcel",
            "members",
            "product",
            "qr_code",
            "reputation",
            "is_outdoor",
            "age_of_plants", 
            "number_of_plants",
            "soil_ph",
            "crop_type",
            "extra_data",  # Include for carbon data
        ]
        read_only_fields = ["id"]

    def get_product(self, history):
        return history.product.name if history.product else None

    def get_parcel(self, history):
        return history.parcel.name if history.parcel else None

    def get_crop_type(self, history):
        if history.crop_type:
            return {
                'id': history.crop_type.id,
                'name': history.crop_type.name,
                'category': history.crop_type.category,
                'slug': history.crop_type.slug
            }
        return None

    def get_members(self, history):
        """
        Ultra-lightweight members list that completely avoids database queries.
        Returns cached members from extra_data if available, otherwise empty list.
        """
        # Check if we have cached member data in extra_data
        if history.extra_data and isinstance(history.extra_data, dict):
            cached_members = history.extra_data.get('cached_members', [])
            if cached_members:
                return [
                    {
                        "id": member.get("id"),
                        "first_name": member.get("first_name", ""),
                        "last_name": member.get("last_name", ""),
                        "image": member.get("image")
                    }
                    for member in cached_members[:3]  # Limit to 3 members
                ]
        
        # Return empty list to avoid expensive queries
        # Members will be loaded on demand when needed
        return []

    def to_representation(self, instance):
        """
        Override to add computed USDA verification status and enhanced production info
        """
        data = super().to_representation(instance)
        
        # Calculate production-level USDA verification status
        try:
            from carbon.models import CarbonEntry
            
            carbon_entries = CarbonEntry.objects.filter(production=instance)
            total_entries = carbon_entries.count()
            
            if total_entries > 0:
                usda_verified_entries = carbon_entries.filter(usda_verified=True).count()
                usda_factors_based_entries = carbon_entries.filter(usda_factors_based=True).count()
                
                # Production is USDA verified if majority of entries are USDA verified or factors-based
                production_usda_verified = (
                    usda_verified_entries > 0 or 
                    usda_factors_based_entries >= (total_entries * 0.5)
                )
                
                # Add to extra_data for frontend
                if data.get('extra_data') is None:
                    data['extra_data'] = {}
                
                data['extra_data']['usda_verified'] = production_usda_verified
                data['extra_data']['usda_verification_details'] = {
                    'total_entries': total_entries,
                    'usda_verified_entries': usda_verified_entries,
                    'usda_factors_based_entries': usda_factors_based_entries,
                    'verification_percentage': round((usda_verified_entries / total_entries * 100), 1) if total_entries > 0 else 0
                }
                
                # Calculate and add carbon totals for dashboard display
                from django.db.models import Sum
                total_emissions = carbon_entries.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
                total_offsets = carbon_entries.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
                carbon_score = 50  # Default score
                
                # Calculate carbon score using the model method with industry benchmark
                if total_emissions > 0 or total_offsets > 0:
                    from carbon.models import CarbonEntry, CarbonBenchmark
                    
                    # Get industry benchmark for the production
                    industry_benchmark = None
                    try:
                        # Get crop type from product name
                        product_name = instance.product.name.lower() if instance.product else None
                        crop_type = None
                        
                        if product_name:
                            # Map product names to benchmark crop types
                            crop_mapping = {
                                'citrus (oranges)': 'orange',
                                'citrus (lemons)': 'lemon', 
                                'strawberries': 'strawberry',
                                'almonds': 'almond',
                                'grapes': 'grape',
                                'apples': 'apple',
                                'avocados': 'avocado',
                                'tomatoes': 'tomato',
                                'corn': 'corn',
                                'soybeans': 'soybean'
                            }
                            
                            crop_type = crop_mapping.get(product_name, product_name.split()[0])
                        
                        # Look for crop-specific benchmark
                        if crop_type:
                            benchmark = CarbonBenchmark.objects.filter(
                                crop_type=crop_type,
                                year=instance.start_date.year if instance.start_date else 2025,
                                usda_verified=True
                            ).first()
                            
                            if benchmark:
                                # Convert per-kg benchmark to total production benchmark
                                # Estimate production weight (default 1000kg if unknown)
                                estimated_production_kg = 1000  # Default estimate
                                industry_benchmark = benchmark.average_emissions * estimated_production_kg
                    
                    except Exception as e:
                        print(f"Error getting benchmark for production {instance.id}: {e}")
                    
                    carbon_score = CarbonEntry.calculate_carbon_score(total_emissions, total_offsets, industry_benchmark)
                
                data['extra_data']['total_emissions'] = float(total_emissions)
                data['extra_data']['total_offsets'] = float(total_offsets)
                data['extra_data']['carbon_score'] = carbon_score
            else:
                # No carbon entries, so not USDA verified
                if data.get('extra_data') is None:
                    data['extra_data'] = {}
                data['extra_data']['usda_verified'] = False
                data['extra_data']['total_emissions'] = 0.0
                data['extra_data']['total_offsets'] = 0.0
                data['extra_data']['carbon_score'] = 50
        
        except Exception as e:
            print(f"Error calculating USDA verification for production {instance.id}: {e}")
            # Fallback to existing logic
            if data.get('extra_data') is None:
                data['extra_data'] = {}
            data['extra_data']['usda_verified'] = False
            data['extra_data']['total_emissions'] = 0.0
            data['extra_data']['total_offsets'] = 0.0
            data['extra_data']['carbon_score'] = 50
        
        # Enhance production name to be more descriptive and unique
        try:
            if data.get('extra_data') is None:
                data['extra_data'] = {}
                
            # Generate a more meaningful production name
            product_name = instance.product.name if instance.product else "Agricultural Product"
            year = instance.start_date.year if instance.start_date else "2025"
            
            # Get production method from extra_data
            production_method = data['extra_data'].get('production_method', 'conventional')
            
            # Create unique name based on product and method (only if not conventional)
            if production_method != 'conventional':
                enhanced_name = f"{production_method.title()} {product_name} {year}"
            else:
                enhanced_name = f"{product_name} {year}"
            
            # Override the name field with enhanced version
            data['name'] = enhanced_name
            
            # Store original name in extra_data for reference
            data['extra_data']['original_name'] = instance.name
            
        except Exception as e:
            print(f"Error enhancing production name for {instance.id}: {e}")
        
        return data


class HistorySerializer(serializers.ModelSerializer):
    events = serializers.SerializerMethodField()
    certificate_percentage = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    parcel = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    operator = BasicUserSerializer(read_only=True)
    crop_type = serializers.SerializerMethodField()

    class Meta:
        model = History
        fields = [
            "id",
            "start_date",
            "finish_date",
            "name",
            "published",
            "events",
            "earning",
            "parcel",
            "members",
            "certificate_percentage",
            "product",
            "qr_code",
            "reputation",
            "images",
            "is_outdoor",
            "age_of_plants",
            "number_of_plants",
            "soil_ph",
            "operator",
            "crop_type",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "certificate_percentage"]

    def get_product(self, history):
        return history.product.name if history.product else None

    def get_events(self, history):
        return history.get_events()

    def get_parcel(self, history):
        return history.parcel.name if history.parcel else None

    def get_certificate_percentage(self, history):
        return history.certificate_percentage

    def get_crop_type(self, history):
        if history.crop_type:
            return {
                'id': history.crop_type.id,
                'name': history.crop_type.name,
                'category': history.crop_type.category,
                'slug': history.crop_type.slug
            }
        return None

    def get_images(self, history):
        try:
            if not history.album:
                return []
            
            request = self.context.get('request')
            return [
                request.build_absolute_uri(image.image.url) if request else image.image.url
                for image in history.album.images.all()
                if image.image is not None
            ]
        except Exception as e:
            print(f"Error getting images: {str(e)}")
            return []

    def get_members(self, history):
        """
        Get production members from involved users, with proper serialization.
        """
        try:
            # First check if we have cached members in extra_data
            if history.extra_data and isinstance(history.extra_data, dict):
                cached_members = history.extra_data.get('cached_members', [])
                if cached_members:
                    return cached_members[:3]  # Limit to 3 members
            
            # Fallback to querying involved users
            user_ids = history.get_involved_users()
            if user_ids:
                members = User.objects.filter(id__in=user_ids).order_by("first_name")[:3]
                return BasicUserSerializer(members, many=True).data
            
            return []
        except Exception as e:
            print(f"Error getting members for history {history.id}: {str(e)}")
            return []


class ListHistoryClassSerializer(serializers.ModelSerializer):
    product = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    parcel = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()

    class Meta:
        model = HistoryScan
        fields = [
            "id",
            "date",
            "product",
            "location",
            "parcel",
            "comment",
        ]

    def get_date(self, history_scan):
        return history_scan.date.strftime("%m/%d/%Y")

    def get_product(self, history_scan):
        return (
            history_scan.history.product.name if history_scan.history.product else None
        )

    def get_location(self, history_scan):
        if history_scan.city is None and history_scan.country is None:
            return "-"
        elif history_scan.city is not None:
            return f"{history_scan.city}"
        elif history_scan.country is not None:
            return f"{history_scan.country}"
        return f"{history_scan.city if history_scan.city is not None else '-'}, {history_scan.country if history_scan.country is not None else '-'}"

    def get_parcel(self, history_scan):
        return history_scan.history.parcel.name if history_scan.history.parcel else None


class PublicProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["name"]


class PublicEstablishmentSerializer(serializers.ModelSerializer):
    location = serializers.SerializerMethodField()

    class Meta:
        model = Establishment
        fields = ["name", "description", "location"]

    def get_location(self, establishment):
        return establishment.get_location()


class PublicParcelSerializer(serializers.ModelSerializer):
    establishment = PublicEstablishmentSerializer()

    class Meta:
        model = Parcel
        fields = ["name", "polygon", "map_metadata", "establishment"]


class PublicHistoryListSerializer(serializers.ModelSerializer):
    product = PublicProductSerializer()
    image = serializers.SerializerMethodField()

    class Meta:
        model = History
        fields = ["id", "name", "product", "reputation", "image"]

    def get_image(self, history):
        if history.album is None or history.album.images.first() is None:
            return None
        request = self.context.get('request')
        image = history.album.images.first() if history.album else None
        return request.build_absolute_uri(image.image.url) if request else image.image.url


class PublicHistorySerializer(serializers.ModelSerializer):
    events = serializers.SerializerMethodField()
    certificate_percentage = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()
    parcel = PublicParcelSerializer()
    product = PublicProductSerializer()
    history_scan = serializers.SerializerMethodField()
    similar_histories = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    qr_code = serializers.SerializerMethodField()

    class Meta:
        model = History
        fields = [
            "id",
            "start_date",
            "finish_date",
            "name",
            "events",
            "certificate_percentage",
            "product",
            "reputation",
            "company",
            "parcel",
            "history_scan",
            "qr_code",
            "images",
            "similar_histories",
        ]

    def get_events(self, history):
        """
        OPTIMIZED: Get events without triggering carbon calculations.
        This prevents USDA API calls for public history display.
        """
        try:
            # Get basic event data without expensive carbon calculations
            events_data = []
            
            # Get events using minimal queries
            chemical_events = history.chemical_events.select_related('chemical').only(
                'id', 'date', 'note', 'chemical__name', 'amount', 'unit'
            )
            production_events = history.production_events.only(
                'id', 'date', 'note', 'amount', 'unit', 'type'
            )
            weather_events = history.weather_events.only(
                'id', 'date', 'note', 'temperature', 'humidity', 'rainfall'
            )
            equipment_events = history.equipment_events.only(
                'id', 'date', 'note', 'type', 'fuel_consumption'
            )
            soil_events = history.soil_management_events.only(
                'id', 'date', 'note', 'type', 'area_treated'
            )
            pest_events = history.pest_management_events.only(
                'id', 'date', 'note', 'type', 'area_treated'
            )
            general_events = history.general_events.only(
                'id', 'date', 'note', 'type'
            )
            
            # Create lightweight event data without carbon calculations
            for event in chemical_events:
                events_data.append({
                    'id': event.id,
                    'date': event.date,
                    'note': event.note,
                    'type': 'Chemical Application',
                    'chemical_name': event.chemical.name if event.chemical else 'Unknown',
                    'amount': event.amount,
                    'unit': event.unit,
                    'event_type': 1,  # CHEMICAL_EVENT_TYPE
                    'carbon_data': None  # Skip carbon calculation for performance
                })
            
            for event in production_events:
                events_data.append({
                    'id': event.id,
                    'date': event.date,
                    'note': event.note,
                    'type': event.get_type_display() or 'Production Activity',
                    'amount': event.amount,
                    'unit': event.unit,
                    'event_type': 2,  # PRODUCTION_EVENT_TYPE
                    'carbon_data': None
                })
            
            for event in weather_events:
                events_data.append({
                    'id': event.id,
                    'date': event.date,
                    'note': event.note,
                    'type': 'Weather Event',
                    'temperature': event.temperature,
                    'humidity': event.humidity,
                    'rainfall': event.rainfall,
                    'event_type': 3,  # WEATHER_EVENT_TYPE
                    'carbon_data': None
                })
            
            for event in equipment_events:
                events_data.append({
                    'id': event.id,
                    'date': event.date,
                    'note': event.note,
                    'type': event.get_type_display() or 'Equipment Use',
                    'fuel_consumption': event.fuel_consumption,
                    'event_type': 4,  # EQUIPMENT_EVENT_TYPE
                    'carbon_data': None
                })
            
            for event in soil_events:
                events_data.append({
                    'id': event.id,
                    'date': event.date,
                    'note': event.note,
                    'type': event.get_type_display() or 'Soil Management',
                    'area_treated': event.area_treated,
                    'event_type': 5,  # SOIL_MANAGEMENT_EVENT_TYPE
                    'carbon_data': None
                })
            
            for event in pest_events:
                events_data.append({
                    'id': event.id,
                    'date': event.date,
                    'note': event.note,
                    'type': event.get_type_display() or 'Pest Management',
                    'area_treated': event.area_treated,
                    'event_type': 6,  # PEST_MANAGEMENT_EVENT_TYPE
                    'carbon_data': None
                })
            
            for event in general_events:
                events_data.append({
                    'id': event.id,
                    'date': event.date,
                    'note': event.note,
                    'type': event.get_type_display() or 'General Event',
                    'event_type': 7,  # GENERAL_EVENT_TYPE
                    'carbon_data': None
                })
            
            # Sort by date
            events_data.sort(key=lambda x: x['date'], reverse=True)
            
            return events_data
            
        except Exception as e:
            print(f"Error getting optimized events: {e}")
            # Return empty list if there's an error
            return []

    def get_certificate_percentage(self, history):
        return history.certificate_percentage

    def get_similar_histories(self, history):
        return PublicHistoryListSerializer(self.context.get("similar_histories", []), many=True, context={'request': self.context.get('request')}).data

    def get_company(self, history):
        return history.parcel.establishment.company.name if history.parcel else None

    def get_parcel(self, history):
        return history.parcel.name if history.parcel else None

    def get_history_scan(self, history):
        return self.context.get("history_scan", None)

    def get_qr_code(self, history):
        if history.qr_code:
            request = self.context.get('request')
            return request.build_absolute_uri(history.qr_code.url) if request else history.qr_code.url
        return None

    def get_images(self, history):
        try:
            if not history.album:
                return []
            
            request = self.context.get('request')
            return [
                request.build_absolute_uri(image.image.url) if request else image.image.url
                for image in history.album.images.all()
                if image.image is not None
            ]
        except Exception as e:
            print(f"Error getting images: {str(e)}")
            return []


class HistoryListOptionsSerializer(serializers.ModelSerializer):
    period = serializers.SerializerMethodField()

    class Meta:
        model = History
        fields = ["id", "period"]

    def get_period(self, history):
        return f"{history.start_date.strftime('%m/%d/%Y')} - {history.finish_date.strftime('%m/%d/%Y')}"


# Equipment Event Serializers
class UpdateEquipmentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentEvent
        fields = "__all__"


class EquipmentEventSerializer(EventSerializer):
    type = serializers.SerializerMethodField()
    event_type = serializers.SerializerMethodField()

    class Meta:
        model = EquipmentEvent
        fields = "__all__"

    def get_type(self, equipment_event):
        type_display = equipment_event.get_type_display()
        if type_display is None:
            return "event.equipment.unknown"
        return f"event.equipment.{type_display.lower().replace(' ', '_')}"

    def get_event_type(self, equipment_event):
        return EQUIPMENT_EVENT_TYPE


# Soil Management Event Serializers
class UpdateSoilManagementEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SoilManagementEvent
        fields = "__all__"


class SoilManagementEventSerializer(EventSerializer):
    type = serializers.SerializerMethodField()
    event_type = serializers.SerializerMethodField()

    class Meta:
        model = SoilManagementEvent
        fields = "__all__"

    def get_type(self, soil_event):
        type_display = soil_event.get_type_display()
        if type_display is None:
            return "event.soil.unknown"
        return f"event.soil.{type_display.lower().replace(' ', '_')}"

    def get_event_type(self, soil_event):
        return SOIL_MANAGEMENT_EVENT_TYPE


# Pest Management Event Serializers
class UpdatePestManagementEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PestManagementEvent
        fields = "__all__"


class PestManagementEventSerializer(EventSerializer):
    type = serializers.SerializerMethodField()
    event_type = serializers.SerializerMethodField()

    class Meta:
        model = PestManagementEvent
        fields = "__all__"

    def get_type(self, pest_event):
        type_display = pest_event.get_type_display()
        if type_display is None:
            return "event.pest.unknown"
        return f"event.pest.{type_display.lower().replace(' ', '_')}"

    def get_event_type(self, pest_event):
        return PEST_MANAGEMENT_EVENT_TYPE

    class Meta:
        model = History
        fields = ["id", "period"]

    def get_period(self, history):
        return f"{history.start_date.strftime('%m/%d/%Y')} - {history.finish_date.strftime('%m/%d/%Y')}"
