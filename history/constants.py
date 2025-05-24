from .models import (
    ProductionEvent,
    WeatherEvent,
    ChemicalEvent,
    GeneralEvent,
    EquipmentEvent,
    SoilManagementEvent,
    BusinessEvent,
    PestManagementEvent,
)

WEATHER_EVENT_TYPE = 0
PRODUCTION_EVENT_TYPE = 1
CHEMICAL_EVENT_TYPE = 2
GENERAL_EVENT_TYPE = 3
EQUIPMENT_EVENT_TYPE = 4
SOIL_MANAGEMENT_EVENT_TYPE = 5
BUSINESS_EVENT_TYPE = 6
PEST_MANAGEMENT_EVENT_TYPE = 7

event_map = {
    0: WeatherEvent,
    1: ProductionEvent,
    2: ChemicalEvent,
    3: GeneralEvent,
    4: EquipmentEvent,
    5: SoilManagementEvent,
    6: BusinessEvent,
    7: PestManagementEvent,
}

ALLOWED_PERIODS = ["week", "month", "year"]
