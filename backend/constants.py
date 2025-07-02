"""
Production-ready constants for Trazo carbon calculations.
All values based on EPA and USDA verified standards.
"""

# EPA-verified carbon footprint conversion factors
class EPAConversions:
    """Environmental Protection Agency verified conversion factors"""
    
    # EPA standard: 1 gallon gasoline = 8.887 kg CO₂e, average 25 mpg
    # Therefore: 1 mile = 8.887/25 = 0.35548 kg CO₂e/mile
    KG_CO2_PER_MILE = 0.35548
    
    # EPA standard: Average tree absorbs ~48 lbs (21.8 kg) CO₂ per year
    KG_CO2_PER_TREE_ANNUAL = 21.8


# USDA-verified carbon score grading thresholds
class USDAGrading:
    """USDA-based carbon footprint grading system (kg CO₂e/kg product)"""
    
    CARBON_SCORE_THRESHOLDS = {
        'A_PLUS': 0.5,
        'A': 1.0,
        'B': 2.0, 
        'C': 3.0,
        'D': 5.0,
        # Above 5.0 = F grade
    }


# User engagement milestones for achievements
class EngagementMilestones:
    """User achievement milestones for sustainable engagement"""
    
    SCAN_MILESTONES = {
        'EXPLORER': 10,      # First engagement milestone
        'COMMITTED': 25,     # Regular user milestone  
        'ADVOCATE': 50,      # Power user milestone
        'CHAMPION': 100,     # Expert user milestone
    }


def get_carbon_score_from_co2e(co2e_value):
    """
    Calculate carbon score grade from CO₂e value using USDA thresholds
    
    Args:
        co2e_value (float): Carbon footprint in kg CO₂e/kg product
        
    Returns:
        str: Grade from A+ to F
    """
    if co2e_value <= USDAGrading.CARBON_SCORE_THRESHOLDS['A_PLUS']:
        return "A+"
    elif co2e_value <= USDAGrading.CARBON_SCORE_THRESHOLDS['A']:
        return "A"
    elif co2e_value <= USDAGrading.CARBON_SCORE_THRESHOLDS['B']:
        return "B"
    elif co2e_value <= USDAGrading.CARBON_SCORE_THRESHOLDS['C']:
        return "C"
    elif co2e_value <= USDAGrading.CARBON_SCORE_THRESHOLDS['D']:
        return "D"
    else:
        return "F"


def calculate_miles_equivalent(kg_co2e):
    """
    Convert carbon footprint to driving miles equivalent using EPA standards
    
    Args:
        kg_co2e (float): Carbon footprint in kg CO₂e
        
    Returns:
        float: Equivalent driving miles
    """
    return kg_co2e / EPAConversions.KG_CO2_PER_MILE


def calculate_trees_equivalent(kg_co2e):
    """
    Convert carbon footprint to tree absorption equivalent using EPA standards
    
    Args:
        kg_co2e (float): Carbon footprint in kg CO₂e
        
    Returns:
        float: Equivalent trees needed for annual absorption
    """
    return kg_co2e / EPAConversions.KG_CO2_PER_TREE_ANNUAL