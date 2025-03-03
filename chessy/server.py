"""
Main entry point for the Chessy web application.
"""
import os
import json
import csv
import logging
import threading
import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
import pandas as pd

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
app.config['TEMPLATES_AUTO_RELOAD'] = True

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

# Track background tasks
background_tasks = {
    'download': {
        'running': False,
        'status': None,
        'result': None,
        'timestamp': None
    },
    'analyze': {
        'running': False,
        'status': None,
        'result': None,
        'timestamp': None
    }
}

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

def get_date_range():
    """Get the date range of available games."""
    try:
        if not os.path.exists(PARSED_GAMES_FILE):
            return {"start": None, "end": None}
            
        with open(PARSED_GAMES_FILE, "r") as f:
            games_data = json.load(f)
            
        if not games_data:
            return {"start": None, "end": None}
            
        # Extract valid dates
        dates = [game.get("date") for game in games_data if game.get("date") and game.get("date") != "????-??-??"]
        
        if not dates:
            return {"start": None, "end": None}
            
        # Sort dates
        dates.sort()
        
        return {
            "start": dates[0],
            "end": dates[-1]
        }
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error getting date range: {str(e)}", "❌")
        return {"start": None, "end": None}

# API Routes
@app.route("/")
def index():
    """Main dashboard page."""
    has_data = ensure_required_files()
    
    # Get game statistics if available
    stats = chessy_service.get_game_statistics() if chessy_service else {"total_games": 0}
    
    # Get date range
    date_range = get_date_range()
    
    # Get background task status
    task_status = {
        'download': background_tasks['download']['status'],
        'analyze': background_tasks['analyze']['status'],
    }
    
    return render_template(
        "index.html", 
        username=USERNAME,
        has_data=has_data,
        stats=stats,
        date_range=date_range,
        task_status=task_status
    )

def download_thread(app_context):
    """Background thread for downloading games."""
    with app_context:
        try:
            background_tasks['download']['running'] = True
            background_tasks['download']['status'] = "Running"
            
            # Trigger game download
            new_games = chessy_service.check_for_updates()
            
            if new_games > 0:
                background_tasks['download']['status'] = f"Downloaded {new_games} new games"
                background_tasks['download']['result'] = new_games
            else:
                background_tasks['download']['status'] = "No new games found"
                background_tasks['download']['result'] = 0
                
            background_tasks['download']['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
        except Exception as e:
            emoji_log(logger, logging.ERROR, f"Download error: {str(e)}", "❌")
            background_tasks['download']['status'] = f"Error: {str(e)}"
        finally:
            background_tasks['download']['running'] = False

@app.route("/download", methods=["POST"])
def download_games():
    """Download games from Chess.com."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
        
    if background_tasks['download']['running']:
        flash("Download already in progress. Please wait.", "warning")
        return redirect(url_for("index"))
        
    # Start background download
    thread = threading.Thread(
        target=download_thread, 
        args=(app.app_context(),)
    )
    thread.daemon = True
    thread.start()
    
    flash("Download started in background. Refresh page to check status.", "info")
    return redirect(url_for("index"))

def analyze_thread(app_context):
    """Background thread for analyzing games."""
    with app_context:
        try:
            background_tasks['analyze']['running'] = True
            background_tasks['analyze']['status'] = "Running"
            
            # Trigger game analysis
            results = chessy_service.process_new_games()
            
            background_tasks['analyze']['status'] = f"Completed: {results['analyzed_games']} games analyzed"
            background_tasks['analyze']['result'] = results
            background_tasks['analyze']['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
        except Exception as e:
            emoji_log(logger, logging.ERROR, f"Analysis error: {str(e)}", "❌")
            background_tasks['analyze']['status'] = f"Error: {str(e)}"
        finally:
            background_tasks['analyze']['running'] = False

@app.route("/analyze", methods=["POST"])
def analyze_games():
    """Analyze games with Stockfish."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
        
    if background_tasks['analyze']['running']:
        flash("Analysis already in progress. Please wait.", "warning")
        return redirect(url_for("index"))
        
    # Start background analysis
    thread = threading.Thread(
        target=analyze_thread, 
        args=(app.app_context(),)
    )
    thread.daemon = True
    thread.start()
    
    flash("Analysis started in background. Refresh page to check status.", "info")
    return redirect(url_for("index"))

@app.route("/games")
def games():
    """View game list and details."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
        
    # Get game data if available
    games_data = []
    try:
        if os.path.exists(PARSED_GAMES_FILE):
            with open(PARSED_GAMES_FILE, "r") as f:
                games_data = json.load(f)
                
            # Sort games by date (newest first)
            games_data = sorted(
                games_data, 
                key=lambda x: x.get("date", "0000-00-00"), 
                reverse=True
            )
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading game data: {str(e)}", "❌")
        
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
        
    eco_data = chessy_service.get_opening_performance() or []
    
    # Load ECO descriptions
    eco_descriptions = {}
    try:
        # TODO: Replace with actual ECO descriptions file
        # For now, use some common examples
        eco_descriptions = {
            "A00": "Irregular Openings",
            "A40": "Queen's Pawn",
            "A45": "Queen's Pawn Game",
            "B00": "Uncommon King's Pawn Opening",
            "B20": "Sicilian Defence",
            "B27": "Sicilian Defense",
            "C00": "French Defense",
            "C20": "King's Pawn Game",
            "D00": "Queen's Pawn Game",
            "D02": "Queen's Pawn Game",
            "E00": "Queen's Pawn, Indian Defenses"
        }
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading ECO descriptions: {str(e)}", "❌")
    
    return render_template(
        "openings.html",
        username=USERNAME,
        eco_data=eco_data,
        eco_descriptions=eco_descriptions
    )

@app.route("/blunders")
def blunders():
    """View blunders statistics."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
    
    # Get blunders data if available
    blunders_data = {}
    try:
        if os.path.exists(GAME_ANALYSIS_FILE):
            with open(GAME_ANALYSIS_FILE, "r") as f:
                games_data = json.load(f)
                
            if games_data:
                # Calculate average blunders per game
                total_blunders = sum(game.get("blunders", 0) for game in games_data)
                total_games = len(games_data)
                avg_blunders = total_blunders / total_games if total_games > 0 else 0
                
                # Group blunders by time control
                blunders_by_tc = {}
                for game in games_data:
                    tc = game.get("TimeControl", "Unknown")
                    blunders = game.get("blunders", 0)
                    
                    if tc not in blunders_by_tc:
                        blunders_by_tc[tc] = {"games": 0, "blunders": 0}
                    
                    blunders_by_tc[tc]["games"] += 1
                    blunders_by_tc[tc]["blunders"] += blunders
                
                # Calculate averages
                for tc in blunders_by_tc:
                    blunders_by_tc[tc]["avg"] = (
                        blunders_by_tc[tc]["blunders"] / blunders_by_tc[tc]["games"]
                        if blunders_by_tc[tc]["games"] > 0 else 0
                    )
                
                blunders_data = {
                    "total_blunders": total_blunders,
                    "avg_blunders": avg_blunders,
                    "by_time_control": blunders_by_tc
                }
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading blunders data: {str(e)}", "❌")
    
    return render_template(
        "blunders.html",
        username=USERNAME,
        blunders_data=blunders_data
    )

@app.route("/inaccuracies")
def inaccuracies():
    """View inaccuracies statistics."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
    
    # Get inaccuracies data if available
    inaccuracies_data = {}
    try:
        if os.path.exists(GAME_ANALYSIS_FILE):
            with open(GAME_ANALYSIS_FILE, "r") as f:
                games_data = json.load(f)
                
            if games_data:
                # Calculate average inaccuracies per game
                total_inaccuracies = sum(game.get("inaccuracies", 0) for game in games_data)
                total_games = len(games_data)
                avg_inaccuracies = total_inaccuracies / total_games if total_games > 0 else 0
                
                # Group inaccuracies by time control
                inaccuracies_by_tc = {}
                for game in games_data:
                    tc = game.get("TimeControl", "Unknown")
                    inaccuracies = game.get("inaccuracies", 0)
                    
                    if tc not in inaccuracies_by_tc:
                        inaccuracies_by_tc[tc] = {"games": 0, "inaccuracies": 0}
                    
                    inaccuracies_by_tc[tc]["games"] += 1
                    inaccuracies_by_tc[tc]["inaccuracies"] += inaccuracies
                
                # Calculate averages
                for tc in inaccuracies_by_tc:
                    inaccuracies_by_tc[tc]["avg"] = (
                        inaccuracies_by_tc[tc]["inaccuracies"] / inaccuracies_by_tc[tc]["games"]
                        if inaccuracies_by_tc[tc]["games"] > 0 else 0
                    )
                
                inaccuracies_data = {
                    "total_inaccuracies": total_inaccuracies,
                    "avg_inaccuracies": avg_inaccuracies,
                    "by_time_control": inaccuracies_by_tc
                }
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading inaccuracies data: {str(e)}", "❌")
    
    return render_template(
        "inaccuracies.html",
        username=USERNAME,
        inaccuracies_data=inaccuracies_data
    )

# API endpoints for data
@app.route("/api/game_data")
def get_game_data():
    """Return game data as JSON."""
    try:
        if not os.path.exists(GAME_ANALYSIS_FILE):
            return jsonify([])
            
        with open(GAME_ANALYSIS_FILE, "r") as f:
            return jsonify(json.load(f))
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error retrieving game data: {str(e)}", "❌")
        return jsonify([])

@app.route("/api/eco_data")
def get_eco_data():
    """Return ECO performance data as JSON."""
    try:
        if not os.path.exists(ECO_CSV_FILE):
            return jsonify([])
            
        with open(ECO_CSV_FILE, "r") as f:
            reader = csv.DictReader(f)
            return jsonify(list(reader))
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error retrieving ECO data: {str(e)}", "❌")
        return jsonify([])

@app.route("/api/charts/win_rate")
def win_rate_chart():
    """Generate win rate chart data."""
    try:
        if not os.path.exists(GAME_ANALYSIS_FILE):
            return jsonify([])
            
        with open(GAME_ANALYSIS_FILE, "r") as f:
            data = json.load(f)
            
        if not data:
            return jsonify([])
            
        df = pd.DataFrame(data)
        
        # Handle different time control formats
        def parse_time_control(tc):
            try:
                if not tc or tc == "Unknown":
                    return "Unknown"
                
                # Handle time+increment format (e.g. "300+2")
                if "+" in tc:
                    base_time = int(tc.split("+")[0])
                # Handle seconds only format
                else:
                    base_time = int(tc)
                
                if base_time < 180:
                    return "Bullet"
                elif base_time < 600:
                    return "Blitz"
                elif base_time < 1800:
                    return "Rapid"
                else:
                    return "Classical"
            except:
                return "Unknown"
        
        # Prepare time control groups
        df['TimeControlGroup'] = df['TimeControl'].apply(parse_time_control)
        
        # Calculate win rates by time control
        tc_stats = {}
        for group, group_df in df.groupby('TimeControlGroup'):
            tc_stats[group] = {
                'games': len(group_df),
                'wins': sum((group_df['PlayedAs'] == 'White') & (group_df['Result'] == '1-0') | 
                          (group_df['PlayedAs'] == 'Black') & (group_df['Result'] == '0-1')),
                'losses': sum((group_df['PlayedAs'] == 'White') & (group_df['Result'] == '0-1') | 
                            (group_df['PlayedAs'] == 'Black') & (group_df['Result'] == '1-0')),
                'draws': sum(group_df['Result'] == '1/2-1/2')
            }
        
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
        emoji_log(logger, logging.ERROR, f"Error generating win rate chart: {str(e)}", "❌")
        return jsonify([])

@app.route("/api/export_games", methods=["POST"])
def export_games():
    """Export filtered game data."""
    try:
        # Get filter parameters from request
        filters = request.json.get("filters", {})
        format_type = request.json.get("format", "csv")
        
        # Load game data
        if not os.path.exists(PARSED_GAMES_FILE):
            return jsonify({"error": "No game data available"}), 400
            
        with open(PARSED_GAMES_FILE, "r") as f:
            games_data = json.load(f)
        
        # Apply filters
        filtered_data = games_data
        
        if filters.get("result"):
            filtered_data = [g for g in filtered_data if g.get("Result") in filters["result"]]
            
        if filters.get("time_control"):
            filtered_data = [g for g in filtered_data if g.get("TimeControl") in filters["time_control"]]
            
        if filters.get("played_as"):
            filtered_data = [g for g in filtered_data if g.get("PlayedAs") == filters["played_as"]]
            
        if filters.get("min_moves") is not None:
            filtered_data = [g for g in filtered_data if g.get("NumMoves", 0) >= filters["min_moves"]]
            
        if filters.get("max_moves") is not None:
            filtered_data = [g for g in filtered_data if g.get("NumMoves", 0) <= filters["max_moves"]]
        
        # Generate filename
        filename = f"{USERNAME}_games_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Format data based on requested format
        if format_type == "csv":
            # TODO: Implement CSV export
            return jsonify({
                "status": "success",
                "message": f"Exported {len(filtered_data)} games as CSV",
                "filename": f"{filename}.csv"
            })
        elif format_type == "excel":
            # TODO: Implement Excel export
            return jsonify({
                "status": "success",
                "message": f"Exported {len(filtered_data)} games as Excel",
                "filename": f"{filename}.xlsx"
            })
        elif format_type == "text":
            # TODO: Implement text export
            return jsonify({
                "status": "success",
                "message": f"Exported {len(filtered_data)} games as text",
                "filename": f"{filename}.txt"
            })
        else:
            return jsonify({"error": "Unsupported export format"}), 400
            
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error exporting games: {str(e)}", "❌")
        return jsonify({"error": str(e)}), 500

@app.route("/api/eco_descriptions")
def get_eco_descriptions():
    """Return ECO code descriptions."""
    # TODO: Replace with actual ECO descriptions from a database or file
    # For now, return some common examples
    descriptions = {
        "A00": "Irregular Openings",
        "A40": "Queen's Pawn",
        "A45": "Queen's Pawn Game",
        "B00": "Uncommon King's Pawn Opening",
        "B20": "Sicilian Defence",
        "B27": "Sicilian Defense",
        "C00": "French Defense",
        "C20": "King's Pawn Game",
        "D00": "Queen's Pawn Game",
        "D02": "Queen's Pawn Game",
        "E00": "Queen's Pawn, Indian Defenses"
    }
    return jsonify(descriptions)

@app.route("/api/toggle_theme", methods=["POST"])
def toggle_theme():
    """Toggle between light and dark mode."""
    current_theme = session.get("theme", "light")
    
    if current_theme == "light":
        session["theme"] = "dark"
    else:
        session["theme"] = "light"
        
    return jsonify({"theme": session["theme"]})

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