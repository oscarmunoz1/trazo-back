from rest_framework import serializers

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
    BusinessEvent,
    PestManagementEvent,
)
from .constants import (
    WEATHER_EVENT_TYPE,
    PRODUCTION_EVENT_TYPE,
    CHEMICAL_EVENT_TYPE,
    GENERAL_EVENT_TYPE,
    EQUIPMENT_EVENT_TYPE,
    SOIL_MANAGEMENT_EVENT_TYPE,
    BUSINESS_EVENT_TYPE,
    PEST_MANAGEMENT_EVENT_TYPE,
)
from common.models import Gallery
from product.models import Product, Parcel
from company.models import Establishment
from users.models import User
from users.serializers import BasicUserSerializer


class EventSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = CommonEvent
        fields = "__all__"

    def get_image(self, event):
        if event.album is not None:
            return event.album.images.first().image.url
        return None


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
        return f"event.chemical.{chemical_event.get_type_display().lower().replace(' ', '_')}"

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
        if type == WeatherEvent.FROST:
            data["lower_temperature"] = instance.extra_data["lower_temperature"]
            data["way_of_protection"] = instance.extra_data["way_of_protection"]
        elif type == WeatherEvent.DROUGHT:
            data["water_deficit"] = instance.extra_data["water_deficit"]
        elif type == WeatherEvent.HAILSTORM:
            data["weight"] = instance.extra_data["weight"]
            data["diameter"] = instance.extra_data["diameter"]
            data["duration"] = instance.extra_data["duration"]
            data["way_of_protection"] = instance.extra_data["way_of_protection"]
        elif type == WeatherEvent.HIGH_TEMPERATURE:
            data["highest_temperature"] = instance.extra_data["highest_temperature"]
            data["start_date"] = instance.extra_data["start_date"]
            data["end_date"] = instance.extra_data["end_date"]
        data.pop("extra_data")
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
        return f"event.weather.{weather_event.get_type_display().lower().replace(' ', '_')}"

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
        return f"event.production.{production_event.get_type_display().lower().replace(' ', '_')}"

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


class HistorySerializer(serializers.ModelSerializer):
    events = serializers.SerializerMethodField()
    certificate_percentage = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()
    parcel = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    operator = BasicUserSerializer(read_only=True)

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

    def get_members(self, history):
        events = history.history_weatherevent_events.all()
        members = []
        for event in events:
            if event.created_by:
                members.append(
                    event.created_by.first_name + " " + event.created_by.last_name
                )
        return members[0:3]

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
        members = User.objects.filter(id__in=history.get_involved_users()).order_by(
            "first_name"
        )[0:2]
        return BasicUserSerializer(members, many=True).data


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
            "images",
            "similar_histories",
        ]

    def get_events(self, history):
        return history.get_events()

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
        return f"event.equipment.{equipment_event.get_type_display().lower().replace(' ', '_')}"

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
        return f"event.soil.{soil_event.get_type_display().lower().replace(' ', '_')}"

    def get_event_type(self, soil_event):
        return SOIL_MANAGEMENT_EVENT_TYPE


# Business Event Serializers
class UpdateBusinessEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessEvent
        fields = "__all__"


class BusinessEventSerializer(EventSerializer):
    type = serializers.SerializerMethodField()
    event_type = serializers.SerializerMethodField()

    class Meta:
        model = BusinessEvent
        fields = "__all__"

    def get_type(self, business_event):
        return f"event.business.{business_event.get_type_display().lower().replace(' ', '_')}"

    def get_event_type(self, business_event):
        return BUSINESS_EVENT_TYPE


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
        return f"event.pest.{pest_event.get_type_display().lower().replace(' ', '_')}"

    def get_event_type(self, pest_event):
        return PEST_MANAGEMENT_EVENT_TYPE
