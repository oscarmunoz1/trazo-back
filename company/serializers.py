from rest_framework.serializers import ModelSerializer
from .models import Company, Establishment
from rest_framework import serializers
from product.serializers import ParcelBasicSerializer
from common.serializers import GallerySerializer
from common.models import Gallery
from users.models import WorksIn
from subscriptions.serializers import SubscriptionSerializer


class EstablishmentSerializer(ModelSerializer):
    parcels = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

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
            "type",
            "latitude",
            "longitude",
            "contact_person",
            "contact_phone",
            "contact_email",
            "facebook",
            "instagram",
            "certifications",
            "about",
            "main_activities",
            "location_highlights",
            "custom_message",
            "images",
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
            
            image_obj = establishment.album.images.first()
            if not image_obj:
                return None
                
            # Use the url property which handles image, image_url, and s3_key
            image_url = image_obj.url
            if not image_url:
                return None

            request = self.context.get('request')
            if request and not image_url.startswith(('http://', 'https://')):
                return request.build_absolute_uri(image_url)
            return image_url
        except Exception as e:
            print(f"Error getting image: {str(e)}")
            return None

    def get_location(self, establishment):
        return establishment.get_location()

    def get_images(self, establishment):
        try:
            if not establishment.album:
                return []
            request = self.context.get('request')
            image_list = []
            for image_obj in establishment.album.images.all():
                image_url = image_obj.url
                if image_url:
                    if request and not image_url.startswith(('http://', 'https://')):
                        image_url = request.build_absolute_uri(image_url)
                    image_list.append({"id": image_obj.id, "url": image_url})
            return image_list
        except Exception as e:
            print(f"Error getting images: {str(e)}")
            return []


class UpdateEstablishmentSerializer(ModelSerializer):
    album = GallerySerializer(required=False)
    s3_keys = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)
    uploaded_image_urls = serializers.ListField(child=serializers.URLField(), required=False, write_only=True)
    images_to_delete = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)

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
            "s3_keys",
            "uploaded_image_urls",
            "images_to_delete",
            "type",
            "latitude",
            "longitude",
            "contact_person",
            "contact_phone",
            "contact_email",
            "facebook",
            "instagram",
            "certifications",
            "about",
            "main_activities",
            "location_highlights",
            "custom_message",
            "address",
        )

    def to_representation(self, instance):
        return EstablishmentSerializer(instance).data

    def update(self, instance, validated_data):
        images_to_delete = validated_data.pop('images_to_delete', [])
        s3_keys = validated_data.pop('s3_keys', None)
        uploaded_image_urls = validated_data.pop('uploaded_image_urls', None)
        album_data = self.context.get("request").FILES
        
        # Create or get the gallery
        gallery = instance.album
        if gallery is None:
            gallery = Gallery.objects.create()
        
        # Delete images from the gallery
        if images_to_delete and instance.album:
            for image_id in images_to_delete:
                instance.album.images.filter(id=image_id).delete()
        
        # Handle S3 keys from production environment
        if s3_keys:
            for s3_key in s3_keys:
                gallery_image = gallery.images.create(s3_key=s3_key)
                gallery_image.save()
            validated_data["album"] = gallery
        
        # Handle uploaded image URLs (for both environments)
        elif uploaded_image_urls:
            for url in uploaded_image_urls:
                gallery_image = gallery.images.create(image_url=url)
                gallery_image.save()
            validated_data["album"] = gallery
        
        # Handle direct file uploads from form (development environment)
        elif album_data:
            for image_data in album_data.values():
                gallery_image = gallery.images.create(image=image_data)
                gallery_image.save()
            validated_data["album"] = gallery
            
        return super().update(instance, validated_data)

    def create(self, validated_data):
        s3_keys = validated_data.pop('s3_keys', None)
        uploaded_image_urls = validated_data.pop('uploaded_image_urls', None)
        album_data = self.context.get("request").FILES
        
        if s3_keys:
            gallery = Gallery.objects.create()
            
            for s3_key in s3_keys:
                gallery_image = gallery.images.create(s3_key=s3_key)
                gallery_image.save()
            
            validated_data["album"] = gallery
        elif uploaded_image_urls:
            gallery = Gallery.objects.create()
            
            for url in uploaded_image_urls:
                gallery_image = gallery.images.create(image_url=url)
                gallery_image.save()
            
            validated_data["album"] = gallery
        elif album_data:
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
            image_list = []
            
            for image_obj in establishment.album.images.all():
                image_url = image_obj.url
                if image_url:
                    if request and not image_url.startswith(('http://', 'https://')):
                        image_url = request.build_absolute_uri(image_url)
                    image_list.append(image_url)
            
            return image_list
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
    subscription = SubscriptionSerializer(read_only=True)
    has_subscription = serializers.SerializerMethodField()
    subscription_plan = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "tradename",
            "address",
            "city",
            "state",
            "country",
            "fiscal_id",
            "logo",
            "description",
            "invitation_code",
            "contact_email",
            "contact_phone",
            "website",
            "facebook",
            "instagram",
            "certifications",
            "establishments",
            "image",
            "subscription",
            "has_subscription",
            "subscription_plan",
        )
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context 

    def get_establishments(self, company):
        try:
            if "request" not in self.context:
                # Return basic establishment data without user-specific filtering
                return BasicEstablishmentSerializer(
                    company.establishment_set.all().order_by("name"), many=True
                ).data
                
            user = self.context["request"].user
            worksIn = WorksIn.objects.filter(user=user, company=company)[0]
            if worksIn.role == "CA":
                return EstablishmentSerializer(
                    company.establishment_set.all().order_by("name"), many=True, context=self.context
                ).data
            return EstablishmentSerializer(
                worksIn.establishments_in_charge.all(), many=True, context=self.context
            ).data
        except Exception as e:
            # Log error and return empty list as fallback
            print(f"Error getting establishments: {str(e)}")
            return []

    def get_image(self, company):
        try:
            if not hasattr(company, 'album'):
                return None
            
            if not company.album or not company.album.images.exists():
                return None
            
            image_obj = company.album.images.first()
            if not image_obj:
                return None
                
            # Use the url property which handles image, image_url, and s3_key
            image_url = image_obj.url
            if not image_url:
                return None

            request = self.context.get('request')
            if request and not image_url.startswith(('http://', 'https://')):
                return request.build_absolute_uri(image_url)
            return image_url
        except Exception as e:
            print(f"Error getting image: {str(e)}")
            return None

    def get_has_subscription(self, obj):
        """Check if company has an active subscription"""
        if hasattr(obj, 'subscription') and obj.subscription:
            return obj.subscription.status in ['active', 'trialing']
        return False
    
    def get_subscription_plan(self, obj):
        """Get serialized subscription plan data if available"""
        if hasattr(obj, 'subscription') and obj.subscription and obj.subscription.plan:
            return {
                'id': obj.subscription.plan.id,
                'name': obj.subscription.plan.name,
                'price': obj.subscription.plan.price,
                'interval': obj.subscription.plan.interval,
                'features': obj.subscription.plan.features
            }
        return None


class CreateCompanySerializer(ModelSerializer):
    class Meta:
        model = Company
        exclude = (
            "fiscal_id",
            "invitation_code",
        )
