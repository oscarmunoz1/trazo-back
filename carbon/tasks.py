from celery import shared_task
from django.db.models import Sum, Avg
from .models import CarbonEntry, CarbonReport, CarbonBenchmark, SustainabilityBadge, CarbonAuditLog
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()

@shared_task
def update_carbon_summaries():
    """
    Nightly task to update carbon summaries for all establishments and productions.
    """
    current_year = timezone.now().year
    # Placeholder logic for updating summaries
    # This will be expanded with detailed aggregation logic
    print(f'Updating carbon summaries for year {current_year}')
    return f'Updated summaries for {current_year}'

@shared_task
def generate_carbon_report(report_id):
    """
    Task to generate a carbon report in the background.
    """
    try:
        report = CarbonReport.objects.get(id=report_id)
        # Placeholder for report generation logic (e.g., PDF creation)
        print(f'Generating report {report_id} for {report.year}')
        # Update report status or save generated file path
        report.document = 'path/to/generated/report.pdf'  # Placeholder
        report.save()
        return f'Report {report_id} generated'
    except CarbonReport.DoesNotExist:
        return f'Report {report_id} not found'

@shared_task
def generate_nightly_reports():
    """Generate carbon reports for all establishments and productions."""
    yesterday = timezone.now().date() - timedelta(days=1)
    
    # Generate establishment reports
    establishments = Establishment.objects.all()
    for establishment in establishments:
        entries = CarbonEntry.objects.filter(
            establishment=establishment,
            timestamp__date=yesterday
        )
        
        total_emissions = entries.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        total_offsets = entries.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        net_footprint = total_emissions - total_offsets
        
        # Calculate carbon score
        industry_average = CarbonBenchmark.objects.filter(
            year=yesterday.year
        ).aggregate(Avg('average_emissions'))['average_emissions__avg'] or 0
        
        carbon_score = 100
        if industry_average > 0:
            ratio = net_footprint / industry_average
            carbon_score = max(1, min(100, int(100 * (1 - ratio))))
        
        # Create report
        CarbonReport.objects.create(
            establishment=establishment,
            period_start=yesterday,
            period_end=yesterday,
            total_emissions=total_emissions,
            total_offsets=total_offsets,
            net_footprint=net_footprint,
            carbon_score=carbon_score,
            generated_at=timezone.now()
        )

@shared_task
def award_sustainability_badges():
    """Award sustainability badges based on carbon performance."""
    # Get all establishments with carbon entries
    establishments = Establishment.objects.filter(
        carbonentry__isnull=False
    ).distinct()
    
    # Also get all productions with carbon entries
    productions = History.objects.filter(
        carbonentry__isnull=False
    ).distinct()
    
    # Get all automatic badges
    automatic_badges = SustainabilityBadge.objects.filter(is_automatic=True)
    
    # Process establishments
    for establishment in establishments:
        # Get latest year with entries
        latest_year = CarbonEntry.objects.filter(
            establishment=establishment
        ).order_by('-year').values_list('year', flat=True).first()
        
        if not latest_year:
            continue
        
        # Calculate carbon score for this establishment
        entries = CarbonEntry.objects.filter(establishment=establishment, year=latest_year)
        total_emissions = entries.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        total_offsets = entries.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        
        # Get industry benchmark if available
        industry_benchmark = 0
        if hasattr(establishment, 'industry'):
            benchmark = CarbonBenchmark.objects.filter(
                industry=establishment.industry,
                year=latest_year
            ).first()
            if benchmark:
                industry_benchmark = benchmark.average_emissions
        
        # Calculate carbon score
        carbon_score = CarbonEntry.calculate_carbon_score(
            total_emissions=total_emissions,
            total_offsets=total_offsets,
            industry_benchmark=industry_benchmark
        )
        
        # Award badges based on score
        for badge in automatic_badges:
            if carbon_score >= badge.minimum_score:
                badge.establishments.add(establishment)
    
    # Process productions
    for production in productions:
        # Calculate carbon score for this production
        entries = CarbonEntry.objects.filter(production=production)
        total_emissions = entries.filter(type='emission').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        total_offsets = entries.filter(type='offset').aggregate(Sum('co2e_amount'))['co2e_amount__sum'] or 0
        
        # Get industry benchmark if available
        industry_benchmark = 0
        if hasattr(production.establishment, 'industry'):
            benchmark = CarbonBenchmark.objects.filter(
                industry=production.establishment.industry,
                year=production.year
            ).first()
            if benchmark:
                industry_benchmark = benchmark.average_emissions
        
        # Calculate carbon score
        carbon_score = CarbonEntry.calculate_carbon_score(
            total_emissions=total_emissions,
            total_offsets=total_offsets,
            industry_benchmark=industry_benchmark
        )
        
        # Award badges based on score
        for badge in automatic_badges:
            if carbon_score >= badge.minimum_score:
                badge.productions.add(production)

@shared_task
def cleanup_old_audit_logs():
    """Clean up audit logs older than 1 year."""
    one_year_ago = timezone.now() - timedelta(days=365)
    CarbonAuditLog.objects.filter(timestamp__lt=one_year_ago).delete()

@shared_task
def update_industry_benchmarks():
    """Update industry benchmarks based on recent data."""
    current_year = timezone.now().year
    
    # Calculate average emissions by industry
    benchmarks = CarbonEntry.objects.filter(
        year=current_year,
        type='emission'
    ).values('establishment__industry').annotate(
        average_emissions=Avg('co2e_amount')
    )
    
    # Update or create benchmarks
    for benchmark in benchmarks:
        CarbonBenchmark.objects.update_or_create(
            year=current_year,
            industry=benchmark['establishment__industry'],
            defaults={
                'average_emissions': benchmark['average_emissions'],
                'updated_at': timezone.now()
            }
        ) 