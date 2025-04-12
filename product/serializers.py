from rest_framework.serializers import ModelSerializer
from .models import Parcel, Product
from rest_framework import serializers
from common.serializers import GallerySerializer, GalleryImageSerializer
from common.models import Gallery
from users.models import User
from users.serializers import BasicUserSerializer
from django.conf import settings


class ParcelBasicSerializer(ModelSerializer):
    product = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    has_current_production = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()

    class Meta:
        model = Parcel
        fields = (
            "id",
            "name",
            "description",
            "product",
            "image",
            "has_current_production",
            "members",
        )

    def get_product(self, parcel):
        return (
            parcel.current_history.product.name
            if parcel.current_history and parcel.current_history.product
            else None
        )

    def get_has_current_production(self, parcel):
        return parcel.current_history is not None

    def get_image(self, parcel):
        try:
            if not parcel.album or not parcel.album.images.exists():
                return None
            
            image_obj = parcel.album.images.first()
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

    def get_members(self, parcel):
        members_ids = []
        for history in parcel.histories.all():
            members_ids += history.get_involved_users()
        members_ids = list(set(members_ids))
        members = User.objects.filter(id__in=members_ids)[0:2]
        return BasicUserSerializer(members, many=True).data


class RetrieveParcelSerializer(ModelSerializer):
    product = serializers.SerializerMethodField()
    establishment = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    productions_completed = serializers.SerializerMethodField()

    class Meta:
        model = Parcel
        exclude = ("album",)

    def get_product(self, parcel):
        return parcel.product.name if parcel.product else None

    def get_establishment(self, parcel):
        return parcel.establishment.name if parcel.establishment else None

    def get_image(self, parcel):
        try:
            if not parcel.album or not parcel.album.images.exists():
                return None
            
            image_obj = parcel.album.images.first()
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

    def get_images(self, parcel):
        try:
            if not parcel.album:
                return []
            
            request = self.context.get('request')
            image_list = []
            
            for image_obj in parcel.album.images.all():
                image_url = image_obj.url
                if image_url:
                    if request and not image_url.startswith(('http://', 'https://')):
                        image_url = request.build_absolute_uri(image_url)
                    image_list.append(image_url)
            
            return image_list
        except Exception as e:
            print(f"Error getting images: {str(e)}")
            return []

    def get_productions_completed(self, parcel):
        return parcel.productions_completed


class CreateParcelSerializer(ModelSerializer):
    product = serializers.SerializerMethodField()
    album = GallerySerializer(required=False)
    image = serializers.SerializerMethodField()
    uploaded_image_urls = serializers.ListField(child=serializers.URLField(), required=False, write_only=True)
    s3_keys = serializers.ListField(child=serializers.CharField(), required=False, write_only=True)

    class Meta:
        model = Parcel
        fields = "__all__"

    def get_product(self, parcel):
        return None

    def update(self, instance, validated_data):
        s3_keys = validated_data.pop('s3_keys', None)
        uploaded_image_urls = validated_data.pop('uploaded_image_urls', None)
        album_data = self.context.get("request").FILES
        
        # Create or get the gallery
        gallery = instance.album
        if gallery is None:
            gallery = Gallery.objects.create()
        
        # Handle S3 keys from production environment
        if s3_keys:
            for s3_key in s3_keys:
                gallery_image = gallery.images.create(s3_key=s3_key)
                gallery_image.save()
            validated_data["album"] = gallery
        
        # Handle uploaded image URLs (for both environments)
        elif uploaded_image_urls:
            for url in uploaded_image_urls:
                if url and isinstance(url, str) and url.startswith('http'):
                    gallery_image = gallery.images.create(image_url=url)
                    gallery_image.save()
            validated_data["album"] = gallery
        
        # Handle direct file uploads from form (development environment)
        elif album_data:
            for image_data in album_data.getlist("album[images]"):
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
                if url and isinstance(url, str) and url.startswith('http'):
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

    def get_image(self, parcel):
        try:
            if not parcel.album or not parcel.album.images.exists():
                return None
            
            image_obj = parcel.album.images.first()
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


class ProductListOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name"]


class ProductListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "description", "image"]
