# -*- coding: utf-8 -*-
from odoo import api, fields, models


class OtmWhatsappMessage(models.Model):
    """The ONE inheritance hook into the base module (matches the same
    pattern used by otm_whatsapp_chatbot - zero edits to the base module's
    own files from this module). Adds the campaign link, and after the base
    module's own idempotent process_status_update() applies a delivery/read/
    failed status from a Meta webhook, mirrors that state onto the campaign
    recipient row so campaign stats/UI reflect real delivery status without
    a second, parallel webhook-processing path."""

    _inherit = "otm.whatsapp.message"

    campaign_id = fields.Many2one(
        "otm.whatsapp.campaign", string="Campaign", index=True, ondelete="set null"
    )
    campaign_recipient_id = fields.Many2one(
        "otm.whatsapp.campaign.recipient",
        string="Campaign Recipient",
        index=True,
        ondelete="set null",
    )

    @api.model
    def process_status_update(self, status):
        message = super().process_status_update(status)
        if message and message.campaign_recipient_id and message.state in (
            "delivered", "read", "failed",
        ):
            vals = {"state": message.state}
            if message.state == "failed":
                vals["error_message"] = message.error_message
            message.campaign_recipient_id.write(vals)
        return message
