# -*- coding: utf-8 -*-
from odoo import fields, models


class OtmWhatsappCampaignVariable(models.Model):
    """One row per {{n}} body placeholder in the campaign's chosen template.
    `sequence` is the placeholder position (1-indexed, matching Meta's
    {{1}}, {{2}}, ... numbering)."""

    _name = "otm.whatsapp.campaign.variable"
    _description = "WhatsApp Campaign Template Variable"
    _order = "sequence"

    campaign_id = fields.Many2one(
        "otm.whatsapp.campaign", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(required=True, default=1)
    source = fields.Selection(
        [
            ("contact_name", "Contact Name"),
            ("contact_phone", "Phone Number"),
            ("profile_name", "WhatsApp Profile Name"),
            ("static", "Static Text"),
        ],
        required=True,
        default="static",
    )
    static_value = fields.Char(
        string="Static Value",
        help="Used when Source = Static Text. Sent as-is for every recipient.",
    )
