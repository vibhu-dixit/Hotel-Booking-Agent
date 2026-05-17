#!/usr/bin/env python3
"""Register (or list) Linq webhook subscriptions. Run from repo root with venv active."""
from __future__ import annotations

import json
import sys

import httpx

from app.core.config import settings


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage:\n"
            "  python scripts/linq_setup_webhook.py list\n"
            "  python scripts/linq_setup_webhook.py create https://YOUR-NGROK.ngrok-free.dev\n"
        )
        sys.exit(1)

    if not settings.linq_api_key:
        print("Set LINQ_API_KEY in .env first")
        sys.exit(1)

    base = settings.linq_base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.linq_api_key}", "Content-Type": "application/json"}

    with httpx.Client(timeout=30.0) as client:
        if sys.argv[1] == "list":
            r = client.get(f"{base}/webhook-subscriptions", headers=headers)
            r.raise_for_status()
            print(json.dumps(r.json(), indent=2))
            return

        if sys.argv[1] == "create":
            if len(sys.argv) < 3:
                print("Pass your ngrok base URL, e.g. https://abc123.ngrok-free.dev")
                sys.exit(1)
            ngrok_base = sys.argv[2].rstrip("/")
            target = f"{ngrok_base}/webhooks/linq?version=2026-02-03"
            payload = {
                "target_url": target,
                "subscribed_events": ["message.received"],
            }
            if settings.linq_from_number:
                payload["phone_numbers"] = [settings.linq_from_number.replace(" ", "")]
            r = client.post(f"{base}/webhook-subscriptions", headers=headers, json=payload)
            if r.status_code >= 400:
                print("Create failed:", r.status_code, r.text[:800])
                sys.exit(1)
            data = r.json()
            print("Created subscription.")
            print("target_url:", target)
            secret = data.get("signing_secret") or data.get("data", {}).get("signing_secret")
            if secret:
                print("\nAdd to .env (shown once only):")
                print(f"LINQ_WEBHOOK_SECRET={secret}")
            print("\nFull response:")
            print(json.dumps(data, indent=2))
            return

    print("Unknown command:", sys.argv[1])
    sys.exit(1)


if __name__ == "__main__":
    main()
