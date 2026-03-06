import streamlit as st
import requests
import plotly.graph_objects as go
import pandas as pd
import time
from datetime import datetime

# --- Page Config ---
st.set_page_config(page_title="F1 Live Monitor", page_icon="🏎️", layout="wide")
st.markdown("""
    <style>
        .main { margin: 0; padding: 0; }
        .header { background: #1a237e; color: white; padding: 15px; text-align: center; }
        .nav { background: #f5f5f5; padding: 10px; border-bottom: 1px solid #ddd; }
        .section { padding: 20px; }
        .alert { padding: 10px; margin: 5px 0; border-radius: 5px; }
        .alert-info { background: #e3f2fd; color: #0d47a1; }
        .alert-warning { background: #fff3e0; color: #e65100; }
        .alert-danger { background: #ffebee; color: #c62828; }
    </style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown("""
    <div class="header">
        <h1>🏎️ F1 Live Monitor</h1>
        <p>Real-time F1 data, circuit maps, and insights</p>
        <p>Last Updated: {}</p>
    </div>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")), unsafe_allow_html=True)

# --- Navigation Tabs ---
tabs = st.tabs(["🌍 Circuit World", "💻 Car Tech", "📈 Team Stats", "📢 Alerts & News", "⚙️ Settings"])

# --- OpenF1 API Setup ---
API_URL_LAPS = "https://api.openf1.org/v1/laps"
API_URL_SESSIONS = "https://api.openf1.org/v1/sessions"
API_URL_DRIVERS = "https://api.openf1.org/v1/drivers"
INVALID_SESSION_KEYS = [9222, 7763, 7764]
REQUEST_DELAY = 2  # Seconds between requests to avoid rate limits
MAX_RETRIES = 3    # Max retries for rate-limited requests

# --- Sample lap data for fallback when API is unavailable ---
SAMPLE_LAP_DATA = [
    {"driver_number": 1, "lap_number": 1, "lap_duration": 90.5, "tire_compound": "Soft", "x": -0.8, "y": 0.5, "position": 1},
    {"driver_number": 44, "lap_number": 1, "lap_duration": 91.2, "tire_compound": "Soft", "x": -0.5, "y": 0.8, "position": 2},
    {"driver_number": 33, "lap_number": 1, "lap_duration": 91.8, "tire_compound": "Medium", "x": 0.0, "y": 0.7, "position": 3},
    {"driver_number": 11, "lap_number": 1, "lap_duration": 92.3, "tire_compound": "Medium", "x": 0.3, "y": 0.5, "position": 4},
    {"driver_number": 16, "lap_number": 1, "lap_duration": 92.7, "tire_compound": "Hard", "x": 0.5, "y": 0.0, "position": 5}
]

# --- Function to Fetch Data (with rate limit handling, retries & fallback) ---
def fetch_data(url, params=None, retries=0):
    try:
        # Add delay before each request to avoid rate limits
        time.sleep(REQUEST_DELAY)
        response = requests.get(url, params=params)
        # Handle rate limits with retries
        if response.status_code == 429:
            if retries < MAX_RETRIES:
                wait_time = int(response.headers.get("Retry-After", 5 * (retries + 1)))
                st.warning(f"Rate limit hit. Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
                return fetch_data(url, params, retries + 1)
            else:
                st.error("Max retries reached. Using sample data instead.")
                return SAMPLE_LAP_DATA if url == API_URL_LAPS else None
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # Use sample data if laps endpoint fails
        if url == API_URL_LAPS:
            st.warning("Could not fetch lap data from API. Using sample data for demonstration.")
            return SAMPLE_LAP_DATA
        # Only show non-404/non-429 errors for other endpoints
        elif "404" not in str(e) and "429" not in str(e):
            st.error(f"Error fetching data: {e}")
        return None

# --- Cache session data to avoid repeated calls ---
@st.cache_data(show_spinner=False)
def get_cached_sessions():
    return fetch_data(API_URL_SESSIONS)

# Get all sessions with caching
sessions_data = get_cached_sessions()
session_key = 7765  # Updated default fallback key (from your sessions data)

if sessions_data:
    # Sort sessions by date (newest first)
    sessions_data.sort(key=lambda x: x.get('date_start', ''), reverse=True)

    # Find the latest session with valid lap data
    latest_session = None
    for session in sessions_data:
        if session.get('session_key') in INVALID_SESSION_KEYS:
            continue
        temp_session_key = session.get('session_key')
        if temp_session_key:
            test_response = fetch_data(API_URL_LAPS, params={"session_key": temp_session_key, "limit": 1})
            if test_response:
                latest_session = session
                session_key = temp_session_key
                print(f"Found valid session: {session_key} for {session.get('session_name', 'Unknown Session')}")
                break

    # If no valid session found, try up to 10 more
    if not latest_session:
        for i in range(1, min(11, len(sessions_data))):
            if i < len(sessions_data):
                session = sessions_data[i]
                if session.get('session_key') in INVALID_SESSION_KEYS:
                    continue
                temp_session_key = session.get('session_key')
                if temp_session_key:
                    test_response = fetch_data(API_URL_LAPS, params={"session_key": temp_session_key, "limit": 1})
                    if test_response:
                        latest_session = session
                        session_key = temp_session_key
                        print(f"Found valid session: {session_key} for {session.get('session_name', 'Unknown Session')}")
                        break

# --- Initialize Session State ---
if "session_key" not in st.session_state:
    st.session_state.session_key = session_key
if "playback_lap" not in st.session_state:
    st.session_state.playback_lap = 0

# --- Sidebar Controls ---
with st.sidebar:
    st.subheader("Controls")
    # Session Selector (only show valid sessions)
    session_options = {}
    if sessions_data:
        for s in sessions_data[:15]:
            if s.get('session_key') in INVALID_SESSION_KEYS:
                continue
            temp_key = s.get('session_key')
            if temp_key:
                test_resp = fetch_data(API_URL_LAPS, params={"session_key": temp_key, "limit": 1})
                if test_resp:
                    name = s.get('session_name', 'Unknown Session')
                    year = s.get('year', 'Unknown Year')
                    session_options[f"{name} ({year})"] = temp_key
    
    if session_options:
        selected_session = st.selectbox("Select Session", options=session_options.keys())
        st.session_state.session_key = session_options[selected_session]
    else:
        st.warning("No valid sessions with lap data available to select")
    
    # Time Range Selector
    time_range = st.selectbox("Time Range", ["1h", "6h", "24h", "Full Session"], key="time_range_select")
    
    # Layer Toggles
    st.subheader("Data Layers")
    show_lap_times = st.checkbox("Lap Times", value=True)
    show_speed_zones = st.checkbox("Speed Zones", value=True)
    show_tire_wear = st.checkbox("Tire Wear", value=False)
    show_penalties = st.checkbox("Penalties", value=True)
    
    # Historical Playback
    st.subheader("Historical Playback")
    playback = st.checkbox("Enable Playback")
    if playback:
        lap_data = fetch_data(API_URL_LAPS, params={"session_key": st.session_state.session_key})
        max_lap = max([l['lap_number'] for l in lap_data]) if lap_data else 1
        st.session_state.playback_lap = st.slider("Select Lap", min_value=1, max_value=max_lap, value=1)
    
    # Export Options
    st.subheader("Export Data")
    export_csv = st.button("Export to CSV")
    export_json = st.button("Export to JSON")

# --- Tab 1: Circuit World ---
with tabs[0]:
    st.subheader("Circuit Map & Live Positions")
    # Sample circuit coordinates (replace with real data if available)
    circuit_coords = pd.DataFrame({
        "x": [-1.0, -0.8, -0.5, 0.0, 0.3, 0.5, 0.3, 0.0, -0.5, -0.8],
        "y": [0.0, 0.5, 0.8, 0.7, 0.5, 0.0, -0.5, -0.7, -0.8, -0.5]
    })
    
    # Get car positions
    lap_data = fetch_data(API_URL_LAPS, params={"session_key": st.session_state.session_key, "limit": 20})
    car_positions = pd.DataFrame()
    if lap_data:
        if playback:
            playback_data = [l for l in lap_data if l.get('lap_number') == st.session_state.playback_lap]
            if playback_data:
                car_positions = pd.DataFrame({
                    "x": [p.get('x') for p in playback_data if 'x' in p],
                    "y": [p.get('y') for p in playback_data if 'y' in p],
                    "driver": [p.get('driver_number') for p in playback_data if 'x' in p]
                })
        else:
            car_positions = pd.DataFrame({
                "x": [l.get('x') for l in lap_data if 'x' in l],
                "y": [l.get('y') for l in lap_data if 'y' in l],
                "driver": [l.get('driver_number') for l in lap_data if 'x' in l]
            })
    
    # Build interactive map
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=circuit_coords["x"], y=circuit_coords["y"],
        mode="lines", line=dict(color="#1a237e", width=3),
        name="Circuit Track"
    ))
    if not car_positions.empty:
        fig.add_trace(go.Scatter(
            x=car_positions["x"], y=car_positions["y"],
            mode="markers+text", marker=dict(color="red", size=10),
            text=car_positions["driver"], textposition="top center",
            name="Car Positions"
        ))
    if show_speed_zones:
        speed_zones = pd.DataFrame({
            "x": [-0.5, 0.3], "y": [0.8, 0.0],
            "label": ["High Speed", "Medium Speed"]
        })
        fig.add_trace(go.Scatter(
            x=speed_zones["x"], y=speed_zones["y"],
            mode="markers", marker=dict(color="orange", size=12, symbol="diamond"),
            text=speed_zones["label"], textposition="bottom center",
            name="Speed Zones"
        ))
    fig.update_layout(
        showlegend=True, height=600,
        title="Current Circuit: Silverstone",
        xaxis_title="X Coordinate", yaxis_title="Y Coordinate"
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Tab 2: Car Tech ---
with tabs[1]:
    st.subheader("Car Technical Data & Telemetry")
    if lap_data and show_lap_times:
        latest_laps = lap_data[:5]
        for lap in latest_laps:
            driver = lap.get('driver_number', 'Unknown')
            lap_num = lap.get('lap_number', 'Unknown')
            dur = lap.get('lap_duration')
            tire = lap.get('tire_compound', 'N/A')
            lap_str = f"{int(dur // 60):02d}:{int(dur % 60):02d}" if dur else "N/A"
            tire_color = "green" if tire == "Soft" else "yellow" if tire == "Medium" else "red"
            st.markdown(f"""
                <div style='border:1px solid #ddd; border-radius:8px; padding:15px; margin:10px 0;'>
                    <h4>Driver {driver} | Lap {lap_num}</h4>
                    <p>Lap Time: {lap_str} | Tire Compound: <span style='color:{tire_color}; font-weight:bold;'>{tire}</span></p>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No car tech data available")

# --- Tab 3: Team Stats ---
with tabs[2]:
    st.subheader("Team & Driver Standings")
    driver_data = fetch_data(API_URL_DRIVERS)
    if driver_data and lap_data:
        standings = {}
        for lap in lap_data:
            driver = lap.get('driver_number')
            pos = lap.get('position')
            if driver not in standings and pos:
                standings[driver] = pos
        sorted_standings = sorted(standings.items(), key=lambda x: x[1])
        standings_df = pd.DataFrame(sorted_standings, columns=["Driver Number", "Position"])
        standings_df["Team"] = [next((d.get('team_name') for d in driver_data if d.get('driver_number') == dr), "N/A") for dr in standings_df["Driver Number"]]
        st.dataframe(standings_df, use_container_width=True, hide_index=True)
    else:
        st.info("No standings data available")

# --- Tab 4: Alerts & News ---
with tabs[3]:
    st.subheader("Live Alerts & F1 News")
    alerts = [
        {"type": "info", "text": "🔄 Live updates active for 2023 British Grand Prix"},
        {"type": "warning", "text": "⚠️ Safety car deployed at lap 25"},
        {"type": "danger", "text": "📢 Driver 44 receives a 5-second penalty for speeding in the pit lane"},
        {"type": "info", "text": "🏆 Driver 1 sets fastest lap of the race: 1:28.456"}
    ]
    if not show_penalties:
        alerts = [a for a in alerts if "penalty" not in a['text'].lower()]
    for alert in alerts:
        st.markdown(f"""<div class='alert alert-{alert["type"]}'>{alert["text"]}</div>""", unsafe_allow_html=True)
    st.subheader("Latest F1 News")
    news = [
        "Hamilton: 'This car has potential to win'",
        "Verstappen: 'We need to improve tire management'",
        "F1 announces new circuit for 2025 season"
    ]
    for item in news:
        st.write(f"- {item}")

# --- Tab 5: Settings ---
with tabs[4]:
    st.subheader("Dashboard Settings")
    st.checkbox("Dark Mode", value=False)
    auto_refresh = st.checkbox("Auto-refresh", value=True)
    refresh_interval = st.number_input("Refresh Interval (seconds)", min_value=10, max_value=60, value=10)  # Increased min to avoid rate limits
    st.selectbox("Map Type", ["2D", "3D"])

# --- Export Functionality ---
if export_csv:
    if lap_data:
        df = pd.DataFrame(lap_data)
        df.to_csv("f1_live_data.csv", index=False)
        st.success("Data exported to CSV successfully!")
    else:
        st.warning("No data to export")
if export_json:
    if lap_data:
        import json
        with open("f1_live_data.json", "w") as f:
            json.dump(lap_data, f)
        st.success
