from django.core.management.base import BaseCommand
from carbon.models import SustainabilityBadge
import os
from django.core.files import File


class Command(BaseCommand):
    help = 'Seeds default sustainability badges'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting badge seeding process...'))
        
        # Create default badges if they don't exist
        badges = [
            {
                'name': 'Carbon Neutral',
                'description': 'This farm or production has achieved carbon neutrality by balancing carbon emissions with an equivalent amount of carbon offsets.',
                'minimum_score': 50,
                'is_automatic': True,
                'criteria': {'net_footprint': 0},
                'icon_filename': 'carbon-neutral.png'
            },
            {
                'name': 'Carbon Negative',
                'description': 'This farm or production has achieved carbon negativity by offsetting more carbon than it emits.',
                'minimum_score': 80,
                'is_automatic': True,
                'criteria': {'net_footprint': -10},
                'icon_filename': 'carbon-negative.png'
            },
            {
                'name': 'Gold Tier',
                'description': 'This farm or production has a carbon score in the top 10% of all producers in its industry.',
                'minimum_score': 90,
                'is_automatic': True,
                'criteria': {'carbon_score': 90},
                'icon_filename': 'gold-tier.png'
            },
            {
                'name': 'Silver Tier',
                'description': 'This farm or production has a carbon score in the top 25% of all producers in its industry.',
                'minimum_score': 75,
                'is_automatic': True,
                'criteria': {'carbon_score': 75},
                'icon_filename': 'silver-tier.png'
            },
            {
                'name': 'Offset Champion',
                'description': 'This farm or production offsets at least 50% of its carbon emissions.',
                'minimum_score': 40,
                'is_automatic': True,
                'criteria': {'offset_ratio': 0.5},
                'icon_filename': 'offset-champion.png'
            },
            {
                'name': 'USDA SOE Verified',
                'description': 'This farm or production has been verified under the USDA Strengthening Organic Enforcement rule.',
                'minimum_score': 0,
                'is_automatic': False,
                'criteria': {'usda_soe_verified': True},
                'icon_filename': 'usda-verified.png'
            },
            {
                'name': 'Sustainable Water Use',
                'description': 'This farm or production employs sustainable water management practices.',
                'minimum_score': 30,
                'is_automatic': False,
                'criteria': {'sustainable_water': True},
                'icon_filename': 'water-sustainable.png'
            },
            {
                'name': 'Low Emission Transport',
                'description': 'This farm or production uses low-emission transportation methods.',
                'minimum_score': 30,
                'is_automatic': False,
                'criteria': {'low_emission_transport': True},
                'icon_filename': 'low-emission-transport.png'
            },
            {
                'name': 'Renewable Energy',
                'description': 'This farm or production uses renewable energy sources for at least 50% of its energy needs.',
                'minimum_score': 40,
                'is_automatic': False,
                'criteria': {'renewable_energy': 0.5},
                'icon_filename': 'renewable-energy.png'
            },
            {
                'name': 'Cover Cropping',
                'description': 'This farm or production uses cover cropping to improve soil health and carbon sequestration.',
                'minimum_score': 30,
                'is_automatic': False,
                'criteria': {'cover_cropping': True},
                'icon_filename': 'cover-cropping.png'
            },
        ]
        
        # Create or update badges
        badges_created = 0
        badges_updated = 0
        
        for badge_data in badges:
            icon_filename = badge_data.pop('icon_filename', None)
            badge, created = SustainabilityBadge.objects.update_or_create(
                name=badge_data['name'],
                defaults=badge_data
            )
            
            if created:
                badges_created += 1
                self.stdout.write(self.style.SUCCESS(f'Created badge: {badge.name}'))
            else:
                badges_updated += 1
                self.stdout.write(self.style.SUCCESS(f'Updated badge: {badge.name}'))
                
            # Add icon if available
            # In a real implementation, you would need to have these icon files in a 
            # specific directory. Since we don't have them here, this is just placeholder code.
            if icon_filename and False:  # Set to True if you have icon files
                icons_dir = os.path.join('path', 'to', 'icons')
                icon_path = os.path.join(icons_dir, icon_filename)
                if os.path.exists(icon_path):
                    with open(icon_path, 'rb') as f:
                        badge.icon.save(icon_filename, File(f), save=True)
        
        self.stdout.write(self.style.SUCCESS(
            f'Badge seeding complete. Created: {badges_created}, Updated: {badges_updated}'
        )) 