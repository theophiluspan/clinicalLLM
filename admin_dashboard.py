# admin_dashboard.py
"""
AI Survey Admin Dashboard
Run with:
streamlit run admin_dashboard.py --server.port 8502
"""

import hmac
import streamlit as st
import pandas as pd
from database import create_database

import hmac
import streamlit as st

st.set_page_config(page_title="Survey Admin Dashboard", layout="wide")


def check_password():
    """Render only the login page until authentication succeeds."""
    if "admin_authenticated" not in st.session_state:
        st.session_state["admin_authenticated"] = False

    if "login_error" not in st.session_state:
        st.session_state["login_error"] = ""

    if st.session_state["admin_authenticated"]:
        return True

    st.title("Admin Login")
    st.write("Please enter the admin password to continue.")

    with st.form("login_form", clear_on_submit=True):
        password = st.text_input("Enter admin password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")

    if submitted:
        correct_password = st.secrets.get("ADMIN_PASSWORD", "")

        if correct_password and hmac.compare_digest(password, correct_password):
            st.session_state["admin_authenticated"] = True
            st.session_state["login_error"] = ""
            st.rerun()
        else:
            st.session_state["login_error"] = "Incorrect password. Please try again."

    if st.session_state["login_error"]:
        st.error(st.session_state["login_error"])

    return False


def logout():
    st.session_state["admin_authenticated"] = False
    st.session_state["login_error"] = ""
    st.rerun()


if not check_password():
    st.stop()

# -----------------------------
# APP STARTS HERE
# -----------------------------
db = create_database()

top_col1, top_col2 = st.columns([6, 1])
with top_col1:
    st.title("AI Survey Admin Dashboard")
with top_col2:
    if st.button("Log out"):
        logout()

st.sidebar.title("Administration")
page = st.sidebar.selectbox(
    "Choose an action:",
    [
        "📊 Participant Target & Allocation",
        "🗑️ Delete Participant(s)",
        "📤 Export / Backup Data",
    ]
)

# --------------------------------------------------
# PARTICIPANT TARGET & ALLOCATION
# --------------------------------------------------
if page == "📊 Participant Target & Allocation":
    st.header("Participant Target & Allocation")

    current_target = db.get_target_participants()
    new_target = st.number_input(
        "Set new target number of participants:",
        min_value=1,
        value=current_target,
        step=1
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("Update Target", type="primary"):
            db.set_target_participants(new_target)
            st.success(f"Participant target updated to {new_target}")

    with col2:
        study_open = db.can_accept_participants()
        st.metric("Study accepting participants", "Yes" if study_open else "No")

    st.subheader("Allocation Summary")
    counts_df = db.get_condition_counts()
    if counts_df.empty:
        st.info("No participants enrolled yet.")
    else:
        st.dataframe(counts_df, use_container_width=True)

    st.subheader("Participant Preview")
    participants_preview = db.get_participant_preview()
    if participants_preview.empty:
        st.info("No participant records available.")
    else:
        st.dataframe(participants_preview, use_container_width=True, height=300)

    st.subheader("Recent Response Preview")
    responses_preview = db.get_response_preview(limit=20)
    if responses_preview.empty:
        st.info("No responses recorded yet.")
    else:
        st.dataframe(responses_preview, use_container_width=True, height=300)

# --------------------------------------------------
# DELETE PARTICIPANTS
# --------------------------------------------------
elif page == "🗑️ Delete Participant(s)":
    st.header("Delete Participant(s)")

    participants_df = db.get_participant_preview()

    if participants_df.empty:
        st.info("No participants available to delete.")
    else:
        st.write("Select one or more participants to delete. Their linked responses will also be deleted.")

        st.dataframe(participants_df, use_container_width=True, height=350)

        participant_options = participants_df.apply(
            lambda row: f"ID {row['id']} | {row['condition']} | responses={row['response_count']} | completed={row['completed']}",
            axis=1
        ).tolist()

        selected_labels = st.multiselect(
            "Select participants to delete:",
            participant_options
        )

        selected_ids = [int(label.split("|")[0].replace("ID", "").strip()) for label in selected_labels]

        if selected_ids:
            st.warning(f"You are about to delete participant IDs: {selected_ids}")

            if st.button("Delete Selected Participants", type="primary"):
                deleted_count = db.delete_selected_participants(selected_ids)
                st.success(f"Deleted {deleted_count} participant(s) and all linked responses.")
                st.rerun()

    st.markdown("---")
    st.subheader("Delete ALL participant and response data")

    st.warning("This will back up all participant and response data, then permanently clear the database tables.")

    if st.button("Backup and Delete ALL Data", type="primary"):
        participants_backup, responses_backup = db.delete_all_data()
        st.success(
            f"All data deleted.\n\n"
            f"Participants backup: {participants_backup}\n"
            f"Responses backup: {responses_backup}"
        )

# --------------------------------------------------
# EXPORT / BACKUP
# --------------------------------------------------
elif page == "📤 Export / Backup Data":
    st.header("Export / Backup Data")

    participants_df = db.export_participants()
    responses_df = db.export_responses()
    joined_df = db.export_joined_data()

    st.subheader("Preview: Participants")
    st.dataframe(participants_df, use_container_width=True, height=250)

    st.subheader("Preview: Responses")
    st.dataframe(responses_df, use_container_width=True, height=250)

    st.subheader("Preview: Joined dataset")
    st.dataframe(joined_df, use_container_width=True, height=300)

    st.download_button(
        label="Download Participants CSV",
        data=participants_df.to_csv(index=False).encode("utf-8"),
        file_name="participants_data.csv",
        mime="text/csv"
    )

    st.download_button(
        label="Download Responses CSV",
        data=responses_df.to_csv(index=False).encode("utf-8"),
        file_name="responses_data.csv",
        mime="text/csv"
    )

    st.download_button(
        label="Download Joined CSV",
        data=joined_df.to_csv(index=False).encode("utf-8"),
        file_name="survey_joined_data.csv",
        mime="text/csv"
    )

    if st.button("Create Backup Files", type="secondary"):
        participants_backup, responses_backup = db.backup_all_data()
        st.success(
            f"Backup created successfully.\n\n"
            f"Participants backup: {participants_backup}\n"
            f"Responses backup: {responses_backup}"
        )

st.markdown("---")
st.markdown("Survey administration dashboard")