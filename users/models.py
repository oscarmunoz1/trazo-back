from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.utils import timezone
from .managers import UserManager
from .constants import USER_TYPE_CHOICES, CONSUMER
from company.models import Company, Establishment
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    username = None  # remove username field, we will use email as unique identifier
    email = models.EmailField(unique=True, null=True, db_index=True)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    phone = models.CharField(max_length=255, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    companies = models.ManyToManyField(
        Company,
        related_name="company_users",
        through="WorksIn",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user_type = models.PositiveSmallIntegerField(
        choices=USER_TYPE_CHOICES, default=CONSUMER
    )
    image = models.ImageField(upload_to="user_images/", blank=True, null=True)

    REQUIRED_FIELDS = []
    USERNAME_FIELD = "email"

    objects = UserManager()

    def __str__(self):
        return self.get_full_name()

    def get_full_name(self):
        return self.first_name + " " + self.last_name
    
    def get_active_company(self):
        # Check for active or trialing subscriptions
        return self.companies.filter(subscription__status__in=["active", "trialing"]).first()

    def get_trial_company(self):
        return self.companies.filter(subscription__status="trialing").first()


class WorksIn(models.Model):
    COMPANY_ADMIN = "CA"
    DOMAIN_SUPERVISOR = "DS"
    DOMAIN_WORKER = "DW"
    DEALER = "DE"

    USER_ROLES = [
        (COMPANY_ADMIN, _("Company Admin")),
        (DOMAIN_SUPERVISOR, _("Domain Supervisor")),
        (DOMAIN_WORKER, _("Domain Worker")),
        (DEALER, _("Dealer")),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_workers"
    )
    role = models.CharField(choices=USER_ROLES, max_length=5)
    establishments_in_charge = models.ManyToManyField(
        Establishment, related_name="workers", blank=True, null=True
    )
    role_group = models.ForeignKey(
        Group, on_delete=models.CASCADE, null=True, blank=True
    )


class VerificationCode(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="verification_code"
    )
    code = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "code")

    def __str__(self):
        return f"{self.user.email} - {self.code}"
