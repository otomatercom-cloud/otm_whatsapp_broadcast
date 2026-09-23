# -*- coding: utf-8 -*-
{
    "name": "Otomater WhatsApp Bulk Broadcast",
    "version": "19.0.1.0.0",
    "category": "Customizations",
    "summary": "Bulk/campaign WhatsApp broadcast messaging (AiSensy-style) on top of otm_whatsapp_coexistence",
    "description": """
Otomater WhatsApp Bulk Broadcast
=================================
Send a single approved Meta WhatsApp template message to many contacts at
once - campaigns, promotions, batch notifications - built entirely on top
of otm_whatsapp_coexistence's real infrastructure:

* Reuses otm.whatsapp.message / otm.whatsapp.contact / otm.whatsapp.template
  / otm.whatsapp.phone as-is - zero edits to those files, only one
  inheritance hook (adds campaign_id to otm.whatsapp.message, and syncs
  delivery/read status back onto the campaign recipient).
* Per-recipient template personalization ({{1}}, {{2}}, ... body variables
  mapped from contact name/phone/profile name or static text).
* Rate-limited sending (configurable messages/minute) via a dedicated cron,
  so a campaign never blasts past Meta's throughput/quality-rating limits.
* Schedule for later or send now; pause/resume/cancel a running campaign.
* Respects each contact's WhatsApp opt-in/opt-out status automatically.
* Paste-a-list recipient import wizard (matches/creates otm.whatsapp.contact
  records via the base module's own get_or_create, so no duplicate contacts).
* Live per-campaign stats: pending / sent / delivered / read / failed.

Only sends APPROVED Meta templates via the official Cloud API (through the
base module's own client) - this is a requirement of Meta's own platform
for any business-initiated/bulk message, not a limitation of this module.
""",
    "author": "Otomater",
    "website": "https://otomater.com",
    "license": "OPL-1",
    "depends": ["base", "mail", "otm_whatsapp_coexistence"],
    "data": [
        "security/ir.model.access.csv",
        "security/whatsapp_broadcast_security_rules.xml",
        "data/ir_cron_data.xml",
        # campaign_import_wizard_views.xml MUST load before
        # whatsapp_campaign_views.xml: the campaign form's button uses
        # %(action_whatsapp_campaign_import_wizard)d, and Odoo resolves a
        # %(xmlid)d reference EAGERLY during XML parsing (odoo/tools/
        # convert.py's _eval_xml -> id_get), not lazily at click time - the
        # action record must already exist in ir.model.data by the time
        # this file is parsed, or install fails with "External ID not
        # found in the system". Confirmed via a real install error on
        # hrms.logiceducation.org.
        "views/campaign_import_wizard_views.xml",
        "views/whatsapp_campaign_views.xml",
        "views/whatsapp_menus.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
