import streamlit as st
import os
from datetime import datetime
from strava_client import StravaClient
from ai_agent import StravaAgent

# Load .env locally; on Streamlit Cloud secrets come from st.secrets
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_secret(key: str, default: str = "") -> str:
    """Read from st.secrets (Streamlit Cloud) or os.environ (.env locally)."""
    try:
        return st.secrets.get(key, os.getenv(key, default))
    except Exception:
        return os.getenv(key, default)


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Strava AI Coach",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

/* Root theme */
:root {
    --orange: #FC4C02;
    --dark: #1a1a1a;
    --card-bg: #242424;
    --border: #333;
    --text-muted: #888;
}

.stApp { background-color: var(--dark); color: #f0f0f0; font-family: 'DM Sans', sans-serif; }

/* Header */
.hero-header {
    background: linear-gradient(135deg, #FC4C02 0%, #e63900 100%);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 16px;
}
.hero-header h1 { font-family: 'Space Mono', monospace; font-size: 28px; margin: 0; color: white; }
.hero-header p { margin: 4px 0 0; color: rgba(255,255,255,0.8); font-size: 14px; }

/* Stat cards */
.stat-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}
.stat-value { font-family: 'Space Mono', monospace; font-size: 26px; color: var(--orange); font-weight: 700; }
.stat-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

/* Activity cards */
.activity-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 10px;
    border-left: 3px solid var(--orange);
}
.activity-title { font-weight: 600; font-size: 15px; margin-bottom: 6px; }
.activity-meta { font-size: 12px; color: var(--text-muted); display: flex; gap: 16px; }

/* Chat */
.chat-user { background: var(--orange); color: white; padding: 12px 16px; border-radius: 12px 12px 4px 12px; margin: 8px 0; max-width: 75%; margin-left: auto; font-size: 14px; }
.chat-ai { background: var(--card-bg); border: 1px solid var(--border); padding: 12px 16px; border-radius: 12px 12px 12px 4px; margin: 8px 0; max-width: 85%; font-size: 14px; line-height: 1.6; }
.chat-label { font-size: 11px; color: var(--text-muted); margin-bottom: 4px; font-family: 'Space Mono', monospace; }

/* Sidebar */
section[data-testid="stSidebar"] { background-color: #1e1e1e !important; border-right: 1px solid var(--border); }

/* Buttons */
.stButton > button {
    background: var(--orange) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.88 !important; }

/* Input */
.stTextInput > div > div > input, .stTextArea > div > div > textarea {
    background: var(--card-bg) !important;
    border: 1px solid var(--border) !important;
    color: #f0f0f0 !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
}

.stSelectbox > div > div { background: var(--card-bg) !important; border-color: var(--border) !important; }
.stAlert { border-radius: 10px !important; }
hr { border-color: var(--border) !important; }

/* Hide Streamlit branding */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "activities" not in st.session_state:
    st.session_state.activities = []
if "athlete" not in st.session_state:
    st.session_state.athlete = None
if "access_token" not in st.session_state:
    st.session_state.access_token = None


# ── Load credentials from .env ────────────────────────────────────────────────
anthropic_key = get_secret("ANTHROPIC_API_KEY")
access_token = get_secret("STRAVA_ACCESS_TOKEN")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.markdown("---")

    num_activities = st.slider("Activities to load", 5, 50, 20)

    if st.button("🔗 Connect & Load Data", use_container_width=True):
        if not access_token:
            st.error("Please enter your Strava Access Token.")
        else:
            with st.spinner("Connecting to Strava..."):
                try:
                    client = StravaClient(access_token)
                    athlete = client.get_athlete()
                    activities = client.get_activities(limit=num_activities)
                    st.session_state.access_token = access_token
                    st.session_state.athlete = athlete
                    st.session_state.activities = activities
                    st.session_state.chat_history = []  # reset chat on new load
                    st.success(f"✅ Loaded {len(activities)} activities!")
                except Exception as e:
                    st.error(f"Connection failed: {e}")

    st.markdown("---")
    if st.session_state.athlete:
        a = st.session_state.athlete
        st.markdown(f"""
        <div style='text-align:center;'>
            <div style='font-size:13px; color:#FC4C02; font-weight:600;'>
                {a.get('firstname', '')} {a.get('lastname', '')}
            </div>
            <div style='font-size:11px; color:#888;'>{a.get('city', '')} · {a.get('country', '')}</div>
        </div>
        """, unsafe_allow_html=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class='hero-header'>
    <div style='font-size:48px;'>🏃</div>
    <div>
        <h1>STRAVA AI COACH</h1>
        <p>Ask anything about your training — powered by Claude + LangChain</p>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Main content ──────────────────────────────────────────────────────────────
if not st.session_state.activities:
    st.info("👈 Click **Connect & Load Data** in the sidebar to get started.")

    st.markdown("### 💬 Example Questions You Can Ask")
    cols = st.columns(2)
    examples = [
        ("📊", "What's my average pace over the last 10 runs?"),
        ("📈", "How has my weekly mileage trended this month?"),
        ("❤️", "What was my highest heart rate activity?"),
        ("🏆", "Which was my longest ride and how did it compare to others?"),
        ("😴", "Am I overtraining based on my recent load?"),
        ("🎯", "Suggest a workout for tomorrow based on my history"),
    ]
    for i, (icon, q) in enumerate(examples):
        with cols[i % 2]:
            st.markdown(f"""
            <div class='activity-card' style='border-left-color:#555;'>
                <span style='font-size:20px;'>{icon}</span>
                <div style='margin-top:6px; font-size:13px; color:#ccc;'>{q}</div>
            </div>
            """, unsafe_allow_html=True)
else:
    activities = st.session_state.activities

    # ── Summary stats ──────────────────────────────────────────────────────────
    total_distance = sum(a.get("distance", 0) for a in activities) / 1000
    total_time_hrs = sum(a.get("moving_time", 0) for a in activities) / 3600
    total_elevation = sum(a.get("total_elevation_gain", 0) for a in activities)
    sport_types = list(set(a.get("sport_type", "Unknown") for a in activities))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""<div class='stat-card'>
            <div class='stat-value'>{total_distance:.0f}</div>
            <div class='stat-label'>Total KM</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class='stat-card'>
            <div class='stat-value'>{total_time_hrs:.1f}</div>
            <div class='stat-label'>Hours</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class='stat-card'>
            <div class='stat-value'>{total_elevation:.0f}m</div>
            <div class='stat-label'>Elevation</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class='stat-card'>
            <div class='stat-value'>{len(activities)}</div>
            <div class='stat-label'>Activities</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Two columns: Activities + Chat ─────────────────────────────────────────
    left, right = st.columns([1, 1.6], gap="large")

    with left:
        st.markdown("### 📋 Recent Activities")
        sport_filter = st.selectbox("Filter by type", ["All"] + sport_types, label_visibility="collapsed")

        filtered = activities if sport_filter == "All" else [
            a for a in activities if a.get("sport_type") == sport_filter
        ]

        for act in filtered[:15]:
            dist_km = act.get("distance", 0) / 1000
            time_min = act.get("moving_time", 0) // 60
            date_str = act.get("start_date_local", "")[:10]
            sport = act.get("sport_type", "Activity")

            sport_emoji = {"Run": "🏃", "Ride": "🚴", "Swim": "🏊", "Walk": "🚶",
                           "Hike": "🥾", "WeightTraining": "🏋️"}.get(sport, "⚡")

            st.markdown(f"""
            <div class='activity-card'>
                <div class='activity-title'>{sport_emoji} {act.get('name', 'Activity')}</div>
                <div class='activity-meta'>
                    <span>📅 {date_str}</span>
                    <span>📍 {dist_km:.2f} km</span>
                    <span>⏱️ {time_min} min</span>
                </div>
            </div>""", unsafe_allow_html=True)

    with right:
        st.markdown("### 💬 AI Coach Chat")

        if not anthropic_key:
            st.warning("⚠️ ANTHROPIC_API_KEY not found in .env file.")
        else:
            # Chat history display
            chat_container = st.container()
            with chat_container:
                for msg in st.session_state.chat_history:
                    if msg["role"] == "user":
                        st.markdown(f"""
                        <div style='text-align:right;'>
                            <div class='chat-label'>YOU</div>
                            <div class='chat-user'>{msg['content']}</div>
                        </div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div>
                            <div class='chat-label'>🤖 AI COACH</div>
                            <div class='chat-ai'>{msg['content']}</div>
                        </div>""", unsafe_allow_html=True)

            # Suggested questions
            if not st.session_state.chat_history:
                st.markdown("<div style='color:#888; font-size:12px; margin-bottom:8px;'>Try asking:</div>",
                            unsafe_allow_html=True)
                suggestions = [
                    "What's my average pace this month?",
                    "Which activity burned the most calories?",
                    "Am I improving over time?",
                    "Suggest a recovery plan",
                ]
                scols = st.columns(2)
                for i, s in enumerate(suggestions):
                    with scols[i % 2]:
                        if st.button(s, key=f"sugg_{i}", use_container_width=True):
                            st.session_state.pending_question = s
                            st.rerun()

            # Handle pending question from suggestion buttons
            if "pending_question" in st.session_state:
                question = st.session_state.pop("pending_question")
                st.session_state.chat_history.append({"role": "user", "content": question})
                with st.spinner("Thinking..."):
                    agent = StravaAgent(anthropic_key, st.session_state.activities,
                                       st.session_state.athlete)
                    answer = agent.ask(question, st.session_state.chat_history[:-1])
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
                st.rerun()

            # Chat input
            with st.form("chat_form", clear_on_submit=True):
                user_input = st.text_input("Ask your AI coach...",
                                           placeholder="e.g. How many km did I run this week?",
                                           label_visibility="collapsed")
                submitted = st.form_submit_button("Send →", use_container_width=True)

            if submitted and user_input.strip():
                st.session_state.chat_history.append({"role": "user", "content": user_input})
                with st.spinner("Thinking..."):
                    agent = StravaAgent(anthropic_key, st.session_state.activities,
                                       st.session_state.athlete)
                    answer = agent.ask(user_input, st.session_state.chat_history[:-1])
                st.session_state.chat_history.append({"role": "assistant", "content": answer})
                st.rerun()

            if st.session_state.chat_history:
                if st.button("🗑️ Clear Chat", use_container_width=True):
                    st.session_state.chat_history = []
                    st.rerun()