from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from filters import firm_match, normalize_company_name, normalize_title
from models import Candidate


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def semantic_company_key(company: str) -> str:
    matched = firm_match(company)
    return normalize_company_name(matched["canonical"] if matched else company)


@dataclass
class DedupResult:
    new: list[Candidate]
    duplicates: list[Candidate]


class InternshipStore:
    def __init__(self, path: str | Path = "seen_internships.db") -> None:
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def close(self) -> None:
        self.conn.close()

    def init_db(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                link TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                normalized_company TEXT NOT NULL,
                title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                source TEXT NOT NULL,
                tier_hint TEXT NOT NULL,
                category TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '',
                posted TEXT NOT NULL DEFAULT '',
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS jobs_semantic_idx
                ON jobs(normalized_company, normalized_title);

            CREATE TABLE IF NOT EXISTS pending_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                token TEXT NOT NULL,
                company TEXT NOT NULL,
                discovered_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                note TEXT NOT NULL DEFAULT '',
                UNIQUE(platform, token)
            );

            CREATE TABLE IF NOT EXISTS active_tokens (
                platform TEXT NOT NULL,
                token TEXT NOT NULL,
                company TEXT NOT NULL,
                tier TEXT NOT NULL DEFAULT '',
                added_at TEXT NOT NULL,
                PRIMARY KEY(platform, token)
            );

            CREATE TABLE IF NOT EXISTS rejected_tokens (
                platform TEXT NOT NULL,
                token TEXT NOT NULL,
                company TEXT NOT NULL,
                rejected_at TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(platform, token)
            );

            CREATE VIEW IF NOT EXISTS pending AS
                SELECT id, platform, token, company, discovered_at, status, note
                FROM pending_tokens;
            """
        )
        self.conn.commit()

    def has_seen_url(self, link: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM jobs WHERE link = ?", (link,)).fetchone()
        return row is not None

    def has_seen_semantic(self, company: str, title: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1 FROM jobs
            WHERE normalized_company = ? AND normalized_title = ?
            """,
            (semantic_company_key(company), normalize_title(title)),
        ).fetchone()
        return row is not None

    def dedupe(self, candidates: Iterable[Candidate], *, dry_run: bool = False) -> DedupResult:
        new: list[Candidate] = []
        duplicates: list[Candidate] = []
        seen_links: set[str] = set()
        seen_semantic: set[tuple[str, str]] = set()

        for candidate in candidates:
            semantic = (
                semantic_company_key(candidate.company),
                normalize_title(candidate.title),
            )
            if (
                candidate.link in seen_links
                or semantic in seen_semantic
                or self.has_seen_url(candidate.link)
                or self.has_seen_semantic(candidate.company, candidate.title)
            ):
                duplicates.append(candidate)
                continue
            seen_links.add(candidate.link)
            seen_semantic.add(semantic)
            new.append(candidate)

        if not dry_run:
            for candidate in new:
                self.insert_job(candidate)
            self.conn.commit()

        return DedupResult(new=new, duplicates=duplicates)

    def insert_job(self, candidate: Candidate) -> None:
        now = utc_now_iso()
        self.conn.execute(
            """
            INSERT OR REPLACE INTO jobs (
                link, company, normalized_company, title, normalized_title, source,
                tier_hint, category, location, posted, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.link,
                candidate.company,
                semantic_company_key(candidate.company),
                candidate.title,
                normalize_title(candidate.title),
                candidate.source,
                candidate.tier_hint,
                candidate.category,
                candidate.location,
                candidate.posted,
                now,
                now,
            ),
        )

    def add_pending_tokens(self, tokens: Iterable[dict[str, str]]) -> int:
        count = 0
        now = utc_now_iso()
        for token in tokens:
            platform = token["platform"]
            value = token["token"]
            if self._active_token_exists(platform, value):
                continue
            if self._rejected_token_exists(platform, value):
                continue
            cursor = self.conn.execute(
                """
                INSERT OR IGNORE INTO pending_tokens
                    (platform, token, company, discovered_at, status, note)
                VALUES (?, ?, ?, ?, 'pending', ?)
                """,
                (
                    platform,
                    value,
                    token.get("company", ""),
                    now,
                    token.get("note", ""),
                ),
            )
            count += max(cursor.rowcount, 0)
        self.conn.commit()
        return count

    def list_pending_tokens(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT id, platform, token, company, discovered_at, note
                FROM pending_tokens
                WHERE status = 'pending'
                ORDER BY discovered_at, id
                """
            )
        )

    def promote_pending(self, pending_id: int, *, tier: str = "") -> None:
        row = self.conn.execute(
            """
            SELECT id, platform, token, company
            FROM pending_tokens
            WHERE id = ? AND status = 'pending'
            """,
            (pending_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"pending token not found: {pending_id}")
        self.conn.execute(
            """
            INSERT OR IGNORE INTO active_tokens(platform, token, company, tier, added_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (row["platform"], row["token"], row["company"], tier, utc_now_iso()),
        )
        self.conn.execute(
            "UPDATE pending_tokens SET status = 'promoted' WHERE id = ?",
            (pending_id,),
        )
        self.conn.commit()

    def reject_pending(self, pending_id: int, *, reason: str = "") -> None:
        row = self.conn.execute(
            """
            SELECT id, platform, token, company
            FROM pending_tokens
            WHERE id = ? AND status = 'pending'
            """,
            (pending_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"pending token not found: {pending_id}")
        self.conn.execute(
            """
            INSERT OR REPLACE INTO rejected_tokens(platform, token, company, rejected_at, reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (row["platform"], row["token"], row["company"], utc_now_iso(), reason),
        )
        self.conn.execute(
            "UPDATE pending_tokens SET status = 'rejected', note = ? WHERE id = ?",
            (reason, pending_id),
        )
        self.conn.commit()

    def active_tokens(self) -> list[dict[str, str]]:
        rows = self.conn.execute(
            "SELECT platform, token, company, tier FROM active_tokens ORDER BY platform, company"
        ).fetchall()
        return [dict(row) for row in rows]

    def prune_active_token(self, token: str, *, platform: str | None = None) -> int:
        if platform:
            cursor = self.conn.execute(
                "DELETE FROM active_tokens WHERE platform = ? AND token = ?",
                (platform, token),
            )
        else:
            cursor = self.conn.execute(
                "DELETE FROM active_tokens WHERE token = ?",
                (token,),
            )
        self.conn.commit()
        return max(cursor.rowcount, 0)

    def _active_token_exists(self, platform: str, token: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM active_tokens WHERE platform = ? AND token = ?",
            (platform, token),
        ).fetchone()
        return row is not None

    def _rejected_token_exists(self, platform: str, token: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM rejected_tokens WHERE platform = ? AND token = ?",
            (platform, token),
        ).fetchone()
        return row is not None
