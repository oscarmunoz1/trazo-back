# Generated manually to update carbon calculations with corrected emission factors

from django.db import migrations
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)


def update_emission_factors_forward(apps, schema_editor):
    """
    Update existing carbon entries with corrected USDA emission factors.
    This migration applies the research-corrected values that show significant
    underestimation in previous USDA factors.
    """
    CarbonEntry = apps.get_model('carbon', 'CarbonEntry')
    CarbonSource = apps.get_model('carbon', 'CarbonSource')
    
    # Correction factors based on research findings
    correction_factors = {
        'nitrogen': 1.88,    # 88% increase (5.86 → 11.0)
        'phosphorus': 6.25,  # 525% increase (0.20 → 1.25) 
        'potassium': 4.0,    # 300% increase (0.15 → 0.60)
    }
    
    # Find fertilizer-related carbon sources
    fertilizer_sources = CarbonSource.objects.filter(
        Q(name__icontains='Fertilizer') | 
        Q(name__icontains='Nitrogen') |
        Q(name__icontains='Phosphorus') |
        Q(name__icontains='Potassium')
    )
    
    if not fertilizer_sources.exists():
        logger.info("No fertilizer-related carbon sources found - skipping migration")
        return
    
    # Find entries to update (created before factor corrections)
    entries_to_update = CarbonEntry.objects.filter(
        source__in=fertilizer_sources,
        usda_factors_based=True,
        created_at__lt='2025-06-27'
    )
    
    total_entries = entries_to_update.count()
    logger.info(f"Updating {total_entries} carbon entries with corrected emission factors")
    
    updated_count = 0
    total_impact = 0.0
    
    for entry in entries_to_update:
        try:
            old_amount = float(entry.amount)
            
            # Determine nutrient type from source name for specific correction
            source_name = entry.source.name.lower()
            
            if 'nitrogen' in source_name or 'urea' in source_name:
                correction_factor = correction_factors['nitrogen']
            elif 'phosphorus' in source_name or 'phosphate' in source_name:
                correction_factor = correction_factors['phosphorus']
            elif 'potassium' in source_name or 'potash' in source_name:
                correction_factor = correction_factors['potassium']
            else:
                # Mixed fertilizer - apply weighted average correction
                correction_factor = (
                    correction_factors['nitrogen'] * 0.6 +
                    correction_factors['phosphorus'] * 0.2 +
                    correction_factors['potassium'] * 0.2
                )
            
            new_amount = old_amount * correction_factor
            impact = new_amount - old_amount
            
            # Update the entry
            entry.amount = new_amount
            entry.description = f"{entry.description} [MIGRATED: Corrected emission factors v3.0.0]"
            entry.data_source = "USDA Agricultural Research Service - Corrected Research Findings"
            entry.save(update_fields=['amount', 'description', 'data_source'])
            
            updated_count += 1
            total_impact += impact
            
            if updated_count % 100 == 0:
                logger.info(f"Updated {updated_count}/{total_entries} entries...")
                
        except Exception as e:
            logger.error(f"Error updating carbon entry {entry.id}: {e}")
            continue
    
    logger.info(f"Migration completed: {updated_count} entries updated, "
                f"total CO2e increase: {total_impact:.2f} kg")


def update_emission_factors_reverse(apps, schema_editor):
    """
    Reverse the emission factor updates by restoring original values.
    Note: This is approximate since we don't store the exact original values.
    """
    CarbonEntry = apps.get_model('carbon', 'CarbonEntry')
    
    # Reverse correction factors
    reverse_factors = {
        'nitrogen': 1.0 / 1.88,     # Reverse 88% increase
        'phosphorus': 1.0 / 6.25,   # Reverse 525% increase
        'potassium': 1.0 / 4.0,     # Reverse 300% increase
    }
    
    # Find entries that were updated by this migration
    entries_to_reverse = CarbonEntry.objects.filter(
        description__icontains='MIGRATED: Corrected emission factors v3.0.0'
    )
    
    total_entries = entries_to_reverse.count()
    logger.info(f"Reversing {total_entries} carbon entries to original emission factors")
    
    for entry in entries_to_reverse:
        try:
            old_amount = float(entry.amount)
            
            # Determine reversal factor from source name
            source_name = entry.source.name.lower()
            
            if 'nitrogen' in source_name or 'urea' in source_name:
                reverse_factor = reverse_factors['nitrogen']
            elif 'phosphorus' in source_name or 'phosphate' in source_name:
                reverse_factor = reverse_factors['phosphorus']
            elif 'potassium' in source_name or 'potash' in source_name:
                reverse_factor = reverse_factors['potassium']
            else:
                # Mixed fertilizer - apply weighted average reverse
                reverse_factor = (
                    reverse_factors['nitrogen'] * 0.6 +
                    reverse_factors['phosphorus'] * 0.2 +
                    reverse_factors['potassium'] * 0.2
                )
            
            new_amount = old_amount * reverse_factor
            
            # Restore the entry
            entry.amount = new_amount
            entry.description = entry.description.replace(
                ' [MIGRATED: Corrected emission factors v3.0.0]', ''
            )
            entry.data_source = "USDA Agricultural Research Service"
            entry.save(update_fields=['amount', 'description', 'data_source'])
            
        except Exception as e:
            logger.error(f"Error reversing carbon entry {entry.id}: {e}")
            continue
    
    logger.info(f"Reverse migration completed for {total_entries} entries")


class Migration(migrations.Migration):

    dependencies = [
        ('carbon', '0022_remove_community_verification_mvp'),
    ]

    operations = [
        migrations.RunPython(
            update_emission_factors_forward,
            update_emission_factors_reverse,
        ),
    ]