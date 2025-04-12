from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

@receiver(post_save, sender='product.Product')
def track_production_creation(sender, instance, created, **kwargs):
    if created:
        try:
            # Check if this product has a parcel relationship
            if hasattr(instance, 'parcel') and instance.parcel:
                # Follow the relationship to get to the company
                company = instance.parcel.establishment.company
                
                if hasattr(company, 'subscription'):
                    # Only count productions created this year
                    start_of_year = timezone.now().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                    # Check if the product has a created_at field
                    if hasattr(instance, 'created_at') and instance.created_at >= start_of_year:
                        company.subscription.used_productions += 1
                        company.subscription.save(update_fields=['used_productions'])
        except Exception as e:
            # Log error but don't fail the save
            print(f"Error tracking production creation: {str(e)}")

@receiver(post_save, sender='common.GalleryImage')
def track_storage_usage(sender, instance, created, **kwargs):
    if created and hasattr(instance, 'image') and instance.image:
        try:
            company = None
            
            # Check if this image belongs to a gallery that's linked to an establishment
            if hasattr(instance, 'gallery') and instance.gallery:
                gallery = instance.gallery
                
                # Check for establishment link
                establishments = gallery.establishment_set.all()
                if establishments.exists():
                    company = establishments.first().company
                
                # If not linked to an establishment, maybe linked to a parcel or product
                if not company:
                    # Add your logic here to find the company based on your data model
                    pass
            
            if company and hasattr(company, 'subscription'):
                # Calculate file size in GB (use image not file based on your model)
                file_size_gb = instance.image.size / (1024 * 1024 * 1024)  # Convert bytes to GB
                company.subscription.used_storage_gb += file_size_gb
                company.subscription.save(update_fields=['used_storage_gb'])
        except Exception as e:
            # Log error but don't fail the save
            print(f"Error tracking storage usage: {str(e)}") 