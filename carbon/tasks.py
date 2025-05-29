"""
Celery tasks for carbon tracking and IoT automation.

This module contains background tasks for:
- Weather monitoring and alerts
- IoT data processing
- Carbon calculation automation
- Report generation
"""

from celery import shared_task
from django.db.models import Sum, Avg
from .models import CarbonEntry, CarbonReport, CarbonBenchmark, SustainabilityBadge, CarbonAuditLog, IoTDevice, IoTDataPoint, Establishment
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.conf import settings
import logging
from .services.weather_api import WeatherService, get_weather_service
from .services.john_deere_api import get_john_deere_api
from company.models import Establishment

User = get_user_model()
logger = logging.getLogger(__name__)

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

@shared_task
def monitor_weather_conditions():
    """
    Monitor weather conditions for all establishments and create alerts when needed.
    
    This task runs every hour to check weather conditions for all establishments
    that have weather monitoring enabled and creates appropriate alerts and
    recommendations.
    """
    logger.info("Starting weather monitoring task")
    
    try:
        weather_service = get_weather_service()
        establishments_processed = 0
        alerts_created = 0
        
        # Get all establishments with location data
        establishments = Establishment.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ).exclude(
            latitude=0,
            longitude=0
        )
        
        logger.info(f"Monitoring weather for {establishments.count()} establishments")
        
        for establishment in establishments:
            try:
                # Get current weather conditions
                weather_data = weather_service.get_current_conditions(
                    float(establishment.latitude),
                    float(establishment.longitude)
                )
                
                if not weather_data:
                    logger.warning(f"No weather data for establishment {establishment.id}")
                    continue
                
                # Check if weather conditions warrant an alert
                should_alert = weather_service.should_trigger_alert(weather_data)
                
                if should_alert:
                    # Generate agricultural recommendations
                    recommendations = weather_service.generate_agricultural_recommendations(
                        weather_data,
                        getattr(establishment, 'establishment_type', 'general')
                    )
                    
                    # Create weather alert event
                    alert_created = create_weather_alert_event.delay(
                        establishment.id,
                        weather_data,
                        recommendations
                    )
                    
                    if alert_created:
                        alerts_created += 1
                        logger.info(f"Weather alert created for establishment {establishment.id}")
                
                establishments_processed += 1
                
            except Exception as e:
                logger.error(f"Error processing weather for establishment {establishment.id}: {e}")
                continue
        
        logger.info(f"Weather monitoring completed: {establishments_processed} processed, {alerts_created} alerts created")
        
        return {
            'status': 'success',
            'establishments_processed': establishments_processed,
            'alerts_created': alerts_created,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Weather monitoring task failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }

@shared_task
def create_weather_alert_event(establishment_id, weather_data, recommendations):
    """
    Create a weather alert event for a specific establishment.
    
    Args:
        establishment_id: ID of the establishment
        weather_data: Current weather conditions
        recommendations: List of agricultural recommendations
    """
    try:
        establishment = Establishment.objects.get(id=establishment_id)
        
        # Get or create weather station device
        device, created = IoTDevice.objects.get_or_create(
            establishment=establishment,
            device_type='weather_station',
            defaults={
                'device_id': f'weather_station_{establishment_id}',
                'name': f'Weather Station - {establishment.name}',
                'status': 'online',
                'battery_level': 100,
                'last_seen': timezone.now()
            }
        )
        
        # Determine alert priority based on recommendations
        critical_count = len([r for r in recommendations if r.get('priority') == 'critical'])
        high_count = len([r for r in recommendations if r.get('priority') == 'high'])
        
        requires_approval = critical_count > 0 or high_count > 0
        confidence = 0.95 if not requires_approval else 0.85
        
        # Create weather data point
        data_point = IoTDataPoint.objects.create(
            device=device,
            timestamp=timezone.now(),
            data={
                'weather_conditions': weather_data,
                'recommendations': recommendations,
                'alert_type': 'automated_weather_monitoring',
                'source': 'weather_monitoring_task',
                'requires_approval': requires_approval,
                'critical_count': critical_count,
                'high_count': high_count
            },
            quality_score=0.95,  # High quality for official weather data
            processed=False
        )
        
        # Update device status
        device.update_status('online')
        device.increment_data_points()
        
        logger.info(f"Weather alert event created: {data_point.id} for establishment {establishment_id}")
        
        return {
            'status': 'success',
            'data_point_id': data_point.id,
            'device_id': device.id,
            'requires_approval': requires_approval,
            'confidence': confidence
        }
        
    except Establishment.DoesNotExist:
        logger.error(f"Establishment {establishment_id} not found")
        return {'status': 'error', 'error': 'Establishment not found'}
    except Exception as e:
        logger.error(f"Error creating weather alert event: {e}")
        return {'status': 'error', 'error': str(e)}

@shared_task
def sync_john_deere_devices():
    """
    Sync data from John Deere API for all connected devices.
    
    This task runs every 30 minutes to fetch the latest data from
    John Deere equipment and create appropriate IoT data points.
    """
    logger.info("Starting John Deere device sync task")
    
    try:
        john_deere_api = get_john_deere_api()
        if not john_deere_api:
            logger.warning("John Deere API not configured, skipping sync")
            return {'status': 'skipped', 'reason': 'API not configured'}
        
        devices_synced = 0
        data_points_created = 0
        
        # Get all IoT devices with John Deere machine IDs
        devices = IoTDevice.objects.filter(
            john_deere_machine_id__isnull=False,
            api_connection_status='connected'
        ).exclude(john_deere_machine_id='')
        
        logger.info(f"Syncing {devices.count()} John Deere devices")
        
        for device in devices:
            try:
                # Get machine data from John Deere API
                machine_data = john_deere_api.get_machine_fuel_data(device.john_deere_machine_id)
                
                if machine_data:
                    # Create IoT data point
                    data_point = IoTDataPoint.objects.create(
                        device=device,
                        timestamp=timezone.now(),
                        data={
                            'fuel_consumption': machine_data,
                            'source': 'john_deere_api_sync',
                            'machine_id': device.john_deere_machine_id,
                            'sync_type': 'scheduled'
                        },
                        quality_score=0.95,
                        processed=False
                    )
                    
                    data_points_created += 1
                    
                    # Update device status
                    device.last_api_sync = timezone.now()
                    device.api_connection_status = 'connected'
                    device.update_status('online')
                    device.increment_data_points()
                    device.save()
                    
                    logger.info(f"Synced data for device {device.id}: {data_point.id}")
                
                devices_synced += 1
                
            except Exception as e:
                logger.error(f"Error syncing device {device.id}: {e}")
                
                # Update device error status
                device.api_connection_status = 'error'
                device.api_error_message = str(e)
                device.save()
                
                continue
        
        logger.info(f"John Deere sync completed: {devices_synced} devices, {data_points_created} data points")
        
        return {
            'status': 'success',
            'devices_synced': devices_synced,
            'data_points_created': data_points_created,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"John Deere sync task failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }

@shared_task
def process_pending_iot_data():
    """
    Process pending IoT data points and create carbon entries where appropriate.
    
    This task runs every 15 minutes to process unprocessed IoT data points
    through the unified workflow.
    """
    logger.info("Starting IoT data processing task")
    
    try:
        # Get unprocessed data points
        pending_data_points = IoTDataPoint.objects.filter(
            processed=False,
            timestamp__gte=timezone.now() - timedelta(hours=24)  # Only process recent data
        ).order_by('timestamp')
        
        logger.info(f"Processing {pending_data_points.count()} pending data points")
        
        processed_count = 0
        auto_approved_count = 0
        manual_approval_count = 0
        
        for data_point in pending_data_points:
            try:
                # Determine confidence score based on data quality and type
                confidence = calculate_data_point_confidence(data_point)
                
                if confidence > 0.9:
                    # High confidence - auto-approve and create carbon entry if applicable
                    if should_create_carbon_entry(data_point):
                        carbon_entry = create_carbon_entry_from_data_point(data_point)
                        if carbon_entry:
                            data_point.carbon_entry = carbon_entry
                            auto_approved_count += 1
                    
                    data_point.processed = True
                    data_point.save()
                    
                elif confidence > 0.7:
                    # Medium confidence - mark for manual approval
                    # Data point remains unprocessed for manual review
                    manual_approval_count += 1
                    
                else:
                    # Low confidence - mark as processed but flag for review
                    data_point.processed = True
                    data_point.anomaly_detected = True
                    data_point.save()
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing data point {data_point.id}: {e}")
                continue
        
        logger.info(f"IoT data processing completed: {processed_count} processed, {auto_approved_count} auto-approved, {manual_approval_count} pending manual approval")
        
        return {
            'status': 'success',
            'processed_count': processed_count,
            'auto_approved_count': auto_approved_count,
            'manual_approval_count': manual_approval_count,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"IoT data processing task failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }

def calculate_data_point_confidence(data_point):
    """
    Calculate confidence score for an IoT data point.
    
    Args:
        data_point: IoTDataPoint instance
        
    Returns:
        float: Confidence score (0.0-1.0)
    """
    base_confidence = data_point.quality_score
    
    # Adjust based on device status
    if data_point.device.status == 'online':
        base_confidence += 0.1
    elif data_point.device.status == 'offline':
        base_confidence -= 0.2
    
    # Adjust based on data recency
    age_hours = (timezone.now() - data_point.timestamp).total_seconds() / 3600
    if age_hours < 1:
        base_confidence += 0.05
    elif age_hours > 24:
        base_confidence -= 0.1
    
    # Adjust based on device type
    if data_point.device.device_type in ['fuel_sensor', 'weather_station']:
        base_confidence += 0.05  # Higher confidence for reliable sensor types
    
    return min(max(base_confidence, 0.0), 1.0)  # Clamp to 0.0-1.0

def should_create_carbon_entry(data_point):
    """
    Determine if a data point should create a carbon entry.
    
    Args:
        data_point: IoTDataPoint instance
        
    Returns:
        bool: True if carbon entry should be created
    """
    data = data_point.data
    
    # Fuel consumption data should create carbon entries
    if 'fuel_consumption' in data:
        return True
    
    # Weather alerts typically don't create carbon entries directly
    if 'weather_conditions' in data:
        return False
    
    # Equipment usage data should create carbon entries
    if data_point.device.device_type == 'fuel_sensor':
        return True
    
    return False

def create_carbon_entry_from_data_point(data_point):
    """
    Create a carbon entry from an IoT data point.
    
    Args:
        data_point: IoTDataPoint instance
        
    Returns:
        CarbonEntry instance or None
    """
    try:
        data = data_point.data
        
        if 'fuel_consumption' in data:
            fuel_data = data['fuel_consumption']
            fuel_amount = fuel_data.get('fuel_used', 0)
            
            if fuel_amount > 0:
                # Calculate CO2e emissions (diesel: ~2.7 kg CO2e per liter)
                co2e_amount = fuel_amount * 2.7
                
                carbon_entry = CarbonEntry.objects.create(
                    establishment=data_point.device.establishment,
                    type='emission',
                    amount=co2e_amount,
                    co2e_amount=co2e_amount,
                    year=timezone.now().year,
                    description=f"Automated fuel consumption entry from {data_point.device.name}",
                    iot_device_id=data_point.device.device_id,
                    timestamp=data_point.timestamp
                )
                
                logger.info(f"Created carbon entry {carbon_entry.id} from data point {data_point.id}")
                return carbon_entry
        
        return None
        
    except Exception as e:
        logger.error(f"Error creating carbon entry from data point {data_point.id}: {e}")
        return None

@shared_task
def cleanup_old_iot_data():
    """
    Clean up old IoT data points to prevent database bloat.
    
    This task runs daily to remove IoT data points older than 90 days
    that have been processed and don't have associated carbon entries.
    """
    logger.info("Starting IoT data cleanup task")
    
    try:
        cutoff_date = timezone.now() - timedelta(days=90)
        
        # Delete old processed data points without carbon entries
        old_data_points = IoTDataPoint.objects.filter(
            timestamp__lt=cutoff_date,
            processed=True,
            carbon_entry__isnull=True
        )
        
        deleted_count = old_data_points.count()
        old_data_points.delete()
        
        logger.info(f"Cleaned up {deleted_count} old IoT data points")
        
        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat(),
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"IoT data cleanup task failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        } 