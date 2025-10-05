import logging
from typing import Optional
from catalog_utils import load_repair_retailer_ids, env_retailer_ids, send_catalog_compat
from wa_cloud_py.components.messages import ReplyButton

logger = logging.getLogger(__name__)


def handle_repairs(whatsapp, phone_number: str, catalog_id: Optional[str] = None):
    # Load repair retailer IDs from repairs.xlsx
    repair_ids = load_repair_retailer_ids()
    
    # Fall back to environment variables if Excel file is empty
    if not repair_ids:
        repair_ids = env_retailer_ids("PRODUCT_RETAILER_ID_REPAIR", "PRODUCT_RETAILER_ID_REPAIR_2")

    if not repair_ids:
        logger.warning("No repair retailer IDs configured (excel or env)")
        try:
            whatsapp.send_interactive_buttons(
                to=phone_number,
                body="No repair packages are configured right now. Contact support to add products.",
                buttons=[ReplyButton(id="contact_support", title="Contact Support")],
            )
        except Exception:
            logger.exception("Failed to send no-configured-repairs message")
        return

    header = "SpectraX Repair Packages"
    body = "🛠 Choose a repair package. Includes diagnostics and software cleanup when registered."
    footer = "Tap a repair package to view details & book."

    logger.info("Sending repair catalog with IDs: %s", repair_ids)
    try:
        send_catalog_compat(whatsapp, to=phone_number, retailer_ids=repair_ids, header=header, body=body, footer=footer, catalog_id=catalog_id, fallback_button_id="browse_repairs")
    except Exception as exc:
        logger.exception("Failed sending repair catalog: %s", exc)
        try:
            whatsapp.send_interactive_buttons(
                to=phone_number,
                body="Sorry, something went wrong while fetching repair packages. Try again later.",
                buttons=[ReplyButton(id="try_again", title="Try Again")],
            )
        except Exception:
            logger.exception("Failed to send failure message")
