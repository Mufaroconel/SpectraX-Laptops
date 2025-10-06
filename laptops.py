import logging
from typing import Optional
from catalog_utils import load_laptop_retailer_ids, env_retailer_ids, send_catalog_compat
from wa_cloud_py.components.messages import ReplyButton

logger = logging.getLogger(__name__)


def handle_buy_laptops(whatsapp, phone_number: str, catalog_id: Optional[str] = None):
    # Load laptop retailer IDs from laptops.xlsx
    laptop_ids = load_laptop_retailer_ids()
    
    # Fall back to environment variables if Excel file is empty
    if not laptop_ids:
        laptop_ids = env_retailer_ids("PRODUCT_RETAILER_ID", "PRODUCT_RETAILER_ID_2")

    if not laptop_ids:
        logger.warning("No laptop retailer IDs configured (excel or env)")
        try:
            whatsapp.send_interactive_buttons(
                to=phone_number,
                body="No laptops are configured right now. Contact support to add products.",
                buttons=[ReplyButton(id="contact_support", title="Contact Support")],
            )
        except Exception:
            logger.exception("Failed to send no-configured-laptops message")
        return

    header = "🔥 SpectraX Laptop Lineup"
    body = (
        "💻 Power that lasts. Protection that never quits.\n\n"
        "Every SpectraX laptop comes with:\n"
        "✨ FREE Starter Essentials pack\n"
        "🛠️ Lifetime Repair Coverage — pay only for parts, software fixes are free\n"
        "🚀 Ongoing updates to keep your laptop blazing fast & secure."
    )
    footer = "👇 Tap to view your next-level laptop."

    logger.info("Sending laptop catalog with IDs: %s", laptop_ids)
    try:
        send_catalog_compat(whatsapp, to=phone_number, retailer_ids=laptop_ids, header=header, body=body, footer=footer, catalog_id=catalog_id, fallback_button_id="browse_laptops")
    except Exception as exc:
        logger.exception("Failed sending laptop catalog: %s", exc)
        try:
            whatsapp.send_interactive_buttons(
                to=phone_number,
                body="Sorry, something went wrong while fetching the catalog. Try again later.",
                buttons=[ReplyButton(id="try_again", title="Try Again")],
            )
        except Exception:
            logger.exception("Failed to send failure message")
