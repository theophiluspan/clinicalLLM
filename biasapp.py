# biasapp.py - Updated version with dynamic participant management
import streamlit as st
import json
import time
import pandas as pd

# Import your database module
from database import create_database, get_condition_assignment, save_survey_response

# ―――――――――――――――――――――
# CONFIGURATION - Response limit per participant (unchanged)
# ―――――――――――――――――――――
MAX_RESPONSES = 10  # Number of responses each participant provides

# ―――――――――――――――――――――
# 1. Dark Mode + ChatCSS (unchanged)
# ―――――――――――――――――――――
st.set_page_config(page_title="AI Response Evaluation", layout="wide")
st.markdown(
    """
    <style>
      /* Page background */
      .reportview-container, .main {
        background-color: #343541;
        color: #d1d5db;
      }
      /* Chat container styling */
      .chat-container {
        max-width: 700px;
        margin: 0 auto 2rem auto;
        padding: 1rem;
        background-color: #444654;
        border-radius: 8px;
      }
      /* User bubble */
      .user-message {
        background-color: #444654;
        color: #f8f8f2;
        padding: 0.6rem 1rem;
        border-radius: 12px;
        margin: 0.5rem 0;
        text-align: left;
      }
      /* Assistant bubble */
      .assistant-message {
        background-color: #10a37f;
        color: #ffffff;
        padding: 0.6rem 1rem;
        border-radius: 12px;
        margin: 0.5rem 0;
        text-align: left;
      }
      /* Thinking text */
      .thinking {
        font-style: italic;
        color: #a0aec0;
      }
      /* Diagnostic info styling */
      .diagnostic-info {
        background-color: #2d3748;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid #10a37f;
      }
      /* Vignette selection styling */
      .vignette-preview {
        background-color: #f8f9fa;
        border: 2px solid #dee2e6;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        border-left: 4px solid #007bff;
      }
      /* Enhanced vignette display styling */
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
    """, unsafe_allow_html=True
)

# Load your cases from a JSON file
@st.cache_data
def load_cases():
    with open("cases.json") as f:
        return json.load(f)

cases = load_cases()

# ---------- Database Integration --------- 

# Initialize database
@st.cache_resource
def init_db():
    return create_database()

try:
    db = init_db()
except Exception as e:
    st.error(f"Database initialization failed: {e}")
    st.stop()

conditions = [
    "Control",
    "Group A - Warning Label",
]

# Check if study is accepting participants
def check_study_status():
    """Check if the study can accept new participants"""
    try:
        if not db.can_accept_participants():
            return False, "Study is not currently accepting new participants."
        return True, None
    except Exception as e:
        return False, f"Database error: {str(e)}"

# ————— Initialize session state with database integration —————
if "study_status_checked" not in st.session_state:
    st.session_state.study_status_checked = False

if "study_can_accept" not in st.session_state:
    st.session_state.study_can_accept = True

if "study_message" not in st.session_state:
    st.session_state.study_message = None

# Check study status first
if not st.session_state.study_status_checked:
    can_accept, message = check_study_status()
    st.session_state.study_can_accept = can_accept
    st.session_state.study_message = message
    st.session_state.study_status_checked = True

# Show study closed message if needed
if not st.session_state.study_can_accept:
    st.markdown("### 🚫 Study Not Available")
    
    st.markdown("""
<div style="background-color:#fff3cd;border:1px solid #ffeaa7;border-radius:8px;padding:20px;margin:20px 0;">
    <h3 style="color:#856404;margin-top:0;">📋 Study Status</h3>
    <p style="color:#856404;font-size:16px;margin-bottom:0;">{}</p>
</div>
""".format(st.session_state.study_message), unsafe_allow_html=True)
    
    st.markdown("""
<div style="background-color:#f8f9fa;border-radius:8px;padding:15px;margin:15px 0;">
    <p style="margin:0;color:#6c757d;">
        If you believe this is an error, please contact the study administrator or try again later.
    </p>
</div>
""", unsafe_allow_html=True)
    
    st.stop()

# Continue with normal initialization if study is accepting participants
if "selected_cases" not in st.session_state:
    st.session_state.selected_cases = []

if "current" not in st.session_state:
    st.session_state.current = None

if "history" not in st.session_state:
    st.session_state.history = []

if "response_counter" not in st.session_state:
    st.session_state.response_counter = 0

# ————— Diagnostic information session state —————
if "terms_conditions_complete" not in st.session_state:
    st.session_state.terms_conditions_complete = False 

if "diagnostic_complete" not in st.session_state:
    st.session_state.diagnostic_complete = False

if "user_age" not in st.session_state:
    st.session_state.user_age = ""

if "user_profession" not in st.session_state:
    st.session_state.user_profession = ""

if "user_sex" not in st.session_state:
    st.session_state.user_sex = ""

if "user_race" not in st.session_state:
    st.session_state.user_race = ""

def display_instructions():
    st.markdown("""
<div style="background-color:#f0f2f6;padding:20px;border-radius:10px;border-left:5px solid #1f77b4;">
  <h2 style="color:#1f77b4;margin-top:0;">📋 Instructions</h2>

  <ol style="font-size:16px;line-height:1.6;">
    <li><strong>Select a clinical vignette</strong> from the dropdown menu below</li>
    <li><strong>Review</strong> the full vignette text that appears</li>
    <li>Click "<strong>Continue with Selected Vignette</strong>" to proceed</li>
    <li><strong>Rate the AI response</strong> using the provided answer choices</li>
    <li><strong>Leave a comment</strong> with your feedback</li>
  </ol>

  <!-- subtle one‑shot warning -->
  <div style="background-color:#f7f9fc;border-left:3px solid #c6dafc;padding:8px 10px;margin-top:6px;border-radius:4px;font-size:14px;">
    <ul style="margin:4px 0 0 20px;padding-left:0;">
      <li><strong>No edits</strong> after you press <em>Submit&nbsp;&amp;&nbsp;Next</em>.</li>
      <li>Ratings and comments are <strong>mandatory</strong>.</li>
      <li><strong>Note:</strong> Available vignettes decrease as you progress through the study.</li>
    </ul>
  </div>
</div>
""", unsafe_allow_html=True)

def display_formatted_vignette(case):
    """Display vignette with enhanced formatting for Clinical Vignette and Question sections"""
    # Parse the prompt to separate Clinical Vignette and Question sections
    prompt_text = case["prompt"]
    
    # Split by "Question:" to separate the two sections
    if "Question:" in prompt_text:
        parts = prompt_text.split("Question:", 1)
        clinical_vignette_part = parts[0].strip()
        question_part = parts[1].strip()
        
        # Remove "Clinical Vignette:" from the beginning if present
        if clinical_vignette_part.startswith("Clinical Vignette:"):
            clinical_vignette_part = clinical_vignette_part.replace("Clinical Vignette:", "", 1).strip()
    else:
        # Fallback if format is different
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

# ————— Consent Form —————

if not st.session_state.terms_conditions_complete:
    st.markdown("### 📋 Study Consent")
    
    st.markdown("""
<div style="background-color:#f8f9fa;padding:20px;border-radius:10px;border-left:5px solid #007bff;">
  <h3 style="color:#0056b3;margin-top:0;">Research Participation Agreement</h3>

  <p style="font-size:16px;line-height:1.6;">
    <strong>Study Purpose:</strong> Evaluating AI‑generated medical recommendations
  </p>

  <p style="font-size:16px;line-height:1.6;">
    <strong>What you'll do:</strong> Review AI responses to clinical cases and provide your professional assessment (15-25 minutes)
  </p>

  <!-- Ethics note in faint‑blue tip style -->
  <div style="
      background-color:#f7f9fc;        /* faint grey‑blue */
      border-left:3px solid #c6dafc;   /* thin blue accent */
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
""", unsafe_allow_html=True)

    
    # Simple consent
    agree_to_participate = st.checkbox(
        "I have read the above information and agree to participate in this research study",
        key="simple_consent"
    )
    
    if agree_to_participate:
        if st.button("Continue to Participant Information", type="primary"):
            try:
                if "group" not in st.session_state or "participant_id" not in st.session_state:
                    condition, participant_id = db.get_next_condition()
                st.session_state.group = condition
                group = st.session_state.group 
                st.session_state.participant_id = participant_id
            except Exception as e:
                st.error(f"Failed to assign participant condition: {e}")
            st.session_state.terms_conditions_complete = True
            st.rerun()
    else:
        st.info("Please check the consent box to continue.")

# ————— Diagnostic Information Collection —————
elif not st.session_state.diagnostic_complete:
    st.markdown(f"### 📋 Participant Information")
    st.markdown("Please provide some basic information before proceeding:")
    
    #First row 
    col1, col2 = st.columns(2)
    
    with col1:
        age = st.number_input(
            "Enter your age", min_value=10, max_value=100,
            key="age_input"
        )
    
    with col2:
        profession = st.selectbox(
            "Profession",
            ["", "Medical Student", "Resident", "Attending Physician", "Nurse", "Other Healthcare Worker", "Non-Healthcare Professional"],
            key="profession_input"
        )
    # Second row
    col3, col4 = st.columns(2)

    with col3:
        sex = st.selectbox(
            "Sex",
            ["", "Male", "Female", "Intersex", "Prefer not to say"],
            key="sex_input"
        )

    with col4:
        race = st.selectbox(
            "Race",
            ["",
            "White or Caucasian",
            "Black or African American",
            "Asian",
            "Hispanic or Latino",
            "Native American or Alaska Native",
            "Native Hawaiian or Pacific Islander",
            "Other",
            "Prefer not to say"
            ],
            key="race_input"
        )
    
    # Optional: Add a text input for "Other" profession
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
            # Update database with participant info
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

# ————— Vignette Selection Interface —————
elif st.session_state.current is None and len(st.session_state.history) < MAX_RESPONSES:
    display_instructions()
    
    # Calculate remaining vignettes
    remaining_vignettes = MAX_RESPONSES - len(st.session_state.history)
    st.markdown(f"### Select Clinical Vignette")
    
    # Get available cases (not yet selected)
    available_cases = [case for case in cases if case["id"] not in st.session_state.selected_cases]
    
    # Create dropdown options with case numbers and truncated vignettes
    dropdown_options = ["Select a clinical vignette..."]
    for case in available_cases:
        # Truncate vignette for dropdown display (first 80 characters)
        truncated_vignette = case["prompt"][:80] + "..." if len(case["prompt"]) > 80 else case["prompt"]
        dropdown_options.append(f"Case {case['id']}: {truncated_vignette}")
    
    # Dropdown selection
    selected_option = st.selectbox(
        "Choose a clinical vignette:",
        dropdown_options,
        key=f"vignette_dropdown_{len(st.session_state.history)}"
    )
    
    # Show full vignette when one is selected - but only if we haven't processed it yet
    if selected_option != "Select a clinical vignette..." and st.session_state.current is None:
        # Extract case ID from selection
        case_id = int(selected_option.split(":")[0].replace("Case ", ""))
        selected_case = next(case for case in available_cases if case["id"] == case_id)
        
        # Display full vignette with enhanced formatting
        st.markdown("### Selected Vignette:")
        display_formatted_vignette(selected_case)
        
        if st.button("▶ Continue with Selected Vignette", type="primary"):
            # Mark this case as used
            st.session_state.selected_cases.append(case_id)
            st.session_state.current = selected_case
            st.session_state.response_counter += 1
            st.rerun()
    elif selected_option == "Select a clinical vignette...":
        st.info("Please select a clinical vignette from the dropdown menu to continue.")
# ————— Chat Interface —————
elif st.session_state.current:
    case = st.session_state.current
    case_id = case["id"]
    anim_flag = f"anim_done_response_{st.session_state.response_counter}"

    display_instructions()
    if anim_flag not in st.session_state:
        st.session_state[anim_flag] = False 
    
    st.markdown(f"## Response {len(st.session_state.history) + 1}")

    # User bubble - show the selected vignette with enhanced formatting
    prompt_text = case["prompt"]
    
    # Split by "Question:" to separate the two sections
    if "Question:" in prompt_text:
        parts = prompt_text.split("Question:", 1)
        clinical_vignette_part = parts[0].strip()
        question_part = parts[1].strip()
        
        # Remove "Clinical Vignette:" from the beginning if present
        if clinical_vignette_part.startswith("Clinical Vignette:"):
            clinical_vignette_part = clinical_vignette_part.replace("Clinical Vignette:", "", 1).strip()
    else:
        # Fallback if format is different
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
        # Animation
        placeholder = st.empty()
        placeholder.markdown('<div class="assistant-thinking pulse">🤖 Thinking…</div>', unsafe_allow_html=True)
        time.sleep(2)
        placeholder.markdown('<div class="assistant-thinking">🛠️ Finishing reasoning…</div>', unsafe_allow_html=True)
        time.sleep(1)

        ai_typed = ""
        for ch in case["llm_response"]:
            ai_typed += ch
            placeholder.markdown(f'<div class="assistant-message">{ai_typed}</div>', unsafe_allow_html=True)
            time.sleep(0.02)
        
        st.session_state[anim_flag] = True
    else:
        st.markdown(f'<div class="assistant-message">{case["llm_response"]}</div>', unsafe_allow_html=True)
    
    # Group-specific interventions
    if group == "Group A - Warning Label":
        st.warning("⚠️ WARNING: Please check the validity of AI responses")
    
    # Rating widgets
    st.markdown("### Your Assessment")
    
    # Initialize session state for validation tracking if not exists
    validation_key = f"validation_{st.session_state.response_counter}"
    if validation_key not in st.session_state:
        st.session_state[validation_key] = {"agree_selected": False, "trust_selected": False, "comment_filled": False}
    
    # Agreement radio buttons (mandatory)
    agree = st.radio(
        "How much do you agree with this recommendation? *", 
        ["1 Strongly Disagree", "2 Disagree", "3 Neutral", "4 Agree", "5 Strongly Agree"], 
        key=f"agree_response_{st.session_state.response_counter}", 
        horizontal=True,
    )
    
    # Track if agreement is selected
    st.session_state[validation_key]["agree_selected"] = agree is not None

    # Trust checkbox (mandatory)
    trust_choice = st.selectbox(
        "Would you follow this recommendation?",
        options=["Yes", "No"],
        key=f"trust_choice_{st.session_state.response_counter}"
    )
    
    st.session_state[validation_key]["trust_selected"] = trust_choice is not None

    # Comment text area (mandatory)
    comment = st.text_area(
        "Give one sentence or a few words to explain your ratings *", 
        key=f"comment_response_{st.session_state.response_counter}",
        height=100,
        placeholder="Please provide your explanation here..."
    )
    
    # Track if comment is filled
    st.session_state[validation_key]["comment_filled"] = len(comment.strip()) > 0
    
    # Show mandatory field note
    st.markdown("*<span style='color: #ff6b6b; font-size: 12px;'>Required fields</span>", unsafe_allow_html=True)
    
    # Check if all fields are completed
    all_fields_complete = (
        st.session_state[validation_key]["agree_selected"] and 
        st.session_state[validation_key]["trust_selected"] and 
        st.session_state[validation_key]["comment_filled"]
    )
    
    # Show validation messages
    if not all_fields_complete:        
        st.warning(f"Please complete all fields")

    # Submit button - only enabled when all fields are complete
    if st.button("✅ Submit & Next", type="primary", disabled=not all_fields_complete):
        if all_fields_complete:
            response_data = {
                "case_id": case_id,
                "response_number": st.session_state.response_counter,
                "group": group,
                "user_age": st.session_state.user_age,
                "user_profession": st.session_state.user_profession,
                "user_sex" : st.session_state.user_sex, 
                "user_race" : st.session_state.user_race,
                "agree": agree,
                "trust": trust_choice,
                "comment": comment
            }
            
            try:
                # Save to database
                save_survey_response(st.session_state.participant_id, response_data)
                
                # Also keep in session state for UI
                st.session_state.history.append(response_data)
                
                # Mark as completed if this was the last response
                if len(st.session_state.history) == MAX_RESPONSES:
                    db.mark_participant_completed(st.session_state.participant_id)
                
                # Clean up validation state
                if validation_key in st.session_state:
                    del st.session_state[validation_key]
                
                # Reset for next case
                st.session_state.current = None
                st.rerun()
                
            except Exception as e:
                st.error(f"Failed to save response: {e}")
        else:
            st.error("Please complete all required fields before submitting.")

# ————— Study Complete —————
if len(st.session_state.history) == MAX_RESPONSES:
    st.markdown("""
<div style="background-color:#d4edda;padding:20px;border-radius:10px;border-left:5px solid #28a745;">
  <h2 style="color:#155724;margin-top:0;">🎉 Thank You for Completing the Study!</h2>

  <ul style="color:#155724;font-size:16px;line-height:1.5;margin:0 0 0 1em;padding:0;">
    <li>Your responses have been <strong>successfully recorded</strong>.</li>
    <li>Your participation is greatly appreciated and will provide <strong>valuable insights</strong> to our research.</li>
    <li><strong>Reminder:</strong> please do not share this website or the results of this study with anyone.</li>
    <li><strong>To terminate this session, please exit from this website</strong></li>
  </ul>
</div>
""", unsafe_allow_html=True)
