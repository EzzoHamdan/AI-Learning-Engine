"""SQLite persistence for learning analytics (the durable side of analytics).

Session-state (ui/tracking.py) only remembers the current run, so streaks and
improvement-over-time reset on every browser refresh. This store writes the same
events to `~/.learning_engine/analytics.db` (path from settings) so they survive,
turning "study streaks" and "progress over time" from advertised into true.

Pure stdlib (`sqlite3`) — imports nothing from the project and no Streamlit, so it
sits below `ui/` (architecture rule R1) and is testable without a Streamlit context.
The read API deliberately returns the SAME shapes the in-session tracker exposes and
that analytics/metrics.py consumes, so the dashboard renders either source unchanged.

Timestamps are stored as UTC ISO-8601 and read back as local-timezone-aware datetimes,
so `.date()` lines up with the dashboard's `datetime.now().date()` used for streaks.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quiz_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT    NOT NULL,
    difficulty      TEXT    NOT NULL,
    quiz_type       TEXT    NOT NULL,
    total_questions INTEGER NOT NULL,
    correct         INTEGER NOT NULL,
    score_pct       REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS question_results (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id        INTEGER NOT NULL REFERENCES quiz_results(id) ON DELETE CASCADE,
    qtype          TEXT    NOT NULL,
    correct        INTEGER NOT NULL,
    difficulty_tag TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS material_events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT    NOT NULL,
    mtype   TEXT    NOT NULL,
    seconds REAL    NOT NULL,
    success INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS flashcard_events (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     TEXT    NOT NULL,
    action TEXT    NOT NULL
);
"""

# Flashcard action -> the counter key the dashboard/metrics expect.
_FLASHCARD_COUNTERS = {
    "viewed": "cards_viewed",
    "correct": "correct_responses",
    "incorrect": "incorrect_responses",
    "skipped": "skipped_responses",
}


def _to_iso(ts: datetime | None) -> str:
    """Normalize a timestamp to a UTC ISO-8601 string (naive is read as local)."""
    if ts is None:
        return datetime.now(UTC).isoformat()
    if ts.tzinfo is None:
        ts = ts.astimezone()  # interpret a naive datetime as local time
    return ts.astimezone(UTC).isoformat()


def _from_iso(s: str) -> datetime:
    """Parse a stored UTC ISO-8601 string back into a local-timezone datetime."""
    return datetime.fromisoformat(s).astimezone()


class AnalyticsStore:
    """SQLite-backed store for quiz/material/flashcard events.

    One short-lived connection per call keeps this safe across Streamlit reruns
    (no long-lived connection shared between threads). `init()` is idempotent.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self.init()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        """Create the schema if it does not exist (safe to call repeatedly)."""
        parent = Path(self._path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------ #
    # Writes
    # ------------------------------------------------------------------ #

    def record_quiz(
        self,
        *,
        difficulty: str,
        quiz_type: str,
        total_questions: int,
        correct: int,
        score_pct: float,
        questions: list[dict],
        ts: datetime | None = None,
    ) -> int:
        """Persist one completed quiz plus its per-question outcomes.

        `questions` items use the tracker's shape: `question_type`, `correct`
        (bool), `difficulty_tag`. Returns the new quiz row id.
        """
        iso = _to_iso(ts)
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO quiz_results "
                "(ts, difficulty, quiz_type, total_questions, correct, score_pct) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (iso, difficulty, quiz_type, total_questions, correct, score_pct),
            )
            # lastrowid is Optional in the stubs but always set after an INSERT.
            quiz_id = int(cur.lastrowid or 0)
            conn.executemany(
                "INSERT INTO question_results (quiz_id, qtype, correct, difficulty_tag) "
                "VALUES (?, ?, ?, ?)",
                [
                    (
                        quiz_id,
                        q.get("question_type", "mcq_tf"),
                        int(bool(q.get("correct", False))),
                        q.get("difficulty_tag", "basic"),
                    )
                    for q in questions
                ],
            )
        return quiz_id

    def record_material_event(
        self, mtype: str, seconds: float, success: bool, ts: datetime | None = None
    ) -> None:
        """Persist one study-material generation attempt."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO material_events (ts, mtype, seconds, success) VALUES (?, ?, ?, ?)",
                (_to_iso(ts), mtype, float(seconds), int(bool(success))),
            )

    def record_flashcard_event(self, action: str, ts: datetime | None = None) -> None:
        """Persist one flashcard interaction (viewed/correct/incorrect/skipped)."""
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO flashcard_events (ts, action) VALUES (?, ?)",
                (_to_iso(ts), action),
            )

    # ------------------------------------------------------------------ #
    # Reads — shapes mirror ui/tracking.py so the dashboard reuses render code
    # ------------------------------------------------------------------ #

    def performance_over_time(self) -> list[dict]:
        """Chronological quiz scores (for the trend chart + velocity/average)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ts, score_pct, difficulty, quiz_type, total_questions, correct "
                "FROM quiz_results ORDER BY ts, id"
            ).fetchall()
        return [
            {
                "timestamp": _from_iso(r["ts"]),
                "score_percentage": r["score_pct"],
                "difficulty": r["difficulty"],
                "quiz_type": r["quiz_type"],
                "total_questions": r["total_questions"],
                "correct_answers": r["correct"],
            }
            for r in rows
        ]

    def difficulty_breakdown(self) -> dict[str, int]:
        """Quiz count grouped by difficulty."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT difficulty, COUNT(*) AS n FROM quiz_results GROUP BY difficulty"
            ).fetchall()
        return {r["difficulty"]: r["n"] for r in rows}

    def type_breakdown(self) -> dict[str, int]:
        """Quiz count grouped by (normalized) quiz type."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT quiz_type, COUNT(*) AS n FROM quiz_results GROUP BY quiz_type"
            ).fetchall()
        return {r["quiz_type"]: r["n"] for r in rows}

    def totals(self) -> dict[str, int]:
        """Aggregate quiz counters across all history."""
        with self._connect() as conn:
            r = conn.execute(
                "SELECT COUNT(*) AS quizzes, "
                "COALESCE(SUM(total_questions), 0) AS questions, "
                "COALESCE(SUM(correct), 0) AS correct FROM quiz_results"
            ).fetchone()
        return {
            "total_quizzes": r["quizzes"],
            "total_questions": r["questions"],
            "total_correct": r["correct"],
        }

    def detailed_results(self) -> list[dict]:
        """Per-quiz detail incl. per-question outcomes (strengths/weaknesses input)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT q.id, q.ts, q.difficulty, q.quiz_type, q.score_pct, "
                "qr.qtype, qr.correct, qr.difficulty_tag "
                "FROM quiz_results q LEFT JOIN question_results qr ON qr.quiz_id = q.id "
                "ORDER BY q.ts, q.id, qr.id"
            ).fetchall()

        by_quiz: dict[int, dict] = {}
        for r in rows:
            quiz = by_quiz.get(r["id"])
            if quiz is None:
                quiz = {
                    "timestamp": _from_iso(r["ts"]),
                    "difficulty": r["difficulty"],
                    "quiz_type": r["quiz_type"],
                    "overall_score": r["score_pct"],
                    "questions": [],
                }
                by_quiz[r["id"]] = quiz
            if r["qtype"] is not None:  # LEFT JOIN yields NULLs for a question-less quiz
                quiz["questions"].append(
                    {
                        "question_type": r["qtype"],
                        "correct": bool(r["correct"]),
                        "difficulty_tag": r["difficulty_tag"],
                    }
                )
        return list(by_quiz.values())

    def material_stats(self) -> dict:
        """Materials analytics in the tracker's `materials_analytics` shape."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ts, mtype, seconds, success FROM material_events ORDER BY ts, id"
            ).fetchall()

        material_types: dict[str, int] = {}
        generation_times: list[dict] = []
        total_materials = 0
        for r in rows:
            success = bool(r["success"])
            if success:
                total_materials += 1
                material_types[r["mtype"]] = material_types.get(r["mtype"], 0) + 1
            generation_times.append(
                {
                    "timestamp": _from_iso(r["ts"]),
                    "material_type": r["mtype"],
                    "generation_time": r["seconds"],
                    "success": success,
                }
            )
        return {
            "total_materials": total_materials,
            "material_types": material_types,
            "generation_times": generation_times,
        }

    def flashcard_totals(self) -> dict[str, int]:
        """Flashcard interaction counters in the `flashcard_interactions` shape."""
        counters = {v: 0 for v in _FLASHCARD_COUNTERS.values()}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT action, COUNT(*) AS n FROM flashcard_events GROUP BY action"
            ).fetchall()
        for r in rows:
            key = _FLASHCARD_COUNTERS.get(r["action"])
            if key:
                counters[key] = r["n"]
        return counters

    def learning_history(self) -> list[dict]:
        """Unified, time-sorted activity timeline across all event types.

        Powers both the detailed-analysis timeline and the all-time streak
        (its per-entry `.date()` becomes the active-days set).
        """
        history: list[dict] = []
        with self._connect() as conn:
            for r in conn.execute(
                "SELECT ts, difficulty, quiz_type, total_questions, score_pct FROM quiz_results"
            ).fetchall():
                history.append(
                    {
                        "timestamp": _from_iso(r["ts"]),
                        "type": "quiz_completion",
                        "data": {
                            "score": r["score_pct"],
                            "difficulty": r["difficulty"],
                            "type": r["quiz_type"],
                            "questions": r["total_questions"],
                        },
                    }
                )
            for r in conn.execute(
                "SELECT ts, mtype, seconds, success FROM material_events"
            ).fetchall():
                history.append(
                    {
                        "timestamp": _from_iso(r["ts"]),
                        "type": "materials_generation",
                        "data": {
                            "type": r["mtype"],
                            "success": bool(r["success"]),
                            "time": r["seconds"],
                        },
                    }
                )
            for r in conn.execute("SELECT ts, action FROM flashcard_events").fetchall():
                history.append(
                    {
                        "timestamp": _from_iso(r["ts"]),
                        "type": "flashcard_review",
                        "data": {"action": r["action"]},
                    }
                )
        history.sort(key=lambda e: e["timestamp"])
        return history

    def active_days(self) -> set[date]:
        """Distinct local calendar days with any recorded activity."""
        return {entry["timestamp"].date() for entry in self.learning_history()}

    # ------------------------------------------------------------------ #
    # Maintenance
    # ------------------------------------------------------------------ #

    def export(self) -> dict[str, list[dict]]:
        """Dump every table as JSON-ready rows (raw UTC timestamps preserved)."""
        tables = ["quiz_results", "question_results", "material_events", "flashcard_events"]
        out: dict[str, list[dict]] = {}
        with self._connect() as conn:
            for table in tables:
                rows = conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
                out[table] = [dict(r) for r in rows]
        return out

    def reset(self) -> None:
        """Delete all recorded data (keeps the schema). Used by "Reset my data"."""
        with self._connect() as conn:
            for table in (
                "question_results",
                "quiz_results",
                "material_events",
                "flashcard_events",
            ):
                conn.execute(f"DELETE FROM {table}")
