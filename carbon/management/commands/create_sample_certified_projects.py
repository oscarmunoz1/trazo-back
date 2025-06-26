from django.core.management.base import BaseCommand
from carbon.models import CarbonOffsetProject
from decimal import Decimal


class Command(BaseCommand):
    help = 'Create sample certified carbon offset projects for testing'

    def handle(self, *args, **options):
        # Clear existing sample projects
        CarbonOffsetProject.objects.filter(name__startswith='[SAMPLE]').delete()
        
        sample_projects = [
            {
                'name': '[SAMPLE] Amazon Rainforest Conservation',
                'description': 'Large-scale reforestation project in the Amazon Basin protecting 50,000 hectares of rainforest and supporting indigenous communities. Verified under VCS standard with permanent forest protection guarantees.',
                'project_type': 'Reforestation',
                'certification_standard': 'VCS (Verra)',
                'location': 'Amazon Basin, Brazil',
                'price_per_ton': Decimal('15.50'),
                'available_capacity': Decimal('25000.00')
            },
            {
                'name': '[SAMPLE] Midwest No-Till Carbon Sequestration',
                'description': 'Agricultural soil carbon sequestration through no-till farming practices across 10,000 acres of corn and soybean fields. Third-party verified using direct soil sampling.',
                'project_type': 'Soil Carbon',
                'certification_standard': 'Climate Action Reserve',
                'location': 'Iowa, USA',
                'price_per_ton': Decimal('22.00'),
                'available_capacity': Decimal('8500.00')
            },
            {
                'name': '[SAMPLE] Renewable Energy Wind Farm',
                'description': 'Clean energy generation from wind power displacing fossil fuel electricity. 150MW capacity with 25-year operational guarantee and grid-verified renewable energy certificates.',
                'project_type': 'Renewable Energy',
                'certification_standard': 'Gold Standard',
                'location': 'Texas, USA',
                'price_per_ton': Decimal('12.75'),
                'available_capacity': Decimal('45000.00')
            },
            {
                'name': '[SAMPLE] Methane Capture Dairy Farm',
                'description': 'Anaerobic digester system capturing methane from dairy operations and converting to renewable energy. Reduces methane emissions while generating clean electricity.',
                'project_type': 'Methane Reduction',
                'certification_standard': 'American Carbon Registry',
                'location': 'California, USA',
                'price_per_ton': Decimal('18.25'),
                'available_capacity': Decimal('3200.00')
            },
            {
                'name': '[SAMPLE] Grassland Restoration Project',
                'description': 'Native grassland restoration on former agricultural land with enhanced grazing management. Improves soil health, biodiversity, and carbon sequestration through rotational grazing.',
                'project_type': 'Grassland Management',
                'certification_standard': 'VCS (Verra)',
                'location': 'Montana, USA',
                'price_per_ton': Decimal('16.90'),
                'available_capacity': Decimal('12000.00')
            },
            {
                'name': '[SAMPLE] Improved Forest Management',
                'description': 'Sustainable forest management practices extending rotation periods and enhancing carbon storage in existing forests. Third-party verified with permanent conservation easements.',
                'project_type': 'Forest Management',
                'certification_standard': 'Climate Action Reserve',
                'location': 'Oregon, USA',
                'price_per_ton': Decimal('19.50'),
                'available_capacity': Decimal('18500.00')
            }
        ]
        
        created_count = 0
        for project_data in sample_projects:
            project, created = CarbonOffsetProject.objects.get_or_create(
                name=project_data['name'],
                defaults=project_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created: {project.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Already exists: {project.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully created {created_count} sample certified projects!'
            )
        )
        self.stdout.write(
            'You can now test the "Certified Projects" tab in the frontend.'
        ) 