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
import time


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


def safe_mark_as_read(message_id: str):
    """Safely mark a WhatsApp message as read; swallow and log errors from the API.

    Some incoming webhook messages reference message IDs that cannot be marked as
    read (for example, legacy or unsupported IDs). Calling the API with an invalid
    ID raises an OAuthException; we log it and continue so the webhook stays healthy.
    """
    try:
        whatsapp.mark_as_read(message_id)
    except Exception as exc:
        # Log full exception for debugging but don't raise — webhook should respond 200
        logger.warning("Failed to mark message with ID %s as read. Reason: %s", message_id, str(exc))


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
            # Send SpectraX welcome message with quick reply buttons
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

        elif isinstance(message, OrderMessage):
            # Mark order message as read (safe)
            safe_mark_as_read(message.id)

            # Build order summary
            summary_lines = [
                f"🚨 NEW LAPTOP ORDER from {message.user.name} ({message.user.phone_number}):",
                f"Order details: {message.order_text}",
                f"Catalog ID: {message.catalog_id}",
                "📦 Products ordered:",
            ]
            for p in message.products:
                # Product is assumed to have title, retail_price, quantity (adjust if structure differs)
                title = getattr(p, "title", getattr(p, "name", "Unnamed"))
                qty = getattr(p, "quantity", getattr(p, "quantity_ordered", 1))
                price = getattr(p, "retail_price", getattr(p, "price", "N/A"))
                summary_lines.append(f"💻 {title} x{qty} @ {price}")

            summary_lines.extend([
                "",
                "⚡ NEXT STEPS:",
                "1. Contact customer for payment & delivery",
                "2. Confirm upgrades/accessories if any",
                "3. Schedule laptop registration after delivery",
                "4. Provide Starter Essentials software access"
            ])

            order_summary = "\n".join(summary_lines)

            # Send order summary to admin
            ADMIN_NUMBER = "263711475883"
            whatsapp.send_text(to=ADMIN_NUMBER, body=order_summary)

            # Acknowledge customer with registration info
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


def handle_buy_laptops(phone_number: str):
    """Send a single product_list catalog message containing the configured laptop products."""
    retailer_ids = [PRODUCT_RETAILER_ID, PRODUCT_RETAILER_ID_2]
    retailer_ids = [rid for rid in retailer_ids if rid]

    if not retailer_ids:
        whatsapp.send_text(to=phone_number, body="No laptop products configured. Please contact support.")
        return

    header = "SpectraX Laptop Catalog"
    body = "💻 Browse our featured laptops. Each purchase includes FREE Starter Essentials software + lifetime repair tracking when registered."
    footer = "Tap a laptop to view details & order."

    try:
        wa_section = CatalogSection(title="Featured Laptops", retailer_product_ids=retailer_ids)
        whatsapp.send_catalog_product_list(
            to=phone_number,
            catalog_id=CATALOG_ID,
            header=header,
            body=body,
            product_sections=[wa_section],
            footer=footer,
        )
    except Exception as exc:
        logger.warning("send_catalog_product_list failed for laptops: %s", str(exc))
        # fallback: send individual product messages
        for rid in retailer_ids:
            try:
                whatsapp.send_catalog_product(
                    to=phone_number,
                    product_retailer_id=rid,
                    catalog_id=CATALOG_ID,
                    body="💻 Tap to view details & order.",
                    footer=footer,
                )
            except Exception as e:
                logger.warning("Fallback send_catalog_product failed for %s: %s", rid, str(e))
        whatsapp.send_catalog(to=phone_number, body="💻 Browse our laptop collection:", footer=footer)


def handle_repairs(phone_number: str):
    """Send a single product_list catalog message containing the configured repair products."""
    repair_ids = [PRODUCT_RETAILER_ID_REPAIR, PRODUCT_RETAILER_ID_REPAIR_2]
    repair_ids = [rid for rid in repair_ids if rid]

    if not repair_ids:
        whatsapp.send_text(to=phone_number, body="No repair products configured. Please contact support.")
        return

    header = "SpectraX Repair Packages"
    body = "🛠 Choose a repair package. Includes diagnostics and software cleanup when registered."
    footer = "Tap a repair package to view details & book."

    try:
        wa_section = CatalogSection(title="Repairs & Services", retailer_product_ids=repair_ids)
        whatsapp.send_catalog_product_list(
            to=phone_number,
            catalog_id=CATALOG_ID,
            header=header,
            body=body,
            product_sections=[wa_section],
            footer=footer,
        )
    except Exception as exc:
        logger.warning("send_catalog_product_list failed for repairs: %s", str(exc))
        # fallback: send individual product messages
        for rid in repair_ids:
            try:
                whatsapp.send_catalog_product(
                    to=phone_number,
                    product_retailer_id=rid,
                    catalog_id=CATALOG_ID,
                    body="🛠 Tap to view details & book.",
                    footer=footer,
                )
            except Exception as e:
                logger.warning("Fallback send_catalog_product failed for %s: %s", rid, str(e))
        whatsapp.send_text(to=phone_number, body="Repairs items unavailable right now. Please contact support.")


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


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
