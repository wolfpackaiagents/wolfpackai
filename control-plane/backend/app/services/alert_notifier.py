"""Alert notification dispatch to Slack webhook, Discord webhook, and SMTP email."""

from __future__ import annotations

import json
import logging
import smtplib
import urllib.request
from dataclasses import dataclass
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from ..models.entities import Alert, AlertDestination

logger = logging.getLogger(__name__)


@dataclass
class NotificationResult:
    success: bool
    error: Optional[str] = None


def format_alert_payload(alert: Alert) -> dict:
    return {
        "id": alert.id,
        "severity": alert.severity,
        "source": alert.source,
        "event_type": alert.event_type,
        "message": alert.message[:500],
        "trace_id": alert.trace_id,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "metadata": alert.metadata_field or {},
    }


def _notify_slack_webhook(config: dict, alert: Alert) -> NotificationResult:
    """Send a formatted alert to a Slack incoming webhook."""
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return NotificationResult(success=False, error="no webhook_url configured")
    payload = format_alert_payload(alert)
    color = {"info": "#3498db", "warning": "#f39c12", "error": "#e74c3c"}.get(payload["severity"], "#95a5a6")
    body = {
        "attachments": [
            {
                "color": color,
                "title": f"[{payload['severity'].upper()}] {payload['event_type']}",
                "text": payload["message"],
                "fields": [
                    {"title": "Source", "value": payload["source"], "short": True},
                    {"title": "Trace", "value": payload["trace_id"] or "-", "short": True},
                ],
                "footer": "Wolfpack AMP",
                "ts": payload["created_at"],
            }
        ]
    }
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10):
            return NotificationResult(success=True)
    except Exception as exc:
        return NotificationResult(success=False, error=str(exc))


def _notify_discord_webhook(config: dict, alert: Alert) -> NotificationResult:
    """Send a formatted alert to a Discord webhook."""
    webhook_url = config.get("webhook_url", "")
    if not webhook_url:
        return NotificationResult(success=False, error="no webhook_url configured")
    payload = format_alert_payload(alert)
    color = {"info": 0x3498DB, "warning": 0xF39C12, "error": 0xE74C3C}.get(payload["severity"], 0x95A5A6)
    body = {
        "embeds": [
            {
                "color": color,
                "title": f"[{payload['severity'].upper()}] {payload['event_type']}",
                "description": payload["message"],
                "fields": [
                    {"name": "Source", "value": payload["source"], "inline": True},
                    {"name": "Trace", "value": payload["trace_id"] or "-", "inline": True},
                ],
                "footer": {"text": "Wolfpack AMP"},
                "timestamp": payload["created_at"],
            }
        ]
    }
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10):
            return NotificationResult(success=True)
    except Exception as exc:
        return NotificationResult(success=False, error=str(exc))


def _notify_smtp(config: dict, alert: Alert) -> NotificationResult:
    """Send a formatted alert email via SMTP."""
    payload = format_alert_payload(alert)
    try:
        host = config["host"]
        port = config.get("port", 587)
        username = config.get("username", "")
        password = config.get("password", "")
        use_tls = config.get("use_tls", True)
        from_addr = config.get("from", "amp@wolfpack.ai")
        to_addrs = config.get("to", [])
        if not isinstance(to_addrs, list):
            to_addrs = [to_addrs]

        if not to_addrs:
            return NotificationResult(success=False, error="no recipients configured")

        subject = f"[{payload['severity'].upper()}] Wolfpack AMP Alert: {payload['event_type']}"
        text = (
            f"Severity: {payload['severity']}\n"
            f"Source: {payload['source']}\n"
            f"Event: {payload['event_type']}\n"
            f"Trace: {payload['trace_id'] or '-'}\n"
            f"Time: {payload['created_at']}\n\n"
            f"Message:\n{payload['message']}\n"
        )
        msg = MIMEText(text)
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)

        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.sendmail(from_addr, to_addrs, msg.as_string())
        return NotificationResult(success=True)
    except Exception as exc:
        return NotificationResult(success=False, error=str(exc))


DISPATCHERS = {
    "slack_webhook": _notify_slack_webhook,
    "discord_webhook": _notify_discord_webhook,
    "smtp": _notify_smtp,
}


def notify(alert: Alert, destinations: list[AlertDestination]) -> list[dict]:
    """Dispatch an alert to every enabled destination for the project.

    Returns a list of per-destination outcome dicts for the caller to persist as
    ``last_error`` / ``last_notified_at``.
    """
    results: list[dict] = []
    for dest in destinations:
        if not dest.enabled:
            continue
        dispatcher = DISPATCHERS.get(dest.destination_type)
        if dispatcher is None:
            continue
        result = dispatcher(dest.config, alert)
        outcome = {"destination_id": dest.id, "success": result.success, "error": result.error}
        results.append(outcome)
        if result.success:
            logger.info("Alert %s notified via %s (%s)", alert.id, dest.name, dest.destination_type)
        else:
            logger.warning("Alert %s notification failed via %s (%s): %s", alert.id, dest.name, dest.destination_type, result.error)
    return results