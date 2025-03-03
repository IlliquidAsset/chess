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
import csv
import threading
from queue import Queue
import time
import threading
from queue import Queue
import time
from flask import current_app

# Global variables for progress tracking
progress_queue = Queue()
current_operation = None
operation_started = None
flash_messages = []  # Store flash messages to apply in request context


# Import chessy modules
from chessy.config import (
    USERNAME, HEADERS, ARCHIVE_FILE, LAST_DOWNLOADED_FILE, 
    GAME_ANALYSIS_FILE, PARSED_GAMES_FILE, ECO_CSV_FILE, 
    STOCKFISH_PATH, validate_config, OUTPUT_DIR, LOGS_DIR,
    config
)
from chessy.services.downloader import ChessComDownloader
from chessy.services.parser import GameParser
from chessy.services.analyzer import GameAnalyzer
from chessy.services import ChessyService
from chessy.utils.logging import setup_logging, emoji_log

progress_queue = Queue()
current_operation = None
operation_started = None

# Initialize app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # For flash messages

# Setup logging
logger = setup_logging(LOGS_DIR)

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
        
        # If we have archive but no parsed games, parse them now
        if os.path.exists(ARCHIVE_FILE):
            try:
                chessy_service.parser.parse_games(ARCHIVE_FILE)
                emoji_log(logger, logging.INFO, "Automatically parsed existing archive file.", "✅")
            except Exception as e:
                emoji_log(logger, logging.ERROR, f"Error parsing existing archive: {str(e)}", "❌")
        
    # Check for game analysis
    if not os.path.exists(GAME_ANALYSIS_FILE):
        emoji_log(logger, logging.WARNING, "No game analysis found. Will run analysis on request.", "⚠️")
        
        # If we have parsed games but no analysis, create a basic analysis file
        if os.path.exists(PARSED_GAMES_FILE):
            try:
                with open(PARSED_GAMES_FILE, 'r') as f:
                    games_data = json.load(f)
                
                # Create a basic analysis file with the games data
                # This ensures the dashboard can show game counts even without full analysis
                with open(GAME_ANALYSIS_FILE, 'w') as f:
                    json.dump(games_data, f, indent=4)
                
                emoji_log(logger, logging.INFO, "Created basic analysis file from parsed games.", "✅")
            except Exception as e:
                emoji_log(logger, logging.ERROR, f"Error creating basic analysis: {str(e)}", "❌")
        
    return True

# API Routes
@app.route("/")
def index():
    """Main dashboard page."""
    has_data = ensure_required_files()
    
    # Get game statistics
    stats = {"total_games": 0, "wins": 0, "losses": 0, "draws": 0}
    
    try:
        # First try to get stats from the service
        if chessy_service:
            service_stats = chessy_service.get_game_statistics()
            if service_stats and service_stats.get('total_games', 0) > 0:
                stats = service_stats
            else:
                # If service stats are empty, try to calculate basic stats from files
                if os.path.exists(PARSED_GAMES_FILE):
                    with open(PARSED_GAMES_FILE, 'r') as f:
                        games_data = json.load(f)
                    
                    total_games = len(games_data)
                    wins = sum(1 for game in games_data 
                            if (game.get("PlayedAs") == "White" and game.get("Result") == "1-0") or
                                (game.get("PlayedAs") == "Black" and game.get("Result") == "0-1"))
                    losses = sum(1 for game in games_data 
                                if (game.get("PlayedAs") == "White" and game.get("Result") == "0-1") or
                                (game.get("PlayedAs") == "Black" and game.get("Result") == "1-0"))
                    draws = sum(1 for game in games_data if game.get("Result") == "1/2-1/2")
                    
                    stats = {
                        "total_games": total_games,
                        "wins": wins,
                        "losses": losses,
                        "draws": draws,
                        "win_percentage": round(wins / total_games * 100, 1) if total_games > 0 else 0
                    }
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error getting statistics: {str(e)}", "❌")
    
    return render_template(
        "index.html", 
        username=USERNAME,
        has_data=has_data,
        stats=stats
    )

@app.route("/api/progress")
def get_progress():
    """Return the current progress status."""
    global current_operation, operation_started
    
    if current_operation is None:
        return jsonify({
            "active": False,
            "message": "No operation in progress"
        })
    
    # Get all messages from the queue without blocking
    messages = []
    try:
        while True:
            message = progress_queue.get_nowait()
            messages.append(message)
    except:
        pass  # Queue is empty
    
    # Calculate elapsed time
    elapsed = 0
    if operation_started:
        elapsed = int(time.time() - operation_started)
    
    return jsonify({
        "active": True,
        "operation": current_operation,
        "elapsed_seconds": elapsed,
        "messages": messages
    })

@app.route("/download", methods=["POST"])
def download_games():
    """Download games from Chess.com."""
    global current_operation, operation_started, progress_queue
    
    # Reset progress tracking
    with progress_queue.mutex:
        progress_queue.queue.clear()
    current_operation = "download"
    operation_started = time.time()
    
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        current_operation = None
        return redirect(url_for("index"))
    
    # Run the download in a background thread
    def download_thread():
        global current_operation
        try:
            progress_queue.put("Starting game download from Chess.com...")
            new_games = chessy_service.check_for_updates()
            
            if new_games > 0:
                progress_queue.put(f"Downloaded {new_games} new games")
                
                # Process new games
                progress_queue.put("Processing downloaded games...")
                results = chessy_service.process_new_games()
                progress_queue.put(f"Processed {results['analyzed_games']} games with {results['openings_analyzed']} openings")
                
                flash(f"Downloaded {new_games} new games successfully!", "success")
                flash(f"Processed {results['analyzed_games']} games with {results['openings_analyzed']} openings.", "success")
            else:
                progress_queue.put("No new games found on Chess.com")
                flash("No new games found on Chess.com", "info")
        except Exception as e:
            emoji_log(logger, logging.ERROR, f"Download error: {str(e)}", "❌")
            progress_queue.put(f"Error: {str(e)}")
            flash(f"Error downloading games: {str(e)}", "error")
        finally:
            current_operation = None
    
    # Start the download thread
    threading.Thread(target=download_thread).start()
    
    # Return success immediately - the thread will continue running
    return jsonify({"status": "success", "message": "Download started"})

@app.route("/analyze", methods=["POST"])
def analyze_games():
    """Analyze games with Stockfish."""
    global current_operation, operation_started, progress_queue
    
    # Reset progress tracking
    with progress_queue.mutex:
        progress_queue.queue.clear()
    current_operation = "analyze"
    operation_started = time.time()
    
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        current_operation = None
        return redirect(url_for("index"))
    
    # Run the analysis in a background thread
    def analyze_thread():
        global current_operation
        try:
            progress_queue.put("Starting game analysis...")
            
            # Trigger full game processing pipeline
            results = chessy_service.process_new_games()
            
            progress_queue.put(f"Analysis complete! Processed {results['analyzed_games']} games.")
            flash(f"Analysis complete! Processed {results['analyzed_games']} games.", "success")
        except Exception as e:
            emoji_log(logger, logging.ERROR, f"Analysis error: {str(e)}", "❌")
            progress_queue.put(f"Error: {str(e)}")
            flash(f"Error analyzing games: {str(e)}", "error")
        finally:
            current_operation = None
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
# Updated API route handlers - replace these in chessy/server.py

@app.route("/api/game_data")
def get_game_data():
    """Return game data as JSON."""
    try:
        if os.path.exists(GAME_ANALYSIS_FILE):
            with open(GAME_ANALYSIS_FILE, "r") as f:
                return jsonify(json.load(f))
        else:
            # If analysis file doesn't exist, try to use parsed games file
            if os.path.exists(PARSED_GAMES_FILE):
                with open(PARSED_GAMES_FILE, "r") as f:
                    return jsonify(json.load(f))
            return jsonify([])  # Return empty list if no data available
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading game data: {str(e)}", "❌")
        return jsonify([]), 500

@app.route("/api/eco_data")
def get_eco_data():
    """Return ECO performance data as JSON."""
    try:
        if os.path.exists(ECO_CSV_FILE):
            with open(ECO_CSV_FILE, "r") as f:
                reader = csv.DictReader(f)
                return jsonify(list(reader))
        else:
            return jsonify([])  # Return empty list if no data available
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading ECO data: {str(e)}", "❌")
        return jsonify([]), 500

@app.route("/api/charts/win_rate")
def win_rate_chart():
    """Generate win rate chart data."""
    try:
        # First try to use the game analysis file
        if os.path.exists(GAME_ANALYSIS_FILE):
            with open(GAME_ANALYSIS_FILE, "r") as f:
                data = json.load(f)
        # If that fails, try the parsed games file
        elif os.path.exists(PARSED_GAMES_FILE):
            with open(PARSED_GAMES_FILE, "r") as f:
                data = json.load(f)
        else:
            # No data available
            return jsonify([])
            
        if not data:
            return jsonify([])
            
        df = pd.DataFrame(data)
        
        # Handle case where TimeControl column might not exist
        if 'TimeControl' not in df.columns:
            return jsonify([
                {
                    'timeControl': 'All Games',
                    'winRate': 0,
                    'games': len(df) if not df.empty else 0
                }
            ])
        
        # Prepare time control groups - handle potential errors in the time control format
        try:
            df['TimeControlGroup'] = df['TimeControl'].apply(lambda x: 
                "Bullet" if x and isinstance(x, str) and int(x.split('+')[0]) < 3 else
                "Blitz" if x and isinstance(x, str) and int(x.split('+')[0]) < 10 else
                "Rapid" if x and isinstance(x, str) and int(x.split('+')[0]) < 30 else
                "Classical"
            )
        except (ValueError, IndexError, AttributeError):
            # If there's any error in parsing time controls, create a simpler grouping
            df['TimeControlGroup'] = 'Unknown'
        
        # If PlayedAs is missing, use a default value
        if 'PlayedAs' not in df.columns:
            df['PlayedAs'] = 'Unknown'
            
        # Calculate win rates by time control, handle the case where we might not have all columns
        chart_data = []
        try:
            # Group by time control
            grouped = df.groupby('TimeControlGroup')
            
            for tc_group, group_df in grouped:
                games = len(group_df)
                wins = 0
                if 'Result' in df.columns:
                    wins = sum((group_df['PlayedAs'] == 'White') & (group_df['Result'] == '1-0') | 
                              (group_df['PlayedAs'] == 'Black') & (group_df['Result'] == '0-1'))
                
                win_rate = (wins / games * 100) if games > 0 else 0
                chart_data.append({
                    'timeControl': tc_group,
                    'winRate': round(win_rate, 1),
                    'games': games
                })
                
            # Sort by number of games
            chart_data = sorted(chart_data, key=lambda x: x['games'], reverse=True)
            
        except Exception as e:
            emoji_log(logger, logging.ERROR, f"Error calculating win rates: {str(e)}", "❌")
            # Return a simple placeholder
            return jsonify([
                {
                    'timeControl': 'All Games',
                    'winRate': 0,
                    'games': len(df) if not df.empty else 0
                }
            ])
            
        return jsonify(chart_data)
        
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error generating win rate chart: {str(e)}", "❌")
        return jsonify([]), 500
        

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
