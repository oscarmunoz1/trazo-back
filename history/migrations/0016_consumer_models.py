"""
Database migration for consumer-specific models
"""
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import django.utils.timezone
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('history', '0015_merge_20250627_2032'),  # Updated to actual latest migration
        ('company', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserFavorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('production', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorited_by', to='history.history')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorites', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='UserImpactSummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_scans', models.IntegerField(default=0)),
                ('total_reviews', models.IntegerField(default=0)),
                ('total_carbon_offset_kg', models.FloatField(default=0.0)),
                ('total_money_saved_usd', models.FloatField(default=0.0)),
                ('miles_driving_offset', models.FloatField(default=0.0)),
                ('trees_equivalent', models.FloatField(default=0.0)),
                ('sustainable_farms_found', models.IntegerField(default=0)),
                ('local_farms_found', models.IntegerField(default=0)),
                ('better_choices_made', models.IntegerField(default=0)),
                ('achievements_earned', models.JSONField(default=list)),
                ('current_level', models.IntegerField(default=1)),
                ('points_earned', models.IntegerField(default=0)),
                ('first_scan_date', models.DateTimeField(blank=True, null=True)),
                ('last_scan_date', models.DateTimeField(blank=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='impact_summary', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='UserProductComparison',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comparison_name', models.CharField(blank=True, max_length=200)),
                ('comparison_data', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('products', models.ManyToManyField(related_name='compared_in', to='history.history')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comparisons', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='UserShoppingGoal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('goal_type', models.CharField(choices=[('carbon_reduction', 'Reduce Carbon Footprint'), ('local_shopping', 'Shop Local'), ('sustainable_farms', 'Support Sustainable Farms'), ('scan_products', 'Scan Products'), ('money_savings', 'Save Money')], max_length=50)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('target_value', models.FloatField()),
                ('current_value', models.FloatField(default=0.0)),
                ('unit', models.CharField(max_length=50)),
                ('start_date', models.DateField(default=django.utils.timezone.now)),
                ('target_date', models.DateField()),
                ('completed_date', models.DateField(blank=True, null=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('completed', 'Completed'), ('paused', 'Paused'), ('cancelled', 'Cancelled')], default='active', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shopping_goals', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='UserShoppingInsight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('insight_type', models.CharField(choices=[('trend', 'Shopping Trend'), ('recommendation', 'Product Recommendation'), ('achievement', 'Achievement Unlock'), ('tip', 'Sustainability Tip'), ('milestone', 'Milestone Reached')], max_length=50)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('data', models.JSONField(default=dict)),
                ('is_read', models.BooleanField(default=False)),
                ('is_dismissed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shopping_insights', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='UserLocalRecommendation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('distance_miles', models.FloatField()),
                ('carbon_score', models.IntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('recommendation_score', models.FloatField()),
                ('is_viewed', models.BooleanField(default=False)),
                ('is_favorited', models.BooleanField(default=False)),
                ('view_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('establishment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recommended_to', to='company.establishment')),
                ('recommended_products', models.ManyToManyField(blank=True, related_name='recommended_to_users', to='history.history')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='local_recommendations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-recommendation_score'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='userlocalrecommendation',
            unique_together={('user', 'establishment')},
        ),
        migrations.AlterUniqueTogether(
            name='userfavorite',
            unique_together={('user', 'production')},
        ),
    ]