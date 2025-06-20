"""
Management command to migrate existing EventTemplate records to the new ProductionTemplate structure.

This command:
1. Creates default ProductionTemplate records for each CropType
2. Migrates existing EventTemplate records to link to these ProductionTemplates
3. Ensures data integrity during the transition
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from carbon.models import CropType, ProductionTemplate, EventTemplate


class Command(BaseCommand):
    help = 'Migrate existing EventTemplate records to new ProductionTemplate structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        try:
            with transaction.atomic():
                # Step 1: Create default ProductionTemplate for each CropType
                self.create_default_production_templates(dry_run)
                
                # Step 2: Migrate existing EventTemplate records
                self.migrate_event_templates(dry_run)
                
                if dry_run:
                    # Rollback the transaction in dry-run mode
                    raise CommandError("Dry run completed - rolling back changes")
                    
        except CommandError:
            if not dry_run:
                raise
            else:
                self.stdout.write(self.style.SUCCESS('Dry run completed successfully'))

    def create_default_production_templates(self, dry_run=False):
        """Create default 'Conventional' ProductionTemplate for each CropType"""
        
        crop_types = CropType.objects.all()
        self.stdout.write(f'Found {crop_types.count()} crop types to process')
        
        for crop_type in crop_types:
            template_name = f"{crop_type.name} - Conventional"
            template_slug = f"{crop_type.slug}_conventional"
            
            # Check if template already exists
            existing_template = ProductionTemplate.objects.filter(
                crop_type=crop_type, 
                slug=template_slug
            ).first()
            
            if existing_template:
                self.stdout.write(f'  ✓ ProductionTemplate already exists: {template_name}')
                continue
            
            if not dry_run:
                production_template = ProductionTemplate.objects.create(
                    crop_type=crop_type,
                    name=template_name,
                    slug=template_slug,
                    farming_approach='conventional',
                    description=f'Traditional {crop_type.name.lower()} production practices using conventional methods.',
                    complexity_level='intermediate',
                    estimated_setup_time=5,
                    projected_emissions_reduction=0.0,  # Baseline conventional approach
                    projected_cost_change=0.0,
                    projected_yield_impact=0.0,
                    premium_pricing_potential='0%',
                    market_demand='high',
                    certification_requirements=[],
                    compliance_notes='Standard USDA agricultural practices',
                    is_active=True,
                    is_recommended=True,  # Default template is recommended
                    usda_reviewed=True,
                    usda_compliant=True,
                )
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created ProductionTemplate: {template_name}'))
            else:
                self.stdout.write(f'  → Would create ProductionTemplate: {template_name}')

    def migrate_event_templates(self, dry_run=False):
        """Migrate existing EventTemplate records to link to ProductionTemplates"""
        
        # Get all EventTemplate records that still have crop_type but no production_template
        event_templates = EventTemplate.objects.filter(
            crop_type__isnull=False,
            production_template__isnull=True
        )
        
        self.stdout.write(f'Found {event_templates.count()} EventTemplate records to migrate')
        
        migrated_count = 0
        for event_template in event_templates:
            crop_type = event_template.crop_type
            
            # Find the corresponding ProductionTemplate
            production_template = ProductionTemplate.objects.filter(
                crop_type=crop_type,
                farming_approach='conventional'
            ).first()
            
            if not production_template:
                self.stdout.write(
                    self.style.ERROR(f'  ✗ No ProductionTemplate found for {crop_type.name}')
                )
                continue
            
            if not dry_run:
                event_template.production_template = production_template
                event_template.save(update_fields=['production_template'])
                migrated_count += 1
                self.stdout.write(f'  ✓ Migrated: {event_template.name} → {production_template.name}')
            else:
                migrated_count += 1
                self.stdout.write(f'  → Would migrate: {event_template.name} → {production_template.name}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Migration completed: {migrated_count} EventTemplate records processed')
        )

    def validate_migration(self):
        """Validate the migration results"""
        
        # Check that all EventTemplates now have production_template
        orphaned_events = EventTemplate.objects.filter(production_template__isnull=True)
        if orphaned_events.exists():
            self.stdout.write(
                self.style.ERROR(f'Found {orphaned_events.count()} EventTemplates without ProductionTemplate')
            )
            return False
        
        # Check that all ProductionTemplates have at least one EventTemplate
        empty_templates = ProductionTemplate.objects.filter(event_templates__isnull=True)
        if empty_templates.exists():
            self.stdout.write(
                self.style.WARNING(f'Found {empty_templates.count()} ProductionTemplates without EventTemplates')
            )
        
        self.stdout.write(self.style.SUCCESS('Migration validation completed'))
        return True 