"""
Guardian Angel — Database Layer

Async SQLite database manager with schema creation, connection pooling,
and CRUD operations for all core tables. The audit_log table is append-only
(no UPDATE or DELETE operations are ever performed on it).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", "guardian_angel.db")


# ── Schema Definition ───────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK(role IN ('elder', 'family')),
    pin_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS consent_records (
    id TEXT PRIMARY KEY,
    elder_id TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    revoked INTEGER NOT NULL DEFAULT 0,
    authorized_family_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (elder_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS invite_codes (
    id TEXT PRIMARY KEY,
    elder_id TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    used INTEGER NOT NULL DEFAULT 0,
    used_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    FOREIGN KEY (elder_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    elder_id TEXT NOT NULL,
    risk_score INTEGER NOT NULL,
    tier TEXT NOT NULL CHECK(tier IN ('low', 'medium', 'high')),
    reasons TEXT NOT NULL DEFAULT '[]',
    action_taken TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    caller_number TEXT,
    caller_verification_score INTEGER,
    scam_pattern_score INTEGER,
    urgency_pressure_score INTEGER,
    matched_phrases TEXT DEFAULT '[]',
    transaction_flagged INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (elder_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    elder_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    risk_decision_json TEXT,
    metadata_json TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (elder_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_alerts_elder ON alerts(elder_id);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_elder ON audit_log(elder_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_consent_elder ON consent_records(elder_id);
"""


# ── Database Manager ────────────────────────────────────────────────────────


class Database:
    """Async SQLite database manager for Guardian Angel."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Open the database connection and create tables."""
        # Ensure directory exists
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(db_dir, exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript(SCHEMA_SQL)
        await self._db.commit()
        logger.info("Database initialized at %s", self.db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    # ── User Operations ─────────────────────────────────────────────────────

    async def create_user(self, name: str, role: str, pin_hash: str) -> dict:
        """Create a new user (elder or family member)."""
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "INSERT INTO users (id, name, role, pin_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, role, pin_hash, now),
        )
        await self.db.commit()
        return {"id": user_id, "name": name, "role": role, "created_at": now}

    async def get_user_by_name(self, name: str) -> Optional[dict]:
        """Retrieve a user by name."""
        async with self.db.execute(
            "SELECT * FROM users WHERE name = ?", (name,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """Retrieve a user by ID."""
        async with self.db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_users_by_role(self, role: str) -> list[dict]:
        """Get all users with a given role."""
        async with self.db.execute(
            "SELECT id, name, role, created_at FROM users WHERE role = ?", (role,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

    # ── Consent Operations ──────────────────────────────────────────────────

    async def get_consent(self, elder_id: str) -> Optional[dict]:
        """Get the consent record for an elder."""
        async with self.db.execute(
            "SELECT * FROM consent_records WHERE elder_id = ?", (elder_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                record = dict(row)
                record["authorized_family_ids"] = json.loads(
                    record["authorized_family_ids"]
                )
                record["active"] = bool(record["active"])
                record["revoked"] = bool(record["revoked"])
                return record
            return None

    async def grant_consent(
        self, elder_id: str, authorized_family_ids: list[str]
    ) -> dict:
        """Create or reactivate a consent record for an elder."""
        now = datetime.now(timezone.utc).isoformat()
        existing = await self.get_consent(elder_id)

        if existing:
            # Reactivate existing record
            await self.db.execute(
                """UPDATE consent_records
                   SET active = 1, revoked = 0, authorized_family_ids = ?, updated_at = ?
                   WHERE elder_id = ?""",
                (json.dumps(authorized_family_ids), now, elder_id),
            )
        else:
            record_id = str(uuid.uuid4())
            await self.db.execute(
                """INSERT INTO consent_records
                   (id, elder_id, active, revoked, authorized_family_ids, created_at, updated_at)
                   VALUES (?, ?, 1, 0, ?, ?, ?)""",
                (record_id, elder_id, json.dumps(authorized_family_ids), now, now),
            )

        await self.db.commit()

        # Audit this consent grant
        await self.append_audit_log(
            elder_id=elder_id,
            event_type="consent_granted",
            metadata={"authorized_family_ids": authorized_family_ids},
        )

        return {
            "elder_id": elder_id,
            "active": True,
            "revoked": False,
            "authorized_family_ids": authorized_family_ids,
            "updated_at": now,
        }

    async def revoke_consent(self, elder_id: str) -> bool:
        """One-tap revoke consent. No confirmation dark patterns."""
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            """UPDATE consent_records
               SET active = 0, revoked = 1, updated_at = ?
               WHERE elder_id = ?""",
            (now, elder_id),
        )
        await self.db.commit()

        # Audit the revocation
        await self.append_audit_log(
            elder_id=elder_id,
            event_type="consent_revoked",
        )
        return True

    async def update_authorized_family(
        self, elder_id: str, family_ids: list[str]
    ) -> None:
        """Update the list of authorized family members."""
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            """UPDATE consent_records
               SET authorized_family_ids = ?, updated_at = ?
               WHERE elder_id = ?""",
            (json.dumps(family_ids), now, elder_id),
        )
        await self.db.commit()

    # ── Invite Code Operations ──────────────────────────────────────────────

    async def create_invite_code(self, elder_id: str) -> dict:
        """Generate a 6-character invite code for the elder to share."""
        code_id = str(uuid.uuid4())
        # Generate a short, easy-to-read code (uppercase, no ambiguous chars)
        code = uuid.uuid4().hex[:6].upper()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=24)

        await self.db.execute(
            """INSERT INTO invite_codes (id, elder_id, code, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?)""",
            (code_id, elder_id, code, now.isoformat(), expires.isoformat()),
        )
        await self.db.commit()
        return {"code": code, "expires_at": expires.isoformat()}

    async def redeem_invite_code(self, code: str, family_id: str) -> Optional[str]:
        """
        Redeem an invite code. Returns the elder_id if successful, None otherwise.
        Adds the family member to the elder's authorized list.
        """
        now = datetime.now(timezone.utc).isoformat()
        async with self.db.execute(
            """SELECT * FROM invite_codes
               WHERE code = ? AND used = 0 AND expires_at > ?""",
            (code.upper(), now),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            invite = dict(row)
            elder_id = invite["elder_id"]

            # Mark code as used
            await self.db.execute(
                "UPDATE invite_codes SET used = 1, used_by = ? WHERE id = ?",
                (family_id, invite["id"]),
            )

            # Add family member to elder's authorized list
            consent = await self.get_consent(elder_id)
            if consent:
                family_ids = consent["authorized_family_ids"]
                if family_id not in family_ids:
                    family_ids.append(family_id)
                    await self.update_authorized_family(elder_id, family_ids)

            await self.db.commit()
            return elder_id

    # ── Alert Operations ────────────────────────────────────────────────────

    async def create_alert(
        self,
        elder_id: str,
        risk_score: int,
        tier: str,
        reasons: list[str],
        action_taken: str,
        summary_text: str,
        caller_number: Optional[str] = None,
        caller_verification_score: Optional[int] = None,
        scam_pattern_score: Optional[int] = None,
        urgency_pressure_score: Optional[int] = None,
        matched_phrases: Optional[list[str]] = None,
        transaction_flagged: bool = False,
    ) -> dict:
        """Create a new alert record."""
        alert_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        await self.db.execute(
            """INSERT INTO alerts
               (id, elder_id, risk_score, tier, reasons, action_taken, summary_text,
                caller_number, caller_verification_score, scam_pattern_score,
                urgency_pressure_score, matched_phrases, transaction_flagged, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                alert_id, elder_id, risk_score, tier, json.dumps(reasons),
                action_taken, summary_text, caller_number,
                caller_verification_score, scam_pattern_score,
                urgency_pressure_score, json.dumps(matched_phrases or []),
                int(transaction_flagged), now,
            ),
        )
        await self.db.commit()

        return {
            "id": alert_id,
            "elder_id": elder_id,
            "risk_score": risk_score,
            "tier": tier,
            "reasons": reasons,
            "action_taken": action_taken,
            "summary_text": summary_text,
            "caller_number": caller_number,
            "created_at": now,
        }

    async def get_alerts_for_elder(self, elder_id: str) -> list[dict]:
        """Get all alerts for an elder (visible on their own dashboard)."""
        async with self.db.execute(
            """SELECT a.*, u.name as elder_name FROM alerts a
               JOIN users u ON a.elder_id = u.id
               WHERE a.elder_id = ?
               ORDER BY a.created_at DESC""",
            (elder_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._parse_alert_row(dict(r)) for r in rows]

    async def get_alerts_for_family(self, family_id: str) -> list[dict]:
        """Get alerts for elders this family member is authorized to see."""
        # Find all elders that have authorized this family member
        async with self.db.execute(
            "SELECT elder_id, authorized_family_ids FROM consent_records WHERE active = 1 AND revoked = 0",
        ) as cursor:
            rows = await cursor.fetchall()

        authorized_elder_ids = []
        for row in rows:
            family_ids = json.loads(row["authorized_family_ids"])
            if family_id in family_ids:
                authorized_elder_ids.append(row["elder_id"])

        if not authorized_elder_ids:
            return []

        placeholders = ",".join("?" for _ in authorized_elder_ids)
        async with self.db.execute(
            f"""SELECT a.*, u.name as elder_name FROM alerts a
                JOIN users u ON a.elder_id = u.id
                WHERE a.elder_id IN ({placeholders})
                ORDER BY a.created_at DESC""",
            authorized_elder_ids,
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._parse_alert_row(dict(r)) for r in rows]

    async def get_alert_by_id(self, alert_id: str) -> Optional[dict]:
        """Get a single alert by ID."""
        async with self.db.execute(
            """SELECT a.*, u.name as elder_name FROM alerts a
               JOIN users u ON a.elder_id = u.id
               WHERE a.id = ?""",
            (alert_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return self._parse_alert_row(dict(row)) if row else None

    def _parse_alert_row(self, row: dict) -> dict:
        """Parse JSON fields in an alert row."""
        row["reasons"] = json.loads(row.get("reasons", "[]"))
        row["matched_phrases"] = json.loads(row.get("matched_phrases", "[]"))
        row["transaction_flagged"] = bool(row.get("transaction_flagged", 0))
        return row

    # ── Audit Log Operations (APPEND-ONLY) ──────────────────────────────────

    async def append_audit_log(
        self,
        elder_id: str,
        event_type: str,
        risk_decision: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Append an entry to the immutable audit log.
        This table supports INSERT only — no UPDATE or DELETE operations.
        """
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        await self.db.execute(
            """INSERT INTO audit_log (id, elder_id, event_type, risk_decision_json, metadata_json, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                log_id, elder_id, event_type,
                json.dumps(risk_decision) if risk_decision else None,
                json.dumps(metadata) if metadata else None,
                now,
            ),
        )
        await self.db.commit()

    async def get_audit_log(self, elder_id: str) -> list[dict]:
        """Read audit log entries for an elder. Read-only access."""
        async with self.db.execute(
            """SELECT * FROM audit_log WHERE elder_id = ?
               ORDER BY timestamp DESC""",
            (elder_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                entry = dict(row)
                if entry.get("risk_decision_json"):
                    entry["risk_decision"] = json.loads(entry["risk_decision_json"])
                if entry.get("metadata_json"):
                    entry["metadata"] = json.loads(entry["metadata_json"])
                results.append(entry)
            return results


# ── Singleton Instance ──────────────────────────────────────────────────────

db = Database()
