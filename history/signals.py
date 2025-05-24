from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import WeatherEvent, ChemicalEvent, ProductionEvent, GeneralEvent, EquipmentEvent, SoilManagementEvent, BusinessEvent, PestManagementEvent
from carbon.services.event_carbon_calculator import EventCarbonCalculator


@receiver(post_save, sender=ChemicalEvent)
def calculate_chemical_event_carbon(sender, instance, created, **kwargs):
    """
    Automatically calculate carbon impact when a chemical event is created or updated
    """
    if created or kwargs.get('update_fields'):  # Only on create or specific field updates
        try:
            calculator = EventCarbonCalculator()
            calculation_result = calculator.calculate_chemical_event_impact(instance)
            
            # Create carbon entry if calculation was successful
            if calculation_result.get('co2e', 0) > 0:
                carbon_entry = calculator.create_carbon_entry_from_event(instance, calculation_result)
                
                # Store calculation result in event's extra_data for future reference
                if not hasattr(instance, 'extra_data') or instance.extra_data is None:
                    instance.extra_data = {}
                
                instance.extra_data['carbon_calculation'] = calculation_result
                
                # Update without triggering signal again
                ChemicalEvent.objects.filter(id=instance.id).update(extra_data=instance.extra_data)
                
                print(f"✅ Carbon calculation completed for Chemical Event {instance.id}: {calculation_result['co2e']} kg CO2e")
            
        except Exception as e:
            print(f"❌ Error calculating carbon for Chemical Event {instance.id}: {e}")


@receiver(post_save, sender=ProductionEvent)
def calculate_production_event_carbon(sender, instance, created, **kwargs):
    """
    Automatically calculate carbon impact when a production event is created or updated
    """
    if created or kwargs.get('update_fields'):
        try:
            calculator = EventCarbonCalculator()
            calculation_result = calculator.calculate_production_event_impact(instance)
            
            # Create carbon entry if calculation was successful
            if calculation_result.get('co2e', 0) > 0:
                carbon_entry = calculator.create_carbon_entry_from_event(instance, calculation_result)
                
                # Store calculation result in event's extra_data
                if not hasattr(instance, 'extra_data') or instance.extra_data is None:
                    instance.extra_data = {}
                
                instance.extra_data['carbon_calculation'] = calculation_result
                
                # Update without triggering signal again
                ProductionEvent.objects.filter(id=instance.id).update(extra_data=instance.extra_data)
                
                print(f"✅ Carbon calculation completed for Production Event {instance.id}: {calculation_result['co2e']} kg CO2e")
            
        except Exception as e:
            print(f"❌ Error calculating carbon for Production Event {instance.id}: {e}")


@receiver(post_save, sender=WeatherEvent)
def calculate_weather_event_carbon(sender, instance, created, **kwargs):
    """
    Automatically calculate carbon impact when a weather event is created or updated
    """
    if created or kwargs.get('update_fields'):
        try:
            calculator = EventCarbonCalculator()
            calculation_result = calculator.calculate_weather_event_impact(instance)
            
            # Create carbon entry if calculation was successful
            if calculation_result.get('co2e', 0) > 0:
                carbon_entry = calculator.create_carbon_entry_from_event(instance, calculation_result)
                
                # Store calculation result in event's extra_data
                if not hasattr(instance, 'extra_data') or instance.extra_data is None:
                    instance.extra_data = {}
                
                instance.extra_data['carbon_calculation'] = calculation_result
                
                # Update without triggering signal again
                WeatherEvent.objects.filter(id=instance.id).update(extra_data=instance.extra_data)
                
                print(f"✅ Carbon calculation completed for Weather Event {instance.id}: {calculation_result['co2e']} kg CO2e")
            
        except Exception as e:
            print(f"❌ Error calculating carbon for Weather Event {instance.id}: {e}")


@receiver(post_save, sender=GeneralEvent)
def calculate_general_event_carbon(sender, instance, created, **kwargs):
    """
    Automatically calculate minimal carbon impact for general events
    """
    if created:  # Only for new general events
        try:
            from carbon.services.event_carbon_calculator import EventCarbonCalculator
            from carbon.models import CarbonEntry
            
            calculator = EventCarbonCalculator()
            
            # General events have minimal standard carbon impact
            calculation_result = {
                'co2e': 0.1,  # Minimal impact
                'efficiency_score': 50.0,
                'usda_verified': False,
                'calculation_method': 'general_event_standard',
                'recommendations': []
            }
            
            # Only create carbon entry if the event might have actual impact
            impact_keywords = ['fuel', 'energy', 'transport', 'machinery', 'equipment']
            if any(keyword in (instance.name + ' ' + instance.observation).lower() 
                   for keyword in impact_keywords):
                carbon_entry = calculator.create_carbon_entry_from_event(instance, calculation_result)
                
                # Store calculation result
                if not hasattr(instance, 'extra_data') or instance.extra_data is None:
                    instance.extra_data = {}
                
                instance.extra_data['carbon_calculation'] = calculation_result
                GeneralEvent.objects.filter(id=instance.id).update(extra_data=instance.extra_data)
                
                print(f"✅ Carbon calculation completed for General Event {instance.id}: {calculation_result['co2e']} kg CO2e")
            
        except Exception as e:
            print(f"❌ Error calculating carbon for General Event {instance.id}: {e}")


@receiver(post_delete, sender=ChemicalEvent)
@receiver(post_delete, sender=ProductionEvent)
@receiver(post_delete, sender=WeatherEvent)
@receiver(post_delete, sender=GeneralEvent)
def cleanup_carbon_entries_on_event_delete(sender, instance, **kwargs):
    """
    Clean up associated carbon entries when events are deleted
    """
    try:
        from carbon.models import CarbonEntry
        
        # Find and delete associated carbon entries
        # We identify them by the description pattern
        event_class_name = instance.__class__.__name__
        carbon_entries = CarbonEntry.objects.filter(
            production=instance.history,
            description__icontains=f"Auto-calculated from {event_class_name}"
        )
        
        deleted_count = carbon_entries.count()
        carbon_entries.delete()
        
        if deleted_count > 0:
            print(f"🗑️ Cleaned up {deleted_count} carbon entries for deleted {event_class_name} {instance.id}")
        
    except Exception as e:
        print(f"❌ Error cleaning up carbon entries for {instance.__class__.__name__} {instance.id}: {e}")


@receiver(post_save, sender=EquipmentEvent)
def calculate_equipment_event_carbon(sender, instance, created, **kwargs):
    """
    Automatically calculate carbon impact for equipment events
    """
    if created:  # Only for new equipment events
        try:
            from carbon.services.event_carbon_calculator import EventCarbonCalculator
            
            calculator = EventCarbonCalculator()
            calculation_result = calculator.calculate_equipment_event_impact(instance)
            
            # Create carbon entry automatically
            carbon_entry = calculator.create_carbon_entry_from_event(instance, calculation_result)
            
            # Store calculation result in event extra_data
            if not hasattr(instance, 'extra_data') or instance.extra_data is None:
                instance.extra_data = {}
            
            instance.extra_data['carbon_calculation'] = calculation_result
            EquipmentEvent.objects.filter(id=instance.id).update(extra_data=instance.extra_data)
            
            print(f"✅ Carbon calculation completed for Equipment Event {instance.id}: {calculation_result['co2e']} kg CO2e")
            
        except Exception as e:
            print(f"❌ Error calculating carbon for Equipment Event {instance.id}: {e}")


@receiver(post_save, sender=SoilManagementEvent)
def calculate_soil_management_event_carbon(sender, instance, created, **kwargs):
    """
    Automatically calculate carbon impact for soil management events
    """
    if created:  # Only for new soil management events
        try:
            from carbon.services.event_carbon_calculator import EventCarbonCalculator
            
            calculator = EventCarbonCalculator()
            calculation_result = calculator.calculate_soil_management_event_impact(instance)
            
            # Create carbon entry automatically
            carbon_entry = calculator.create_carbon_entry_from_event(instance, calculation_result)
            
            # Store calculation result in event extra_data
            if not hasattr(instance, 'extra_data') or instance.extra_data is None:
                instance.extra_data = {}
            
            instance.extra_data['carbon_calculation'] = calculation_result
            SoilManagementEvent.objects.filter(id=instance.id).update(extra_data=instance.extra_data)
            
            print(f"✅ Carbon calculation completed for Soil Management Event {instance.id}: {calculation_result['co2e']} kg CO2e")
            
        except Exception as e:
            print(f"❌ Error calculating carbon for Soil Management Event {instance.id}: {e}")


@receiver(post_save, sender=BusinessEvent)
def calculate_business_event_carbon(sender, instance, created, **kwargs):
    """
    Automatically calculate carbon impact for business events
    """
    if created:  # Only for new business events
        try:
            from carbon.services.event_carbon_calculator import EventCarbonCalculator
            
            calculator = EventCarbonCalculator()
            calculation_result = calculator.calculate_business_event_impact(instance)
            
            # Create carbon entry automatically (only if there's significant impact)
            if abs(calculation_result['co2e']) > 0.1:
                carbon_entry = calculator.create_carbon_entry_from_event(instance, calculation_result)
            
            # Store calculation result in event extra_data
            if not hasattr(instance, 'extra_data') or instance.extra_data is None:
                instance.extra_data = {}
            
            instance.extra_data['carbon_calculation'] = calculation_result
            BusinessEvent.objects.filter(id=instance.id).update(extra_data=instance.extra_data)
            
            print(f"✅ Carbon calculation completed for Business Event {instance.id}: {calculation_result['co2e']} kg CO2e")
            
        except Exception as e:
            print(f"❌ Error calculating carbon for Business Event {instance.id}: {e}")


@receiver(post_save, sender=PestManagementEvent)
def calculate_pest_management_event_carbon(sender, instance, created, **kwargs):
    """
    Automatically calculate carbon impact for pest management events
    """
    if created:  # Only for new pest management events
        try:
            from carbon.services.event_carbon_calculator import EventCarbonCalculator
            
            calculator = EventCarbonCalculator()
            calculation_result = calculator.calculate_pest_management_event_impact(instance)
            
            # Create carbon entry automatically (only for significant impacts)
            if abs(calculation_result['co2e']) > 0.05:
                carbon_entry = calculator.create_carbon_entry_from_event(instance, calculation_result)
            
            # Store calculation result in event extra_data
            if not hasattr(instance, 'extra_data') or instance.extra_data is None:
                instance.extra_data = {}
            
            instance.extra_data['carbon_calculation'] = calculation_result
            PestManagementEvent.objects.filter(id=instance.id).update(extra_data=instance.extra_data)
            
            print(f"✅ Carbon calculation completed for Pest Management Event {instance.id}: {calculation_result['co2e']} kg CO2e")
            
        except Exception as e:
            print(f"❌ Error calculating carbon for Pest Management Event {instance.id}: {e}") 