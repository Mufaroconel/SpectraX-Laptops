#!/usr/bin/env python3
"""
Test OrderMessage handling functionality
"""

from datetime import datetime
import json

# Test order data structure (simulating WhatsApp OrderMessage)
test_order_data = {
    "catalog_id": "TEST_CATALOG_001",
    "order_text": "I would like to order 2 gaming laptops and 1 repair service",
    "products": [
        {
            "title": "Gaming Laptop Pro",
            "quantity": 2,
            "retail_price": 1299.99,
            "product_retailer_id": "LAPTOP_GAMING_001"
        },
        {
            "title": "Laptop Screen Repair",
            "quantity": 1,
            "retail_price": 199.99,
            "product_retailer_id": "REPAIR_SCREEN_001"
        }
    ]
}

test_user = {
    "name": "Test Customer",
    "phone_number": "263711475883"
}

def test_order_processing():
    """Test order data structure and calculations"""
    print("🧪 Testing OrderMessage Processing...")
    print(f"📋 Order Text: {test_order_data['order_text']}")
    print(f"🏪 Catalog ID: {test_order_data['catalog_id']}")
    print(f"👤 Customer: {test_user['name']} ({test_user['phone_number']})")
    print()
    
    total_amount = 0
    print("📦 Products:")
    for i, product in enumerate(test_order_data['products'], 1):
        title = product['title']
        quantity = product['quantity']
        price = product['retail_price']
        retailer_id = product['product_retailer_id']
        
        item_total = price * quantity
        total_amount += item_total
        
        print(f"{i}. {title}")
        print(f"   • Quantity: {quantity}")
        print(f"   • Unit Price: ${price:.2f}")
        print(f"   • Subtotal: ${item_total:.2f}")
        print(f"   • Product ID: {retailer_id}")
        print()
    
    print(f"💰 Total Order Value: ${total_amount:.2f}")
    print(f"📊 Total Items: {len(test_order_data['products'])}")
    print(f"🕐 Processing Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test order type detection
    laptop_products = [p for p in test_order_data['products'] if 'LAPTOP' in p['product_retailer_id']]
    repair_products = [p for p in test_order_data['products'] if 'REPAIR' in p['product_retailer_id']]
    
    if laptop_products and repair_products:
        order_type = "MIXED (LAPTOP + REPAIR)"
    elif laptop_products:
        order_type = "LAPTOP"
    elif repair_products:
        order_type = "REPAIR"
    else:
        order_type = "UNKNOWN"
    
    print(f"🏷 Order Type: {order_type}")
    print(f"💻 Laptop Products: {len(laptop_products)}")
    print(f"🛠 Repair Products: {len(repair_products)}")
    
    print("\n✅ Order processing test completed successfully!")

if __name__ == "__main__":
    test_order_processing()
