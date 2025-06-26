#!/usr/bin/env python3
"""
Fix the carbon score calculation issue where new establishments 
with no carbon entries get a default score of 85 instead of 0.
"""

def fix_carbon_score_calculation():
    """Fix the carbon score calculation in views.py"""
    
    # Read the file
    with open('carbon/views.py', 'r') as f:
        content = f.read()
    
    # Replace the problematic default score
    old_code = '''            # Calculate carbon score (0-100)
            carbon_score = 85  # Default score
            if total_emissions > 0:
                offset_percentage = min(100, (total_offsets / total_emissions) * 100)
                if offset_percentage >= 100:
                    carbon_score = 90 + min(10, ((offset_percentage - 100) / 50) * 10)
                else:
                    carbon_score = max(10, min(90, offset_percentage * 0.85))
            elif total_offsets > 0:
                carbon_score = 95  # Excellent if only offsets'''
    
    new_code = '''            # Calculate carbon score (0-100)
            carbon_score = 0  # Default score for no data
            if total_emissions > 0:
                offset_percentage = min(100, (total_offsets / total_emissions) * 100)
                if offset_percentage >= 100:
                    carbon_score = 90 + min(10, ((offset_percentage - 100) / 50) * 10)
                else:
                    carbon_score = max(10, min(90, offset_percentage * 0.85))
            elif total_offsets > 0:
                carbon_score = 95  # Excellent if only offsets
            elif total_emissions == 0 and total_offsets == 0:
                carbon_score = 0  # No data available - cannot calculate score'''
    
    # Replace the code
    if old_code in content:
        content = content.replace(old_code, new_code)
        
        # Write back to file
        with open('carbon/views.py', 'w') as f:
            f.write(content)
        
        print("✅ Fixed carbon score calculation in views.py")
        print("   - Changed default score from 85 to 0 for establishments with no data")
        print("   - Added explicit handling for zero emissions and offsets")
        return True
    else:
        print("❌ Could not find the problematic code section")
        return False

if __name__ == "__main__":
    success = fix_carbon_score_calculation()
    exit(0 if success else 1)
