# Generated manually for Trazo field length improvements
# Addresses CRITICAL issue where 30-character limits were too restrictive for real-world use

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('history', '0001_initial'),
    ]

    operations = [
        # History model field length improvements
        migrations.AlterField(
            model_name='history',
            name='name',
            field=models.CharField(max_length=150, blank=True, null=True, help_text='Production name'),
        ),
        migrations.AlterField(
            model_name='history',
            name='lot_id',
            field=models.CharField(max_length=50, blank=True, null=True, help_text='Lot identifier'),
        ),
        migrations.AlterField(
            model_name='history',
            name='age_of_plants',
            field=models.CharField(max_length=50, blank=True, null=True, help_text='Age of plants/trees'),
        ),
        migrations.AlterField(
            model_name='history',
            name='number_of_plants',
            field=models.CharField(max_length=50, blank=True, null=True, help_text='Number of plants'),
        ),
        migrations.AlterField(
            model_name='history',
            name='soil_ph',
            field=models.CharField(max_length=20, blank=True, null=True, help_text='Soil pH level'),
        ),
        
        # GeneralEvent model field length improvements
        migrations.AlterField(
            model_name='generalevent',
            name='name',
            field=models.CharField(max_length=150, help_text='Event name'),
        ),
        
        # HistoryScan model field length improvements
        migrations.AlterField(
            model_name='historyscan',
            name='ip_address',
            field=models.CharField(max_length=45, blank=True, null=True, help_text='IP address (IPv4/IPv6)'),
        ),
        migrations.AlterField(
            model_name='historyscan',
            name='city',
            field=models.CharField(max_length=100, blank=True, null=True, help_text='Scanner city'),
        ),
        migrations.AlterField(
            model_name='historyscan',
            name='country',
            field=models.CharField(max_length=100, blank=True, null=True, help_text='Scanner country'),
        ),
    ]