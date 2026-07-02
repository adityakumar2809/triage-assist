"""SQLite persistence helpers for screening history and admin analytics."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.data.load_curated import (
    load_body_system_groups,
    load_category_lookup,
    load_danger_phrase_rules,
    load_red_flag_rules,
)
from app.data.symptom_vocabulary import (
    FROZEN_SYMPTOM_COLUMNS,
    FROZEN_SYMPTOM_ORDER,
)

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "triage_assist.sqlite3"
MODEL_METRICS_PATH = (
    Path(__file__).resolve().parents[1]
    / "model"
    / "model_comparison_metrics.json"
)


@dataclass(frozen=True)
class ScreeningStore:
    """Persistence gateway for B9 screening history and analytics."""

    db_path: Path

    def initialize(self) -> None:
        """Create the schema and seed reference/audit tables once."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._create_schema(connection)
            self._seed_reference_tables(connection)

    def persist_screening(
        self,
        *,
        entered_structured_symptoms: list[str],
        entered_free_text_symptoms: list[str],
        understood_confirmed_symptoms: list[str],
        understood_unsure_symptoms: list[str],
        risk_answers: dict[str, str],
        result_object: dict[str, Any],
        unmatched_tokens: list[str],
        disclaimer_version: str,
    ) -> str:
        """Persist one completed screening and return its session id."""
        session_id = str(uuid4())
        created_at = _utc_iso_now()

        structured_symptoms = _canonicalize_symptoms(
            entered_structured_symptoms
        )
        free_text_symptoms = _canonicalize_symptoms(entered_free_text_symptoms)
        confirmed_symptoms = _canonicalize_symptoms(
            understood_confirmed_symptoms
        )
        unsure_symptoms = [
            symptom
            for symptom in _canonicalize_symptoms(understood_unsure_symptoms)
            if symptom not in set(confirmed_symptoms)
        ]
        normalized_unmatched_tokens = _normalize_tokens(unmatched_tokens)

        emergency_routed = int(
            bool(result_object.get("emergency_routed", False))
        )
        low_confidence = int(bool(result_object.get("low_confidence", False)))
        model_confidence = _coerce_optional_float(
            result_object.get("model_confidence")
        )
        urgency = str(result_object.get("urgency", "moderate"))
        urgency_message = str(result_object.get("urgency_message", ""))
        point_of_care = str(
            result_object.get("point_of_care", "General Physician")
        )
        point_of_care_note = str(result_object.get("point_of_care_note", ""))
        seek_sooner_if = result_object.get("seek_sooner_if", [])
        if not isinstance(seek_sooner_if, list):
            seek_sooner_if = []

        predicted_categories = _normalize_predicted_categories(
            result_object.get("predicted_categories")
        )
        primary_category_name = _resolve_primary_category_name(
            result_object=result_object,
            predicted_categories=predicted_categories,
            low_confidence=bool(low_confidence),
            emergency_routed=bool(emergency_routed),
        )

        with self._connect() as connection:
            symptom_id_by_name = _load_symptom_id_by_name(connection)
            category_id_by_name = _load_category_id_by_name(connection)
            specialist_rows = _load_specialist_rows(connection)
            specialist_group_id = _resolve_specialist_group_id(
                point_of_care=point_of_care,
                specialist_rows=specialist_rows,
            )
            primary_category_id = (
                category_id_by_name.get(primary_category_name)
                if primary_category_name
                else None
            )

            with connection:
                connection.execute(
                    """
                    INSERT INTO screening_session (
                        session_id,
                        created_at,
                        emergency_routed,
                        low_confidence,
                        model_confidence
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        created_at,
                        emergency_routed,
                        low_confidence,
                        model_confidence,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO triage_result (
                        session_id,
                        urgency,
                        urgency_message,
                        point_of_care,
                        point_of_care_note,
                        specialist_group_id,
                        primary_category_id,
                        seek_sooner_if,
                        disclaimer_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        urgency,
                        urgency_message,
                        point_of_care,
                        point_of_care_note,
                        specialist_group_id,
                        primary_category_id,
                        json.dumps(seek_sooner_if),
                        disclaimer_version,
                    ),
                )
                _insert_entered_symptoms(
                    connection=connection,
                    session_id=session_id,
                    symptom_id_by_name=symptom_id_by_name,
                    structured_symptoms=structured_symptoms,
                    free_text_symptoms=free_text_symptoms,
                )
                _insert_understood_symptoms(
                    connection=connection,
                    session_id=session_id,
                    symptom_id_by_name=symptom_id_by_name,
                    confirmed_symptoms=confirmed_symptoms,
                    unsure_symptoms=unsure_symptoms,
                )
                _insert_risk_answers(
                    connection=connection,
                    session_id=session_id,
                    risk_answers=risk_answers,
                )
                _insert_predicted_categories(
                    connection=connection,
                    session_id=session_id,
                    category_id_by_name=category_id_by_name,
                    predicted_categories=predicted_categories,
                )
                _increment_unmatched_token_stats(
                    connection=connection,
                    tokens=normalized_unmatched_tokens,
                    timestamp=created_at,
                )
        return session_id

    def list_history(self, session_ids: list[str]) -> list[dict[str, str]]:
        """Return persisted history rows scoped to held session ids."""
        normalized_ids = _normalize_session_ids(session_ids)
        if not normalized_ids:
            return []

        placeholders = ",".join("?" for _ in normalized_ids)
        query = f"""
            SELECT
                tr.session_id AS session_id,
                ss.created_at AS created_at,
                tr.urgency AS urgency,
                tr.point_of_care AS point_of_care
            FROM triage_result tr
            JOIN screening_session ss
                ON ss.session_id = tr.session_id
            WHERE tr.session_id IN ({placeholders})
            ORDER BY ss.created_at DESC
        """
        with self._connect() as connection:
            rows = connection.execute(query, normalized_ids).fetchall()
        return [
            {
                "session_id": str(row["session_id"]),
                "created_at": str(row["created_at"]),
                "urgency": str(row["urgency"]),
                "point_of_care": str(row["point_of_care"]),
            }
            for row in rows
        ]

    def get_result_view(
        self,
        *,
        session_id: str,
        disclaimer_text: str,
    ) -> dict[str, Any] | None:
        """Load a persisted session as the user-facing result view."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    tr.urgency,
                    tr.urgency_message,
                    tr.point_of_care,
                    tr.point_of_care_note,
                    tr.seek_sooner_if,
                    ss.low_confidence,
                    ss.emergency_routed,
                    ss.created_at
                FROM triage_result tr
                JOIN screening_session ss
                    ON ss.session_id = tr.session_id
                WHERE tr.session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if row is None:
                return None

            symptoms_rows = connection.execute(
                """
                SELECT s.canonical_name
                FROM understood_symptom us
                JOIN symptom s
                    ON s.symptom_id = us.symptom_id
                WHERE us.session_id = ? AND us.confirmed = 1
                ORDER BY s.symptom_id ASC
                """,
                (session_id,),
            ).fetchall()
            areas_rows = connection.execute(
                """
                SELECT ad.safe_phrasing
                FROM predicted_category pc
                JOIN advisory_display ad
                    ON ad.category_id = pc.category_id
                WHERE pc.session_id = ?
                ORDER BY pc.rank ASC
                """,
                (session_id,),
            ).fetchall()

        seek_sooner_if = _decode_seek_sooner_if(row["seek_sooner_if"])
        return {
            "result": {
                "urgency": str(row["urgency"]),
                "urgency_message": str(row["urgency_message"]),
                "point_of_care": str(row["point_of_care"]),
                "point_of_care_note": str(row["point_of_care_note"] or ""),
                "symptoms_understood": [
                    str(item["canonical_name"]) for item in symptoms_rows
                ],
                "areas_to_discuss": [
                    str(item["safe_phrasing"]) for item in areas_rows
                ],
                "seek_sooner_if": seek_sooner_if,
                "low_confidence": bool(row["low_confidence"]),
                "emergency_routed": bool(row["emergency_routed"]),
                "disclaimer": disclaimer_text,
            },
            "created_at": str(row["created_at"]),
        }

    def get_admin_analytics(
        self,
        *,
        selected_model_name: str,
    ) -> dict[str, Any]:
        """Return aggregate-only analytics for the admin dashboard."""
        with self._connect() as connection:
            total_screenings = int(
                connection.execute(
                    "SELECT COUNT(*) AS row_count FROM screening_session"
                ).fetchone()["row_count"]
            )
            urgency_distribution = connection.execute(
                """
                SELECT urgency, COUNT(*) AS row_count
                FROM triage_result
                GROUP BY urgency
                ORDER BY row_count DESC, urgency ASC
                """
            ).fetchall()
            common_symptoms = connection.execute(
                """
                SELECT s.canonical_name, COUNT(*) AS row_count
                FROM understood_symptom us
                JOIN symptom s ON s.symptom_id = us.symptom_id
                WHERE us.confirmed = 1
                GROUP BY s.canonical_name
                ORDER BY row_count DESC, s.canonical_name ASC
                LIMIT 10
                """
            ).fetchall()
            frequent_categories = connection.execute(
                """
                SELECT cc.category_name, COUNT(*) AS row_count
                FROM triage_result tr
                JOIN condition_category cc
                    ON cc.category_id = tr.primary_category_id
                WHERE tr.primary_category_id IS NOT NULL
                GROUP BY cc.category_name
                ORDER BY row_count DESC, cc.category_name ASC
                LIMIT 10
                """
            ).fetchall()
            daily_counts = connection.execute(
                """
                SELECT substr(created_at, 1, 10) AS created_day,
                       COUNT(*) AS row_count
                FROM screening_session
                GROUP BY created_day
                ORDER BY created_day DESC
                LIMIT 14
                """
            ).fetchall()
            confidence_row = connection.execute(
                """
                SELECT
                    COUNT(model_confidence) AS scored_count,
                    AVG(model_confidence) AS average_confidence
                FROM screening_session
                WHERE model_confidence IS NOT NULL
                """
            ).fetchone()
            model_metric_rows = connection.execute(
                """
                SELECT metric_name, metric_value
                FROM model_performance
                WHERE model_name = ?
                ORDER BY metric_name ASC
                """,
                (selected_model_name,),
            ).fetchall()

        return {
            "total_screenings": total_screenings,
            "urgency_distribution": [
                {
                    "urgency": str(row["urgency"]),
                    "count": int(row["row_count"]),
                }
                for row in urgency_distribution
            ],
            "common_symptoms": [
                {
                    "symptom": str(row["canonical_name"]),
                    "count": int(row["row_count"]),
                }
                for row in common_symptoms
            ],
            "frequent_categories": [
                {
                    "category": str(row["category_name"]),
                    "count": int(row["row_count"]),
                }
                for row in frequent_categories
            ],
            "daily_counts": [
                {
                    "date": str(row["created_day"]),
                    "count": int(row["row_count"]),
                }
                for row in daily_counts
            ],
            "confidence_summary": {
                "scored_count": int(confidence_row["scored_count"]),
                "average_confidence": (
                    None
                    if confidence_row["average_confidence"] is None
                    else round(float(confidence_row["average_confidence"]), 4)
                ),
            },
            "model_performance": {
                "selected_model_name": selected_model_name,
                "metrics": {
                    str(row["metric_name"]): round(
                        float(row["metric_value"]), 6
                    )
                    for row in model_metric_rows
                },
            },
        }

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        """Create all B9 schema tables if they do not already exist."""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS symptom (
                symptom_id INTEGER PRIMARY KEY,
                canonical_name TEXT NOT NULL UNIQUE,
                column_class TEXT NOT NULL
                    CHECK (column_class IN ('S', 'H', 'C')),
                body_system TEXT
            );

            CREATE TABLE IF NOT EXISTS specialist_group (
                specialist_group_id INTEGER PRIMARY KEY,
                group_name TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL
                    CHECK (kind IN ('primary', 'note_only', 'reserved'))
            );

            CREATE TABLE IF NOT EXISTS condition_category (
                category_id INTEGER PRIMARY KEY,
                category_name TEXT NOT NULL UNIQUE,
                severity_tier INTEGER NOT NULL
                    CHECK (severity_tier IN (1, 2, 3, 4)),
                specialist_group_id INTEGER NOT NULL,
                FOREIGN KEY (specialist_group_id)
                    REFERENCES specialist_group(specialist_group_id)
            );

            CREATE TABLE IF NOT EXISTS advisory_display (
                category_id INTEGER PRIMARY KEY,
                safe_phrasing TEXT NOT NULL,
                point_of_care_note TEXT,
                FOREIGN KEY (category_id)
                    REFERENCES condition_category(category_id)
            );

            CREATE TABLE IF NOT EXISTS screening_session (
                session_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                emergency_routed INTEGER NOT NULL
                    CHECK (emergency_routed IN (0, 1)),
                low_confidence INTEGER NOT NULL
                    CHECK (low_confidence IN (0, 1)),
                model_confidence REAL
            );

            CREATE TABLE IF NOT EXISTS entered_symptom (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                symptom_id INTEGER NOT NULL,
                source TEXT NOT NULL
                    CHECK (source IN ('structured', 'free_text')),
                UNIQUE(session_id, symptom_id, source),
                FOREIGN KEY (session_id)
                    REFERENCES screening_session(session_id),
                FOREIGN KEY (symptom_id) REFERENCES symptom(symptom_id)
            );

            CREATE TABLE IF NOT EXISTS understood_symptom (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                symptom_id INTEGER NOT NULL,
                confirmed INTEGER NOT NULL CHECK (confirmed IN (0, 1)),
                UNIQUE(session_id, symptom_id),
                FOREIGN KEY (session_id)
                    REFERENCES screening_session(session_id),
                FOREIGN KEY (symptom_id) REFERENCES symptom(symptom_id)
            );

            CREATE TABLE IF NOT EXISTS risk_factor_answer (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                answer INTEGER NOT NULL CHECK (answer IN (0, 1)),
                UNIQUE(session_id, feature_name),
                FOREIGN KEY (session_id)
                    REFERENCES screening_session(session_id)
            );

            CREATE TABLE IF NOT EXISTS triage_result (
                session_id TEXT PRIMARY KEY,
                urgency TEXT NOT NULL CHECK (
                    urgency IN ('low', 'moderate', 'high', 'emergency')
                ),
                urgency_message TEXT NOT NULL,
                point_of_care TEXT NOT NULL,
                point_of_care_note TEXT,
                specialist_group_id INTEGER,
                primary_category_id INTEGER,
                seek_sooner_if TEXT,
                disclaimer_version TEXT NOT NULL,
                FOREIGN KEY (session_id)
                    REFERENCES screening_session(session_id),
                FOREIGN KEY (specialist_group_id)
                    REFERENCES specialist_group(specialist_group_id),
                FOREIGN KEY (primary_category_id)
                    REFERENCES condition_category(category_id)
            );

            CREATE TABLE IF NOT EXISTS predicted_category (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                probability REAL NOT NULL,
                UNIQUE(session_id, rank),
                FOREIGN KEY (session_id)
                    REFERENCES screening_session(session_id),
                FOREIGN KEY (category_id)
                    REFERENCES condition_category(category_id)
            );

            CREATE TABLE IF NOT EXISTS unmatched_token_stat (
                token TEXT PRIMARY KEY,
                occurrence_count INTEGER NOT NULL,
                last_seen_at TEXT
            );

            CREATE TABLE IF NOT EXISTS red_flag_rule (
                rule_id INTEGER PRIMARY KEY,
                trigger_type TEXT NOT NULL CHECK (
                    trigger_type IN ('red_flag_symptom', 'danger_phrase')
                ),
                trigger_value TEXT NOT NULL,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS model_performance (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                recorded_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL
            );
            """
        )

    def _seed_reference_tables(self, connection: sqlite3.Connection) -> None:
        """Seed read-mostly tables from frozen artifacts and metrics."""
        if _table_row_count(connection, "symptom") == 0:
            self._seed_symptoms(connection)
        if _table_row_count(connection, "specialist_group") == 0:
            self._seed_categories_and_specialists(connection)
        if _table_row_count(connection, "red_flag_rule") == 0:
            self._seed_red_flag_rules(connection)
        if _table_row_count(connection, "model_performance") == 0:
            self._seed_model_performance(connection)

    def _seed_symptoms(self, connection: sqlite3.Connection) -> None:
        """Insert the frozen vocabulary as the `symptom` reference table."""
        symptom_to_body_system: dict[str, str] = {}
        for body_system, symptoms in load_body_system_groups().items():
            for symptom_name in symptoms:
                symptom_to_body_system[symptom_name] = body_system

        rows = [
            (
                int(index),
                str(name),
                str(class_tag).replace("*", ""),
                symptom_to_body_system.get(str(name)),
            )
            for index, name, class_tag in FROZEN_SYMPTOM_COLUMNS
        ]
        with connection:
            connection.executemany(
                """
                INSERT INTO symptom (
                    symptom_id,
                    canonical_name,
                    column_class,
                    body_system
                ) VALUES (?, ?, ?, ?)
                """,
                rows,
            )

    def _seed_categories_and_specialists(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        """Insert lookup-driven specialist/category/advisory reference rows."""
        lookup_rows = load_category_lookup()
        seen_specialists: set[str] = set()
        specialist_names: list[str] = []
        for row in lookup_rows:
            point_of_care = str(row["point_of_care"])
            if point_of_care not in seen_specialists:
                seen_specialists.add(point_of_care)
                specialist_names.append(point_of_care)
        for reserved_name in ("General Physician", "Emergency Department"):
            if reserved_name not in seen_specialists:
                seen_specialists.add(reserved_name)
                specialist_names.append(reserved_name)

        specialist_rows: list[tuple[int, str, str]] = []
        for index, name in enumerate(specialist_names, start=1):
            kind = (
                "reserved"
                if name in {"General Physician", "Emergency Department"}
                else "primary"
            )
            specialist_rows.append((index, name, kind))

        specialist_id_by_name = {row[1]: row[0] for row in specialist_rows}
        category_rows: list[tuple[int, str, int, int]] = []
        advisory_rows: list[tuple[int, str, str]] = []
        for index, row in enumerate(lookup_rows, start=1):
            severity_tier = int(str(row["severity_tier"]).split()[-1])
            category_rows.append(
                (
                    index,
                    str(row["condition_category"]),
                    severity_tier,
                    specialist_id_by_name[str(row["point_of_care"])],
                )
            )
            advisory_rows.append(
                (
                    index,
                    str(row["safe_display_phrasing"]),
                    str(row.get("point_of_care_note", "")),
                )
            )

        with connection:
            connection.executemany(
                """
                INSERT INTO specialist_group (
                    specialist_group_id,
                    group_name,
                    kind
                ) VALUES (?, ?, ?)
                """,
                specialist_rows,
            )
            connection.executemany(
                """
                INSERT INTO condition_category (
                    category_id,
                    category_name,
                    severity_tier,
                    specialist_group_id
                ) VALUES (?, ?, ?, ?)
                """,
                category_rows,
            )
            connection.executemany(
                """
                INSERT INTO advisory_display (
                    category_id,
                    safe_phrasing,
                    point_of_care_note
                ) VALUES (?, ?, ?)
                """,
                advisory_rows,
            )

    def _seed_red_flag_rules(self, connection: sqlite3.Connection) -> None:
        """Insert the audit-only mirror of red-flag and danger-phrase rules."""
        red_flag_rules = load_red_flag_rules()
        danger_phrase_rules = load_danger_phrase_rules()
        rows: list[tuple[int, str, str, str]] = []
        next_rule_id = 1

        for symptom_name in red_flag_rules.get("solo_triggers", []):
            rows.append(
                (
                    next_rule_id,
                    "red_flag_symptom",
                    str(symptom_name),
                    "",
                )
            )
            next_rule_id += 1

        for entry in danger_phrase_rules:
            note = str(entry.get("emergency_category", ""))
            for phrase in entry.get("phrases", []):
                rows.append(
                    (
                        next_rule_id,
                        "danger_phrase",
                        str(phrase),
                        note,
                    )
                )
                next_rule_id += 1

        with connection:
            connection.executemany(
                """
                INSERT INTO red_flag_rule (
                    rule_id,
                    trigger_type,
                    trigger_value,
                    note
                ) VALUES (?, ?, ?, ?)
                """,
                rows,
            )

    def _seed_model_performance(self, connection: sqlite3.Connection) -> None:
        """Seed model metrics from the bundled evaluation artifact."""
        with MODEL_METRICS_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        recorded_at = _utc_iso_now()
        metric_names = (
            "macro_f1",
            "weighted_f1",
            "accuracy",
            "vignette_top1_match_count",
            "vignette_expected_in_top3_count",
        )
        rows: list[tuple[str, str, float, str]] = []
        for result_row in payload.get("results", []):
            model_name = str(result_row.get("model_name", ""))
            for metric_name in metric_names:
                if metric_name not in result_row:
                    continue
                rows.append(
                    (
                        model_name,
                        metric_name,
                        float(result_row[metric_name]),
                        recorded_at,
                    )
                )

        with connection:
            connection.executemany(
                """
                INSERT INTO model_performance (
                    model_name,
                    metric_name,
                    metric_value,
                    recorded_at
                ) VALUES (?, ?, ?, ?)
                """,
                rows,
            )

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with row dict access and FK checks."""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def resolve_db_path(raw_path: str | None) -> Path:
    """Resolve an optional db path override."""
    if raw_path is None or not raw_path.strip():
        return DEFAULT_DB_PATH
    return Path(raw_path).expanduser().resolve()


def _table_row_count(connection: sqlite3.Connection, table_name: str) -> int:
    row = connection.execute(
        f"SELECT COUNT(*) AS row_count FROM {table_name}"
    ).fetchone()
    return int(row["row_count"])


def _load_symptom_id_by_name(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    rows = connection.execute(
        "SELECT symptom_id, canonical_name FROM symptom"
    ).fetchall()
    return {str(row["canonical_name"]): int(row["symptom_id"]) for row in rows}


def _load_category_id_by_name(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    rows = connection.execute(
        "SELECT category_id, category_name FROM condition_category"
    ).fetchall()
    return {str(row["category_name"]): int(row["category_id"]) for row in rows}


def _load_specialist_rows(
    connection: sqlite3.Connection,
) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT specialist_group_id, group_name, kind
        FROM specialist_group
        """
    ).fetchall()
    return {
        str(row["group_name"]): {
            "specialist_group_id": int(row["specialist_group_id"]),
            "kind": str(row["kind"]),
        }
        for row in rows
    }


def _resolve_specialist_group_id(
    *,
    point_of_care: str,
    specialist_rows: dict[str, dict[str, Any]],
) -> int | None:
    row = specialist_rows.get(point_of_care)
    if row is None:
        return None
    if row["kind"] != "primary":
        return None
    return int(row["specialist_group_id"])


def _insert_entered_symptoms(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    symptom_id_by_name: dict[str, int],
    structured_symptoms: list[str],
    free_text_symptoms: list[str],
) -> None:
    rows: list[tuple[str, int, str]] = []
    for symptom_name in structured_symptoms:
        symptom_id = symptom_id_by_name.get(symptom_name)
        if symptom_id is None:
            continue
        rows.append((session_id, symptom_id, "structured"))
    for symptom_name in free_text_symptoms:
        symptom_id = symptom_id_by_name.get(symptom_name)
        if symptom_id is None:
            continue
        rows.append((session_id, symptom_id, "free_text"))

    connection.executemany(
        """
        INSERT OR IGNORE INTO entered_symptom (
            session_id,
            symptom_id,
            source
        ) VALUES (?, ?, ?)
        """,
        rows,
    )


def _insert_understood_symptoms(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    symptom_id_by_name: dict[str, int],
    confirmed_symptoms: list[str],
    unsure_symptoms: list[str],
) -> None:
    rows: list[tuple[str, int, int]] = []
    for symptom_name in confirmed_symptoms:
        symptom_id = symptom_id_by_name.get(symptom_name)
        if symptom_id is None:
            continue
        rows.append((session_id, symptom_id, 1))
    for symptom_name in unsure_symptoms:
        symptom_id = symptom_id_by_name.get(symptom_name)
        if symptom_id is None:
            continue
        rows.append((session_id, symptom_id, 0))

    connection.executemany(
        """
        INSERT OR IGNORE INTO understood_symptom (
            session_id,
            symptom_id,
            confirmed
        ) VALUES (?, ?, ?)
        """,
        rows,
    )


def _insert_risk_answers(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    risk_answers: dict[str, str],
) -> None:
    rows = [
        (
            session_id,
            feature_name,
            int(answer == "yes"),
        )
        for feature_name, answer in sorted(risk_answers.items())
    ]
    connection.executemany(
        """
        INSERT OR REPLACE INTO risk_factor_answer (
            session_id,
            feature_name,
            answer
        ) VALUES (?, ?, ?)
        """,
        rows,
    )


def _insert_predicted_categories(
    *,
    connection: sqlite3.Connection,
    session_id: str,
    category_id_by_name: dict[str, int],
    predicted_categories: list[dict[str, Any]],
) -> None:
    rows: list[tuple[str, int, int, float]] = []
    for default_rank, item in enumerate(predicted_categories, start=1):
        category_name = str(item.get("category", ""))
        category_id = category_id_by_name.get(category_name)
        if category_id is None:
            continue
        rank = int(item.get("rank", default_rank))
        probability = float(item.get("probability", 0.0))
        probability = max(0.0, min(1.0, probability))
        rows.append((session_id, category_id, rank, probability))

    connection.executemany(
        """
        INSERT OR REPLACE INTO predicted_category (
            session_id,
            category_id,
            rank,
            probability
        ) VALUES (?, ?, ?, ?)
        """,
        rows,
    )


def _increment_unmatched_token_stats(
    *,
    connection: sqlite3.Connection,
    tokens: list[str],
    timestamp: str,
) -> None:
    for token in tokens:
        connection.execute(
            """
            INSERT INTO unmatched_token_stat (
                token,
                occurrence_count,
                last_seen_at
            ) VALUES (?, 1, ?)
            ON CONFLICT(token) DO UPDATE SET
                occurrence_count = occurrence_count + 1,
                last_seen_at = excluded.last_seen_at
            """,
            (token, timestamp),
        )


def _decode_seek_sooner_if(raw_value: Any) -> list[str]:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return []
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


def _normalize_predicted_categories(raw_value: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_value, start=1):
        if not isinstance(item, dict):
            continue
        category_name = str(item.get("category", "")).strip()
        if not category_name:
            continue
        probability = _coerce_optional_float(item.get("probability"))
        if probability is None:
            continue
        rank = item.get("rank", index)
        normalized.append(
            {
                "category": category_name,
                "probability": max(0.0, min(1.0, probability)),
                "rank": int(rank),
            }
        )
    return normalized


def _resolve_primary_category_name(
    *,
    result_object: dict[str, Any],
    predicted_categories: list[dict[str, Any]],
    low_confidence: bool,
    emergency_routed: bool,
) -> str | None:
    if emergency_routed or low_confidence:
        return None
    explicit_name = str(result_object.get("primary_category", "")).strip()
    if explicit_name:
        return explicit_name
    if predicted_categories:
        return str(predicted_categories[0]["category"])
    return None


def _normalize_session_ids(raw_values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _normalize_tokens(raw_tokens: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        item = str(token).strip().lower()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized


def _canonicalize_symptoms(raw_values: list[str]) -> list[str]:
    valid_names = set(FROZEN_SYMPTOM_ORDER)
    selected_set = {
        str(item).strip()
        for item in raw_values
        if str(item).strip() in valid_names
    }
    return [
        symptom_name
        for symptom_name in FROZEN_SYMPTOM_ORDER
        if symptom_name in selected_set
    ]


def _coerce_optional_float(raw_value: Any) -> float | None:
    if raw_value is None:
        return None
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None
    return value


def _utc_iso_now() -> str:
    return datetime.now(UTC).isoformat()
