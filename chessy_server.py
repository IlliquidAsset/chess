from flask import Flask, render_template, jsonify
import os
import json
import pandas as pd
import plotly.express as px
from chessy_analysis import analyze_games
from chessy_parser import parse_games
from chessy_downloader import fetch_and_save_games

# -----------------------------------------------------------------------------
# 🛠 CONFIGURATION
# -----------------------------------------------------------------------------
DATA_DIR = "output"
GAME_ANALYSIS_FILE = os.path.join(DATA_DIR, "game_analysis.json")
PARSED_GAMES_FILE = os.path.join(DATA_DIR, "IlliquidAsset_games_parsed.json")
ARCHIVE_FILE = os.path.join(DATA_DIR, "IlliquidAsset_GameArchive.pgn")

app = Flask(__name__)

# -----------------------------------------------------------------------------
# ✅ ENSURE ALL NECESSARY FILES EXIST
# -----------------------------------------------------------------------------

def ensure_required_files():
    """
    Checks if required analysis files exist, and generates them if missing.
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # Step 1: Ensure we have a PGN archive
    if not os.path.exists(ARCHIVE_FILE):
        print("⚠️ No PGN archive found. Downloading games...")
        fetch_and_save_games()

    # Step 2: Ensure parsed game data exists
    if not os.path.exists(PARSED_GAMES_FILE):
        print("⚠️ No parsed games file found. Parsing PGN...")
        parse_games(ARCHIVE_FILE)

    # Step 3: Ensure game analysis exists
    if not os.path.exists(GAME_ANALYSIS_FILE):
        print("⚠️ No game analysis found. Running analysis...")
        analyze_games(ARCHIVE_FILE)

# Run file check before starting the server
ensure_required_files()

# -----------------------------------------------------------------------------
# 🌍 FLASK API ROUTES
# -----------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def get_data():
    """ Returns game data as JSON """
    with open(GAME_ANALYSIS_FILE, "r") as file:
        return jsonify(json.load(file))

@app.route("/elo_chart")
def elo_chart():
    """ Generates an interactive Elo chart using Plotly """
    with open(GAME_ANALYSIS_FILE, "r") as file:
        data = json.load(file)

    if not data:
        return jsonify({"error": "No data available"})

    df = pd.DataFrame(data)

    if df.empty or "YourElo" not in df.columns:
        return jsonify({"error": "Missing required data for visualization"})

    fig = px.scatter(
        df,
        x="Date",
        y="YourElo",
        color="Result",
        title="Your Elo Progression Over Time",
        hover_data=["Opponent", "OpponentEloStart", "OpponentEloNow"]
    )

    return fig.to_json()

# -----------------------------------------------------------------------------
# 🚀 RUN SERVER
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)