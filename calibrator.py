import os
import json
from typing import List, Dict, Any, Tuple
from sheets import SheetUploader
import config

# Configuration
SPREADSHEET_ID = config.SPREADSHEET_ID
TAB_NAME = "Transactions_Raw" # Or the sheet where manual categorization happens

def calibrate():
    print(f"Connecting to Google Sheets: {SPREADSHEET_ID}...")
    uploader = SheetUploader(SPREADSHEET_ID)
    uploader.authenticate()
    
    print(f"Fetching data from tab '{TAB_NAME}'...")
    try:
        rows = uploader.read_sheet(TAB_NAME)
    except Exception as e:
        print(f"Error reading sheet: {e}")
        return

    if not rows:
        print("No data found in the sheet.")
        return

    print(f"Processing {len(rows)} rows...")
    
    # We look for patterns where 'merchant' or 'description' maps to a category
    # The user might have a column named '분류' or 'category'
    # Based on fill_category.py, it was column L (index 11).
    # get_all_records() uses the first row as keys.
    
    # Find relevant keys
    possible_cat_keys = ["분류", "category", "Category", "Item", "아이템"]
    cat_key = next((k for k in possible_cat_keys if k in rows[0]), None)
    
    if not cat_key:
        print(f"Could not find a category column. Available columns: {list(rows[0].keys())}")
        return

    print(f"Using '{cat_key}' as the category column.")

    # Patterns: (merchant, description) -> category
    new_rules: Dict[Tuple[str, str], str] = {}
    
    for row in rows:
        merchant = str(row.get("merchant", "")).strip()
        description = str(row.get("description", "")).strip()
        category = str(row.get(cat_key, "")).strip()
        
        if not category:
            continue
        
        # Heuristic: if category is likely a Whooing category (Korean) 
        # or an ACCOUNTS/EXP/INC key.
        
        # For now, let's just collect merchant -> category mapping
        if merchant:
            new_rules[(merchant, "")] = category
        elif description:
            new_rules[("", description)] = category

    print(f"Found {len(new_rules)} potential rules.")
    
    # Generate snippets
    print("\n--- Suggested CATEGORY_RULES for union.py ---")
    print("# Add these to CATEGORY_RULES list in union.py")
    
    # To keep it simple, generate a sorted list of unique rules
    sorted_rules = sorted(new_rules.items())
    for (m, d), cat in sorted_rules:
        # Check if it's already an EXP key or needs mapping
        # For now, just print the raw mapping
        if m:
            print(f'    (10, r"{m}", "{cat}"),')
        elif d:
            print(f'    (5, r"{d}", "{cat}"),')

    print("\n--- End of Suggestions ---")
    print("Note: Review the suggestions before adding them to union.py.")

if __name__ == "__main__":
    calibrate()
