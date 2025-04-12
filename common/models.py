from django.db import models
from django.conf import settings

class Gallery(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class GalleryImage(models.Model):
    gallery = models.ForeignKey(
        Gallery, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="gallery_images/", blank=True, null=True)
    s3_key = models.CharField(max_length=255, blank=True, null=True)
    image_url = models.URLField(max_length=1000, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Image {self.id} for Gallery {self.gallery.id}"
        
    @property
    def url(self):
        if self.s3_key:
            return f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{self.s3_key}"
        elif self.image_url:
            return self.image_url
        elif self.image:
            return self.image.url
        return None