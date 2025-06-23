from django.core.management.base import BaseCommand
from django.db.models import Sum
from carbon.models import CarbonEntry, EstablishmentCarbonFootprint, CarbonSource
from company.models import Establishment, Company
from users.models import User
from datetime import datetime, timedelta
import json

class Command(BaseCommand):
    help = 'Test carbon data flow and identify issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-sample',
            action='store_true',
            help='Create sample carbon data if none exists',
        )
        parser.add_argument(
            '--establishment-id',
            type=int,
            help='Test specific establishment ID',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🔍 TESTING CARBON DATA FLOW'))
        self.stdout.write('=' * 50)
        
        # Test 1: Check existing data
        results = self.test_existing_data()
        
        # Test 2: Create sample data if requested and none exists
        if options['create_sample'] and results['total_entries'] == 0:
            self.stdout.write('\n📝 CREATING SAMPLE DATA')
            self.create_sample_data()
            results = self.test_existing_data()  # Re-test after creation
        
        # Test 3: Test specific establishment if provided
        if options['establishment_id']:
            self.test_establishment_data(options['establishment_id'])
        
        # Test 4: Test API endpoint structure
        self.test_api_structure()
        
        self.stdout.write(self.style.SUCCESS('\n✅ TESTING COMPLETED'))

    def test_existing_data(self):
        """Test existing carbon data"""
        self.stdout.write('\n📊 CHECKING EXISTING DATA')
        self.stdout.write('-' * 30)
        
        # Count carbon entries
        carbon_entries = CarbonEntry.objects.all()
        total_entries = carbon_entries.count()
        self.stdout.write(f"Total Carbon Entries: {total_entries}")
        
        # Count establishments with data
        establishments_with_data = Establishment.objects.filter(
            id__in=carbon_entries.values_list('establishment_id', flat=True)
        ).distinct()
        
        self.stdout.write(f"Establishments with Carbon Data: {establishments_with_data.count()}")
        
        # Show sample entries
        if carbon_entries.exists():
            self.stdout.write('\n✅ Sample Carbon Entries:')
            for entry in carbon_entries[:3]:
                self.stdout.write(f"  - ID: {entry.id}, Type: {entry.type}, Amount: {entry.amount} kg CO₂e")
                self.stdout.write(f"    Establishment: {entry.establishment_id}, Date: {entry.timestamp}")
        
        # Check footprint summaries
        footprints = EstablishmentCarbonFootprint.objects.all()
        self.stdout.write(f"\nEstablishment Footprints: {footprints.count()}")
        
        if footprints.exists():
            for fp in footprints[:2]:
                self.stdout.write(f"  - Est {fp.establishment_id}: {fp.total_emissions} kg CO₂e")
        
        return {
            'total_entries': total_entries,
            'establishments_with_data': establishments_with_data.count(),
            'sample_establishment_id': establishments_with_data.first().id if establishments_with_data.exists() else None
        }

    def test_establishment_data(self, establishment_id):
        """Test data for specific establishment"""
        self.stdout.write(f'\n🏢 TESTING ESTABLISHMENT {establishment_id}')
        self.stdout.write('-' * 30)
        
        try:
            establishment = Establishment.objects.get(id=establishment_id)
            self.stdout.write(f"Name: {establishment.name}")
            
            # Get entries
            entries = CarbonEntry.objects.filter(establishment_id=establishment_id)
            self.stdout.write(f"Carbon Entries: {entries.count()}")
            
            # Calculate totals
            emissions = entries.filter(type='emission').aggregate(total=Sum('amount'))['total'] or 0
            offsets = entries.filter(type='offset').aggregate(total=Sum('amount'))['total'] or 0
            
            self.stdout.write(f"Total Emissions: {emissions} kg CO₂e")
            self.stdout.write(f"Total Offsets: {offsets} kg CO₂e")
            self.stdout.write(f"Net Carbon: {emissions - offsets} kg CO₂e")
            
            # Check if summary exists
            footprint = EstablishmentCarbonFootprint.objects.filter(
                establishment_id=establishment_id
            ).first()
            
            if footprint:
                self.stdout.write(f"✅ Summary Record: {footprint.total_emissions} kg CO₂e")
            else:
                self.stdout.write("⚠️  No summary record - data calculated dynamically")
                
        except Establishment.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ Establishment {establishment_id} not found"))

    def create_sample_data(self):
        """Create sample carbon data"""
        self.stdout.write('Creating sample carbon data...')
        
        # Get first establishment
        establishment = Establishment.objects.first()
        if not establishment:
            self.stdout.write(self.style.ERROR("❌ No establishments found"))
            return
        
        # Get or create carbon sources
        fuel_source, _ = CarbonSource.objects.get_or_create(
            name='Diesel Fuel',
            defaults={
                'description': 'Diesel fuel consumption',
                'unit': 'liters',
                'category': 'Fuel',
                'default_emission_factor': 2.68,
                'usda_verified': True
            }
        )
        
        fertilizer_source, _ = CarbonSource.objects.get_or_create(
            name='Nitrogen Fertilizer',
            defaults={
                'description': 'Nitrogen fertilizer application',
                'unit': 'kg',
                'category': 'Fertilizer',
                'default_emission_factor': 5.5,
                'usda_verified': True
            }
        )
        
        # Get first user
        user = User.objects.first()
        
        # Create sample entries
        current_year = datetime.now().year
        
        # Emission entries
        CarbonEntry.objects.create(
            establishment=establishment,
            created_by=user,
            type='emission',
            source=fuel_source,
            amount=150.5,
            year=current_year,
            description='Tractor fuel consumption - monthly average',
            usda_verified=True
        )
        
        CarbonEntry.objects.create(
            establishment=establishment,
            created_by=user,
            type='emission',
            source=fertilizer_source,
            amount=275.0,
            year=current_year,
            description='Spring fertilizer application',
            usda_verified=True
        )
        
        # Offset entry
        CarbonEntry.objects.create(
            establishment=establishment,
            created_by=user,
            type='offset',
            source=None,
            amount=50.0,
            year=current_year,
            description='Tree planting carbon sequestration',
            usda_verified=False
        )
        
        # Create summary footprint
        total_emissions = 425.5
        total_offsets = 50.0
        
        EstablishmentCarbonFootprint.objects.create(
            establishment=establishment,
            year=current_year,
            total_emissions=total_emissions,
            total_offsets=total_offsets,
            net_carbon=total_emissions - total_offsets,
            carbon_score=75
        )
        
        self.stdout.write(f"✅ Created sample data for {establishment.name}")
        self.stdout.write(f"   - 2 emission entries (425.5 kg CO₂e)")
        self.stdout.write(f"   - 1 offset entry (50.0 kg CO₂e)")
        self.stdout.write(f"   - Summary footprint record")

    def test_api_structure(self):
        """Test the API data structure that frontend expects"""
        self.stdout.write('\n🌐 TESTING API STRUCTURE')
        self.stdout.write('-' * 30)
        
        # Get sample establishment with data
        establishment = Establishment.objects.filter(
            id__in=CarbonEntry.objects.values_list('establishment_id', flat=True)
        ).first()
        
        if not establishment:
            self.stdout.write("❌ No establishment with carbon data found")
            return
        
        # Simulate API response structure
        entries = CarbonEntry.objects.filter(establishment=establishment)
        emissions = entries.filter(type='emission').aggregate(total=Sum('amount'))['total'] or 0
        offsets = entries.filter(type='offset').aggregate(total=Sum('amount'))['total'] or 0
        
        # Check footprint summary
        footprint = EstablishmentCarbonFootprint.objects.filter(
            establishment=establishment
        ).first()
        
        api_response = {
            'total_emissions': float(emissions),
            'total_offsets': float(offsets),
            'net_carbon': float(emissions - offsets),
            'carbon_score': footprint.carbon_score if footprint else 85,
            'year': datetime.now().year,
            'establishment_id': establishment.id,
            'has_data': emissions > 0 or offsets > 0
        }
        
        self.stdout.write("✅ API Response Structure:")
        self.stdout.write(json.dumps(api_response, indent=2))
        
        # Test entries endpoint structure
        entries_response = []
        for entry in entries[:3]:
            entries_response.append({
                'id': entry.id,
                'type': entry.type,
                'amount': float(entry.amount),
                'source': entry.source.name if entry.source else None,
                'timestamp': entry.timestamp.isoformat(),
                'description': entry.description
            })
        
        self.stdout.write(f"\n✅ Entries Response ({len(entries_response)} items):")
        if entries_response:
            self.stdout.write(json.dumps(entries_response[0], indent=2)) 