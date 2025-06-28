# Generated manually for Trazo field length improvements
# Addresses CRITICAL issue where 30-character limits were too restrictive for real-world use

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0001_initial'),
    ]

    operations = [
        # Company model field length improvements
        migrations.AlterField(
            model_name='company',
            name='name',
            field=models.CharField(max_length=150, help_text='Company name'),
        ),
        migrations.AlterField(
            model_name='company',
            name='tradename',
            field=models.CharField(max_length=150, blank=True, null=True, help_text='Trade name or DBA'),
        ),
        migrations.AlterField(
            model_name='company',
            name='address',
            field=models.CharField(max_length=200, help_text='Street address'),
        ),
        migrations.AlterField(
            model_name='company',
            name='city',
            field=models.CharField(max_length=100, help_text='City name'),
        ),
        migrations.AlterField(
            model_name='company',
            name='state',
            field=models.CharField(max_length=100, help_text='State or province'),
        ),
        migrations.AlterField(
            model_name='company',
            name='country',
            field=models.CharField(max_length=100, blank=True, null=True, help_text='Country name'),
        ),
        migrations.AlterField(
            model_name='company',
            name='fiscal_id',
            field=models.CharField(max_length=50, help_text='Tax ID, RUT, or EIN', blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='company',
            name='invitation_code',
            field=models.CharField(max_length=50, blank=True, null=True, help_text='Invitation code for new users'),
        ),
        migrations.AlterField(
            model_name='company',
            name='contact_email',
            field=models.EmailField(max_length=254, blank=True, null=True, help_text='Primary contact email'),
        ),
        migrations.AlterField(
            model_name='company',
            name='contact_phone',
            field=models.CharField(max_length=20, blank=True, null=True, help_text='Primary contact phone'),
        ),
        
        # Establishment model field length improvements
        migrations.AlterField(
            model_name='establishment',
            name='name',
            field=models.CharField(max_length=150, help_text='Establishment name'),
        ),
        migrations.AlterField(
            model_name='establishment',
            name='address',
            field=models.CharField(max_length=200, help_text='Street address'),
        ),
        migrations.AlterField(
            model_name='establishment',
            name='city',
            field=models.CharField(max_length=100, blank=True, null=True, help_text='City name'),
        ),
        migrations.AlterField(
            model_name='establishment',
            name='zone',
            field=models.CharField(max_length=100, blank=True, null=True, help_text='Zone or region'),
        ),
        migrations.AlterField(
            model_name='establishment',
            name='state',
            field=models.CharField(max_length=100, help_text='State or province'),
        ),
        migrations.AlterField(
            model_name='establishment',
            name='country',
            field=models.CharField(max_length=100, blank=True, null=True, help_text='Country name'),
        ),
        migrations.AlterField(
            model_name='establishment',
            name='type',
            field=models.CharField(max_length=100, blank=True, null=True, help_text='Establishment type'),
        ),
        migrations.AlterField(
            model_name='establishment',
            name='latitude',
            field=models.FloatField(blank=True, null=True, help_text='GPS latitude'),
        ),
        migrations.AlterField(
            model_name='establishment',
            name='longitude',
            field=models.FloatField(blank=True, null=True, help_text='GPS longitude'),
        ),
        migrations.AlterField(
            model_name='establishment',
            name='contact_person',
            field=models.CharField(max_length=100, blank=True, null=True, help_text='Contact person name'),
        ),
        migrations.AlterField(
            model_name='establishment',
            name='contact_phone',
            field=models.CharField(max_length=20, blank=True, null=True, help_text='Contact phone number'),
        ),
        migrations.AlterField(
            model_name='establishment',
            name='phone',
            field=models.CharField(max_length=20, blank=True, null=True, help_text='Main establishment phone'),
        ),
    ]