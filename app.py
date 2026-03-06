import streamlit as st
import requests
import plotly.graph_objects as go
import pandas as pd
import time
from datetime import datetime

# --- Page Config (Match World Monitor's Wide Layout) ---
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

# --- Header (Like World Monitor's Top Bar) ---
st.markdown("""
    <div class="header">
        <h1>🏎️ F1 Live Monitor</h1>
        <p>Real-time F1 data, circuit maps, and insights</p>
        <p>Last Updated: {}</p>
    </div>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")), unsafe_allow_html=True)

# --- Navigation Tabs (Like World Monitor's Top Nav) ---
tabs = st.tabs(["🌍 Circuit World", "💻 Car Tech", "📈 Team Stats", "📢 Alerts & News", "⚙️ Settings"])

# --- OpenF1 API Setup ---
API_URL_LAPS = "https://api.openf1.org/v1/laps"
API_URL_SESSIONS = "https://api.openf1.org/v1/sessions"
API_URL_DRIVERS = "https://api.openf1.org/v1/drivers"

# --- Function to Fetch Data (with error handling) ---
def fetch_data(url, params=None):
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

# Get all sessions with error handling
sessions_data = fetch_data(API_URL_SESSIONS)
session_key = 9148  # Default fallback key

if sessions_data:
    # Sort sessions by date (newest first)
    sessions_data.sort(key=lambda x: x.get('date_start', ''), reverse=True)

    # Find the latest session (or live one if in progress)
    latest_session = None
    for session in sessions_data:
        # Check common live status labels (adjust if needed)
        status = session.get('status', '').lower()
        if status in ['active', 'live', 'in_progress']:
            latest_session = session
            break
    # If no live session, take the most recent one
    if not latest_session and sessions_data:
        latest_session = sessions_data[0]

    if latest_session:
        temp_session_key = latest_session.get('session_key')
        if temp_session_key:
            session_key = temp_session_key
            print(f"Using session key: {session_key} for {latest_session.get('session_name', 'Unknown Session')}")
            
            # Verify this session has lap data before using it
            test_response = fetch_data(API_URL_LAPS, params={"session_key": session_key, "limit": 1})
            if not test_response:
                print(f"No lap data for session {session_key}, trying next most recent")
                # Try the next session in the list if the first one has no data
                for i in range(1, min(5, len(sessions_data))):  # Check up to 5 sessions
                    if i < len(sessions_data):
                        latest_session = sessions_data[i]
                        temp_session_key = latest_session.get('session_key')
                        if temp_session_key:
                            session_key = temp_session_key
                            test_response = fetch_data(API_URL_LAPS, params={"session_key": session_key, "limit": 1})
                            if test_response:
                                print(f"Found valid session: {session_key} for {latest_session.get('session_name', 'Unknown Session')}")
                                break

# --- Initialize Session State ---
if "session_key" not in st.session_state:
    st.session_state.session_key = session_key
if "playback_lap" not in st.session_state:
    st.session_state.playback_lap = 0

# --- Sidebar Controls (Like World Monitor's Layers/Time Select) ---
with st.sidebar:
    st.subheader("Controls")
    # Session Selector
    sessions = fetch_data(API_URL_SESSIONS)
    session_options = {}
    if sessions:
        for s in sessions[:10]:
            # Get values safely, with defaults if missing
            name = s.get('session_name', 'Unknown Session')
            year = s.get('year', 'Unknown Year')
            key = s.get('session_key')
            # Only add to options if we have a valid session key
            if key is not None:
                session_options[f"{name} ({year})"] = key
    
    if session_options:
        selected_session = st.selectbox("Select Session", options=session_options.keys())
        st.session_state.session_key = session_options[selected_session]
    else:
        st.warning("No sessions available to select")
    
    # Time Range Selector (Like World Monitor's 1h/6h/24h)
    time_range = st.selectbox("Time Range", ["1h", "6h", "24h", "Full Session"], key="time_range_select")
    
    # Layer Toggles (Like World Monitor's Layers)
    st.subheader("Data Layers")
    show_lap_times = st.checkbox("Lap Times", value=True)
    show_speed_zones = st.checkbox("Speed Zones", value=True)
    show_tire_wear = st.checkbox("Tire Wear", value=False)
    show_penalties = st.checkbox("Penalties", value=True)
    
    # Historical Playback (Like World Monitor's Playback)
    st.subheader("Historical Playback")
    playback = st.checkbox("Enable Playback")
    if playback:
        lap_data = fetch_data(API_URL_LAPS, params={"session_key": st.session_state.session_key})
        max_lap = max([l['lap_number'] for l in lap_data]) if lap_data else 1
        st.session_state.playback_lap = st.slider("Select Lap", min_value=1, max_value=max_lap, value=1)
    
    # Export Options (Like World Monitor's Export)
    st.subheader("Export Data")
    export_csv = st.button("Export to CSV")
    export_json = st.button("Export to JSON")

# --- Tab 1: Circuit World (Interactive Map - Like World Monitor's Map) ---
with tabs[0]:
    st.subheader("Circuit Map & Live Positions")
    # Get circuit coordinates (sample for Silverstone; replace with real data)
    circuit_coords = pd.DataFrame({
        "x": [-1.0, -0.8, -0.5, 0.0, 0.3, 0.5, 0.3, 0.0, -0.5, -0.8],
        "y": [0.0, 0.5, 0.8, 0.7, 0.5, 0.0, -0.5, -0.7, -0.8, -0.5]
    })
    
    # Get car positions
    lap_data = fetch_data(API_URL_LAPS, params={"session_key": st.session_state.session_key, "limit": 20})
    car_positions = pd.DataFrame()
    if lap_data:
        if playback:
            # Use selected lap for playback
            playback_data = [l for l in lap_data if l.get('lap_number') == st.session_state.playback_lap]
            if playback_data:
                car_positions = pd.DataFrame({
                    "x": [p.get('x') for p in playback_data if 'x' in p],
                    "y": [p.get('y') for p in playback_data if 'y' in p],
                    "driver": [p.get('driver_number') for p in playback_data if 'x' in p]
                })
        else:
            # Use latest positions
            car_positions = pd.DataFrame({
                "x": [l.get('x') for l in lap_data if 'x' in l],
                "y": [l.get('y') for l in lap_data if 'y' in l],
                "driver": [l.get('driver_number') for l in lap_data if 'x' in l]
            })
    
    # Build interactive map
    fig = go.Figure()
    # Add circuit path
    fig.add_trace(go.Scatter(
        x=circuit_coords["x"], y=circuit_coords["y"],
        mode="lines", line=dict(color="#1a237e", width=3),
        name="Circuit Track"
    ))
    # Add car positions
    if not car_positions.empty:
        fig.add_trace(go.Scatter(
            x=car_positions["x"], y=car_positions["y"],
            mode="markers+text", marker=dict(color="red", size=10),
            text=car_positions["driver"], textposition="top center",
            name="Car Positions"
        ))
    # Add speed zones if toggled
    if show_speed_zones:
        # Sample speed zones (replace with real data)
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
    # Update layout
    fig.update_layout(
        showlegend=True, height=600,
        title="Current Circuit: Silverstone",
        xaxis_title="X Coordinate", yaxis_title="Y Coordinate"
    )
    st.plotly_chart(fig, use_container_width=True)

# --- Tab 2: Car Tech (Like World Monitor's Tech Section) ---
with tabs[1]:
    st.subheader("Car Technical Data & Telemetry")
    if lap_data and show_lap_times:
        # Show latest lap data
        latest_laps = lap_data[:5]
        for lap in latest_laps:
            driver = lap.get('driver_number', 'Unknown')
            lap_num = lap.get('lap_number', 'Unknown')
            dur = lap.get('lap_duration')
            tire = lap.get('tire_compound', 'N/A')
            # Format lap time
            if dur:
                mins = int(dur // 60)
                secs = int(dur % 60)
                lap_str = f"{mins:02d}:{secs:02d}"
            else:
                lap_str = "N/A"
            # Color-code tire wear
            tire_color = "green" if tire == "Soft" else "yellow" if tire == "Medium" else "red"
            st.markdown(f"""
                <div style='border:1px solid #ddd; border-radius:8px; padding:15px; margin:10px 0;'>
                    <h4>Driver {driver} | Lap {lap_num}</h4>
                    <p>Lap Time: {lap_str} | Tire Compound: <span style='color:{tire_color}; font-weight:bold;'>{tire}</span></p>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No car tech data available")

# --- Tab 3: Team Stats (Like World Monitor's Finance Section) ---
with tabs[2]:
    st.subheader("Team & Driver Standings")
    # Get driver data
    driver_data = fetch_data(API_URL_DRIVERS)
    if driver_data and lap_data:
        # Calculate standings
        standings = {}
        for lap in lap_data:
            driver = lap.get('driver_number')
            pos = lap.get('position')
            if driver not in standings and pos:
                standings[driver] = pos
        # Sort by position
        sorted_standings = sorted(standings.items(), key=lambda x: x[1])
        # Create table
        standings_df = pd.DataFrame(sorted_standings, columns=["Driver Number", "Position"])
        # Add team names
        standings_df["Team"] = [next((d.get('team_name') for d in driver_data if d.get('driver_number') == dr), "N/A") for dr in standings_df["Driver Number"]]
        st.dataframe(standings_df, use_container_width=True, hide_index=True)
    else:
        st.info("No standings data available")

# --- Tab 4: Alerts & News (Like World Monitor's News Section) ---
with tabs[3]:
    st.subheader("Live Alerts & F1 News")
    # Sample alerts (replace with real F1 news API)
    alerts = [
        {"type": "info", "text": "🔄 Live updates active for 2023 British Grand Prix"},
        {"type": "warning", "text": "⚠️ Safety car deployed at lap 25"},
        {"type": "danger", "text": "📢 Driver 44 receives a 5-second penalty for speeding in the pit lane"},
        {"type": "info", "text": "🏆 Driver 1 sets fastest lap of the race: 1:28.456"}
    ]
    # Filter alerts based on toggles
    if not show_penalties:
        alerts = [a for a in alerts if "penalty" not in a['text'].lower()]
    # Display alerts
    for alert in alerts:
        st.markdown(f"""
            <div class='alert alert-{alert["type"]}'>{alert["text"]}</div>
        """, unsafe_allow_html=True)
    # Live news feed (sample)
    st.subheader("Latest F1 News")
    news = [
        "Hamilton: 'This car has potential to win'",
        "Verstappen: 'We need to improve tire management'",
        "F1 announces new circuit for 2025 season"
    ]
    for item in news:
        st.write(f"- {item}")

# --- Tab 5: Settings (Like World Monitor's Settings) ---
with tabs[4]:
    st.subheader("Dashboard Settings")
    st.checkbox("Dark Mode", value=False)
    auto_refresh = st.checkbox("Auto-refresh", value=True)
    refresh_interval = st.number_input("Refresh Interval (seconds)", min_value=5, max_value=60, value=5)
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
        st.success("Data exported to JSON successfully!")
    else:
        st.warning("No data to export")

# --- Auto-refresh ---
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
