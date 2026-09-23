# -*- coding: utf-8 -*-
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class OtmWhatsappCampaign(models.Model):
    _name = "otm.whatsapp.campaign"
    _description = "WhatsApp Bulk Broadcast Campaign"
    _inherit = ["mail.thread"]
    _order = "create_date desc"
    _rec_name = "name"

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(related="phone_id.company_id", store=True, index=True)

    phone_id = fields.Many2one(
        "otm.whatsapp.phone", string="Send From", required=True, tracking=True,
        domain=[("status", "=", "connected")],
        help="The connected WhatsApp number this campaign sends from.",
    )
    integration_id = fields.Many2one(related="phone_id.integration_id", store=True)
    template_id = fields.Many2one(
        "otm.whatsapp.template", string="Template", required=True, tracking=True,
        domain="[('integration_id', '=', integration_id), ('status', '=', 'approved')]",
        help="Only an APPROVED Meta template can be used for a bulk/business-initiated send.",
    )

    contact_ids = fields.Many2many(
        "otm.whatsapp.contact", string="Recipients",
        help="Add contacts directly, or use the Import wizard to add by phone number.",
    )
    exclude_opted_out = fields.Boolean(
        default=True,
        help="Never send to a contact whose WhatsApp opt-in status is 'Opted Out', "
        "even if manually added here.",
    )

    variable_ids = fields.One2many(
        "otm.whatsapp.campaign.variable", "campaign_id", string="Template Variables"
    )
    header_param_static = fields.Char(
        string="Header Value",
        help="Only needed if the chosen template's header itself has a {{1}} "
        "placeholder. Sent as-is for every recipient.",
    )

    recipient_ids = fields.One2many(
        "otm.whatsapp.campaign.recipient", "campaign_id", string="Recipients (Built)"
    )

    scheduled_at = fields.Datetime(
        string="Scheduled At", tracking=True,
        help="Leave empty and use 'Send Now' to start immediately instead of scheduling.",
    )
    rate_limit_per_minute = fields.Integer(
        string="Rate Limit (msgs/min)", default=60,
        help="How many messages this campaign sends per minute. Keep this conservative "
        "(Meta throttles by tier and this also protects your number's quality rating).",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("scheduled", "Scheduled"),
            ("sending", "Sending"),
            ("paused", "Paused"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    start_date = fields.Datetime(readonly=True)
    end_date = fields.Datetime(readonly=True)

    total_count = fields.Integer(compute="_compute_stats")
    pending_count = fields.Integer(compute="_compute_stats")
    sent_count = fields.Integer(compute="_compute_stats")
    delivered_count = fields.Integer(compute="_compute_stats")
    read_count = fields.Integer(compute="_compute_stats")
    failed_count = fields.Integer(compute="_compute_stats")

    @api.depends("recipient_ids.state")
    def _compute_stats(self):
        for rec in self:
            recipients = rec.recipient_ids
            rec.total_count = len(recipients)
            rec.pending_count = len(recipients.filtered(lambda r: r.state == "pending"))
            rec.sent_count = len(recipients.filtered(lambda r: r.state == "sent"))
            rec.delivered_count = len(recipients.filtered(lambda r: r.state == "delivered"))
            rec.read_count = len(recipients.filtered(lambda r: r.state == "read"))
            rec.failed_count = len(
                recipients.filtered(lambda r: r.state in ("failed", "skipped"))
            )

    # ------------------------------------------------------------------
    # Recipient / variable building
    # ------------------------------------------------------------------
    def action_build_recipients(self):
        """Idempotent: only adds recipient rows for contacts not already
        present (unique(campaign_id, contact_id) also guards this at the
        DB level), so this can safely be re-run after adding more contacts."""
        Recipient = self.env["otm.whatsapp.campaign.recipient"]
        for campaign in self:
            existing_ids = set(campaign.recipient_ids.mapped("contact_id").ids)
            contacts = campaign.contact_ids.filtered(lambda c: c.id not in existing_ids)
            if campaign.exclude_opted_out:
                contacts = contacts.filtered(lambda c: c.opt_in_status != "opted_out")
            vals_list = [
                {"campaign_id": campaign.id, "contact_id": c.id, "state": "pending"}
                for c in contacts
            ]
            if vals_list:
                Recipient.create(vals_list)
        return True

    def action_sync_variables(self):
        """Resizes variable_ids to match the chosen template's variable_count
        (parsed from Meta's real template definition - see
        otm.whatsapp.template._parse_components_meta in the base module)."""
        Variable = self.env["otm.whatsapp.campaign.variable"]
        for campaign in self:
            needed = campaign.template_id.variable_count or 0
            current = campaign.variable_ids.sorted("sequence")
            if len(current) > needed:
                current[needed:].unlink()
                current = current[:needed]
            for seq in range(len(current) + 1, needed + 1):
                Variable.create(
                    {"campaign_id": campaign.id, "sequence": seq, "source": "static", "static_value": ""}
                )
        return True

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def _check_ready_to_send(self):
        self.ensure_one()
        if not self.template_id or self.template_id.status != "approved":
            raise UserError(_("Select an approved WhatsApp template before sending."))
        if self.phone_id.status != "connected":
            raise UserError(_("The selected WhatsApp number is not connected."))
        if not self.recipient_ids:
            self.action_build_recipients()
        if not self.recipient_ids:
            raise UserError(_("This campaign has no recipients. Add contacts first."))

    def action_schedule(self):
        for campaign in self:
            if not campaign.scheduled_at:
                raise UserError(_("Set a scheduled date/time first, or use Send Now."))
            if campaign.scheduled_at <= fields.Datetime.now():
                raise UserError(_("Scheduled time must be in the future."))
            campaign._check_ready_to_send()
            campaign.write({"state": "scheduled"})
        return True

    def action_start(self):
        """'Send Now' - starts sending immediately (state='sending'); the
        rate-limited cron then dispatches the actual batches, exactly like
        a scheduled campaign whose time has arrived."""
        for campaign in self:
            if campaign.state not in ("draft", "scheduled", "paused"):
                raise UserError(_("Only a draft, scheduled or paused campaign can be started."))
            campaign._check_ready_to_send()
            campaign.write({"state": "sending", "start_date": fields.Datetime.now()})
        return True

    def action_pause(self):
        self.filtered(lambda c: c.state == "sending").write({"state": "paused"})
        return True

    def action_resume(self):
        self.filtered(lambda c: c.state == "paused").write({"state": "sending"})
        return True

    def action_cancel(self):
        for campaign in self:
            if campaign.state in ("completed", "cancelled"):
                continue
            campaign.recipient_ids.filtered(lambda r: r.state == "pending").write(
                {"state": "cancelled"}
            )
            campaign.write({"state": "cancelled", "end_date": fields.Datetime.now()})
        return True

    def action_reset_to_draft(self):
        self.filtered(lambda c: c.state in ("cancelled", "completed")).write({"state": "draft"})
        return True

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _resolve_body_params(self, contact):
        self.ensure_one()
        values = []
        for var in self.variable_ids.sorted("sequence"):
            if var.source == "contact_name":
                values.append(contact.name or "")
            elif var.source == "contact_phone":
                values.append(contact.phone or "")
            elif var.source == "profile_name":
                values.append(contact.profile_name or contact.name or "")
            else:  # static
                values.append(var.static_value or "")
        return values

    def _send_to_recipient(self, recipient):
        """Creates the real otm.whatsapp.message row (reusing the base
        module's own model/queue/state machine - never a parallel send
        path) and sends it immediately via message._send(), so this
        campaign's own rate-limited cron controls pacing instead of the
        base module's generic 2-minute/200-at-a-time queue cron."""
        self.ensure_one()
        contact = recipient.contact_id
        if contact.opt_in_status == "opted_out":
            recipient.write({"state": "skipped", "error_message": "Contact has opted out."})
            return
        if not contact.phone:
            recipient.write({"state": "failed", "error_message": "Contact has no phone number."})
            return

        conversation = self.env["otm.whatsapp.conversation"].get_or_create(
            self.phone_id.id, contact.id
        )
        body_params = self._resolve_body_params(contact)
        message = self.env["otm.whatsapp.message"].create(
            {
                "phone_id": self.phone_id.id,
                "conversation_id": conversation.id,
                "direction": "out",
                "message_type": "template",
                "template_id": self.template_id.id,
                "body": self.template_id.template_name,
                "state": "queued",
                "template_variables_json": json.dumps(body_params) if body_params else False,
                "template_header_param": self.header_param_static or False,
                "campaign_id": self.id,
                "campaign_recipient_id": recipient.id,
            }
        )
        recipient.write({"message_id": message.id, "state": "queued"})
        message._send()
        vals = {"state": message.state if message.state in ("sent", "failed") else "queued"}
        if message.state == "failed":
            vals["error_message"] = message.error_message
        recipient.write(vals)

    def _process_batch(self):
        self.ensure_one()
        Recipient = self.env["otm.whatsapp.campaign.recipient"]
        limit = max(1, self.rate_limit_per_minute or 60)
        batch = Recipient.search(
            [("campaign_id", "=", self.id), ("state", "=", "pending")], limit=limit
        )
        for recipient in batch:
            try:
                self._send_to_recipient(recipient)
            except Exception as exc:  # noqa: BLE001 - one bad recipient must not abort the batch
                _logger.exception(
                    "WhatsApp campaign %s: failed sending to recipient %s", self.id, recipient.id
                )
                recipient.write({"state": "failed", "error_message": str(exc)})

        remaining = Recipient.search_count(
            [("campaign_id", "=", self.id), ("state", "=", "pending")]
        )
        if remaining == 0:
            self.write({"state": "completed", "end_date": fields.Datetime.now()})

    @api.model
    def _cron_process_campaigns(self):
        """Cron entry point (delegate pattern, matching the base module's
        own _cron_process_queue/_cron_sync_templates convention)."""
        now = fields.Datetime.now()
        due = self.search([("state", "=", "scheduled"), ("scheduled_at", "<=", now)])
        if due:
            due.write({"state": "sending", "start_date": now})

        sending = self.search([("state", "=", "sending")])
        for campaign in sending:
            try:
                campaign._process_batch()
            except Exception:  # noqa: BLE001 - one bad campaign must not abort the others
                _logger.exception("WhatsApp campaign %s: batch processing failed", campaign.id)
