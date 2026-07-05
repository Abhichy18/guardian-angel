"""
Guardian Angel — Seed Data Script

Seeds the database with demo users, consent records, and sample alerts
for development and testing purposes.

Usage:
    python demo/seed_data.py
"""

import asyncio
import sys
import uuid
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
import bcrypt

# Add project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.db import db
# fn added 
@app.on_event("startup")
async def startup_db_client():
    """Startup hook: connect to and initialize the SQLite database."""
    logger.info("Starting up database...")
    await db.connect()
    await db.close()
    logger.info("Database schema verification completed.")

    # Seed demo data on every startup (safe since seed() clears tables first)
    logger.info("Seeding demo data...")
    await seed()
    logger.info("Demo data seeded successfully.")

async def seed():
    """Populate the database with demo data."""

    print("\n🌱 Seeding Guardian Angel demo data...\n")

    await db.connect()

    try:
        # Clear existing tables first for a clean seed
        print("🧹 Clearing existing data...")
        await db.db.execute("DELETE FROM audit_log")
        await db.db.execute("DELETE FROM alerts")
        await db.db.execute("DELETE FROM invite_codes")
        await db.db.execute("DELETE FROM consent_records")
        await db.db.execute("DELETE FROM users")
        await db.db.commit()

        # 1. Create demo users
        elder_id = str(uuid.uuid4())
        family_id = str(uuid.uuid4())
        pin_hash = bcrypt.hashpw("1234".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        now_str = datetime.now(timezone.utc).isoformat()

        # Insert Elder (Margaret Johnson)
        await db.db.execute(
            "INSERT INTO users (id, name, role, pin_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (elder_id, "Margaret Johnson", "elder", pin_hash, now_str)
        )
        # Insert Family (Sarah Johnson)
        await db.db.execute(
            "INSERT INTO users (id, name, role, pin_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (family_id, "Sarah Johnson", "family", pin_hash, now_str)
        )
        print(f"  👤 Created Elder: Margaret Johnson (PIN: 1234, ID: {elder_id[:12]}...)")
        print(f"  👤 Created Family: Sarah Johnson (PIN: 1234, ID: {family_id[:12]}...)")

        # 2. Create consent record
        consent_id = str(uuid.uuid4())
        authorized_ids = json.dumps([family_id])
        await db.db.execute(
            """INSERT INTO consent_records 
               (id, elder_id, active, revoked, authorized_family_ids, created_at, updated_at)
               VALUES (?, ?, 1, 0, ?, ?, ?)""",
            (consent_id, elder_id, authorized_ids, now_str, now_str)
        )
        print(f"  ✅ Consent granted: Margaret → Sarah\n")

        # 3. Create sample alerts
        now = datetime.now(timezone.utc)

        sample_alerts = [
            {
                "id": str(uuid.uuid4()),
                "elder_id": elder_id,
                "risk_score": 95,
                "tier": "high",
                "reasons": json.dumps([
                    "Government impersonation detected",
                    "Gift card payment requested",
                    "Arrest threat used as pressure tactic",
                    "Caller demanded immediate action"
                ]),
                "action_taken": "alert_family",
                "summary_text": "IRS impersonation scam: caller demanded $4,500 in gift cards under threat of arrest.",
                "caller_number": "+18005551234",
                "caller_verification_score": 10,
                "scam_pattern_score": 95,
                "urgency_pressure_score": 90,
                "matched_phrases": json.dumps(["arrest warrant", "gift card", "back taxes", "irs"]),
                "transaction_flagged": 1,
                "created_at": (now - timedelta(hours=2)).isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "elder_id": elder_id,
                "risk_score": 88,
                "tier": "high",
                "reasons": json.dumps([
                    "Bank impersonation detected",
                    "Social Security number requested",
                    "Password/credential harvesting attempt",
                    "Urgency pressure applied"
                ]),
                "action_taken": "alert_family",
                "summary_text": "Bank impersonation: caller requested SSN and banking credentials.",
                "caller_number": "+18005559876",
                "caller_verification_score": 20,
                "scam_pattern_score": 88,
                "urgency_pressure_score": 85,
                "matched_phrases": json.dumps(["social security", "online banking", "verify account", "unauthorized charges"]),
                "transaction_flagged": 0,
                "created_at": (now - timedelta(hours=5)).isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "elder_id": elder_id,
                "risk_score": 55,
                "tier": "medium",
                "reasons": json.dumps([
                    "Caller identity could not be verified",
                    "Personal information was requested",
                    "Caller used mild urgency language"
                ]),
                "action_taken": "warn_elder",
                "summary_text": "Unverified caller requesting personal information. Possible social engineering.",
                "caller_number": "+18005554321",
                "caller_verification_score": 40,
                "scam_pattern_score": 55,
                "urgency_pressure_score": 50,
                "matched_phrases": json.dumps(["remote access", "virus", "tech support"]),
                "transaction_flagged": 0,
                "created_at": (now - timedelta(days=1)).isoformat()
            },
            {
                "id": str(uuid.uuid4()),
                "elder_id": elder_id,
                "risk_score": 15,
                "tier": "low",
                "reasons": json.dumps([
                    "Unknown caller number",
                    "No suspicious patterns detected"
                ]),
                "action_taken": "log_only",
                "summary_text": "Unknown number — call content appears benign. Doctor appointment reminder.",
                "caller_number": "+15551234567",
                "caller_verification_score": 90,
                "scam_pattern_score": 10,
                "urgency_pressure_score": 5,
                "matched_phrases": json.dumps([]),
                "transaction_flagged": 0,
                "created_at": (now - timedelta(days=2)).isoformat()
            }
        ]

        for a in sample_alerts:
            await db.db.execute(
                """INSERT INTO alerts
                   (id, elder_id, risk_score, tier, reasons, action_taken, summary_text,
                    caller_number, caller_verification_score, scam_pattern_score,
                    urgency_pressure_score, matched_phrases, transaction_flagged, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    a["id"], a["elder_id"], a["risk_score"], a["tier"], a["reasons"],
                    a["action_taken"], a["summary_text"], a["caller_number"],
                    a["caller_verification_score"], a["scam_pattern_score"],
                    a["urgency_pressure_score"], a["matched_phrases"],
                    a["transaction_flagged"], a["created_at"]
                )
            )

        print(f"  🚨 Created {len(sample_alerts)} sample alerts:")
        for a in sample_alerts:
            tier_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(a["tier"], "⚪")
            print(f"    {tier_emoji} [{a['tier'].upper()}] {a['summary_text'][:65]}...")

        # 4. Log audit entries
        for a in sample_alerts:
            log_id = str(uuid.uuid4())
            await db.db.execute(
                """INSERT INTO audit_log 
                   (id, elder_id, event_type, risk_decision_json, metadata_json, timestamp)
                   VALUES (?, ?, 'alert_created', ?, NULL, ?)""",
                (
                    log_id, elder_id,
                    json.dumps({
                        "risk_score": a["risk_score"],
                        "tier": a["tier"],
                        "reasons": json.loads(a["reasons"]),
                        "action": a["action_taken"]
                    }),
                    a["created_at"]
                )
            )

        await db.db.commit()
        print(f"\n  📋 Created {len(sample_alerts)} audit log entries.")

        print("\n" + "=" * 50)
        print("🌱 Seed data complete!")
        print("=" * 50)
        print(f"\n  Elder Login Name:  Margaret Johnson")
        print(f"  Family Login Name: Sarah Johnson")
        print(f"  PIN for both:      1234")
        print(f"  (Use these details to log in to the web UI)\n")

    except Exception as e:
        print(f"\n❌ Seed error: {e}")
        raise
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(seed())
