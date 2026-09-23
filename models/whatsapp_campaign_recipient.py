# -*- coding: utf-8 -*-
from odoo import fields, models


class OtmWhatsappCampaignRecipient(models.Model):
    _name = "otm.whatsapp.campaign.recipient"
    _description = "WhatsApp Campaign Recipient"
    _order = "id"
    _rec_name = "contact_id"

    campaign_id = fields.Many2one(
        "otm.whatsapp.campaign", required=True, ondelete="cascade", index=True
    )
    contact_id = fields.Many2one(
        "otm.whatsapp.contact", required=True, ondelete="restrict", index=True
    )
    message_id = fields.Many2one("otm.whatsapp.message", string="Sent Message", readonly=True)
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("queued", "Queued"),
            ("sent", "Sent"),
            ("delivered", "Delivered"),
            ("read", "Read"),
            ("failed", "Failed"),
            ("skipped", "Skipped"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    error_message = fields.Text(readonly=True)

    _campaign_contact_uniq = models.Constraint(
        "unique(campaign_id, contact_id)",
        "This contact is already a recipient of this campaign.",
    )
