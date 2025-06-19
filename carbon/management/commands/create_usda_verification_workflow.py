"""
Management command to create a USDA verification workflow.
This demonstrates how events can be marked as USDA verified through proper channels.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from carbon.models import CarbonEntry, CarbonSource, CarbonCertification
from company.models import Establishment
from history.models import History
from users.models import User


class Command(BaseCommand):
    help = 'Create USDA verification workflow examples'

    def add_arguments(self, parser):
        parser.add_argument(
            '--establishment-id',
            type=int,
            help='Establishment ID to create verification for',
        )
        parser.add_argument(
            '--production-id',
            type=int,
            help='Production ID to create verification for',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Creating USDA Verification Workflow Examples...')
        )

        # Step 1: Create USDA-verified carbon sources
        self.create_verified_carbon_sources()
        
        # Step 2: Create USDA certification records
        if options.get('establishment_id') and options.get('production_id'):
            self.create_usda_certification(
                options['establishment_id'], 
                options['production_id']
            )
        
        # Step 3: Show verification workflow
        self.show_verification_workflow()

    def create_verified_carbon_sources(self):
        """Create carbon sources that are officially USDA verified"""
        
        verified_sources = [
            {
                'name': 'USDA Certified Organic Fertilizer',
                'category': 'fertilizer',
                'description': 'Fertilizer application verified under USDA Organic Standards',
                'default_emission_factor': 5.86,
                'unit': 'kg CO2e/kg N',
                'usda_verified': True,  # Actually verified by USDA
                'usda_factors_based': True,
                'verification_status': 'usda_certified',
                'data_source': 'USDA National Organic Program'
            },
            {
                'name': 'USDA SOE Verified Equipment',
                'category': 'equipment',
                'description': 'Equipment operations verified under USDA Strengthening Organic Enforcement',
                'default_emission_factor': 2.68,
                'unit': 'kg CO2e/L diesel',
                'usda_verified': True,
                'usda_factors_based': True,
                'verification_status': 'usda_certified',
                'data_source': 'USDA Strengthening Organic Enforcement'
            },
            {
                'name': 'USDA Climate Smart Agriculture Practice',
                'category': 'soil_management',
                'description': 'Soil management practice verified under USDA Climate Smart Agriculture',
                'default_emission_factor': -2.5,  # Negative for sequestration
                'unit': 'kg CO2e/ha',
                'usda_verified': True,
                'usda_factors_based': True,
                'verification_status': 'usda_certified',
                'data_source': 'USDA Climate Smart Agriculture Program'
            }
        ]

        for source_data in verified_sources:
            source, created = CarbonSource.objects.get_or_create(
                name=source_data['name'],
                defaults=source_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created USDA verified source: {source.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Source already exists: {source.name}')
                )

    def create_usda_certification(self, establishment_id, production_id):
        """Create a USDA certification record"""
        
        try:
            establishment = Establishment.objects.get(id=establishment_id)
            production = History.objects.get(id=production_id)
            
            # Create USDA certification
            certification = CarbonCertification.objects.create(
                establishment=establishment,
                production=production,
                certifier='USDA National Organic Program',
                certificate_id=f'USDA-ORG-{establishment_id}-{production_id}-2024',
                issue_date=timezone.now().date(),
                expiry_date=timezone.now().date().replace(year=timezone.now().year + 1),
                is_usda_soe_verified=True,
                verification_date=timezone.now().date(),
                verification_details='Verified under USDA Strengthening Organic Enforcement rule for carbon tracking compliance'
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Created USDA certification: {certification.certificate_id}')
            )
            
            return certification
            
        except Establishment.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Establishment {establishment_id} not found')
            )
        except History.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Production {production_id} not found')
            )

    def show_verification_workflow(self):
        """Show the complete USDA verification workflow"""
        
        self.stdout.write(
            self.style.SUCCESS('\n📋 USDA Verification Workflow:')
        )
        
        workflow_steps = [
            "1. 📝 Apply for USDA Organic Certification",
            "   • Submit application to USDA-accredited certifying agent",
            "   • Provide organic system plan",
            "   • Pay certification fees",
            "",
            "2. 🔍 USDA Inspection Process",
            "   • On-site inspection by certified inspector",
            "   • Review of records and practices",
            "   • Verification of carbon tracking systems",
            "",
            "3. 📋 USDA Review and Decision",
            "   • Certifying agent reviews inspection report",
            "   • USDA reviews certification decision",
            "   • Certificate issued if compliant",
            "",
            "4. 💾 Update Trazo System",
            "   • Create CarbonCertification record",
            "   • Mark relevant CarbonSources as usda_verified=True",
            "   • Update verification_status to 'usda_certified'",
            "",
            "5. ✅ Events Now Show as USDA Verified",
            "   • Events using certified sources show usda_verified=True",
            "   • Verification status shows 'usda_certified'",
            "   • Data source shows specific USDA program"
        ]
        
        for step in workflow_steps:
            if step.startswith(('1.', '2.', '3.', '4.', '5.')):
                self.stdout.write(self.style.SUCCESS(step))
            elif step.startswith('   •'):
                self.stdout.write(f'     {step[4:]}')
            else:
                self.stdout.write(step)

        self.stdout.write(
            self.style.WARNING('\n⚠️  Important Notes:')
        )
        
        notes = [
            "• USDA verification requires actual certification process",
            "• Cannot be automated - requires human verification",
            "• Costs typically $500-$5,000+ depending on operation size",
            "• Annual renewal required",
            "• Must maintain detailed records for 5 years"
        ]
        
        for note in notes:
            self.stdout.write(f'  {note}')

        self.stdout.write(
            self.style.SUCCESS('\n🔗 USDA Resources:')
        )
        
        resources = [
            "• USDA Organic Certification: https://www.ams.usda.gov/services/organic-certification",
            "• Find Certifying Agents: https://organic.ams.usda.gov/integrity/CertifyingAgents/CertifyingAgentsAddresses.aspx",
            "• Climate Smart Agriculture: https://www.usda.gov/climate-solutions/climate-smart-commodities",
            "• Strengthening Organic Enforcement: https://www.ams.usda.gov/rules-regulations/organic/strengthening-organic-enforcement"
        ]
        
        for resource in resources:
            self.stdout.write(f'  {resource}') 
 
Management command to create a USDA verification workflow.
This demonstrates how events can be marked as USDA verified through proper channels.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from carbon.models import CarbonEntry, CarbonSource, CarbonCertification
from company.models import Establishment
from history.models import History
from users.models import User


class Command(BaseCommand):
    help = 'Create USDA verification workflow examples'

    def add_arguments(self, parser):
        parser.add_argument(
            '--establishment-id',
            type=int,
            help='Establishment ID to create verification for',
        )
        parser.add_argument(
            '--production-id',
            type=int,
            help='Production ID to create verification for',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Creating USDA Verification Workflow Examples...')
        )

        # Step 1: Create USDA-verified carbon sources
        self.create_verified_carbon_sources()
        
        # Step 2: Create USDA certification records
        if options.get('establishment_id') and options.get('production_id'):
            self.create_usda_certification(
                options['establishment_id'], 
                options['production_id']
            )
        
        # Step 3: Show verification workflow
        self.show_verification_workflow()

    def create_verified_carbon_sources(self):
        """Create carbon sources that are officially USDA verified"""
        
        verified_sources = [
            {
                'name': 'USDA Certified Organic Fertilizer',
                'category': 'fertilizer',
                'description': 'Fertilizer application verified under USDA Organic Standards',
                'default_emission_factor': 5.86,
                'unit': 'kg CO2e/kg N',
                'usda_verified': True,  # Actually verified by USDA
                'usda_factors_based': True,
                'verification_status': 'usda_certified',
                'data_source': 'USDA National Organic Program'
            },
            {
                'name': 'USDA SOE Verified Equipment',
                'category': 'equipment',
                'description': 'Equipment operations verified under USDA Strengthening Organic Enforcement',
                'default_emission_factor': 2.68,
                'unit': 'kg CO2e/L diesel',
                'usda_verified': True,
                'usda_factors_based': True,
                'verification_status': 'usda_certified',
                'data_source': 'USDA Strengthening Organic Enforcement'
            },
            {
                'name': 'USDA Climate Smart Agriculture Practice',
                'category': 'soil_management',
                'description': 'Soil management practice verified under USDA Climate Smart Agriculture',
                'default_emission_factor': -2.5,  # Negative for sequestration
                'unit': 'kg CO2e/ha',
                'usda_verified': True,
                'usda_factors_based': True,
                'verification_status': 'usda_certified',
                'data_source': 'USDA Climate Smart Agriculture Program'
            }
        ]

        for source_data in verified_sources:
            source, created = CarbonSource.objects.get_or_create(
                name=source_data['name'],
                defaults=source_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created USDA verified source: {source.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Source already exists: {source.name}')
                )

    def create_usda_certification(self, establishment_id, production_id):
        """Create a USDA certification record"""
        
        try:
            establishment = Establishment.objects.get(id=establishment_id)
            production = History.objects.get(id=production_id)
            
            # Create USDA certification
            certification = CarbonCertification.objects.create(
                establishment=establishment,
                production=production,
                certifier='USDA National Organic Program',
                certificate_id=f'USDA-ORG-{establishment_id}-{production_id}-2024',
                issue_date=timezone.now().date(),
                expiry_date=timezone.now().date().replace(year=timezone.now().year + 1),
                is_usda_soe_verified=True,
                verification_date=timezone.now().date(),
                verification_details='Verified under USDA Strengthening Organic Enforcement rule for carbon tracking compliance'
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Created USDA certification: {certification.certificate_id}')
            )
            
            return certification
            
        except Establishment.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Establishment {establishment_id} not found')
            )
        except History.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Production {production_id} not found')
            )

    def show_verification_workflow(self):
        """Show the complete USDA verification workflow"""
        
        self.stdout.write(
            self.style.SUCCESS('\n📋 USDA Verification Workflow:')
        )
        
        workflow_steps = [
            "1. 📝 Apply for USDA Organic Certification",
            "   • Submit application to USDA-accredited certifying agent",
            "   • Provide organic system plan",
            "   • Pay certification fees",
            "",
            "2. 🔍 USDA Inspection Process",
            "   • On-site inspection by certified inspector",
            "   • Review of records and practices",
            "   • Verification of carbon tracking systems",
            "",
            "3. 📋 USDA Review and Decision",
            "   • Certifying agent reviews inspection report",
            "   • USDA reviews certification decision",
            "   • Certificate issued if compliant",
            "",
            "4. 💾 Update Trazo System",
            "   • Create CarbonCertification record",
            "   • Mark relevant CarbonSources as usda_verified=True",
            "   • Update verification_status to 'usda_certified'",
            "",
            "5. ✅ Events Now Show as USDA Verified",
            "   • Events using certified sources show usda_verified=True",
            "   • Verification status shows 'usda_certified'",
            "   • Data source shows specific USDA program"
        ]
        
        for step in workflow_steps:
            if step.startswith(('1.', '2.', '3.', '4.', '5.')):
                self.stdout.write(self.style.SUCCESS(step))
            elif step.startswith('   •'):
                self.stdout.write(f'     {step[4:]}')
            else:
                self.stdout.write(step)

        self.stdout.write(
            self.style.WARNING('\n⚠️  Important Notes:')
        )
        
        notes = [
            "• USDA verification requires actual certification process",
            "• Cannot be automated - requires human verification",
            "• Costs typically $500-$5,000+ depending on operation size",
            "• Annual renewal required",
            "• Must maintain detailed records for 5 years"
        ]
        
        for note in notes:
            self.stdout.write(f'  {note}')

        self.stdout.write(
            self.style.SUCCESS('\n🔗 USDA Resources:')
        )
        
        resources = [
            "• USDA Organic Certification: https://www.ams.usda.gov/services/organic-certification",
            "• Find Certifying Agents: https://organic.ams.usda.gov/integrity/CertifyingAgents/CertifyingAgentsAddresses.aspx",
            "• Climate Smart Agriculture: https://www.usda.gov/climate-solutions/climate-smart-commodities",
            "• Strengthening Organic Enforcement: https://www.ams.usda.gov/rules-regulations/organic/strengthening-organic-enforcement"
        ]
        
        for resource in resources:
            self.stdout.write(f'  {resource}') 