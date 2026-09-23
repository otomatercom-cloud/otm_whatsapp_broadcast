# Otomater WhatsApp Bulk Broadcast (`otm_whatsapp_broadcast`)

Bulk/campaign WhatsApp sending (AiSensy-style) built entirely on top of the
real, already-deployed `otm_whatsapp_coexistence` module. No duplicated
infrastructure: it reuses `otm.whatsapp.message`'s send/state-machine,
`otm.whatsapp.contact`'s get-or-create/normalize logic, `otm.whatsapp.phone`
and the base module's own `MetaWhatsappClient`.

## What this module adds

- `otm.whatsapp.campaign` - a broadcast: sender number, template, recipients,
  per-recipient template variable mapping, schedule, rate limit, live stats.
- `otm.whatsapp.campaign.variable` - one row per `{{n}}` body placeholder in
  the chosen template; each maps to contact name / phone / WhatsApp profile
  name / or a fixed static value.
- `otm.whatsapp.campaign.recipient` - one row per contact in the campaign,
  tracking pending → queued → sent → delivered → read (or failed/skipped).
- A paste-a-list import wizard (`phone` or `phone,Name` per line) that
  matches/creates `otm.whatsapp.contact` records via the base module's own
  `normalize_phone()`/get-or-create pattern - never duplicates a contact.
- A dedicated 1-minute cron (`_cron_process_campaigns`) that starts due
  scheduled campaigns and sends up to `rate_limit_per_minute` messages per
  campaign per run - kept **separate** from the base module's own
  `_cron_process_queue` (2 min / 200 at a time, no per-campaign throttle)
  specifically so a bulk send can never blow past Meta's per-number
  throughput limits or tank a number's quality rating.

## The ONE inheritance hook into the base module

`models/whatsapp_message.py` in this module does a plain `_inherit =
"otm.whatsapp.message"` to add `campaign_id`/`campaign_recipient_id` and to
mirror a delivered/read/failed status update (already applied by the base
module's own idempotent `process_status_update()`) onto the campaign
recipient row. **Zero edits to the base module's own files for this part** -
same pattern already used by `otm_whatsapp_chatbot`.

## Real bug fixed in the base module (`otm_whatsapp_coexistence`) as a prerequisite

`meta_whatsapp_client.send_template()` was resending the template's raw
**definition** JSON (`str(tpl.get("components"))` from the `message_templates`
list endpoint - HEADER/BODY/BUTTONS structure with `{{1}}` placeholder text
and `example` values, and not even valid JSON) straight back to Meta as the
**send-time** payload. This only happened to work for a template with zero
variables; any template using `{{1}}`, `{{2}}`, ... (i.e. exactly what a
personalized bulk campaign needs) would be rejected by Meta's API. Fixed to
build the real send-time shape - `components: [{"type": "body", "parameters":
[{"type": "text", "text": "<value>"}]}]` - verified against Meta's real
`message-templates` send-time documentation. `otm.whatsapp.message` gained
two new fields (`template_variables_json`, `template_header_param`) so this
also benefits any future non-campaign template send, and
`otm.whatsapp.template.variable_count`/`has_buttons` (declared before but
never actually populated) are now filled in during template sync via a new
`_parse_components_meta()` helper, which this module also uses to size the
per-campaign variable-mapping table.

## Known limitations (honest, not yet verified against a live send)

- Only a single dynamic **body** parameter set is supported per recipient,
  plus one optional header value. Dynamic **button** parameters (e.g. a
  per-recipient URL button) are not implemented - not needed for a plain
  text/marketing broadcast, but would need a small extension to
  `send_template()`/`_send_to_recipient()` if a template requires one.
- This code has been written and reviewed against the real, currently
  deployed source of `otm_whatsapp_coexistence` (staged directly from
  `E:\odoo19\custom-addons\otm_whatsapp_coexistence` on your machine), but
  **has not yet been installed/upgraded and test-fired against a real Meta
  template with variables** in this session - no shell/terminal access to
  your Odoo server was available here. Please run, in order, before relying
  on it for a real send:
  1. `-u otm_whatsapp_coexistence,otm_whatsapp_broadcast --stop-after-init`
     (upgrades the base module for the `send_template`/template-sync fix,
     then installs this new module).
  2. Re-sync templates (Configuration > Templates > Sync, or wait for the
     daily cron) so `variable_count` gets populated for your real templates.
  3. Create a campaign against a template that actually has a `{{1}}` body
     variable, with 1-2 test recipients, and confirm delivery on a real
     phone before pointing it at a real audience.
- Bulk template sends to numbers outside their existing 24-hour service
  window are still subject to Meta's own business-initiated-conversation
  and template-category rules - this module does not attempt to work around
  those (nor should it).
