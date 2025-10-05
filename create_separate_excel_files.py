"""
create_separate_excel_files.py

Creates two separate Excel files:
- laptops.xlsx with laptop retailer IDs
- repairs.xlsx with repair retailer IDs
"""
import os
from typing import List
from dotenv import load_dotenv
from openpyxl import Workbook

load_dotenv()


def create_excel_file(filename: str, header: str, retailer_ids: List[str]) -> None:
    """Create an Excel file with the given retailer IDs."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    
    # Add header
    ws.append([header])
    
    # Add retailer IDs
    if not retailer_ids:
        ws.append(["(none configured)"])
    else:
        for rid in retailer_ids:
            ws.append([rid])
    
    wb.save(filename)
    print(f"Created {filename} with {len(retailer_ids)} retailer IDs")


def main() -> None:
    # Laptop retailer IDs
    laptop_ids = []
    laptop_id_1 = os.getenv("PRODUCT_RETAILER_ID")
    laptop_id_2 = os.getenv("PRODUCT_RETAILER_ID_2")
    
    if laptop_id_1 and laptop_id_1.strip():
        laptop_ids.append(laptop_id_1.strip())
    if laptop_id_2 and laptop_id_2.strip():
        laptop_ids.append(laptop_id_2.strip())
    
    # Repair retailer IDs
    repair_ids = []
    repair_id_1 = os.getenv("PRODUCT_RETAILER_ID_REPAIR")
    repair_id_2 = os.getenv("PRODUCT_RETAILER_ID_REPAIR_2")
    
    if repair_id_1 and repair_id_1.strip():
        repair_ids.append(repair_id_1.strip())
    if repair_id_2 and repair_id_2.strip():
        repair_ids.append(repair_id_2.strip())
    
    # Create separate Excel files
    create_excel_file("laptops.xlsx", "retailer_id", laptop_ids)
    create_excel_file("repairs.xlsx", "retailer_id", repair_ids)
    
    print(f"Laptop IDs: {laptop_ids}")
    print(f"Repair IDs: {repair_ids}")


if __name__ == "__main__":
    main()
