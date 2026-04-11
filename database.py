import io
import time
import threading
from contextlib import contextmanager

import gspread
import pandas as pd
import streamlit as st

db_lock = threading.Lock()


class SurveyDatabase:
    def __init__(self):
        self.gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        self.sheet = self.gc.open(st.secrets["SPREADSHEET_NAME"])
        self._init_sheet()

    def _init_sheet(self):
        self.participants_ws = self._get_or_create_ws(
            "participants",
            ["id", "condition", "age", "profession", "sex", "race", "completed", "created_at"],
        )
        self.responses_ws = self._get_or_create_ws(
            "responses",
            [
                "id",
                "participant_id",
                "case_id",
                "response_number",
                "group_condition",
                "user_age",
                "user_profession",
                "user_sex",
                "user_race",
                "agree_rating",
                "trust_rating",
                "comment",
                "created_at",
            ],
        )
        self.metadata_ws = self._get_or_create_ws(
            "metadata",
            ["key", "value"],
        )

        metadata = self._read_ws(self.metadata_ws)
        if metadata.empty:
            self.metadata_ws.append_rows(
                [
                    ["target_participants", "20"],
                    ["study_active", "true"],
                ]
            )

    def _get_or_create_ws(self, title, headers):
        try:
            ws = self.sheet.worksheet(title)
        except gspread.WorksheetNotFound:
            ws = self.sheet.add_worksheet(title=title, rows=1000, cols=max(10, len(headers)))
            ws.append_row(headers)
        return ws

    def _read_ws(self, ws):
        records = ws.get_all_records()
        return pd.DataFrame(records)

    def _write_df(self, ws, df):
        ws.clear()
        if df.empty:
            return
        ws.update([df.columns.tolist()] + df.fillna("").astype(str).values.tolist())

    def _next_id(self, df):
        if df.empty:
            return 1
        numeric = pd.to_numeric(df["id"], errors="coerce").dropna()
        return int(numeric.max()) + 1 if not numeric.empty else 1

    def get_target_participants(self) -> int:
        meta = self._read_ws(self.metadata_ws)
        row = meta.loc[meta["key"] == "target_participants", "value"]
        return int(row.iloc[0]) if not row.empty else 20

    def set_target_participants(self, target: int):
        meta = self._read_ws(self.metadata_ws)
        if (meta["key"] == "target_participants").any():
            meta.loc[meta["key"] == "target_participants", "value"] = str(target)
        else:
            meta = pd.concat([meta, pd.DataFrame([{"key": "target_participants", "value": str(target)}])], ignore_index=True)
        self._write_df(self.metadata_ws, meta)

    def can_accept_participants(self) -> bool:
        meta = self._read_ws(self.metadata_ws)
        participants = self.export_participants()

        active_row = meta.loc[meta["key"] == "study_active", "value"]
        target_row = meta.loc[meta["key"] == "target_participants", "value"]

        active = (active_row.iloc[0].lower() == "true") if not active_row.empty else True
        target = int(target_row.iloc[0]) if not target_row.empty else 20
        current = len(participants)

        return active and current < target

    def get_condition_counts(self) -> pd.DataFrame:
        participants = self.export_participants()
        if participants.empty:
            return pd.DataFrame(columns=["condition", "total_participants", "completed_participants"])

        participants["completed"] = participants["completed"].astype(str).str.lower().isin(["true", "1"])
        out = (
            participants.groupby("condition", dropna=False)
            .agg(
                total_participants=("id", "count"),
                completed_participants=("completed", "sum"),
            )
            .reset_index()
            .sort_values("condition")
        )
        return out

    def get_next_condition(self) -> tuple[str, int]:
        with db_lock:
            if not self.can_accept_participants():
                raise Exception("Study is not accepting new participants")

            participants = self.export_participants()
            target_participants = self.get_target_participants()

            current_control = len(participants[participants["condition"] == "Control"]) if not participants.empty else 0
            current_warning = len(participants[participants["condition"] == "Group A - Warning Label"]) if not participants.empty else 0

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
                condition = ["Control", "Group A - Warning Label"][total % 2]

            new_id = self._next_id(participants if not participants.empty else pd.DataFrame(columns=["id"]))
            self.participants_ws.append_row(
                [new_id, condition, "", "", "", "", "False", time.strftime("%Y-%m-%d %H:%M:%S")]
            )
            return condition, new_id

    def update_participant_info(self, participant_id: int, age: int, profession: str, sex: str, race: str):
        participants = self.export_participants()
        if participants.empty:
            return

        mask = pd.to_numeric(participants["id"], errors="coerce") == participant_id
        participants.loc[mask, ["age", "profession", "sex", "race"]] = [age, profession, sex, race]
        self._write_df(self.participants_ws, participants)

    def mark_participant_completed(self, participant_id: int):
        participants = self.export_participants()
        if participants.empty:
            return

        mask = pd.to_numeric(participants["id"], errors="coerce") == participant_id
        participants.loc[mask, "completed"] = "True"
        self._write_df(self.participants_ws, participants)

    def save_response(self, participant_id: int, response_data: dict):
        responses = self.export_responses()
        new_id = self._next_id(responses if not responses.empty else pd.DataFrame(columns=["id"]))

        self.responses_ws.append_row(
            [
                new_id,
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
                time.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )

    def export_participants(self) -> pd.DataFrame:
        return self._read_ws(self.participants_ws)

    def export_responses(self) -> pd.DataFrame:
        return self._read_ws(self.responses_ws)

    def export_joined_data(self) -> pd.DataFrame:
        participants = self.export_participants()
        responses = self.export_responses()

        if participants.empty:
            return pd.DataFrame()

        participants = participants.rename(columns={"id": "participant_id", "created_at": "participant_created_at"})
        if responses.empty:
            return participants

        responses = responses.rename(columns={"id": "response_id", "created_at": "response_created_at"})
        return participants.merge(responses, on="participant_id", how="left")

    def get_participant_preview(self) -> pd.DataFrame:
        participants = self.export_participants()
        responses = self.export_responses()

        if participants.empty:
            return pd.DataFrame()

        if responses.empty:
            participants["response_count"] = 0
            return participants.sort_values("id", ascending=False)

        counts = (
            responses.groupby("participant_id")
            .size()
            .reset_index(name="response_count")
        )
        participants["id_num"] = pd.to_numeric(participants["id"], errors="coerce")
        counts["participant_id"] = pd.to_numeric(counts["participant_id"], errors="coerce")

        out = participants.merge(counts, left_on="id_num", right_on="participant_id", how="left")
        out["response_count"] = out["response_count"].fillna(0).astype(int)
        return out.drop(columns=["id_num", "participant_id"], errors="ignore").sort_values("id", ascending=False)

    def get_response_preview(self, limit: int = 20) -> pd.DataFrame:
        responses = self.export_responses()
        if responses.empty:
            return responses
        return responses.sort_values("id", ascending=False).head(limit)

    def delete_selected_participants(self, participant_ids: list[int]):
        if not participant_ids:
            return 0

        participants = self.export_participants()
        responses = self.export_responses()

        pid_set = set(map(int, participant_ids))
        participants = participants[~pd.to_numeric(participants["id"], errors="coerce").isin(pid_set)]

        if not responses.empty:
            responses = responses[~pd.to_numeric(responses["participant_id"], errors="coerce").isin(pid_set)]

        self._write_df(self.participants_ws, participants)
        self._write_df(self.responses_ws, responses)
        return len(participant_ids)

    def backup_all_data(self) -> tuple[str, str]:
        participants_file = f"participants_backup_{int(time.time())}.csv"
        responses_file = f"responses_backup_{int(time.time())}.csv"
        self.export_participants().to_csv(participants_file, index=False)
        self.export_responses().to_csv(responses_file, index=False)
        return participants_file, responses_file

    def delete_all_data(self) -> tuple[str, str]:
        p, r = self.backup_all_data()
        self._write_df(self.participants_ws, pd.DataFrame(columns=["id", "condition", "age", "profession", "sex", "race", "completed", "created_at"]))
        self._write_df(self.responses_ws, pd.DataFrame(columns=["id", "participant_id", "case_id", "response_number", "group_condition", "user_age", "user_profession", "user_sex", "user_race", "agree_rating", "trust_rating", "comment", "created_at"]))
        return p, r


def create_database():
    return SurveyDatabase()


def get_condition_assignment():
    db = create_database()
    return db.get_next_condition()


def save_survey_response(participant_id: int, response_data: dict):
    db = create_database()
    db.save_response(participant_id, response_data)