from rest_framework.serializers import ModelSerializer
from .models import Company, Establishment
from rest_framework import serializers
from product.serializers import ParcelBasicSerializer
from common.serializers import GallerySerializer
from common.models import Gallery
from users.models import WorksIn


class EstablishmentSerializer(ModelSerializer):
    parcels = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()

    class Meta:
        model = Establishment
        fields = (
            "id",
            "name",
            "description",
            "address",
            "city",
            "zone",
            "state",
            "image",
            "parcels",
            "image",
            "country",
            "location",
        )

    def get_parcels(self, establishment):
        return ParcelBasicSerializer(
            establishment.parcels.all(), 
            many=True,
            context=self.context
        ).data

    def get_image(self, establishment):
        try:
            if not establishment.album or not establishment.album.images.exists():
                return None
            
            image = establishment.album.images.first().image
            if not image:
                return None

            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(image.url)
            return image.url
        except Exception as e:
            print(f"Error getting image: {str(e)}")
            return None

    def get_location(self, establishment):
        return establishment.get_location()


class UpdateEstablishmentSerializer(ModelSerializer):
    album = GallerySerializer(required=False)

    class Meta:
        model = Establishment
        fields = (
            "id",
            "name",
            "city",
            "zone",
            "album",
            "state",
            "company",
            "description",
            "country",
        )

    def to_representation(self, instance):
        return EstablishmentSerializer(instance).data

    def update(self, instance, validated_data):
        album_data = self.context.get("request").FILES
        if album_data:
            gallery = instance.album
            if gallery is None:
                gallery = Gallery.objects.create()
            for image_data in album_data.values():
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


class RetrieveEstablishmentSerializer(ModelSerializer):
    parcels = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    class Meta:
        model = Establishment
        fields = "__all__"

    def get_images(self, establishment):
        try:
            if not establishment.album:
                return []
            
            request = self.context.get('request')
            return [
                request.build_absolute_uri(image.image.url) if request else image.image.url
                for image in establishment.album.images.all()
                if image.image is not None
            ]
        except Exception as e:
            print(f"Error getting images: {str(e)}")
            return []
    
    def get_parcels(self, establishment):
        return ParcelBasicSerializer(
            establishment.parcels.all(), 
            many=True,
            context=self.context
        ).data


class EstablishmentSeriesSerializer(serializers.Serializer):
    scans = serializers.ListField()
    sales = serializers.ListField()

    class Meta:
        fields = ["scans", "sales"]


class EstablishmentChartSerializer(serializers.Serializer):
    series = EstablishmentSeriesSerializer()
    options = serializers.SerializerMethodField()

    class Meta:
        model = Establishment
        fields = ["series", "options"]

    def get_options(self, establishment):
        period = self.context["period"]
        if period == "week":
            week_days = [
                "Sun",
                "Mon",
                "Tue",
                "Wed",
                "Thu",
                "Fri",
                "Sat",
            ]
            return [week_days[day - 1] for day in self.context["days"]]
        elif period == "month":
            return self.context["days"]
        elif period == "year":
            return [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ]
        return []


class EstablishmentProductsReputationSerializer(serializers.Serializer):
    series = serializers.ListField()
    options = serializers.ListField()

    class Meta:
        model = Establishment
        fields = ["series", "options"]


class BasicEstablishmentSerializer(ModelSerializer):
    class Meta:
        model = Establishment
        fields = (
            "id",
            "name",
        )


class RetrieveCompanySerializer(ModelSerializer):
    establishments = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "tradename",
            "address",
            "image",
            "city",
            "state",
            "country",
            "logo",
            "description",
            "establishments",
        )
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context 

    def get_establishments(self, company):
        user = self.context["request"].user
        worksIn = WorksIn.objects.filter(user=user, company=company)[0]
        if worksIn.role == "CA":
            return EstablishmentSerializer(
                company.establishment_set.all().order_by("name"), many=True, context=self.context
            ).data
        return EstablishmentSerializer(
            worksIn.establishments_in_charge.all(), many=True, context=self.context
        ).data

    def get_image(self, company):
        try:
            if not company.album or not company.album.images.exists():
                return None
            
            image = company.album.images.first().image
            if not image:
                return None

            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(image.url)
            return image.url
        except Exception as e:
            print(f"Error getting image: {str(e)}")
            return None


class CreateCompanySerializer(ModelSerializer):
    class Meta:
        model = Company
        exclude = (
            "fiscal_id",
            "invitation_code",
        )
