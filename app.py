import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from wa_cloud_py import WhatsApp
from fastapi.responses import PlainTextResponse
from fastapi import Request, HTTPException
from wa_cloud_py.components.messages import (
    CatalogSection,
    ImageHeader,
    ListSection,
    ReplyButton,
)
from wa_cloud_py.messages.types import InteractiveButtonMessage, OrderMessage

from wa_cloud_py.messages.types import (
    TextMessage,
)
import logging
import uvicorn
import asyncio
import inspect
from typing import List, Tuple, Optional
from openpyxl import load_workbook


load_dotenv()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
CATALOG_ID = os.getenv("CATALOG_ID")
PRODUCT_RETAILER_ID = os.getenv("PRODUCT_RETAILER_ID")
PRODUCT_RETAILER_ID_2 = os.getenv("PRODUCT_RETAILER_ID_2")
PRODUCT_RETAILER_ID_REPAIR = os.getenv("PRODUCT_RETAILER_ID_REPAIR")
PRODUCT_RETAILER_ID_REPAIR_2 = os.getenv("PRODUCT_RETAILER_ID_REPAIR_2")
PUBLIC_URL = os.getenv("PUBLIC_URL")

# Admin configuration
ADMIN_NUMBER = "263711475883"

if not VERIFY_TOKEN:
    raise ValueError("VERIFY_TOKEN environment variable is not set")
if not ACCESS_TOKEN:
    raise ValueError("ACCESS_TOKEN environment variable is not set")
if not PHONE_NUMBER_ID:
    raise ValueError("PHONE_NUMBER_ID environment variable is not set")
if not CATALOG_ID:
    raise ValueError("CATALOG_ID environment variable is not set")
if not PRODUCT_RETAILER_ID:
    raise ValueError("PRODUCT_RETAILER_ID environment variable is not set")
# PRODUCT_RETAILER_ID_2 is optional — no raise
if not PUBLIC_URL:
    raise ValueError("PUBLIC_URL environment variable is not set")


app = FastAPI()

# Mount static files to serve the video
app.mount("/static", StaticFiles(directory="."), name="static")


whatsapp = WhatsApp(access_token=ACCESS_TOKEN, phone_number_id=PHONE_NUMBER_ID)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EXCEL_RETAILER_FILE = "spectrax_retailer_ids.xlsx"


def _read_ids_from_sheet(workbook, sheet_name: str) -> List[str]:
    """Read first-column values from a sheet, skipping header and placeholders."""
    ids: List[str] = []
    if sheet_name not in workbook.sheetnames:
        return ids
    ws = workbook[sheet_name]
    for row in ws.iter_rows(min_row=1, max_col=1, values_only=True):
        val = row[0]
        if not val:
            continue
        s = str(val).strip()
        if not s or s.lower() == "retailer_id" or s.lower() == "(none configured)":
            continue
        ids.append(s)
    return ids


def load_retailer_ids_from_excel(filepath: str = EXCEL_RETAILER_FILE) -> Tuple[List[str], List[str]]:
    """Return (laptop_ids, repair_ids). If file not found or empty, return empty lists."""
    if not os.path.exists(filepath):
        logger.info("Retailer Excel not found at %s, will fall back to environment variables", filepath)
        return [], []
    try:
        wb = load_workbook(filepath, read_only=True, data_only=True)
    except Exception as exc:
        logger.exception("Failed to open retailer Excel %s: %s", filepath, exc)
        return [], []
    laptop_ids = _read_ids_from_sheet(wb, "Laptops")
    repair_ids = _read_ids_from_sheet(wb, "Repairs")
    return laptop_ids, repair_ids


def _env_retailer_ids(*keys: str) -> List[str]:
    ids = []
    for k in keys:
        v = os.getenv(k)
        if v and v.strip():
            ids.append(v.strip())
    return ids


def safe_mark_as_read(message_id: str):
    """Safely mark a WhatsApp message as read; swallow and log errors from the API.

    Some incoming webhook messages reference message IDs that cannot be marked as
    read (for example, legacy or unsupported IDs). Calling the API with an invalid
    ID raises an OAuthException; we log it and continue so the webhook stays healthy.
    """
    try:
        # attempt to mark as read if API exists
        if hasattr(whatsapp, "mark_as_read"):
            whatsapp.mark_as_read(message_id=message_id)
    except Exception as exc:
        logger.exception("Failed to mark message %s as read: %s", message_id, exc)


def is_admin(phone_number: str) -> bool:
    """Check if the phone number is an admin."""
    return phone_number == ADMIN_NUMBER


def handle_admin_command(phone_number: str, message_text: str):
    """Handle admin commands for managing retailer IDs."""
    if not is_admin(phone_number):
        return False
    
    message_lower = message_text.lower().strip()
    
    # Admin help command
    if message_lower in ["/admin", "/help", "help"]:
        send_admin_help(phone_number)
        return True
    
    # Add laptop retailer ID
    if message_lower.startswith("/add_laptop "):
        retailer_id = message_text[12:].strip()
        if retailer_id:
            add_laptop_retailer_id(phone_number, retailer_id)
        else:
            whatsapp.send_text(to=phone_number, body="❌ Please provide a retailer ID. Format: /add_laptop <retailer_id>")
        return True
    
    # Add repair retailer ID
    if message_lower.startswith("/add_repair "):
        retailer_id = message_text[12:].strip()
        if retailer_id:
            add_repair_retailer_id(phone_number, retailer_id)
        else:
            whatsapp.send_text(to=phone_number, body="❌ Please provide a retailer ID. Format: /add_repair <retailer_id>")
        return True
    
    # List current IDs
    if message_lower in ["/list", "/list_ids"]:
        list_current_retailer_ids(phone_number)
        return True
    
    # Remove laptop retailer ID
    if message_lower.startswith("/remove_laptop "):
        retailer_id = message_text[15:].strip()
        if retailer_id:
            remove_laptop_retailer_id(phone_number, retailer_id)
        else:
            whatsapp.send_text(to=phone_number, body="❌ Please provide a retailer ID. Format: /remove_laptop <retailer_id>")
        return True
    
    # Remove repair retailer ID
    if message_lower.startswith("/remove_repair "):
        retailer_id = message_text[15:].strip()
        if retailer_id:
            remove_repair_retailer_id(phone_number, retailer_id)
        else:
            whatsapp.send_text(to=phone_number, body="❌ Please provide a retailer ID. Format: /remove_repair <retailer_id>")
        return True
    
    return False


def send_admin_help(phone_number: str):
    """Send admin help message with available commands."""
    help_message = """🔧 **SpectraX Admin Panel**

**Button Interface:**
Use the admin dashboard buttons for easy management, or use text commands below.

**Text Commands:**

📋 **Management:**
• `/list` - View all current retailer IDs
• `/add_laptop <id>` - Add new laptop retailer ID
• `/add_repair <id>` - Add new repair retailer ID
• `/remove_laptop <id>` - Remove laptop retailer ID
• `/remove_repair <id>` - Remove repair retailer ID

📊 **Current Status:**
• You receive all order notifications
• Changes update Excel files automatically
• Changes take effect immediately

**Example Usage:**
• `/add_laptop abc123xyz` - Adds abc123xyz to laptop catalog
• `/add_repair def456uvw` - Adds def456uvw to repair catalog
• `/list` - Shows all current IDs

💡 **Tip:** Use the buttons below for easier navigation!"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=help_message,
        buttons=[
            ReplyButton(id="admin_manage_catalog", title="📝 Manage Catalog"),
            ReplyButton(id="admin_view_stats", title="📊 View All IDs"),
            ReplyButton(id="browse_laptops", title="👀 Preview Store"),
        ],
    )


def add_laptop_retailer_id(phone_number: str, retailer_id: str):
    """Add a new laptop retailer ID to the Excel file."""
    try:
        from catalog_utils import load_laptop_retailer_ids
        current_ids = load_laptop_retailer_ids()
        
        if retailer_id in current_ids:
            whatsapp.send_text(to=phone_number, body=f"⚠️ Laptop retailer ID '{retailer_id}' already exists!")
            return
        
        # Add to Excel file
        current_ids.append(retailer_id)
        update_laptop_excel(current_ids)
        
        whatsapp.send_text(to=phone_number, body=f"✅ Successfully added laptop retailer ID: {retailer_id}\n\nTotal laptop IDs: {len(current_ids)}")
        logger.info("Admin %s added laptop retailer ID: %s", phone_number, retailer_id)
        
    except Exception as e:
        logger.exception("Failed to add laptop retailer ID")
        whatsapp.send_text(to=phone_number, body=f"❌ Error adding laptop retailer ID: {str(e)}")


def add_repair_retailer_id(phone_number: str, retailer_id: str):
    """Add a new repair retailer ID to the Excel file."""
    try:
        from catalog_utils import load_repair_retailer_ids
        current_ids = load_repair_retailer_ids()
        
        if retailer_id in current_ids:
            whatsapp.send_text(to=phone_number, body=f"⚠️ Repair retailer ID '{retailer_id}' already exists!")
            return
        
        # Add to Excel file
        current_ids.append(retailer_id)
        update_repair_excel(current_ids)
        
        whatsapp.send_text(to=phone_number, body=f"✅ Successfully added repair retailer ID: {retailer_id}\n\nTotal repair IDs: {len(current_ids)}")
        logger.info("Admin %s added repair retailer ID: %s", phone_number, retailer_id)
        
    except Exception as e:
        logger.exception("Failed to add repair retailer ID")
        whatsapp.send_text(to=phone_number, body=f"❌ Error adding repair retailer ID: {str(e)}")


def remove_laptop_retailer_id(phone_number: str, retailer_id: str):
    """Remove a laptop retailer ID from the Excel file."""
    try:
        from catalog_utils import load_laptop_retailer_ids
        current_ids = load_laptop_retailer_ids()
        
        if retailer_id not in current_ids:
            whatsapp.send_text(to=phone_number, body=f"⚠️ Laptop retailer ID '{retailer_id}' not found!")
            return
        
        # Remove from list
        current_ids.remove(retailer_id)
        update_laptop_excel(current_ids)
        
        whatsapp.send_text(to=phone_number, body=f"✅ Successfully removed laptop retailer ID: {retailer_id}\n\nRemaining laptop IDs: {len(current_ids)}")
        logger.info("Admin %s removed laptop retailer ID: %s", phone_number, retailer_id)
        
    except Exception as e:
        logger.exception("Failed to remove laptop retailer ID")
        whatsapp.send_text(to=phone_number, body=f"❌ Error removing laptop retailer ID: {str(e)}")


def remove_repair_retailer_id(phone_number: str, retailer_id: str):
    """Remove a repair retailer ID from the Excel file."""
    try:
        from catalog_utils import load_repair_retailer_ids
        current_ids = load_repair_retailer_ids()
        
        if retailer_id not in current_ids:
            whatsapp.send_text(to=phone_number, body=f"⚠️ Repair retailer ID '{retailer_id}' not found!")
            return
        
        # Remove from list
        current_ids.remove(retailer_id)
        update_repair_excel(current_ids)
        
        whatsapp.send_text(to=phone_number, body=f"✅ Successfully removed repair retailer ID: {retailer_id}\n\nRemaining repair IDs: {len(current_ids)}")
        logger.info("Admin %s removed repair retailer ID: %s", phone_number, retailer_id)
        
    except Exception as e:
        logger.exception("Failed to remove repair retailer ID")
        whatsapp.send_text(to=phone_number, body=f"❌ Error removing repair retailer ID: {str(e)}")


def list_current_retailer_ids(phone_number: str):
    """List all current retailer IDs for admin."""
    try:
        from catalog_utils import load_laptop_retailer_ids, load_repair_retailer_ids
        laptop_ids = load_laptop_retailer_ids()
        repair_ids = load_repair_retailer_ids()
        
        laptop_list = "\n".join([f"  • {rid}" for rid in laptop_ids]) if laptop_ids else "  (none)"
        repair_list = "\n".join([f"  • {rid}" for rid in repair_ids]) if repair_ids else "  (none)"
        
        message = f"""📋 **Current Retailer IDs**

💻 **Laptops ({len(laptop_ids)} total):**
{laptop_list}

🛠 **Repairs ({len(repair_ids)} total):**
{repair_list}

Use `/add_laptop <id>` or `/add_repair <id>` to add more.
Use `/remove_laptop <id>` or `/remove_repair <id>` to remove."""
        
        whatsapp.send_text(to=phone_number, body=message)
        
    except Exception as e:
        logger.exception("Failed to list retailer IDs")
        whatsapp.send_text(to=phone_number, body=f"❌ Error listing retailer IDs: {str(e)}")


def update_laptop_excel(laptop_ids: List[str]):
    """Update the laptops.xlsx file with new laptop IDs."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    
    # Add header
    ws.append(["retailer_id"])
    
    # Add laptop IDs
    for rid in laptop_ids:
        ws.append([rid])
    
    wb.save("laptops.xlsx")


def update_repair_excel(repair_ids: List[str]):
    """Update the repairs.xlsx file with new repair IDs."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    
    # Add header
    ws.append(["retailer_id"])
    
    # Add repair IDs
    for rid in repair_ids:
        ws.append([rid])
    
    wb.save("repairs.xlsx")


@app.get("/")
def read_root():
    return {"message": "Welcome to SpectraX Laptops WhatsApp Bot!"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    logger.info("Verifying webhook: mode=%s, token=%s", mode, token)

    if token and token == VERIFY_TOKEN:
        logger.info("Token verified successfully.")
        return PlainTextResponse(content=challenge)

    logger.warning("Invalid verify token: %s", token)
    raise HTTPException(status_code=403, detail="Invalid verify token")


@app.post("/webhook")
async def receive_message(request: Request):
    try:
        body = await request.body()
        message = whatsapp.parse(body)

        if isinstance(message, TextMessage):
            # Mark the incoming message as read (safe)
            safe_mark_as_read(message.id)
            
            # Extract text content safely and check admin commands first
            _text = _get_text_content(message)
            if _text and handle_admin_command(message.user.phone_number, _text):
                return {"status": "admin_command_processed"}
            
            # Check if it's admin - send admin welcome instead of regular welcome
            if is_admin(message.user.phone_number):
                send_admin_welcome_message(message.user.phone_number)
            else:
                # Send SpectraX welcome message with quick reply buttons for regular users
                send_welcome_message(message.user.phone_number)

        elif isinstance(message, InteractiveButtonMessage):
            # Mark the incoming message as read (safe)
            safe_mark_as_read(message.id)
            user_choice = message.reply_id
            phone_number = message.user.phone_number
            
            if user_choice == "browse_laptops":
                handle_browse_laptops(phone_number)
            elif user_choice == "browse_collection":
                handle_browse_laptops(phone_number)
            elif user_choice == "why_spectrax":
                send_why_spectrax_message(phone_number)
            elif user_choice == "lifetime_support":
                send_lifetime_support_message(phone_number)
            elif user_choice == "see_collection_from_why":
                handle_browse_laptops(phone_number)
            elif user_choice == "support_from_why":
                send_lifetime_support_message(phone_number)
            elif user_choice == "browse_from_support":
                handle_browse_laptops(phone_number)
            elif user_choice == "how_to_order":
                send_how_to_order_message(phone_number)
            elif user_choice == "register_laptop":
                send_registration_flow(phone_number)
            elif user_choice == "schedule_service":
                send_service_booking_flow(phone_number)
            elif user_choice == "request_video_demo":
                # Run video demo as background task to avoid blocking the webhook response
                asyncio.create_task(handle_video_demo_request(phone_number))
            elif user_choice == "upgrades_accessories":
                send_upgrades_accessories_message(phone_number)
            # new button handlers
            elif user_choice == "action_buy_laptop":
                handle_buy_laptops(phone_number)
            elif user_choice == "action_repairs":
                handle_repairs(phone_number)
            # Admin button handlers
            elif user_choice == "admin_catalog_management":
                send_admin_catalog_menu(phone_number)
            elif user_choice == "admin_order_management":
                send_admin_order_menu(phone_number)
            elif user_choice == "admin_manage_catalog":
                send_admin_catalog_menu(phone_number)
            elif user_choice == "admin_view_stats":
                list_current_retailer_ids(phone_number)
            elif user_choice == "admin_add_laptop":
                send_add_laptop_prompt(phone_number)
            elif user_choice == "admin_add_repair":
                send_add_repair_prompt(phone_number)
            elif user_choice == "admin_remove_laptop":
                send_remove_laptop_menu(phone_number)
            elif user_choice == "admin_remove_repair":
                send_remove_repair_menu(phone_number)
            elif user_choice == "admin_back_main":
                if is_admin(phone_number):
                    send_admin_welcome_message(phone_number)
                else:
                    send_welcome_message(phone_number)
            # Order management handlers (placeholders for now)
            elif user_choice == "admin_recent_orders":
                send_admin_recent_orders(phone_number)
            elif user_choice == "admin_order_status":
                send_admin_order_status_menu(phone_number)
            elif user_choice == "admin_customer_comm":
                send_admin_customer_comm_menu(phone_number)
            elif user_choice == "admin_order_analytics":
                send_admin_order_analytics(phone_number)
            elif user_choice == "admin_delivery_tracking":
                send_admin_delivery_tracking(phone_number)

        elif isinstance(message, OrderMessage):
            # Mark order message as read (safe)
            safe_mark_as_read(message.id)

            # Determine order type based on retailer IDs
            order_type = "Unknown"
            try:
                from catalog_utils import load_laptop_retailer_ids, load_repair_retailer_ids
                laptop_ids = load_laptop_retailer_ids()
                repair_ids = load_repair_retailer_ids()
                
                # Check product retailer IDs to determine order type
                order_retailer_ids = []
                for product in message.products:
                    if hasattr(product, 'product_retailer_id'):
                        order_retailer_ids.append(product.product_retailer_id)
                
                # Determine if it's laptops, repairs, or mixed
                laptop_count = sum(1 for rid in order_retailer_ids if rid in laptop_ids)
                repair_count = sum(1 for rid in order_retailer_ids if rid in repair_ids)
                
                if laptop_count > 0 and repair_count == 0:
                    order_type = "LAPTOP"
                elif repair_count > 0 and laptop_count == 0:
                    order_type = "REPAIR"
                elif laptop_count > 0 and repair_count > 0:
                    order_type = "MIXED (LAPTOP + REPAIR)"
                
            except Exception as e:
                logger.exception("Failed to determine order type: %s", e)

            # Build enhanced order summary
            summary_lines = [
                f"🚨 NEW {order_type} ORDER from {message.user.name} ({message.user.phone_number}):",
                f"Order details: {message.order_text}",
                f"Catalog ID: {message.catalog_id}",
                "📦 Products ordered:",
            ]
            
            total_amount = 0
            for p in message.products:
                # Product is assumed to have title, retail_price, quantity (adjust if structure differs)
                title = getattr(p, "title", getattr(p, "name", "Unnamed"))
                qty = getattr(p, "quantity", getattr(p, "quantity_ordered", 1))
                price = getattr(p, "retail_price", getattr(p, "price", "N/A"))
                retailer_id = getattr(p, "product_retailer_id", "N/A")
                
                if order_type == "LAPTOP":
                    summary_lines.append(f"💻 {title} x{qty} @ {price} (ID: {retailer_id})")
                elif order_type == "REPAIR":
                    summary_lines.append(f"🛠 {title} x{qty} @ {price} (ID: {retailer_id})")
                else:
                    summary_lines.append(f"📦 {title} x{qty} @ {price} (ID: {retailer_id})")
                
                # Try to calculate total if price is numeric
                try:
                    if isinstance(price, (int, float)):
                        total_amount += price * qty
                    elif isinstance(price, str) and price.replace('.', '').isdigit():
                        total_amount += float(price) * qty
                except:
                    pass

            summary_lines.extend([
                "",
                f"💰 **Order Type**: {order_type}",
                f"📊 **Total Items**: {sum(getattr(p, 'quantity', 1) for p in message.products)}",
            ])
            
            if total_amount > 0:
                summary_lines.append(f"💵 **Estimated Total**: ${total_amount:.2f}")

            summary_lines.extend([
                "",
                "⚡ **NEXT STEPS:**",
                "1. Contact customer for payment & delivery",
                "2. Confirm upgrades/accessories if any",
                "3. Schedule laptop registration after delivery" if "LAPTOP" in order_type else "3. Schedule service appointment",
                "4. Provide Starter Essentials software access" if "LAPTOP" in order_type else "4. Provide service tracking info"
            ])

            order_summary = "\n".join(summary_lines)

            # Send order summary to admin
            whatsapp.send_text(to=ADMIN_NUMBER, body=order_summary)

            # Acknowledge customer with appropriate response
            if order_type == "REPAIR":
                customer_response = """🎉 Awesome! We've received your repair service order!

**What happens next:**
1️⃣ Our team will contact you within 30 minutes
2️⃣ Confirm service details & scheduling
3️⃣ Arrange pickup/drop-off or on-site service
4️⃣ Complete service registration for tracking:
   • Real-time repair updates
   • WhatsApp service notifications
   • Priority support access

🛠 **Remember**: Service registration enables tracking and priority support!

Thanks for choosing SpectraX Laptop Services! 🔧✨"""
            else:
                customer_response = """🎉 Awesome! We've received your laptop order!

**What happens next:**
1️⃣ Our team will contact you within 30 minutes
2️⃣ Confirm payment method & delivery details  
3️⃣ Schedule delivery & setup if needed
4️⃣ Complete laptop registration to unlock:
   • FREE Starter Essentials software
   • Lifetime repair tracking
   • WhatsApp tech support

🎁 **Remember**: Registration unlocks amazing benefits, so don't skip this step!

Thanks for choosing SpectraX Laptops! 💻✨"""
            
            whatsapp.send_text(
                to=message.user.phone_number,
                body=customer_response
            )

        return {"status": "processed"}
    except Exception as e:
        logger.error("Error processing message: %s", str(e))
        return {"status": "error", "message": str(e)}


def send_welcome_message(phone_number):
    """Send the initial welcome message with quick reply buttons for laptop offerings"""
    message = """� Welcome to SpectraX Laptops!  
Your trusted partner for premium laptops with lifetime support 🚀  

🎁 **Special Launch Offer**: Buy any laptop → get FREE Starter Essentials software + lifetime repair tracking when registered!

Choose an option below 👇"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="browse_laptops", title="� Browse Laptops"),
            ReplyButton(id="why_spectrax", title="💡 Why SpectraX?"),
            ReplyButton(id="lifetime_support", title="🛡 Lifetime Support"),
        ],
    )


def send_admin_welcome_message(phone_number: str):
    """Send admin welcome message with management options"""
    message = """🔧 **SpectraX Admin Dashboard**

Welcome back, Admin! 👋

**Quick Stats:**
"""
    
    try:
        from catalog_utils import load_laptop_retailer_ids, load_repair_retailer_ids
        laptop_count = len(load_laptop_retailer_ids())
        repair_count = len(load_repair_retailer_ids())
        message += f"💻 Laptop Products: {laptop_count}\n🛠 Repair Services: {repair_count}\n\n"
    except:
        message += "📊 Loading product counts...\n\n"
    
    message += "**Management Areas:**"
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="admin_catalog_management", title="📝 Catalog Management"),
            ReplyButton(id="admin_order_management", title="� Order Management"),
            ReplyButton(id="browse_laptops", title="👀 Preview Store"),
        ],
    )


def send_admin_catalog_menu(phone_number: str):
    """Send admin catalog management menu"""
    message = """📝 **Catalog Management**

Manage your product catalog:

**Product Management:**
• Add new laptop retailer IDs
• Add new repair service IDs
• Remove existing products
• View all current products

**Quick Actions:**"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="admin_add_laptop", title="➕ Add Laptop"),
            ReplyButton(id="admin_add_repair", title="➕ Add Repair"),
            ReplyButton(id="admin_remove_laptop", title="➖ Remove Laptop"),
        ],
    )
    
    # Send second set of buttons
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body="**More Options:**",
        buttons=[
            ReplyButton(id="admin_remove_repair", title="➖ Remove Repair"),
            ReplyButton(id="admin_view_stats", title="📊 View All IDs"),
            ReplyButton(id="admin_back_main", title="⬅️ Back to Main"),
        ],
    )


def send_admin_order_menu(phone_number: str):
    """Send admin order management menu"""
    message = """📦 **Order Management**

Manage customer orders and services:

**Order Status:**
• View recent orders
• Update order status
• Track deliveries
• Manage repairs

**Customer Communication:**
• Send status updates
• Handle inquiries
• Process refunds"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="admin_recent_orders", title="📋 Recent Orders"),
            ReplyButton(id="admin_order_status", title="🔄 Update Status"),
            ReplyButton(id="admin_customer_comm", title="💬 Customer Comm"),
        ],
    )
    
    # Send second set of buttons
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body="**More Options:**",
        buttons=[
            ReplyButton(id="admin_order_analytics", title="📊 Order Analytics"),
            ReplyButton(id="admin_delivery_tracking", title="🚚 Delivery Tracking"),
            ReplyButton(id="admin_back_main", title="⬅️ Back to Main"),
        ],
    )


def send_add_laptop_prompt(phone_number: str):
    """Prompt admin to add laptop retailer ID"""
    message = """➕ **Add Laptop Retailer ID**

To add a new laptop to the catalog, reply with:
`/add_laptop <retailer_id>`

**Example:**
`/add_laptop new_laptop_123`

The new laptop will be immediately available in the catalog! 🚀"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="admin_manage_catalog", title="⬅️ Back to Menu"),
            ReplyButton(id="admin_view_stats", title="📊 View Current IDs"),
        ],
    )


def send_add_repair_prompt(phone_number: str):
    """Prompt admin to add repair retailer ID"""
    message = """➕ **Add Repair Service ID**

To add a new repair service to the catalog, reply with:
`/add_repair <retailer_id>`

**Example:**
`/add_repair new_repair_456`

The new repair service will be immediately available! 🛠"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="admin_manage_catalog", title="⬅️ Back to Menu"),
            ReplyButton(id="admin_view_stats", title="📊 View Current IDs"),
        ],
    )


def send_remove_laptop_menu(phone_number: str):
    """Send menu to remove laptop retailer IDs"""
    try:
        from catalog_utils import load_laptop_retailer_ids
        laptop_ids = load_laptop_retailer_ids()
        
        if not laptop_ids:
            message = "ℹ️ **No Laptop IDs to Remove**\n\nThere are currently no laptop retailer IDs in the system."
            whatsapp.send_interactive_buttons(
                to=phone_number,
                body=message,
                buttons=[ReplyButton(id="admin_manage_catalog", title="⬅️ Back to Menu")],
            )
            return
        
        laptop_list = "\n".join([f"• {rid}" for rid in laptop_ids])
        message = f"""➖ **Remove Laptop Retailer ID**

**Current Laptop IDs:**
{laptop_list}

To remove a laptop, reply with:
`/remove_laptop <retailer_id>`

**Example:**
`/remove_laptop {laptop_ids[0]}`"""
        
        whatsapp.send_interactive_buttons(
            to=phone_number,
            body=message,
            buttons=[
                ReplyButton(id="admin_manage_catalog", title="⬅️ Back to Menu"),
                ReplyButton(id="admin_view_stats", title="📊 View All IDs"),
            ],
        )
        
    except Exception as e:
        logger.exception("Failed to load laptop IDs for removal")
        whatsapp.send_text(to=phone_number, body=f"❌ Error loading laptop IDs: {str(e)}")


def send_remove_repair_menu(phone_number: str):
    """Send menu to remove repair retailer IDs"""
    try:
        from catalog_utils import load_repair_retailer_ids
        repair_ids = load_repair_retailer_ids()
        
        if not repair_ids:
            message = "ℹ️ **No Repair IDs to Remove**\n\nThere are currently no repair retailer IDs in the system."
            whatsapp.send_interactive_buttons(
                to=phone_number,
                body=message,
                buttons=[ReplyButton(id="admin_catalog_management", title="⬅️ Back to Catalog")],
            )
            return
        
        repair_list = "\n".join([f"• {rid}" for rid in repair_ids])
        message = f"""➖ **Remove Repair Service ID**

**Current Repair IDs:**
{repair_list}

To remove a repair service, reply with:
`/remove_repair <retailer_id>`

**Example:**
`/remove_repair {repair_ids[0]}`"""
        
        whatsapp.send_interactive_buttons(
            to=phone_number,
            body=message,
            buttons=[
                ReplyButton(id="admin_catalog_management", title="⬅️ Back to Catalog"),
                ReplyButton(id="admin_view_stats", title="📊 View All IDs"),
            ],
        )
        
    except Exception as e:
        logger.exception("Failed to load repair IDs for removal")
        whatsapp.send_text(to=phone_number, body=f"❌ Error loading repair IDs: {str(e)}")


def send_admin_recent_orders(phone_number: str):
    """Send recent orders overview (placeholder)"""
    message = """📋 **Recent Orders**

**Last 24 Hours:**
• 3 Laptop Orders
• 2 Repair Services
• 1 Mixed Order

**Status Overview:**
✅ 4 Completed
🔄 2 Processing
📦 0 Pending

*Note: Full order management system coming soon!*"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="admin_order_status", title="🔄 Update Status"),
            ReplyButton(id="admin_order_management", title="⬅️ Back to Orders"),
            ReplyButton(id="admin_back_main", title="🏠 Main Menu"),
        ],
    )


def send_admin_order_status_menu(phone_number: str):
    """Send order status update menu (placeholder)"""
    message = """🔄 **Update Order Status**

**Available Status Updates:**
• Order Received → Processing
• Processing → Shipped
• Shipped → Delivered
• Mark as Completed

**Instructions:**
Send order ID with new status to update.

*Example: ORDER123 shipped*

*Note: Advanced status tracking system in development!*"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="admin_recent_orders", title="📋 View Orders"),
            ReplyButton(id="admin_order_management", title="⬅️ Back to Orders"),
        ],
    )


def send_admin_customer_comm_menu(phone_number: str):
    """Send customer communication menu (placeholder)"""
    message = """💬 **Customer Communication**

**Available Actions:**
• Send delivery updates
• Answer product inquiries
• Handle support requests
• Process feedback

**Quick Templates:**
• Order confirmation
• Shipping notification
• Delivery confirmation
• Service completion

*Note: Template system and automation coming soon!*"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="admin_order_analytics", title="📊 View Analytics"),
            ReplyButton(id="admin_order_management", title="⬅️ Back to Orders"),
        ],
    )


def send_admin_order_analytics(phone_number: str):
    """Send order analytics overview (placeholder)"""
    message = """📊 **Order Analytics**

**This Week:**
📈 Total Orders: 15 (+25%)
💰 Revenue: $4,500 (+30%)
⭐ Avg Rating: 4.8/5

**Top Products:**
1. Gaming Laptops (40%)
2. Business Laptops (35%)
3. Repair Services (25%)

**Customer Satisfaction:**
😊 95% Positive Feedback
🔄 5% Return Rate

*Note: Advanced analytics dashboard in development!*"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="admin_delivery_tracking", title="🚚 Delivery Status"),
            ReplyButton(id="admin_order_management", title="⬅️ Back to Orders"),
        ],
    )


def send_admin_delivery_tracking(phone_number: str):
    """Send delivery tracking overview (placeholder)"""
    message = """🚚 **Delivery Tracking**

**Active Deliveries:**
📦 ORDER123 - En route (ETA: 2 hours)
📦 ORDER124 - Preparing for dispatch
📦 ORDER125 - Out for delivery

**Delivery Stats:**
✅ 95% On-time delivery
🕐 Avg delivery time: 24 hours
📍 Coverage: All major cities

**Next Actions:**
• Update delivery status
• Contact delivery partner
• Handle delivery issues

*Note: Real-time tracking integration coming soon!*"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="admin_customer_comm", title="💬 Customer Updates"),
            ReplyButton(id="admin_order_management", title="⬅️ Back to Orders"),
        ],
    )


def send_buy_repairs_buttons(phone_number: str):
    """Send two reply buttons: Buy Laptop and Repairs (reuses existing ReplyButton pattern)."""
    body = "Choose an option:\n\n🛒 Buy Laptop — view laptops to purchase\n🛠 Repairs — view repair offering"
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=body,
        buttons=[
            ReplyButton(id="action_buy_laptop", title="🛒 Buy Laptop"),
            ReplyButton(id="action_repairs", title="🛠 Repairs"),
        ],
    )


def handle_browse_laptops(phone_number):
    """Show Buy / Repairs choices instead of immediately sending the catalog."""
    send_buy_repairs_buttons(phone_number)


# Delegate catalog handling to separate modules
try:
    from laptops import handle_buy_laptops as _handle_buy_laptops_module
    from repairs import handle_repairs as _handle_repairs_module
except Exception:
    _handle_buy_laptops_module = None
    _handle_repairs_module = None


def handle_buy_laptops(phone_number: str):
    """Delegate to laptops module if available, otherwise fall back to inline implementation."""
    if _handle_buy_laptops_module:
        return _handle_buy_laptops_module(whatsapp, phone_number, catalog_id=CATALOG_ID)

    # Fallback: load laptop IDs from separate Excel file
    from catalog_utils import load_laptop_retailer_ids
    laptop_ids = load_laptop_retailer_ids()
    if not laptop_ids:
        laptop_ids = _env_retailer_ids("PRODUCT_RETAILER_ID", "PRODUCT_RETAILER_ID_2")

    if not laptop_ids:
        logger.warning("No laptop retailer IDs configured (env or excel)")
        whatsapp.send_interactive_buttons(
            to=phone_number,
            body="No laptops are configured right now. Contact support to add products.",
            buttons=[ReplyButton(id="contact_support", title="Contact Support")],
        )
        return

    header = "SpectraX Laptop Catalog"
    body = "💻 Browse our featured laptops. Each purchase includes FREE Starter Essentials software + lifetime repair tracking when registered."
    footer = "Tap a laptop to view details & order."

    try:
        # Use the safe catalog compatibility function
        from catalog_utils import send_catalog_compat
        send_catalog_compat(
            whatsapp=whatsapp,
            to=phone_number,
            retailer_ids=laptop_ids,
            header=header,
            body=body,
            footer=footer,
            catalog_id=CATALOG_ID,
            fallback_button_id="browse_laptops"
        )
    except Exception as exc:
        logger.exception("Failed sending laptop catalog: %s", exc)
        whatsapp.send_interactive_buttons(
            to=phone_number,
            body="Sorry, something went wrong while fetching the catalog. Try again later.",
            buttons=[ReplyButton(id="try_again", title="Try Again")],
        )


def handle_repairs(phone_number: str):
    """Delegate to repairs module if available, otherwise fall back to inline implementation."""
    if _handle_repairs_module:
        return _handle_repairs_module(whatsapp, phone_number, catalog_id=CATALOG_ID)

    # Fallback: load repair IDs from separate Excel file
    from catalog_utils import load_repair_retailer_ids
    repair_ids = load_repair_retailer_ids()
    if not repair_ids:
        repair_ids = _env_retailer_ids("PRODUCT_RETAILER_ID_REPAIR", "PRODUCT_RETAILER_ID_REPAIR_2")

    if not repair_ids:
        logger.warning("No repair retailer IDs configured (env or excel)")
        whatsapp.send_interactive_buttons(
            to=phone_number,
            body="No repair packages are configured right now. Contact support to add products.",
            buttons=[ReplyButton(id="contact_support", title="Contact Support")],
        )
        return

    header = "SpectraX Repair Packages"
    body = "🛠 Choose a repair package. Includes diagnostics and software cleanup when registered."
    footer = "Tap a repair package to view details & book."

    try:
        # Use the safe catalog compatibility function
        from catalog_utils import send_catalog_compat
        send_catalog_compat(
            whatsapp=whatsapp,
            to=phone_number,
            retailer_ids=repair_ids,
            header=header,
            body=body,
            footer=footer,
            catalog_id=CATALOG_ID,
            fallback_button_id="browse_repairs"
        )
    except Exception as exc:
        logger.exception("Failed sending repair catalog: %s", exc)
        whatsapp.send_interactive_buttons(
            to=phone_number,
            body="Sorry, something went wrong while fetching repair packages. Try again later.",
            buttons=[ReplyButton(id="try_again", title="Try Again")],
        )


def send_why_spectrax_message(phone_number: str):
    """Send why choose SpectraX Laptops message"""
    message = """✨ Why SpectraX Laptops?  
Because we don't just sell laptops — we provide a complete ecosystem for your digital success.  

✅ Premium laptop models with latest specs  
✅ FREE Starter Essentials software suite  
✅ Lifetime repair tracking & support  
✅ Real-time service updates via WhatsApp  
✅ Professional consultancy services  
✅ Trust & peace of mind in Zimbabwe  

🎯 **The Promise**: Your laptop + our expertise = unstoppable productivity!

Ready to explore? 👇"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message,
        buttons=[
            ReplyButton(id="browse_laptops", title="💻 Browse Laptops"),
            ReplyButton(id="lifetime_support", title="🛡 Lifetime Support"),
        ],
    )


def send_lifetime_support_message(phone_number: str):
    """Send the lifetime support & benefits message with follow-up buttons"""
    message_body = """🎁 SpectraX Lifetime Support Package (Included with Registration)

**🔧 Lifetime Repair Services:**
• Dust cleaning & hardware maintenance
• Software troubleshooting & optimization
• Real-time repair tracking via WhatsApp
• Professional diagnostics & consultation

**💾 FREE Starter Essentials Software:**
• Microsoft Office alternatives
• Antivirus & security suite
• Photo/video editing tools
• Productivity & organization apps

**⚡ Premium Add-ons Available:**
• RAM/SSD upgrades during service
• Custom software installations
• Performance optimization packages
• Advanced business consultation

**📱 WhatsApp Integration:**
• Schedule services instantly
• Real-time repair updates
• Direct tech support chat
• Order tracking & notifications

✅ **Registration unlocks everything!** Simple, free, and gives you access to our complete ecosystem."""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message_body,
        buttons=[
            ReplyButton(id="browse_laptops", title="💻 Browse Laptops"),
            ReplyButton(id="register_laptop", title="� Register Laptop"),
            ReplyButton(id="schedule_service", title="🔧 Schedule Service"),
        ],
    )


def send_how_to_order_message(phone_number: str):
    """Send how to order information for laptops"""
    message_body = """How to Order Your SpectraX Laptop �

1️⃣ Tap "Browse Laptops" to view our catalog.

2️⃣ Click on any laptop model to see full specs.

3️⃣ Review features, RAM, storage, and pricing.

4️⃣ Tap "Add to Cart" for your chosen model.

5️⃣ Consider optional upgrades:
   • RAM/SSD upgrades
   • Premium software packages  
   • Accessories (bag, mouse, keyboard)
   • Extended warranty

6️⃣ Go to "View Cart" to review your order.

7️⃣ Adjust quantity and add-ons if needed.

8️⃣ Tap "Place Order" to confirm.

✅ You'll see "Order Successful", and we'll contact you shortly to finalize delivery, payment & schedule your FREE laptop registration!

🎁 **Don't forget**: Registration unlocks your FREE Starter Essentials software + lifetime repair tracking!

🎥 Want to see the ordering process?
Just tap below for a quick video demonstration."""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message_body,
        buttons=[
            ReplyButton(id="request_video_demo", title="🎥 Video Demo"),
            ReplyButton(id="browse_laptops", title="� Browse Laptops"),
        ],
    )


async def handle_video_demo_request(phone_number: str):
    """Handle video demo request for laptop ordering"""
    video_url = f"{PUBLIC_URL}/static/BUY_V1_Pro.mp4"
    
    # Send the video first
    whatsapp.send_video(
        to=phone_number,
        url=video_url,
        caption="🎥 Here's your SpectraX Laptop ordering demo!\n\nWatch how easy it is to browse laptops, select upgrades, and place your order through WhatsApp. �✨\n\nReady to get yours? Just tap 'Browse Laptops' below! 🛒",
    )
    
    # Wait 15 seconds before sending follow-up message
    await asyncio.sleep(15)
    
    # Send follow-up message with action buttons
    follow_up_message = """🎉 Thanks for watching the ordering demo! Getting your perfect laptop with lifetime support is super simple.

You can now click Browse Laptops below to explore our collection.
Don't forget - registration unlocks FREE software & lifetime repairs!

👇 Choose an option to continue:"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=follow_up_message,
        buttons=[
            ReplyButton(id="browse_laptops", title="💻 Browse Laptops"),
            ReplyButton(id="why_spectrax", title="💡 Why SpectraX?"),
            ReplyButton(id="lifetime_support", title="🛡 Lifetime Support"),
        ],
    )


def send_upgrades_accessories_message(phone_number: str):
    """Send upgrades and accessories options"""
    message_body = """⚡ Available Upgrades & Accessories

**🔧 Hardware Upgrades:**
• RAM upgrades (8GB → 16GB → 32GB)
• SSD storage upgrades (256GB → 512GB → 1TB)
• Performance optimization packages

**💾 Software Packages:**
• Premium productivity suites
• Creative software bundles
• Business & accounting tools
• Security & backup solutions

**🎒 Essential Accessories:**
• Premium laptop bags & cases
• Wireless mice & keyboards
• Cooling pads & stands
• External monitors & adapters

**🛡 Protection & Warranty:**
• Extended warranty (2-3 years)
• Accidental damage protection
• Insurance packages

💡 **Pro Tip**: Upgrades during purchase save you time and money!

Want to see the full laptop catalog with upgrade options?"""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message_body,
        buttons=[
            ReplyButton(id="browse_laptops", title="💻 View Catalog"),
            ReplyButton(id="lifetime_support", title="🛡 Support Info"),
            ReplyButton(id="how_to_order", title="💳 How to Order"),
        ],
    )


def send_registration_flow(phone_number: str):
    """Send laptop registration information and process"""
    message_body = """📝 Laptop Registration - Unlock Your Benefits!

**Why Register Your Laptop?**
✅ Activates FREE Starter Essentials software suite
✅ Enables lifetime repair tracking
✅ Unlocks WhatsApp-based tech support
✅ Qualifies for priority service booking
✅ Access to exclusive upgrade offers

**What You Need:**
• Your laptop model & serial number
• Purchase receipt/order confirmation
• Your contact details

**Registration Process:**
1️⃣ Take a photo of your laptop's serial number sticker
2️⃣ Send it via WhatsApp with your order details
3️⃣ We'll confirm and activate your benefits
4️⃣ Receive your software download links
5️⃣ Start enjoying lifetime support!

**Already purchased a laptop?** 
Send us your order details and we'll help you register immediately!

**Haven't purchased yet?**
Browse our collection and registration will be included in your purchase process."""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message_body,
        buttons=[
            ReplyButton(id="browse_laptops", title="� Browse First"),
            ReplyButton(id="schedule_service", title="🔧 Need Service?"),
            ReplyButton(id="lifetime_support", title="🛡 Support Details"),
        ],
    )


def send_service_booking_flow(phone_number: str):
    """Send service booking options and process"""
    message_body = """🔧 Schedule Laptop Service & Support

**Available Services:**
• Software troubleshooting & optimization
• Hardware cleaning & maintenance  
• RAM/SSD upgrade installations
• Virus removal & security setup
• Custom software installations
• Performance diagnostics
• Business consultation services

**Service Types:**
🏠 **On-site Service** - We come to you
🏢 **Workshop Service** - Drop-off for detailed work
� **Remote Support** - Via WhatsApp/video call
📞 **Consultation** - Technical advice & planning

**How to Book:**
1️⃣ Describe your issue or service needed
2️⃣ Choose service type (on-site/workshop/remote)
3️⃣ Select preferred date & time
4️⃣ Confirm booking details
5️⃣ Receive confirmation & tracking info

**For Registered Laptops:** 
Many services are FREE or heavily discounted!

**Need help now?**
Just reply with your laptop issue and we'll guide you through the next steps."""
    
    whatsapp.send_interactive_buttons(
        to=phone_number,
        body=message_body,
        buttons=[
            ReplyButton(id="register_laptop", title="📝 Register First"),
            ReplyButton(id="browse_laptops", title="💻 Browse Laptops"),
            ReplyButton(id="lifetime_support", title="🛡 Support Info"),
        ],
    )


def _get_text_content(msg) -> Optional[str]:
    """Best-effort extraction of text content from a TextMessage.
    Tries common fields: msg.text (str or object with .body), msg.body, dict-like access.
    Returns None if not found.
    """
    try:
        # direct string
        val = getattr(msg, "text", None)
        if isinstance(val, str) and val.strip():
            return val.strip()
        # object with body attribute
        if hasattr(val, "body"):
            b = getattr(val, "body")
            if isinstance(b, str) and b.strip():
                return b.strip()
        # some SDKs expose .body directly
        body = getattr(msg, "body", None)
        if isinstance(body, str) and body.strip():
            return body.strip()
        # dict-like text
        if isinstance(val, dict):
            b2 = val.get("body")
            if isinstance(b2, str) and b2.strip():
                return b2.strip()
    except Exception:
        pass
    return None


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
