"""
Selection RP — Database Manager
SQLite · asyncio-safe (синхронні виклики у thread-pool)
"""

import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "selection_rp.db")

# ─────────────────────────────────────────────────────────────
class Database:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    # ── DDL ──────────────────────────────────────────────────
    def _create_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
        PRAGMA journal_mode=WAL;

        -- Персонал
        CREATE TABLE IF NOT EXISTS staff (
            user_id     INTEGER NOT NULL,
            guild_id    INTEGER NOT NULL,
            username    TEXT,
            level       INTEGER NOT NULL DEFAULT 1,
            added_by    INTEGER,
            added_at    TEXT DEFAULT (datetime('now')),
            notes       TEXT,
            PRIMARY KEY (user_id, guild_id)
        );

        -- Попередження
        CREATE TABLE IF NOT EXISTS warnings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            guild_id    INTEGER NOT NULL,
            reason      TEXT NOT NULL,
            moderator   INTEGER NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            active      INTEGER DEFAULT 1
        );

        -- Мьюти
        CREATE TABLE IF NOT EXISTS mutes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            guild_id    INTEGER NOT NULL,
            reason      TEXT,
            moderator   INTEGER NOT NULL,
            duration    INTEGER,           -- секунди, NULL = постійно
            expires_at  TEXT,              -- ISO datetime або NULL
            created_at  TEXT DEFAULT (datetime('now')),
            active      INTEGER DEFAULT 1
        );

        -- Бани
        CREATE TABLE IF NOT EXISTS bans (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            guild_id    INTEGER NOT NULL,
            username    TEXT,
            reason      TEXT NOT NULL,
            moderator   INTEGER NOT NULL,
            duration    INTEGER,           -- секунди, NULL = назавжди
            expires_at  TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            active      INTEGER DEFAULT 1
        );

        -- Кіки
        CREATE TABLE IF NOT EXISTS kicks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            guild_id    INTEGER NOT NULL,
            username    TEXT,
            reason      TEXT NOT NULL,
            moderator   INTEGER NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- Скарги
        CREATE TABLE IF NOT EXISTS complaints (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id        INTEGER NOT NULL,
            author_id       INTEGER NOT NULL,
            author_name     TEXT,
            target_id       INTEGER,
            target_name     TEXT,
            category        TEXT NOT NULL,
            description     TEXT NOT NULL,
            evidence        TEXT,           -- посилання/опис
            status          TEXT DEFAULT 'pending',
            -- pending | reviewing | resolved | rejected
            handler_id      INTEGER,        -- модератор що взяв
            handler_note    TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now')),
            message_id      INTEGER         -- ID повідомлення в каналі скарг
        );

        -- Лог дій
        CREATE TABLE IF NOT EXISTS action_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id    INTEGER NOT NULL,
            action      TEXT NOT NULL,
            actor_id    INTEGER,
            target_id   INTEGER,
            details     TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- Налаштування серверу
        CREATE TABLE IF NOT EXISTS settings (
            guild_id    INTEGER PRIMARY KEY,
            log_channel         INTEGER,
            action_log_channel  INTEGER,
            join_log_channel    INTEGER,
            complaint_channel   INTEGER,
            complaint_log_channel INTEGER,
            muted_role          INTEGER,
            ban_appeal_channel  INTEGER
        );
        """)
        self.conn.commit()

    # ══════════════════════════════════════════════════════════
    #  STAFF
    # ══════════════════════════════════════════════════════════
    def add_staff(self, user_id, guild_id, username, level, added_by=None, notes=None):
        self.conn.execute(
            "INSERT OR REPLACE INTO staff "
            "(user_id, guild_id, username, level, added_by, notes) "
            "VALUES (?,?,?,?,?,?)",
            (user_id, guild_id, username, level, added_by, notes)
        )
        self.conn.commit()

    def remove_staff(self, user_id, guild_id):
        self.conn.execute(
            "DELETE FROM staff WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        )
        self.conn.commit()

    def get_staff(self, user_id, guild_id):
        return self.conn.execute(
            "SELECT * FROM staff WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        ).fetchone()

    def get_all_staff(self, guild_id):
        return self.conn.execute(
            "SELECT * FROM staff WHERE guild_id=? ORDER BY level DESC",
            (guild_id,)
        ).fetchall()

    def get_staff_level(self, user_id, guild_id):
        row = self.get_staff(user_id, guild_id)
        return row["level"] if row else 0

    def update_staff_level(self, user_id, guild_id, level):
        self.conn.execute(
            "UPDATE staff SET level=? WHERE user_id=? AND guild_id=?",
            (level, user_id, guild_id)
        )
        self.conn.commit()

    # ══════════════════════════════════════════════════════════
    #  WARNINGS
    # ══════════════════════════════════════════════════════════
    def add_warning(self, user_id, guild_id, reason, moderator_id):
        cur = self.conn.execute(
            "INSERT INTO warnings (user_id, guild_id, reason, moderator) "
            "VALUES (?,?,?,?)",
            (user_id, guild_id, reason, moderator_id)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_warnings(self, user_id, guild_id, active_only=True):
        q = "SELECT * FROM warnings WHERE user_id=? AND guild_id=?"
        if active_only:
            q += " AND active=1"
        q += " ORDER BY created_at DESC"
        return self.conn.execute(q, (user_id, guild_id)).fetchall()

    def count_warnings(self, user_id, guild_id):
        return self.conn.execute(
            "SELECT COUNT(*) FROM warnings WHERE user_id=? AND guild_id=? AND active=1",
            (user_id, guild_id)
        ).fetchone()[0]

    def remove_warning(self, warning_id, guild_id):
        self.conn.execute(
            "UPDATE warnings SET active=0 WHERE id=? AND guild_id=?",
            (warning_id, guild_id)
        )
        self.conn.commit()

    def clear_warnings(self, user_id, guild_id):
        self.conn.execute(
            "UPDATE warnings SET active=0 WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        )
        self.conn.commit()

    # ══════════════════════════════════════════════════════════
    #  MUTES
    # ══════════════════════════════════════════════════════════
    def add_mute(self, user_id, guild_id, reason, moderator_id, duration=None):
        expires = None
        if duration:
            from datetime import timedelta
            expires = (datetime.now(timezone.utc) + timedelta(seconds=duration)).isoformat()
        cur = self.conn.execute(
            "INSERT INTO mutes (user_id, guild_id, reason, moderator, duration, expires_at) "
            "VALUES (?,?,?,?,?,?)",
            (user_id, guild_id, reason, moderator_id, duration, expires)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_active_mute(self, user_id, guild_id):
        return self.conn.execute(
            "SELECT * FROM mutes WHERE user_id=? AND guild_id=? AND active=1 "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id, guild_id)
        ).fetchone()

    def unmute(self, user_id, guild_id):
        self.conn.execute(
            "UPDATE mutes SET active=0 WHERE user_id=? AND guild_id=? AND active=1",
            (user_id, guild_id)
        )
        self.conn.commit()

    def get_expired_mutes(self):
        now = datetime.now(timezone.utc).isoformat()
        return self.conn.execute(
            "SELECT * FROM mutes WHERE active=1 AND expires_at IS NOT NULL AND expires_at <= ?",
            (now,)
        ).fetchall()

    def deactivate_mute(self, mute_id):
        self.conn.execute("UPDATE mutes SET active=0 WHERE id=?", (mute_id,))
        self.conn.commit()

    # ══════════════════════════════════════════════════════════
    #  BANS
    # ══════════════════════════════════════════════════════════
    def add_ban(self, user_id, guild_id, username, reason, moderator_id, duration=None):
        expires = None
        if duration:
            from datetime import timedelta
            expires = (datetime.now(timezone.utc) + timedelta(seconds=duration)).isoformat()
        cur = self.conn.execute(
            "INSERT INTO bans (user_id, guild_id, username, reason, moderator, duration, expires_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (user_id, guild_id, username, reason, moderator_id, duration, expires)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_ban(self, user_id, guild_id):
        return self.conn.execute(
            "SELECT * FROM bans WHERE user_id=? AND guild_id=? AND active=1 LIMIT 1",
            (user_id, guild_id)
        ).fetchone()

    def unban(self, user_id, guild_id):
        self.conn.execute(
            "UPDATE bans SET active=0 WHERE user_id=? AND guild_id=? AND active=1",
            (user_id, guild_id)
        )
        self.conn.commit()

    def get_ban_list(self, guild_id, limit=50):
        return self.conn.execute(
            "SELECT * FROM bans WHERE guild_id=? AND active=1 ORDER BY created_at DESC LIMIT ?",
            (guild_id, limit)
        ).fetchall()

    def get_expired_bans(self):
        now = datetime.now(timezone.utc).isoformat()
        return self.conn.execute(
            "SELECT * FROM bans WHERE active=1 AND expires_at IS NOT NULL AND expires_at <= ?",
            (now,)
        ).fetchall()

    # ══════════════════════════════════════════════════════════
    #  KICKS
    # ══════════════════════════════════════════════════════════
    def add_kick(self, user_id, guild_id, username, reason, moderator_id):
        cur = self.conn.execute(
            "INSERT INTO kicks (user_id, guild_id, username, reason, moderator) "
            "VALUES (?,?,?,?,?)",
            (user_id, guild_id, username, reason, moderator_id)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_kicks(self, user_id, guild_id):
        return self.conn.execute(
            "SELECT * FROM kicks WHERE user_id=? AND guild_id=? ORDER BY created_at DESC",
            (user_id, guild_id)
        ).fetchall()

    # ══════════════════════════════════════════════════════════
    #  COMPLAINTS
    # ══════════════════════════════════════════════════════════
    def add_complaint(self, guild_id, author_id, author_name, target_id,
                      target_name, category, description, evidence=None):
        cur = self.conn.execute(
            "INSERT INTO complaints "
            "(guild_id, author_id, author_name, target_id, target_name, "
            " category, description, evidence) VALUES (?,?,?,?,?,?,?,?)",
            (guild_id, author_id, author_name, target_id, target_name,
             category, description, evidence)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_complaint(self, complaint_id):
        return self.conn.execute(
            "SELECT * FROM complaints WHERE id=?", (complaint_id,)
        ).fetchone()

    def get_complaints(self, guild_id, status=None, limit=50):
        q = "SELECT * FROM complaints WHERE guild_id=?"
        params = [guild_id]
        if status:
            q += " AND status=?"
            params.append(status)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return self.conn.execute(q, params).fetchall()

    def get_user_complaints_today(self, user_id, guild_id):
        return self.conn.execute(
            "SELECT COUNT(*) FROM complaints WHERE author_id=? AND guild_id=? "
            "AND date(created_at)=date('now')",
            (user_id, guild_id)
        ).fetchone()[0]

    def update_complaint_status(self, complaint_id, status, handler_id=None, note=None, msg_id=None):
        fields = ["status=?", "updated_at=datetime('now')"]
        params = [status]
        if handler_id is not None:
            fields.append("handler_id=?"); params.append(handler_id)
        if note is not None:
            fields.append("handler_note=?"); params.append(note)
        if msg_id is not None:
            fields.append("message_id=?"); params.append(msg_id)
        params.append(complaint_id)
        self.conn.execute(
            f"UPDATE complaints SET {', '.join(fields)} WHERE id=?", params
        )
        self.conn.commit()

    def count_complaints_by_status(self, guild_id):
        rows = self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM complaints WHERE guild_id=? GROUP BY status",
            (guild_id,)
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}

    # ══════════════════════════════════════════════════════════
    #  ACTION LOG
    # ══════════════════════════════════════════════════════════
    def log_action(self, guild_id, action, actor_id=None, target_id=None, details=None):
        self.conn.execute(
            "INSERT INTO action_log (guild_id, action, actor_id, target_id, details) "
            "VALUES (?,?,?,?,?)",
            (guild_id, action, actor_id, target_id, details)
        )
        self.conn.commit()

    def get_action_log(self, guild_id, limit=100):
        return self.conn.execute(
            "SELECT * FROM action_log WHERE guild_id=? ORDER BY created_at DESC LIMIT ?",
            (guild_id, limit)
        ).fetchall()

    # ══════════════════════════════════════════════════════════
    #  SETTINGS
    # ══════════════════════════════════════════════════════════
    def get_settings(self, guild_id):
        row = self.conn.execute(
            "SELECT * FROM settings WHERE guild_id=?", (guild_id,)
        ).fetchone()
        if not row:
            self.conn.execute(
                "INSERT OR IGNORE INTO settings (guild_id) VALUES (?)", (guild_id,)
            )
            self.conn.commit()
            return self.conn.execute(
                "SELECT * FROM settings WHERE guild_id=?", (guild_id,)
            ).fetchone()
        return row

    def set_channel(self, guild_id, channel_type, channel_id):
        valid = {"log_channel","action_log_channel","join_log_channel",
                 "complaint_channel","complaint_log_channel","ban_appeal_channel"}
        if channel_type not in valid:
            return
        self.get_settings(guild_id)  # ensure row exists
        self.conn.execute(
            f"UPDATE settings SET {channel_type}=? WHERE guild_id=?",
            (channel_id, guild_id)
        )
        self.conn.commit()

    def set_muted_role(self, guild_id, role_id):
        self.get_settings(guild_id)
        self.conn.execute(
            "UPDATE settings SET muted_role=? WHERE guild_id=?", (role_id, guild_id)
        )
        self.conn.commit()

    # ── Помічник: профіль юзера ──────────────────────────────
    def get_user_profile(self, user_id, guild_id):
        return {
            "warnings": self.count_warnings(user_id, guild_id),
            "all_warnings": self.get_warnings(user_id, guild_id),
            "active_mute": self.get_active_mute(user_id, guild_id),
            "ban": self.get_ban(user_id, guild_id),
            "kicks": self.get_kicks(user_id, guild_id),
            "staff": self.get_staff(user_id, guild_id),
            "complaints_filed": self.conn.execute(
                "SELECT COUNT(*) FROM complaints WHERE author_id=? AND guild_id=?",
                (user_id, guild_id)
            ).fetchone()[0],
        }
