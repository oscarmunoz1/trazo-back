from django.core.management.base import BaseCommand
from carbon.models import CarbonEntry

class Command(BaseCommand):
    help = 'Updates co2e_amount field on all CarbonEntry records that have it set to 0'

    def handle(self, *args, **kwargs):
        entries = CarbonEntry.objects.filter(co2e_amount=0)
        
        if not entries.exists():
            self.stdout.write(self.style.SUCCESS('No entries with co2e_amount=0 found'))
            return
            
        updated_count = 0
        for entry in entries:
            entry.co2e_amount = entry.amount
            entry.save()
            updated_count += 1
            
        self.stdout.write(self.style.SUCCESS(f'Successfully updated co2e_amount for {updated_count} CarbonEntry records')) 