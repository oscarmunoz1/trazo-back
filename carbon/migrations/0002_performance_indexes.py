# Generated for Phase 1 Performance Optimization

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('carbon', '0001_initial'),  # Replace with your latest migration
        ('history', '0001_initial'),  # Replace with your latest migration
    ]

    operations = [
        # Indexes for QR endpoint performance
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_carbonentry_production_type ON carbon_carbonentry(production_id, type);",
            "DROP INDEX IF EXISTS idx_carbonentry_production_type;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_carbonentry_establishment_year ON carbon_carbonentry(establishment_id, year, type);",
            "DROP INDEX IF EXISTS idx_carbonentry_establishment_year;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_history_qr_lookup ON history_history(id, published, finish_date);",
            "DROP INDEX IF EXISTS idx_history_qr_lookup;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_carbonentry_co2e_amount ON carbon_carbonentry(co2e_amount, type);",
            "DROP INDEX IF EXISTS idx_carbonentry_co2e_amount;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_establishment_location ON company_establishment(latitude, longitude);",
            "DROP INDEX IF EXISTS idx_establishment_location;"
        ),
        # Index for carbon benchmarks lookup
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_carbon_benchmark_crop_year ON carbon_carbonbenchmark(crop_type, year, usda_verified);",
            "DROP INDEX IF EXISTS idx_carbon_benchmark_crop_year;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_carbon_benchmark_industry_year ON carbon_carbonbenchmark(industry, year, crop_type);",
            "DROP INDEX IF EXISTS idx_carbon_benchmark_industry_year;"
        ),
    ] 