import json
from django.core.management.base import BaseCommand
from django.db import transaction
from history.models import History

class Command(BaseCommand):
    help = 'Pre-cache member data for existing productions to improve dashboard performance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--parcel-id',
            type=int,
            help='Cache members for a specific parcel only',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of productions to process in each batch',
        )

    def handle(self, *args, **options):
        parcel_id = options.get('parcel_id')
        batch_size = options.get('batch_size')

        # Build queryset
        queryset = History.objects.all()
        if parcel_id:
            queryset = queryset.filter(parcel_id=parcel_id)
            self.stdout.write(f'Processing productions for parcel {parcel_id}...')
        else:
            self.stdout.write('Processing all productions...')

        total_count = queryset.count()
        self.stdout.write(f'Found {total_count} productions to process')

        processed = 0
        updated = 0

        # Process in batches
        for start in range(0, total_count, batch_size):
            end = min(start + batch_size, total_count)
            batch = queryset[start:end]

            with transaction.atomic():
                for history in batch:
                    try:
                        # Get unique members from all events
                        members_dict = {}
                        
                        # Get members from all event types WITHOUT triggering carbon calculations
                        # Use direct model queries instead of serializers to avoid USDA API calls
                        from history.models import (
                            WeatherEvent, ChemicalEvent, ProductionEvent, 
                            GeneralEvent, EquipmentEvent, SoilManagementEvent, PestManagementEvent
                        )
                        
                        # Query each event type directly to get created_by users
                        event_querysets = [
                            history.history_weatherevent_events.select_related('created_by').only('created_by'),
                            history.history_chemicalevent_events.select_related('created_by').only('created_by'),
                            history.history_productionevent_events.select_related('created_by').only('created_by'),
                            history.history_generalevent_events.select_related('created_by').only('created_by'),
                            history.history_equipmentevent_events.select_related('created_by').only('created_by'),
                            history.history_soilmanagementevent_events.select_related('created_by').only('created_by'),
                            history.history_pestmanagementevent_events.select_related('created_by').only('created_by'),
                        ]
                        
                        # Collect unique users from all event types
                        for queryset in event_querysets:
                            for event in queryset:
                                if hasattr(event, 'created_by') and event.created_by:
                                    user = event.created_by
                                    members_dict[user.id] = {
                                        'id': user.id,
                                        'first_name': user.first_name,
                                        'last_name': user.last_name,
                                        'image': user.image.url if user.image else None
                                    }

                        # Convert to list and limit to 5 members
                        cached_members = list(members_dict.values())[:5]

                        # Update extra_data with cached members
                        if history.extra_data is None:
                            history.extra_data = {}
                        
                        history.extra_data['cached_members'] = cached_members
                        history.save(update_fields=['extra_data'])
                        
                        updated += 1
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Error processing production {history.id}: {str(e)}'
                            )
                        )

                    processed += 1

            # Progress update
            self.stdout.write(f'Processed {processed}/{total_count} productions...')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully cached member data for {updated} productions'
            )
        ) 