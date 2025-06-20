from django.db import models
from datetime import datetime
from company.models import Establishment


class Product(models.Model):
    name = models.CharField(max_length=30)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="product_images", blank=True)

    def __str__(self):
        return self.name


class Parcel(models.Model):
    name = models.CharField(max_length=30)
    description = models.TextField(blank=True, null=True)
    album = models.ForeignKey(
        "common.Gallery", on_delete=models.CASCADE, blank=True, null=True
    )
    establishment = models.ForeignKey(
        Establishment, on_delete=models.CASCADE, related_name="parcels"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, blank=True, null=True
    )
    area = models.FloatField(help_text="Parcel area in hectares")
    certified = models.BooleanField(
        default=False, help_text="Certified by a professional"
    )
    current_history = models.OneToOneField(
        "history.History",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="current_parcel",
    )
    polygon = models.JSONField(blank=True, null=True)
    map_metadata = models.JSONField(blank=True, null=True)
    # crop_type removed - now stored in History model for per-production tracking
    soil_type = models.CharField(max_length=50, blank=True, null=True)
    unique_code = models.CharField(max_length=50, blank=True, null=True)
    certification_type = models.CharField(max_length=50, blank=True, null=True)
    contact_person = models.CharField(max_length=60, blank=True, null=True)
    contact_phone = models.CharField(max_length=30, blank=True, null=True)
    contact_email = models.EmailField(max_length=254, blank=True, null=True)

    def __str__(self):
        return str(self.id) + " - " + self.name + " - " + self.establishment.name

    @property
    def productions_completed(self):
        return self.histories.filter(finish_date__year=datetime.now().year).count()

    def finish_current_history(self, history_data, images):
        if self.current_history is not None:
            self.current_history.finish(history_data, images)
            history = self.current_history
            self.current_history = None
            self.save()
            return history
        return None
