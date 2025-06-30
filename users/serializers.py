from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings
from django.contrib.auth.models import update_last_login
from django.core.exceptions import ObjectDoesNotExist
from .models import User, WorksIn
from .constants import PRODUCER, USER_TYPE_CHOICES


class WorksInSerializer(serializers.ModelSerializer):
    """
    Serializer for WorksIn.
    """

    id = serializers.ReadOnlyField(source="company.id")
    user = serializers.SerializerMethodField()
    establishments_in_charge = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    class Meta:
        model = WorksIn
        fields = (
            "id",
            "user",
            "role",
            "establishments_in_charge",
        )

    def get_picture(self, obj):
        return obj.company.picture.url if obj.company.picture else None

    def get_establishments_in_charge(self, obj):
        from company.serializers import BasicEstablishmentSerializer

        return BasicEstablishmentSerializer(
            obj.establishments_in_charge.all(), many=True
        ).data

    def get_user(self, obj):
        return obj.user.get_full_name()

    def get_role(self, obj):
        return obj.get_role_display()


class BasicUserSerializer(serializers.ModelSerializer):
    """
    Serializer for User.
    """

    companies = WorksInSerializer(source="worksin_set", many=True)
    full_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "phone",
            "full_name",
            "is_superuser",
            "companies",
            "first_name",
            "last_name",
            "user_type",
            "image",
        ]
        read_only_field = [
            "is_active",
        ]

    def get_full_name(self, user):
        return user.get_full_name()


class MeSerializer(BasicUserSerializer):
    """
    Serializer for User to get their profile.
    """

    class Meta:
        model = User
        fields = BasicUserSerializer.Meta.fields + ["username", "user_type"]
        read_only_fields = ["username"]


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        refresh = self.get_token(self.user)

        data["user"] = BasicUserSerializer(self.user).data
        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        data["user_type"] = self.user.user_type

        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, self.user)

        return data


class RegisterSerializer(BasicUserSerializer):
    password = serializers.CharField(
        max_length=128, min_length=8, write_only=True, required=True
    )
    email = serializers.EmailField(required=True, write_only=True, max_length=128)
    first_name = serializers.CharField(required=True, write_only=True, max_length=128)
    last_name = serializers.CharField(required=True, write_only=True, max_length=128)
    user_type = serializers.CharField(required=True, write_only=True, max_length=128)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "is_active",
            "user_type",
        ]

    def create(self, validated_data):
        # Convert user_type string to integer if needed
        user_type = validated_data.get('user_type')
        if isinstance(user_type, str):
            # Create a mapping from string values to integer values
            user_type_mapping = {
                'SUPERUSER': 1,
                'STAFF': 2, 
                'CONSUMER': 3,
                'PRODUCER': 4,
                'CERTIFIER': 5
            }
            validated_data['user_type'] = user_type_mapping.get(user_type.upper(), 3)  # Default to CONSUMER if not found
        
        try:
            user = User.objects.get(email=validated_data["email"])
        except ObjectDoesNotExist:
            user = User.objects.create_user(**validated_data)
        return user
