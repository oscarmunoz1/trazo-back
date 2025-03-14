from django.db import models
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.conf import settings


class Company(models.Model):
    name = models.CharField(max_length=30)
    tradename = models.CharField(max_length=30, blank=True, null=True)
    address = models.CharField(max_length=30)
    city = models.CharField(max_length=30)
    state = models.CharField(max_length=30)
    country = models.CharField(max_length=30, blank=True, null=True)
    fiscal_id = models.CharField(max_length=30, help_text="RUT", blank=True, null=True)
    logo = models.ImageField(upload_to="company_logos", blank=True)
    description = models.TextField(blank=True, null=True)
    invitation_code = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        verbose_name = _("Company")
        verbose_name_plural = _("Companies")

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("company-detail", kwargs={"id": self.id})


class Establishment(models.Model):
    name = models.CharField(max_length=30)
    address = models.CharField(max_length=30)
    city = models.CharField(max_length=30, blank=True, null=True)
    zone = models.CharField(max_length=30, blank=True, null=True)
    state = models.CharField(max_length=30)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    album = models.ForeignKey(
        "common.Gallery", on_delete=models.CASCADE, blank=True, null=True
    )
    description = models.TextField(blank=True, null=True)
    country = models.CharField(max_length=30, blank=True, null=True)

    class Meta:
        verbose_name = _("Establishment")
        verbose_name_plural = _("Establishments")

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("establishment-detail", kwargs={"id": self.id})

    def get_location(self) -> str:
        return f"{self.city if self.city is not None else '-'}, {self.country if self.country is not None else '-'}"
