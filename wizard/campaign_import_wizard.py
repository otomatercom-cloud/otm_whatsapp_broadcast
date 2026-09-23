# -*- coding: utf-8 -*-
from odoo import fields, models


class OtmWhatsappCampaignImportWizard(models.TransientModel):
    """Paste-a-list recipient import - matches or creates otm.whatsapp.contact
    records via the base module's own normalize_phone()/search pattern
    (never a raw create, so re-importing the same list is safe and never
    duplicates a contact)."""

    _name = "otm.whatsapp.campaign.import.wizard"
    _description = "Import WhatsApp Campaign Recipients"

    campaign_id = fields.Many2one("otm.whatsapp.campaign", required=True)
    numbers_text = fields.Text(
        string="Phone Numbers",
        required=True,
        help="One recipient per line. Either just a phone number, or "
        "'phone,Name' to also set the contact's name, e.g.:\n"
        "919876543210,Anjali Menon\n919876500000",
    )

    def action_import(self):
        self.ensure_one()
        Contact = self.env["otm.whatsapp.contact"]
        contacts = self.campaign_id.contact_ids
        for line in (self.numbers_text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",", 1)]
            phone = parts[0]
            name = parts[1] if len(parts) > 1 and parts[1] else phone
            if not phone:
                continue
            normalized = Contact.normalize_phone(phone)
            if not normalized:
                continue
            contact = Contact.search([("normalized_phone", "=", normalized)], limit=1)
            if not contact:
                contact = Contact.create({"name": name, "phone": phone})
            contacts |= contact
        self.campaign_id.write({"contact_ids": [(6, 0, contacts.ids)]})
        self.campaign_id.action_build_recipients()
        return {"type": "ir.actions.act_window_close"}
