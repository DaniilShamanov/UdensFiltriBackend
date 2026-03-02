import json
from urllib import error, request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class SendGridEmailBackend(BaseEmailBackend):
    api_url = "https://api.sendgrid.com/v3/mail/send"

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = getattr(settings, "SENDGRID_API_KEY", "")
        if not api_key:
            if not self.fail_silently:
                raise ValueError("SENDGRID_API_KEY is not configured")
            return 0

        sent_count = 0
        for message in email_messages:
            payload = {
                "personalizations": [{"to": [{"email": addr} for addr in message.to]}],
                "from": {"email": message.from_email or settings.DEFAULT_FROM_EMAIL},
                "subject": message.subject,
                "content": [{"type": "text/plain", "value": message.body}],
            }

            if message.alternatives:
                for body, mimetype in message.alternatives:
                    if mimetype == "text/html":
                        payload["content"].append({"type": "text/html", "value": body})

            req = request.Request(
                self.api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )

            try:
                with request.urlopen(req, timeout=10) as response:
                    if 200 <= response.status < 300:
                        sent_count += 1
                    elif not self.fail_silently:
                        raise RuntimeError(f"SendGrid returned HTTP {response.status}")
            except error.HTTPError as exc:
                if not self.fail_silently:
                    raise RuntimeError(f"SendGrid HTTP error: {exc.code}") from exc
            except Exception:
                if not self.fail_silently:
                    raise

        return sent_count
