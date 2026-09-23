# Security policy

© 3MH Technologies — https://3mh.pages.dev/ — https://t.me/j49_c

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

- Email: **contact@3mh.pages.dev** (PGP on request), or
- Telegram: [@j49_c](https://t.me/j49_c)

Include steps to reproduce, affected version, and impact. You'll get an acknowledgement within 72 hours and a status update within 7 days.

## Supported versions

| Version | Supported |
|---|---|
| 1.x | ✅ |
| < 1.0 | ❌ |

## Scope notes

- The SDK never transmits credentials other than the cookie you configure; it never logs cookie values.
- Treat `NOTRACK_COOKIE` as a secret: keep it in environment variables or a secrets manager, never in source control.
- The SDK performs no telemetry and makes no requests other than to `NOTRACK_BASE`.
