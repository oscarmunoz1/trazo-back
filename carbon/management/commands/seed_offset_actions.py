from django.core.management.base import BaseCommand
from carbon.models import CarbonOffsetAction

class Command(BaseCommand):
    help = 'Seeds CarbonOffsetAction entries for the compensation dropdown'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Creating offset actions...'))
        
        # Define offset actions
        offset_actions = [
            {
                'name': 'Reforestación',
                'description': 'Plantar árboles para compensar emisiones de carbono',
                'unit': 'árboles plantados',
                'verification_required': True,
                'cost_per_unit': 2.50,
            },
            {
                'name': 'Energía Renovable',
                'description': 'Inversión en proyectos de energía solar o eólica',
                'unit': 'kWh compensados',
                'verification_required': True,
                'cost_per_unit': 0.05,
            },
            {
                'name': 'Captura de Metano',
                'description': 'Captura de metano en vertederos o granjas',
                'unit': 'kg CH4 capturado',
                'verification_required': True,
                'cost_per_unit': 4.00,
            },
            {
                'name': 'Eficiencia Energética',
                'description': 'Proyectos de mejora de eficiencia energética',
                'unit': 'kWh ahorrados',
                'verification_required': False,
                'cost_per_unit': 0.10,
            },
            {
                'name': 'Compostaje',
                'description': 'Compostaje de residuos orgánicos',
                'unit': 'kg residuos compostados',
                'verification_required': False,
                'cost_per_unit': 0.20,
            },
            {
                'name': 'Créditos de Carbono',
                'description': 'Compra de créditos de carbono verificados',
                'unit': 'tCO₂e',
                'verification_required': True,
                'cost_per_unit': 15.00,
            },
        ]
        
        # Create the offset actions
        actions_created = 0
        actions_updated = 0
        
        for action_data in offset_actions:
            action, created = CarbonOffsetAction.objects.update_or_create(
                name=action_data['name'],
                defaults=action_data
            )
            
            if created:
                actions_created += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {action.name}'))
            else:
                actions_updated += 1
                self.stdout.write(self.style.SUCCESS(f'Updated: {action.name}'))
        
        self.stdout.write(self.style.SUCCESS(f'Created {actions_created} new offset actions'))
        self.stdout.write(self.style.SUCCESS(f'Updated {actions_updated} existing offset actions')) 