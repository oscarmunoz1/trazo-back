#!/usr/bin/env python3

# Check for type code collisions across event models
codes = {
    'WeatherEvent': ['FR', 'DR', 'HL', 'HT', 'TS', 'HW', 'HH', 'LH'],
    'ChemicalEvent': ['FE', 'PE', 'FU', 'HE'],
    'ProductionEvent': ['PL', 'HA', 'IR', 'PR'],
    'EquipmentEvent': ['MN', 'RE', 'CA', 'FC', 'BD', 'EI'],
    'SoilManagementEvent': ['ST', 'PA', 'OM', 'CC', 'TI', 'CO'],
    'BusinessEvent': ['HS', 'CE', 'IN', 'IS', 'MA', 'CT', 'CM'],
    'PestManagementEvent': ['SC', 'BR', 'TM', 'PI', 'TA', 'IP']
}

from collections import defaultdict

code_usage = defaultdict(list)
for event_type, type_codes in codes.items():
    for code in type_codes:
        code_usage[code].append(event_type)

print('TYPE CODE COLLISIONS:')
collisions_found = False
for code, event_types in code_usage.items():
    if len(event_types) > 1:
        print(f'  {code}: {event_types}')
        collisions_found = True

if not collisions_found:
    print('  No collisions found')

print()
print('ALL CODES BY EVENT TYPE:')
for event_type, type_codes in codes.items():
    print(f'  {event_type}: {type_codes}') 