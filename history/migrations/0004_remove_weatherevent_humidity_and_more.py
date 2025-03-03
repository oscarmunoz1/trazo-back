# Generated by Django 4.1.4 on 2023-10-09 19:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("history", "0003_alter_history_published"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="weatherevent",
            name="humidity",
        ),
        migrations.RemoveField(
            model_name="weatherevent",
            name="temperature",
        ),
        migrations.RemoveField(
            model_name="weatherevent",
            name="time_period",
        ),
        migrations.AddField(
            model_name="history",
            name="extra_data",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="history",
            name="type",
            field=models.CharField(
                blank=True,
                choices=[("OR", "Orchard"), ("GA", "Garden")],
                max_length=2,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="weatherevent",
            name="extra_data",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="weatherevent",
            name="type",
            field=models.CharField(
                choices=[
                    ("FR", "Frost"),
                    ("DR", "Drought"),
                    ("HA", "Hailstorm"),
                    ("HT", "High Temperature"),
                    ("TS", "Tropical Storm"),
                    ("HW", "High Winds"),
                    ("HH", "High Humidity"),
                    ("LH", "Low Humidity"),
                ],
                max_length=2,
            ),
        ),
    ]
