import json
import time
import streamlit as st

from database import create_database, save_survey_response

MAX_RESPONSES = 10

st.set_page_config(page_title="AI Response Evaluation", layout="wide")

st.markdown(
    """
    <style>
      .reportview-container, .main {
        background-color: #343541;
        color: #d1d5db;
      }
      .chat-container {
        max-width: 700px;
        margin: 0 auto 2rem auto;
        padding: 1rem;
        background-color: #444654;
        border-radius: 8px;
      }
      .user-message {
        background-color: #444654;
        color: #f8f8f2;
        padding: 0.6rem 1rem;
        border-radius: 12px;
        margin: 0.5rem 0;
        text-align: left;
      }
      .assistant-message {
        background-color: #10a37f;
        color: #ffffff;
        padding: 0.6rem 1rem;
        border-radius: 12px;
        margin: 0.5rem 0;
        text-align: left;
      }
      .thinking {
        font-style: italic;
        color: #a0aec0;
      }
      .diagnostic-info {
        background-color: #2d3748;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid #10a37f;
      }
      .vignette-preview {
        background-color: #f8f9fa;
        border: 2px solid #dee2e6;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid #007bff;
      }
      .vignette-display {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 20px;
        margin: 15px 0;
        border-left: 4px solid #007bff;
      }
      .vignette-header {
        font-size: 1.5em;
        font-weight: bold;
        color: #0056b3;
        margin-bottom: 10px;
      }
      .vignette-content {
        font-size: 1.1em;
        line-height: 1.6;
        margin-bottom: 15px;
        color: #495057;
      }
      .question-header {
        font-size: 1.5em;
        font-weight: bold;
        color: #0056b3;
        margin-bottom: 10px;
        margin-top: 15px;
      }
      .question-content {
        font-size: 1.1em;
        line-height: 1.6;
        color: #495057;
      }
      @keyframes pulse {
        0%   { transform: scale(1); }
        50%  { transform: scale(1.05); }
        100% { transform: scale(1); }
      }
      .assistant-thinking.pulse {
        animation: pulse 1s infinite;
        display: inline-block;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_cases():
    with open("cases.json") as f:
        return json.load(f)


@st.cache_resource
def init_db():
    return create_database()


cases = load_cases()

try:
    db = init_db()
except Exception as e:
    st.error(f"Database initialization failed: {e}")
    st.stop()


def check_study_status():
    try:
        if not db.can_accept_participants():
            return False, "Study is not currently accepting new participants."
        return True, None
    except Exception as e:
        return False, f"Database error: {str(e)}"


if "study_status_checked" not in st.session_state:
    st.session_state.study_status_checked = False
if "study_can_accept" not in st.session_state:
    st.session_state.study_can_accept = True
if "study_message" not in st.session_state:
    st.session_state.study_message = None

if not st.session_state.study_status_checked:
    can_accept, message = check_study_status()
    st.session_state.study_can_accept = can_accept
    st.session_state.study_message = message
    st.session_state.study_status_checked = True

if not st.session_state.study_can_accept:
    st.markdown("### 🚫 Study Not Available")
    st.markdown(
        """
<div style="background-color:#fff3cd;border:1px solid #ffeaa7;border-radius:8px;padding:20px;margin:20px 0;">
    <h3 style="color:#856404;margin-top:0;">📋 Study Status</h3>
    <p style="color:#856404;font-size:16px;margin-bottom:0;">{}</p>
</div>
""".format(st.session_state.study_message),
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div style="background-color:#f8f9fa;border-radius:8px;padding:15px;margin:15px 0;">
    <p style="margin:0;color:#6c757d;">
        If you believe this is an error, please contact the study administrator or try again later.
    </p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.stop()

for key, default in {
    "selected_cases": [],
    "current": None,
    "history": [],
    "response_counter": 0,
    "terms_conditions_complete": False,
    "diagnostic_complete": False,
    "user_age": "",
    "user_profession": "",
    "user_sex": "",
    "user_race": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def display_instructions():
    st.markdown(
        """
<div style="background-color:#f0f2f6;padding:20px;border-radius:10px;border-left:5px solid #1f77b4;">
  <h2 style="color:#1f77b4;margin-top:0;">📋 Instructions</h2>

  <ol style="font-size:16px;line-height:1.6;">
    <li><strong>Select a clinical vignette</strong> from the dropdown menu below</li>
    <li><strong>Review</strong> the full vignette text that appears</li>
    <li>Click "<strong>Continue with Selected Vignette</strong>" to proceed</li>
    <li><strong>Rate the AI response</strong> using the provided answer choices</li>
    <li><strong>Leave a comment</strong> with your feedback</li>
  </ol>

  <div style="background-color:#f7f9fc;border-left:3px solid #c6dafc;padding:8px 10px;margin-top:6px;border-radius:4px;font-size:14px;">
    <ul style="margin:4px 0 0 20px;padding-left:0;">
      <li><strong>No edits</strong> after you press <em>Submit&nbsp;&amp;&nbsp;Next</em>.</li>
      <li>Ratings and comments are <strong>mandatory</strong>.</li>
      <li><strong>Note:</strong> Available vignettes decrease as you progress through the study.</li>
    </ul>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def display_formatted_vignette(case):
    prompt_text = case["prompt"]

    if "Question:" in prompt_text:
        parts = prompt_text.split("Question:", 1)
        clinical_vignette_part = parts[0].strip()
        question_part = parts[1].strip()

        if clinical_vignette_part.startswith("Clinical Vignette:"):
            clinical_vignette_part = clinical_vignette_part.replace("Clinical Vignette:", "", 1).strip()
    else:
        clinical_vignette_part = prompt_text
        question_part = "What is your assessment of the AI's recommendation for this case?"

    vignette_html = f"""
    <div class="vignette-display">
        <div class="vignette-header">Clinical Vignette:</div>
        <div class="vignette-content">{clinical_vignette_part}</div>
        <div class="question-header">Question:</div>
        <div class="question-content">{question_part}</div>
    </div>
    """
    st.markdown(vignette_html, unsafe_allow_html=True)


if not st.session_state.terms_conditions_complete:
    st.markdown("### 📋 Study Consent")

    st.markdown(
        """
<div style="background-color:#f8f9fa;padding:20px;border-radius:10px;border-left:5px solid #007bff;">
  <h3 style="color:#0056b3;margin-top:0;">Research Participation Agreement</h3>

  <p style="font-size:16px;line-height:1.6;">
    <strong>Study Purpose:</strong> Evaluating AI-generated medical recommendations
  </p>

  <p style="font-size:16px;line-height:1.6;">
    <strong>What you'll do:</strong> Review AI responses to clinical cases and provide your professional assessment (15-25 minutes)
  </p>

  <div style="
      background-color:#f7f9fc;
      border-left:3px solid #c6dafc;
      padding:8px 10px;
      margin:8px 0;
      border-radius:4px;
      font-size:14px;
  ">
    <span style="color:#1565c0;">
      <strong>✓ Ethics Note:</strong> All clinical vignettes are fictional and created for research purposes only. No real patient information is used.
    </span>
  </div>

  <p style="font-size:16px;line-height:1.6;">
    <strong>Privacy:</strong> Your responses are anonymous and will be used solely for research purposes
  </p>
</div>
""",
        unsafe_allow_html=True,
    )

    agree_to_participate = st.checkbox(
        "I have read the above information and agree to participate in this research study",
        key="simple_consent",
    )

    if agree_to_participate:
        if st.button("Continue to Participant Information", type="primary"):
            try:
                if "group" not in st.session_state or "participant_id" not in st.session_state:
                    condition, participant_id = db.get_next_condition()
                    st.session_state.group = condition
                    st.session_state.participant_id = participant_id

                st.session_state.terms_conditions_complete = True
                st.rerun()
            except Exception as e:
                st.error(f"Failed to assign participant condition: {e}")
    else:
        st.info("Please check the consent box to continue.")

elif not st.session_state.diagnostic_complete:
    st.markdown("### 📋 Participant Information")
    st.markdown("Please provide some basic information before proceeding:")

    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Enter your age", min_value=10, max_value=100, key="age_input")
    with col2:
        profession = st.selectbox(
            "Profession",
            ["", "Medical Student", "Resident", "Attending Physician", "Nurse", "Other Healthcare Worker", "Non-Healthcare Professional"],
            key="profession_input",
        )

    col3, col4 = st.columns(2)
    with col3:
        sex = st.selectbox(
            "Sex",
            ["", "Male", "Female", "Intersex", "Prefer not to say"],
            key="sex_input",
        )
    with col4:
        race = st.selectbox(
            "Race",
            [
                "",
                "White or Caucasian",
                "Black or African American",
                "Asian",
                "Hispanic or Latino",
                "Native American or Alaska Native",
                "Native Hawaiian or Pacific Islander",
                "Other",
                "Prefer not to say",
            ],
            key="race_input",
        )

    if profession == "Other Healthcare Worker":
        other_profession = st.text_input("Please specify your healthcare role:", key="other_profession")
        if other_profession:
            profession = f"Other Healthcare Worker: {other_profession}"
    elif profession == "Non-Healthcare Professional":
        other_profession = st.text_input("Please specify your profession:", key="other_profession")
        if other_profession:
            profession = f"Non-Healthcare Professional: {other_profession}"

    if race == "Other":
        other_race = st.text_input("Please specify your race:", key="other_race")
        if other_race:
            race = f"Other race: {other_race}"

    if age and profession and sex and race:
        if st.button("Continue to Study", type="primary"):
            try:
                db.update_participant_info(st.session_state.participant_id, age, profession, sex, race)
                st.session_state.user_age = age
                st.session_state.user_profession = profession
                st.session_state.user_sex = sex
                st.session_state.user_race = race
                st.session_state.diagnostic_complete = True
                st.rerun()
            except Exception as e:
                st.error(f"Database error: {e}")
    else:
        st.info("Please complete all fields to continue.")

elif st.session_state.current is None and len(st.session_state.history) < MAX_RESPONSES:
    display_instructions()
    st.markdown("### Select Clinical Vignette")

    available_cases = [case for case in cases if case["id"] not in st.session_state.selected_cases]

    dropdown_options = ["Select a clinical vignette..."]
    for case in available_cases:
        truncated_vignette = case["prompt"][:80] + "..." if len(case["prompt"]) > 80 else case["prompt"]
        dropdown_options.append(f"Case {case['id']}: {truncated_vignette}")

    selected_option = st.selectbox(
        "Choose a clinical vignette:",
        dropdown_options,
        key=f"vignette_dropdown_{len(st.session_state.history)}",
    )

    if selected_option != "Select a clinical vignette..." and st.session_state.current is None:
        case_id = int(selected_option.split(":")[0].replace("Case ", ""))
        selected_case = next(case for case in available_cases if case["id"] == case_id)

        st.markdown("### Selected Vignette:")
        display_formatted_vignette(selected_case)

        if st.button("▶ Continue with Selected Vignette", type="primary"):
            st.session_state.selected_cases.append(case_id)
            st.session_state.current = selected_case
            st.session_state.response_counter += 1
            st.rerun()
    else:
        st.info("Please select a clinical vignette from the dropdown menu to continue.")

elif st.session_state.current:
    case = st.session_state.current
    case_id = case["id"]
    anim_flag = f"anim_done_response_{st.session_state.response_counter}"

    display_instructions()
    if anim_flag not in st.session_state:
        st.session_state[anim_flag] = False

    st.markdown(f"## Response {len(st.session_state.history) + 1}")

    prompt_text = case["prompt"]
    if "Question:" in prompt_text:
        parts = prompt_text.split("Question:", 1)
        clinical_vignette_part = parts[0].strip()
        question_part = parts[1].strip()

        if clinical_vignette_part.startswith("Clinical Vignette:"):
            clinical_vignette_part = clinical_vignette_part.replace("Clinical Vignette:", "", 1).strip()
    else:
        clinical_vignette_part = prompt_text
        question_part = "What is your assessment of the AI's recommendation for this case?"

    vignette_html = f"""
    <div class="user-message">
        <div style="font-size: 1.3em; font-weight: bold; color: #f8f8f2; margin-bottom: 8px;">Clinical Vignette:</div>
        <div style="margin-bottom: 12px;">{clinical_vignette_part}</div>
        <div style="font-size: 1.3em; font-weight: bold; color: #f8f8f2; margin-bottom: 8px;">Question:</div>
        <div>{question_part}</div>
    </div>
    """
    st.markdown(vignette_html, unsafe_allow_html=True)

    if not st.session_state[anim_flag]:
        placeholder = st.empty()

        # Initial thinking animation
        placeholder.markdown(
            '<div class="assistant-thinking pulse">🤖 Thinking…</div>',
            unsafe_allow_html=True
        )
        time.sleep(1.2)

        placeholder.markdown(
            '<div class="assistant-thinking">🛠️ Finishing reasoning…</div>',
            unsafe_allow_html=True
        )
        time.sleep(0.8)

        # Type out the response gradually
        ai_typed = ""
        for ch in case["llm_response"]:
            ai_typed += ch
            placeholder.markdown(
                f'<div class="assistant-message">{ai_typed}</div>',
                unsafe_allow_html=True
            )
            time.sleep(0.008)

        st.session_state[anim_flag] = True
    else:
        st.markdown(
            f'<div class="assistant-message">{case["llm_response"]}</div>',
            unsafe_allow_html=True
        )
        
    if st.session_state.get("group") == "Group A - Warning Label":
        st.warning("⚠️ WARNING: Please check the validity of AI responses")

    st.markdown("### Your Assessment")

    validation_key = f"validation_{st.session_state.response_counter}"
    if validation_key not in st.session_state:
        st.session_state[validation_key] = {"agree_selected": False, "trust_selected": False, "comment_filled": False}

    agree = st.radio(
        "How much do you agree with this recommendation? *",
        ["1 Strongly Disagree", "2 Disagree", "3 Neutral", "4 Agree", "5 Strongly Agree"],
        key=f"agree_response_{st.session_state.response_counter}",
        horizontal=True,
    )
    st.session_state[validation_key]["agree_selected"] = agree is not None

    trust_choice = st.selectbox(
        "Would you follow this recommendation?",
        options=["Yes", "No"],
        key=f"trust_choice_{st.session_state.response_counter}",
    )
    st.session_state[validation_key]["trust_selected"] = trust_choice is not None

    comment = st.text_area(
        "Give one sentence or a few words to explain your ratings *",
        key=f"comment_response_{st.session_state.response_counter}",
        height=100,
        placeholder="Please provide your explanation here...",
    )
    st.session_state[validation_key]["comment_filled"] = len(comment.strip()) > 0

    st.markdown("*<span style='color: #ff6b6b; font-size: 12px;'>Required fields</span>", unsafe_allow_html=True)

    all_fields_complete = (
        st.session_state[validation_key]["agree_selected"]
        and st.session_state[validation_key]["trust_selected"]
        and st.session_state[validation_key]["comment_filled"]
    )

    if not all_fields_complete:
        st.warning("Please complete all fields")

    if st.button("✅ Submit & Next", type="primary", disabled=not all_fields_complete):
        if all_fields_complete:
            response_data = {
                "case_id": case_id,
                "response_number": st.session_state.response_counter,
                "group": st.session_state.get("group"),
                "user_age": st.session_state.user_age,
                "user_profession": st.session_state.user_profession,
                "user_sex": st.session_state.user_sex,
                "user_race": st.session_state.user_race,
                "agree": agree,
                "trust": trust_choice,
                "comment": comment,
            }

            try:
                save_survey_response(st.session_state.participant_id, response_data)
                st.session_state.history.append(response_data)

                if len(st.session_state.history) == MAX_RESPONSES:
                    db.mark_participant_completed(st.session_state.participant_id)

                if validation_key in st.session_state:
                    del st.session_state[validation_key]

                st.session_state.current = None
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save response: {e}")
        else:
            st.error("Please complete all required fields before submitting.")

if len(st.session_state.history) == MAX_RESPONSES:
    st.markdown(
        """
<div style="background-color:#d4edda;padding:20px;border-radius:10px;border-left:5px solid #28a745;">
  <h2 style="color:#155724;margin-top:0;">🎉 Thank You for Completing the Study!</h2>

  <ul style="color:#155724;font-size:16px;line-height:1.5;margin:0 0 0 1em;padding:0;">
    <li>Your responses have been <strong>successfully recorded</strong>.</li>
    <li>Your participation is greatly appreciated and will provide <strong>valuable insights</strong> to our research.</li>
    <li><strong>Reminder:</strong> please do not share this website or the results of this study with anyone.</li>
    <li><strong>To terminate this session, please exit from this website</strong></li>
  </ul>
</div>
""",
        unsafe_allow_html=True,
    )
