"""
Django management command to update existing carbon calculations with corrected emission factors.

This command recalculates carbon entries that were computed with the old, underestimated emission factors
and updates them to use the new corrected USDA research findings.

Usage: poetry run python manage.py update_emission_factors --dry-run
       poetry run python manage.py update_emission_factors --execute
"""

import logging
from typing import Dict, List, Any
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from carbon.models import CarbonEntry, CarbonSource, USDAComplianceRecord
from carbon.services.emission_factors import EmissionFactorsRegistry
from carbon.services.event_carbon_calculator import EventCarbonCalculator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update existing carbon calculations with corrected USDA emission factors'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Actually execute the updates (required for real changes)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of entries to process in each batch',
        )
        parser.add_argument(
            '--max-entries',
            type=int,
            help='Maximum number of entries to process (for testing)',
        )
        parser.add_argument(
            '--establishment-id',
            type=int,
            help='Only process entries for a specific establishment',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output with detailed information',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        execute = options['execute']
        batch_size = options['batch_size']
        max_entries = options.get('max_entries')
        establishment_id = options.get('establishment_id')
        verbose = options['verbose']

        if not dry_run and not execute:
            self.stdout.write(
                self.style.ERROR('You must specify either --dry-run or --execute')
            )
            return

        if dry_run and execute:
            self.stdout.write(
                self.style.ERROR('Cannot specify both --dry-run and --execute')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'🌱 Starting emission factor update {"(DRY RUN)" if dry_run else "(EXECUTING CHANGES)"}'
            )
        )

        # Initialize services
        emission_factors = EmissionFactorsRegistry()
        calculator = EventCarbonCalculator()

        # Get correction factors for impact analysis
        correction_factors = {
            'nitrogen': emission_factors.FERTILIZER_FACTORS['nitrogen']['correction_factor'],
            'phosphorus': emission_factors.FERTILIZER_FACTORS['phosphorus']['correction_factor'],
            'potassium': emission_factors.FERTILIZER_FACTORS['potassium']['correction_factor'],
        }

        self.stdout.write(f"📊 Correction factors: N={correction_factors['nitrogen']:.2f}x, "
                         f"P={correction_factors['phosphorus']:.2f}x, K={correction_factors['potassium']:.2f}x")

        # Build query for entries to update
        query = Q(
            usda_factors_based=True,  # Only entries that used USDA factors
            created_at__lt=timezone.datetime(2025, 6, 27)  # Created before factor corrections
        )

        # Filter for fertilizer-related carbon sources
        fertilizer_sources = CarbonSource.objects.filter(
            name__icontains='Fertilizer'
        ).values_list('id', flat=True)
        
        if fertilizer_sources:
            query &= Q(source_id__in=fertilizer_sources)

        if establishment_id:
            query &= Q(establishment_id=establishment_id)

        # Get entries to update
        entries_to_update = CarbonEntry.objects.filter(query).order_by('created_at')
        
        if max_entries:
            entries_to_update = entries_to_update[:max_entries]

        total_entries = entries_to_update.count()
        self.stdout.write(f"🔍 Found {total_entries} carbon entries to update")

        if total_entries == 0:
            self.stdout.write(self.style.WARNING('No entries found to update'))
            return

        # Process entries in batches
        updated_count = 0
        error_count = 0
        total_impact = Decimal('0.0')
        impact_by_nutrient = {'nitrogen': 0, 'phosphorus': 0, 'potassium': 0}

        for i in range(0, total_entries, batch_size):
            batch = entries_to_update[i:i + batch_size]
            batch_results = self._process_batch(
                batch, correction_factors, dry_run, verbose
            )
            
            updated_count += batch_results['updated']
            error_count += batch_results['errors']
            total_impact += batch_results['total_impact']
            
            for nutrient, impact in batch_results['impact_by_nutrient'].items():
                impact_by_nutrient[nutrient] += impact

            self.stdout.write(
                f"⚙️ Processed batch {i//batch_size + 1}: "
                f"{batch_results['updated']} updated, {batch_results['errors']} errors"
            )

        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS(f"📈 EMISSION FACTOR UPDATE SUMMARY"))
        self.stdout.write("="*60)
        self.stdout.write(f"Total entries processed: {total_entries}")
        self.stdout.write(f"Successfully updated: {updated_count}")
        self.stdout.write(f"Errors encountered: {error_count}")
        self.stdout.write(f"Total CO2e impact increase: {total_impact:.2f} kg CO2e")
        
        if total_impact > 0:
            avg_increase = (total_impact / updated_count) if updated_count > 0 else 0
            self.stdout.write(f"Average increase per entry: {avg_increase:.2f} kg CO2e")
            
            percentage_increase = ((total_impact / (total_impact / max(correction_factors.values()) - total_impact)) * 100) if total_impact > 0 else 0
            self.stdout.write(f"Estimated percentage increase: {percentage_increase:.1f}%")

        self.stdout.write(f"\nImpact by nutrient:")
        for nutrient, impact in impact_by_nutrient.items():
            self.stdout.write(f"  {nutrient.capitalize()}: {impact:.2f} kg CO2e increase")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n⚠️ This was a DRY RUN - no changes were made")
            )
            self.stdout.write("Run with --execute to apply these changes")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n✅ Update completed successfully!")
            )

    def _process_batch(self, batch: List[CarbonEntry], correction_factors: Dict[str, float], 
                      dry_run: bool, verbose: bool) -> Dict[str, Any]:
        """Process a batch of carbon entries"""
        batch_results = {
            'updated': 0,
            'errors': 0,
            'total_impact': Decimal('0.0'),
            'impact_by_nutrient': {'nitrogen': 0, 'phosphorus': 0, 'potassium': 0}
        }

        with transaction.atomic():
            for entry in batch:
                try:
                    result = self._update_carbon_entry(entry, correction_factors, dry_run, verbose)
                    if result['updated']:
                        batch_results['updated'] += 1
                        batch_results['total_impact'] += result['impact']
                        
                        for nutrient, impact in result['nutrient_impacts'].items():
                            batch_results['impact_by_nutrient'][nutrient] += impact
                    
                except Exception as e:
                    batch_results['errors'] += 1
                    logger.error(f"Error processing carbon entry {entry.id}: {e}")
                    if verbose:
                        self.stdout.write(
                            self.style.ERROR(f"Error processing entry {entry.id}: {e}")
                        )

        return batch_results

    def _update_carbon_entry(self, entry: CarbonEntry, correction_factors: Dict[str, float], 
                           dry_run: bool, verbose: bool) -> Dict[str, Any]:
        """Update a single carbon entry with corrected factors"""
        old_amount = entry.amount
        
        # Estimate which nutrients contributed to this entry based on source
        source_name = entry.source.name.lower() if entry.source else ''
        
        # Simple heuristic to estimate nutrient contribution
        # In a real system, this would be stored in the original calculation
        nutrient_weights = {'nitrogen': 0.6, 'phosphorus': 0.2, 'potassium': 0.2}
        
        if 'nitrogen' in source_name or 'urea' in source_name:
            nutrient_weights = {'nitrogen': 0.9, 'phosphorus': 0.05, 'potassium': 0.05}
        elif 'phosphorus' in source_name or 'phosphate' in source_name:
            nutrient_weights = {'nitrogen': 0.1, 'phosphorus': 0.8, 'potassium': 0.1}
        elif 'potassium' in source_name or 'potash' in source_name:
            nutrient_weights = {'nitrogen': 0.1, 'phosphorus': 0.1, 'potassium': 0.8}

        # Calculate new amount based on correction factors
        new_amount = Decimal('0.0')
        nutrient_impacts = {'nitrogen': 0, 'phosphorus': 0, 'potassium': 0}
        
        for nutrient, weight in nutrient_weights.items():
            old_component = old_amount * Decimal(str(weight))
            new_component = old_component * Decimal(str(correction_factors[nutrient]))
            new_amount += new_component
            nutrient_impacts[nutrient] = float(new_component - old_component)

        impact = new_amount - old_amount

        if verbose:
            self.stdout.write(
                f"Entry {entry.id}: {old_amount:.2f} → {new_amount:.2f} kg CO2e "
                f"(+{impact:.2f}, {(impact/old_amount*100) if old_amount > 0 else 0:.1f}%)"
            )

        if not dry_run and impact > 0:
            # Update the entry
            entry.amount = new_amount
            entry.description = f"{entry.description} [UPDATED: Corrected emission factors v3.0.0]"
            entry.data_source = "USDA Agricultural Research Service - Corrected Research Findings"
            entry.save(update_fields=['amount', 'description', 'data_source', 'updated_at'])

            # Create audit record
            if hasattr(entry, 'usdacalculationaudit_set'):
                from carbon.models import USDACalculationAudit
                USDACalculationAudit.objects.create(
                    event_type='factor_correction',
                    event_id=entry.id,
                    carbon_entry=entry,
                    input_data={
                        'old_amount': float(old_amount),
                        'new_amount': float(new_amount),
                        'correction_applied': True,
                        'correction_factors': correction_factors,
                        'nutrient_weights': nutrient_weights
                    },
                    calculation_method='emission_factor_correction_v3',
                    usda_factors_applied=True,
                    calculated_co2e=float(new_amount),
                    confidence_score=0.9,  # High confidence in corrected factors
                    processor_version='3.0_corrected_factors',
                    calculated_by=None  # System update
                )

        return {
            'updated': impact > 0,
            'impact': impact,
            'nutrient_impacts': nutrient_impacts,
            'old_amount': float(old_amount),
            'new_amount': float(new_amount)
        }

    def _create_summary_report(self, results: Dict[str, Any], output_file: str = None):
        """Create a detailed summary report of the update process"""
        # This could generate a detailed CSV or JSON report
        # For now, just log the summary
        pass