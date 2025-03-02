"""
Main entry point for the Chessy web application.
"""
import os
import json
import logging
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Import chessy modules
from chessy.config import (
    USERNAME, HEADERS, ARCHIVE_FILE, LAST_DOWNLOADED_FILE, 
    GAME_ANALYSIS_FILE, PARSED_GAMES_FILE, ECO_CSV_FILE, 
    STOCKFISH_PATH, validate_config, OUTPUT_DIR, config
)
from chessy.services.downloader import ChessComDownloader
from chessy.services.parser import GameParser
from chessy.services.analyzer import GameAnalyzer
from chessy.services import ChessyService
from chessy.utils.logging import setup_logging, emoji_log

# Initialize app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # For flash messages

# Setup logging
logger = setup_logging(OUTPUT_DIR)

# Initialize services
def init_services():
    """Initialize all required services."""
    try:
        # Validate configuration
        valid = validate_config()
        if not valid:
            emoji_log(logger, logging.WARNING, 
                     "Configuration issues detected. Some features may be limited.", "⚠️")
        
        # Initialize core services
        downloader = ChessComDownloader(
            username=USERNAME,
            headers=HEADERS,
            archive_file=ARCHIVE_FILE,
            last_downloaded_file=LAST_DOWNLOADED_FILE
        )
        
        parser = GameParser(
            username=USERNAME,
            parsed_games_file=PARSED_GAMES_FILE
        )
        
        analyzer = GameAnalyzer(
            config=config
        )
        
        # Initialize main service
        service = ChessyService(
            downloader=downloader,
            parser=parser,
            analyzer=analyzer,
            config=config
        )
        
        emoji_log(logger, logging.INFO, f"Services initialized for user: {USERNAME}", "✅")
        return service
        
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Failed to initialize services: {str(e)}", "❌")
        logging.exception("Detailed error information:")
        return None

# Initialize the service
chessy_service = init_services()

# Ensure all required files exist
def ensure_required_files():
    """Ensure necessary files exist for the application to function."""
    if not chessy_service:
        return False
        
    # Check for archive file
    if not os.path.exists(ARCHIVE_FILE):
        emoji_log(logger, logging.WARNING, "No game archive found. Will prompt user to download games.", "⚠️")
        return False
        
    # Check for parsed game data
    if not os.path.exists(PARSED_GAMES_FILE):
        emoji_log(logger, logging.WARNING, "No parsed games file found. Will process on first request.", "⚠️")
        
    # Check for game analysis
    if not os.path.exists(GAME_ANALYSIS_FILE):
        emoji_log(logger, logging.WARNING, "No game analysis found. Will run analysis on request.", "⚠️")
        
    return True

# API Routes
@app.route("/")
def index():
    """Main dashboard page."""
    has_data = ensure_required_files()
    
    # Get game statistics if available
    stats = chessy_service.get_game_statistics() if chessy_service else {"total_games": 0}
    
    return render_template(
        "index.html", 
        username=USERNAME,
        has_data=has_data,
        stats=stats
    )

@app.route("/download", methods=["POST"])
def download_games():
    """Download games from Chess.com."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
        
    try:
        # Trigger game download
        new_games = chessy_service.check_for_updates()
        
        if new_games > 0:
            flash(f"Downloaded {new_games} new games successfully!", "success")
            
            # Process new games
            results = chessy_service.process_new_games()
            flash(f"Processed {results['analyzed_games']} games with {results['openings_analyzed']} openings.", "success")
        else:
            flash("No new games found on Chess.com", "info")
            
        return redirect(url_for("index"))
        
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Download error: {str(e)}", "❌")
        flash(f"Error downloading games: {str(e)}", "error")
        return redirect(url_for("index"))

@app.route("/analyze", methods=["POST"])
def analyze_games():
    """Analyze games with Stockfish."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
        
    try:
        # Trigger full game processing pipeline
        results = chessy_service.process_new_games()
        
        flash(f"Analysis complete! Processed {results['analyzed_games']} games.", "success")
        return redirect(url_for("index"))
        
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Analysis error: {str(e)}", "❌")
        flash(f"Error analyzing games: {str(e)}", "error")
        return redirect(url_for("index"))

@app.route("/games")
def games():
    """View game list and details."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
        
    # Get game data if available
    try:
        with open(PARSED_GAMES_FILE, "r") as f:
            games_data = json.load(f)
    except Exception:
        games_data = []
        
    return render_template(
        "games.html",
        username=USERNAME,
        games=games_data
    )

@app.route("/openings")
def openings():
    """View opening statistics."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
        
    eco_data = chessy_service.get_opening_performance()
    
    return render_template(
        "openings.html",
        username=USERNAME,
        eco_data=eco_data
    )

# API endpoints for data
@app.route("/api/game_data")
def get_game_data():
    """Return game data as JSON."""
    try:
        with open(GAME_ANALYSIS_FILE, "r") as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/eco_data")
def get_eco_data():
    """Return ECO performance data as JSON."""
    try:
        with open(ECO_CSV_FILE, "r") as f:
            reader = csv.DictReader(f)
            return jsonify(list(reader))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/charts/win_rate")
def win_rate_chart():
    """Generate win rate chart data."""
    try:
        with open(GAME_ANALYSIS_FILE, "r") as f:
            data = json.load(f)
            
        if not data:
            return jsonify({"error": "No data available"})
            
        df = pd.DataFrame(data)
        
        # Prepare time control groups
        df['TimeControl'] = df['TimeControl'].apply(lambda x: 
            "Bullet" if int(x.split('+')[0]) < 3 else
            "Blitz" if int(x.split('+')[0]) < 10 else
            "Rapid" if int(x.split('+')[0]) < 30 else
            "Classical"
        )
        
        # Calculate win rates by time control
        tc_stats = df.groupby('TimeControl').apply(lambda x: {
            'games': len(x),
            'wins': sum((x['PlayedAs'] == 'White') & (x['Result'] == '1-0') | 
                        (x['PlayedAs'] == 'Black') & (x['Result'] == '0-1')),
            'losses': sum((x['PlayedAs'] == 'White') & (x['Result'] == '0-1') | 
                          (x['PlayedAs'] == 'Black') & (x['Result'] == '1-0')),
            'draws': sum(x['Result'] == '1/2-1/2')
        }).to_dict()
        
        # Create chart data
        chart_data = []
        for tc, stats in tc_stats.items():
            win_rate = stats['wins'] / stats['games'] * 100 if stats['games'] > 0 else 0
            chart_data.append({
                'timeControl': tc,
                'winRate': round(win_rate, 1),
                'games': stats['games']
            })
            
        return jsonify(chart_data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run the application
def main():
    # Validate config before starting
    if not validate_config():
        emoji_log(logger, logging.WARNING, 
                 "Configuration validation failed. Application may not function correctly.", "⚠️")
    
    emoji_log(logger, logging.INFO, f"Starting Chessy server for user: {USERNAME}", "🚀")
    app.run(debug=True)
    
if __name__ == "__main__":
    main()
