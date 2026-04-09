# database.py
"""
Database module for AI Response Evaluation Survey
Handles all data persistence, condition assignment, and admin operations
"""

import sqlite3
import threading
import time
import pandas as pd
from contextlib import contextmanager

db_lock = threading.Lock()
DB_NAME = "survey_data.db"


class SurveyDatabase:
    def __init__(self, db_name: str = DB_NAME):
        self.db_name = db_name
        self.init_database()

    @contextmanager
    def get_connection(self):
        with db_lock:
            conn = sqlite3.connect(self.db_name)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            try:
                yield conn
            finally:
                conn.close()

    def init_database(self):
        with self.get_connection() as conn:
            # Participants table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    condition TEXT NOT NULL,
                    age INTEGER,
                    profession TEXT,
                    sex TEXT,
                    race TEXT,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Responses table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    participant_id INTEGER NOT NULL,
                    case_id INTEGER,
                    response_number INTEGER,
                    group_condition TEXT,
                    user_age INTEGER,
                    user_profession TEXT,
                    user_sex TEXT,
                    user_race TEXT,
                    agree_rating TEXT,
                    trust_rating TEXT,
                    comment TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE
                )
            """)

            # Metadata table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Initialize defaults
            defaults = {
                "target_participants": "20",
                "study_active": "true",
            }

            for key, value in defaults.items():
                cursor = conn.execute(
                    "SELECT value FROM study_metadata WHERE key = ?",
                    (key,)
                )
                if cursor.fetchone() is None:
                    conn.execute(
                        "INSERT INTO study_metadata (key, value) VALUES (?, ?)",
                        (key, value)
                    )

            conn.commit()

    def set_target_participants(self, target: int):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO study_metadata (key, value)
                VALUES (?, ?)
            """, ("target_participants", str(target)))
            conn.commit()

    def get_target_participants(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(
                'SELECT value FROM study_metadata WHERE key = "target_participants"'
            )
            result = cursor.fetchone()
            return int(result["value"]) if result else 10

    def set_study_active(self, active: bool):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO study_metadata (key, value)
                VALUES (?, ?)
            """, ("study_active", "true" if active else "false"))
            conn.commit()

    def can_accept_participants(self) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT
                    (SELECT value FROM study_metadata WHERE key = 'study_active' LIMIT 1) AS active,
                    (SELECT value FROM study_metadata WHERE key = 'target_participants' LIMIT 1) AS target,
                    (SELECT COUNT(*) FROM participants) AS current_count
            """)
            result = cursor.fetchone()

            active = (result["active"] or "false").lower() == "true"
            target = int(result["target"]) if result["target"] else 10
            current = result["current_count"] or 0

            return active and current < target

    def get_condition_counts(self) -> pd.DataFrame:
        with self.get_connection() as conn:
            query = """
                SELECT
                    condition,
                    COUNT(*) AS total_participants,
                    SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS completed_participants
                FROM participants
                GROUP BY condition
                ORDER BY condition
            """
            return pd.read_sql_query(query, conn)

    def get_next_condition(self) -> tuple[str, int]:
        """
        Balanced allocation:
        assigns the participant to the arm with fewer participants,
        while respecting target split.
        """
        if not self.can_accept_participants():
            raise Exception("Study is not accepting new participants")

        # Get target BEFORE acquiring the lock again inside this method
        target_participants = self.get_target_participants()

        conditions = ["Control", "Group A - Warning Label"]

        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT condition, COUNT(*) AS count
                FROM participants
                GROUP BY condition
            """)
            results = cursor.fetchall()

            counts = {row["condition"]: row["count"] for row in results}

            current_control = counts.get("Control", 0)
            current_warning = counts.get("Group A - Warning Label", 0)

            base_per_condition = target_participants // 2
            remainder = target_participants % 2

            target_control = base_per_condition + remainder
            target_warning = base_per_condition

            if current_control < target_control and current_warning < target_warning:
                condition = "Control" if current_control <= current_warning else "Group A - Warning Label"
            elif current_control < target_control:
                condition = "Control"
            elif current_warning < target_warning:
                condition = "Group A - Warning Label"
            else:
                total = current_control + current_warning
                condition = conditions[total % 2]

            cursor = conn.execute("""
                INSERT INTO participants (condition)
                VALUES (?)
            """, (condition,))
            participant_id = cursor.lastrowid
            conn.commit()

            return condition, participant_id

    def update_participant_info(self, participant_id: int, age: int, profession: str, sex: str, race: str):
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE participants
                SET age = ?, profession = ?, sex = ?, race = ?
                WHERE id = ?
            """, (age, profession, sex, race, participant_id))
            conn.commit()

    def mark_participant_completed(self, participant_id: int):
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE participants
                SET completed = 1
                WHERE id = ?
            """, (participant_id,))
            conn.commit()

    def save_response(self, participant_id: int, response_data: dict):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO responses (
                    participant_id,
                    case_id,
                    response_number,
                    group_condition,
                    user_age,
                    user_profession,
                    user_sex,
                    user_race,
                    agree_rating,
                    trust_rating,
                    comment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                participant_id,
                response_data["case_id"],
                response_data["response_number"],
                response_data["group"],
                response_data["user_age"],
                response_data["user_profession"],
                response_data["user_sex"],
                response_data["user_race"],
                response_data["agree"],
                response_data["trust"],
                response_data["comment"],
            ))
            conn.commit()

    def export_participants(self) -> pd.DataFrame:
        with self.get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM participants ORDER BY id", conn)

    def export_responses(self) -> pd.DataFrame:
        with self.get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM responses ORDER BY participant_id, response_number", conn)

    def export_joined_data(self) -> pd.DataFrame:
        with self.get_connection() as conn:
            query = """
                SELECT
                    p.id AS participant_id,
                    p.condition,
                    p.age,
                    p.profession,
                    p.sex,
                    p.race,
                    p.completed,
                    p.created_at AS participant_created_at,
                    r.id AS response_id,
                    r.case_id,
                    r.response_number,
                    r.agree_rating,
                    r.trust_rating,
                    r.comment,
                    r.created_at AS response_created_at
                FROM participants p
                LEFT JOIN responses r
                    ON p.id = r.participant_id
                ORDER BY p.id, r.response_number
            """
            return pd.read_sql_query(query, conn)

    def get_participant_preview(self) -> pd.DataFrame:
        with self.get_connection() as conn:
            query = """
                SELECT
                    p.id,
                    p.condition,
                    p.age,
                    p.profession,
                    p.sex,
                    p.race,
                    p.completed,
                    p.created_at,
                    COUNT(r.id) AS response_count
                FROM participants p
                LEFT JOIN responses r
                    ON p.id = r.participant_id
                GROUP BY p.id
                ORDER BY p.id DESC
            """
            return pd.read_sql_query(query, conn)

    def get_response_preview(self, limit: int = 20) -> pd.DataFrame:
        with self.get_connection() as conn:
            query = f"""
                SELECT
                    r.id,
                    r.participant_id,
                    r.case_id,
                    r.response_number,
                    r.group_condition,
                    r.agree_rating,
                    r.trust_rating,
                    r.comment,
                    r.created_at
                FROM responses r
                ORDER BY r.id DESC
                LIMIT {int(limit)}
            """
            return pd.read_sql_query(query, conn)

    def delete_participant(self, participant_id: int):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM participants WHERE id = ?", (participant_id,))
            conn.commit()

    def delete_selected_participants(self, participant_ids: list[int]):
        if not participant_ids:
            return 0

        placeholders = ",".join(["?"] * len(participant_ids))
        with self.get_connection() as conn:
            conn.execute(
                f"DELETE FROM participants WHERE id IN ({placeholders})",
                tuple(participant_ids)
            )
            conn.commit()
        return len(participant_ids)

    def backup_all_data(self) -> tuple[str, str]:
        participants_file = f"participants_backup_{int(time.time())}.csv"
        responses_file = f"responses_backup_{int(time.time())}.csv"

        participants_df = self.export_participants()
        responses_df = self.export_responses()

        participants_df.to_csv(participants_file, index=False)
        responses_df.to_csv(responses_file, index=False)

        return participants_file, responses_file

    def delete_all_data(self) -> tuple[str, str]:
        participants_file, responses_file = self.backup_all_data()

        with self.get_connection() as conn:
            conn.execute("DELETE FROM responses")
            conn.execute("DELETE FROM participants")
            conn.commit()

        return participants_file, responses_file


def create_database() -> SurveyDatabase:
    return SurveyDatabase()


def get_condition_assignment() -> tuple[str, int]:
    db = create_database()
    return db.get_next_condition()


def save_survey_response(participant_id: int, response_data: dict):
    db = create_database()
    db.save_response(participant_id, response_data)