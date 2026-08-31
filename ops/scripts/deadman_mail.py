#!/usr/bin/env python3
"""Send the watchdog's alert mail. Body and recipient come from the environment.

Same SMTP path jobrun uses, and the same one the Ofelia and xyOps watchdogs
used before it -- proven in production rather than newly invented.
"""

from __future__ import annotations

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage


def main() -> int:
    to = os.environ.get("ALERT_TO", "").strip()
    if not to:
        print("deadman: ALERT_TO is empty; cannot send alert", file=sys.stderr)
        return 1

    m = EmailMessage()
    m["From"] = os.environ.get("MAIL_FROM", "TPP Ops <reports@idtpp.com>")
    m["To"] = to
    m["Subject"] = os.environ.get("SUBJECT", "[ALERT] Dokploy schedules are UNHEALTHY")
    m.set_content(os.environ.get("BODY", "(no body)"))

    s = smtplib.SMTP(
        os.environ.get("SMTP_HOST", "mail.idtpp.com"),
        int(os.environ.get("SMTP_PORT", "587")),
        timeout=60,
    )
    s.starttls(context=ssl.create_default_context())
    s.login(os.environ.get("SMTP_USER", "reports@idtpp.com"), os.environ["SMTP_PASS"])
    s.send_message(m)
    s.quit()
    print("alert sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
