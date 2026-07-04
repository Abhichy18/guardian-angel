"""
Guardian Angel — Demo Replay Script

Replays sample call transcripts through the Guardian Angel backend API
to demonstrate scam detection, alert generation, and family notification flows.

Usage:
    python demo/replay_demo.py [--base-url http://127.0.0.1:8000] [--delay 2.0]
"""

import asyncio
import json
import sys
import os
import argparse
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import httpx
except ImportError:
    print("⚠️  httpx is required for the demo script. Install with: pip install httpx")
    sys.exit(1)


SAMPLE_CALLS_PATH = Path(__file__).parent / "sample_calls.json"


async def replay_demo(base_url: str, delay: float):
    """Replay all sample calls through the API."""

    # Load sample data
    with open(SAMPLE_CALLS_PATH, "r") as f:
        calls = json.load(f)

    print("\n" + "=" * 60)
    print("🛡️  Guardian Angel — Demo Replay")
    print("=" * 60)
    print(f"  Base URL: {base_url}")
    print(f"  Calls to replay: {len(calls)}")
    print(f"  Chunk delay: {delay}s")
    print("=" * 60 + "\n")

    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Step 1: Register demo elder user
        print("📝 Registering demo elder user...")
        reg_resp = await client.post("/api/auth/register", json={
            "username": "Demo Elder",
            "role": "elder",
            "password": "demo123"
        })

        if reg_resp.status_code in (200, 409):  # 409 = already exists
            print("  ✅ Demo elder registered (or already exists).\n")
        else:
            print(f"  ⚠️  Registration response: {reg_resp.status_code} - {reg_resp.text}")

        # Step 2: Login as demo elder
        login_resp = await client.post("/api/auth/login", json={
            "username": "Demo Elder",
            "password": "demo123"
        })

        if login_resp.status_code != 200:
            print(f"  ❌ Login failed: {login_resp.text}")
            return

        login_data = login_resp.json()
        token = login_data.get("token", "")
        elder_id = login_data.get("user", {}).get("id", "")
        headers = {"Authorization": f"Bearer {token}"}
        print(f"  🔑 Logged in as elder. ID: {elder_id[:12]}...\n")

        # Step 3: Grant consent
        print("✅ Granting consent for demo...")
        consent_resp = await client.post("/api/consent/grant", json={
            "authorized_family_ids": []
        }, headers=headers)
        print(f"  Consent: {consent_resp.status_code}\n")

        # Step 4: Replay each call
        for i, call in enumerate(calls):
            print(f"📞 Call {i + 1}/{len(calls)}: {call['description']}")
            print(f"   Caller: {call['caller_claimed_identity']} ({call['caller_number']})")
            print(f"   Expected Risk: {call['expected_risk_tier'].upper()}")
            print(f"   Expected Patterns: {', '.join(call['expected_patterns']) or 'None'}")
            print()

            # Send each transcript chunk as a call event
            for j, chunk in enumerate(call["transcript_chunks"]):
                event_payload = {
                    "call_id": call["call_id"],
                    "elder_id": elder_id,
                    "caller_number": call["caller_number"],
                    "caller_claimed_identity": call["caller_claimed_identity"],
                    "speaker": chunk["speaker"],
                    "text": chunk["text"],
                    "chunk_index": j,
                    "is_final_chunk": j == len(call["transcript_chunks"]) - 1
                }

                print(f"   [{chunk['speaker'].upper()}]: {chunk['text'][:80]}{'...' if len(chunk['text']) > 80 else ''}")

                try:
                    event_resp = await client.post(
                        "/api/events/call-chunk",
                        json=event_payload,
                        headers=headers
                    )

                    if event_resp.status_code == 200:
                        result = event_resp.json()
                        if result.get("alert_generated"):
                            tier = result.get("risk_tier", "unknown")
                            tier_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(tier, "⚪")
                            print(f"   {tier_emoji} ALERT GENERATED — Risk: {tier.upper()}")
                    else:
                        print(f"   ⚠️  Event response: {event_resp.status_code}")
                except Exception as e:
                    print(f"   ❌ Error sending chunk: {e}")

                await asyncio.sleep(delay)

            print(f"\n   {'─' * 40}\n")

        # Step 5: Fetch final alert summary
        print("\n📊 Final Alert Summary:")
        print("=" * 60)
        try:
            alerts_resp = await client.get(f"/api/alerts/elder/{elder_id}", headers=headers)
            if alerts_resp.status_code == 200:
                alerts = alerts_resp.json()
                print(f"   Total alerts generated: {len(alerts)}")
                for alert in alerts:
                    tier_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(alert.get("tier", ""), "⚪")
                    print(f"   {tier_emoji} [{alert.get('tier', 'unknown').upper()}] {alert.get('summary_text', 'N/A')}")
            else:
                print(f"   Could not fetch alerts: {alerts_resp.status_code}")
        except Exception as e:
            print(f"   Error fetching alerts: {e}")

    print("\n" + "=" * 60)
    print("🛡️  Demo replay complete!")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Guardian Angel Demo Replay")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend API base URL")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between transcript chunks (seconds)")
    args = parser.parse_args()

    asyncio.run(replay_demo(args.base_url, args.delay))


if __name__ == "__main__":
    main()
