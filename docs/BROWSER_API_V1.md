# Browser Worker API v1

The OpenAPI contract is [`contracts/browser-api-v1.yaml`](../contracts/browser-api-v1.yaml). It defines session creation/status/cleanup, structured observations, single actions, control mode, citizen input, screenshot retrieval, and screenshot streaming.

Observations use explicit page states (`ready`, `loading`, `authentication_required`, `captcha_detected`, `unexpected_error`, `closed`) and structured interactive element roles. IDs are valid only for the observation that produced them. Actions carry an idempotency identifier and the source observation ID. Supported agent actions are navigation, click, fill, selection, checkbox changes, key press, scroll, back, reload, and file upload through a short-lived backend file reference. The worker rejects stale or unsafe actions.

Sensitive actions such as OTP entry, payment, legal declarations, and final submission remain under citizen control.

Every route except `/healthz` requires the configured bearer service token. Session creation and navigation require HTTPS destinations whose hosts are in `BROWSER_ALLOWED_DOMAINS`. File upload references are short-lived HTTPS URLs and require an explicit `BROWSER_FILE_REFERENCE_DOMAINS` allowlist; local file paths are rejected.
