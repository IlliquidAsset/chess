"""
Main entry point for the Chessy web application.
"""
import os
import json
import csv
import logging
import threading
import datetime
import traceback
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

################################################################################
# I. APPLICATION INITIALIZATION
################################################################################
# Initialize app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # For flash messages
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Setup logging
logger = setup_logging(OUTPUT_DIR)

# Track background tasks
background_tasks = {
    'download': {
        'running': False,
        'status': None,
        'result': None,
        'timestamp': None,
        'messages': [],
        'start_time': None,
        'elapsed_seconds': 0,
        'total': 0,
        'current': 0,
        'percentage': 0
    },
    'analyze': {
        'running': False,
        'status': None,
        'result': None,
        'timestamp': None,
        'messages': [],
        'start_time': None,
        'elapsed_seconds': 0,
        'total': 0,
        'current': 0,
        'percentage': 0
    }
}

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

################################################################################
# II. UTILITY FUNCTIONS
################################################################################
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
        # Try to parse games from archive file if it exists
        if os.path.exists(ARCHIVE_FILE) and chessy_service:
            try:
                # Create an empty parsed games file
                with open(PARSED_GAMES_FILE, "w") as f:
                    f.write(json.dumps([]))
                    
                # Parse games
                emoji_log(logger, logging.INFO, f"Parsing games from existing archive: {ARCHIVE_FILE}", "📊")
                games_data = chessy_service.parser.parse_games(ARCHIVE_FILE)
                if games_data:
                    emoji_log(logger, logging.INFO, f"Successfully parsed {len(games_data)} games", "✅")
            except Exception as e:
                emoji_log(logger, logging.ERROR, f"Error parsing games: {str(e)}", "❌")
        
    # Check for game analysis
    if not os.path.exists(GAME_ANALYSIS_FILE):
        emoji_log(logger, logging.WARNING, "No game analysis found. Will run analysis on request.", "⚠️")
        # Create an empty analysis file so JSON reads don't fail
        try:
            with open(GAME_ANALYSIS_FILE, "w") as f:
                f.write(json.dumps([]))
        except Exception as e:
            emoji_log(logger, logging.ERROR, f"Error creating empty analysis file: {str(e)}", "❌")
        
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

################################################################################
# III. BACKGROUND TASKS
################################################################################
def download_thread(app_context):
    """Background thread for downloading games."""
    with app_context:
        try:
            background_tasks['download']['running'] = True
            background_tasks['download']['status'] = "Running"
            background_tasks['download']['messages'] = ["Starting download..."]
            background_tasks['download']['start_time'] = datetime.datetime.now()
            background_tasks['download']['total'] = 0
            background_tasks['download']['current'] = 0
            background_tasks['download']['percentage'] = 0
            
            # Trigger game download
            background_tasks['download']['messages'].append("Checking for new games...")
            new_games = chessy_service.check_for_updates()
            
            if new_games > 0:
                background_tasks['download']['messages'].append(f"Found {new_games} new games")
                background_tasks['download']['status'] = f"Downloaded {new_games} new games"
                background_tasks['download']['result'] = new_games
                
                # If games were downloaded, parse them immediately to avoid empty JSON errors
                background_tasks['download']['messages'].append("Parsing downloaded games...")
                if os.path.exists(ARCHIVE_FILE):
                    try:
                        games_data = chessy_service.parser.parse_games(ARCHIVE_FILE)
                        if games_data:
                            background_tasks['download']['messages'].append(f"Successfully parsed {len(games_data)} games")
                    except Exception as e:
                        background_tasks['download']['messages'].append(f"Error parsing games: {str(e)}")
            else:
                background_tasks['download']['messages'].append("No new games found")
                background_tasks['download']['status'] = "No new games found"
                background_tasks['download']['result'] = 0
                
            background_tasks['download']['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            end_time = datetime.datetime.now()
            background_tasks['download']['elapsed_seconds'] = (end_time - background_tasks['download']['start_time']).total_seconds()
                
        except Exception as e:
            error_msg = f"Download error: {str(e)}"
            emoji_log(logger, logging.ERROR, error_msg, "❌")
            background_tasks['download']['status'] = f"Error: {str(e)}"
            background_tasks['download']['messages'].append(error_msg)
            
            # Log detailed traceback
            traceback_text = traceback.format_exc()
            logger.error(f"Detailed error:\n{traceback_text}")
            
        finally:
            background_tasks['download']['running'] = False

def analyze_thread(app_context):
    """Background thread for analyzing games."""
    with app_context:
        try:
            background_tasks['analyze']['running'] = True
            background_tasks['analyze']['status'] = "Running"
            background_tasks['analyze']['messages'] = ["Starting analysis..."]
            background_tasks['analyze']['start_time'] = datetime.datetime.now()
            
            # Get the total number of games for progress tracking
            total_games = 0
            if os.path.exists(PARSED_GAMES_FILE):
                try:
                    with open(PARSED_GAMES_FILE, "r") as f:
                        parsed_games = json.load(f)
                        total_games = len(parsed_games)
                except Exception as e:
                    emoji_log(logger, logging.ERROR, f"Error loading parsed games: {str(e)}", "❌")
            
            background_tasks['analyze']['total'] = total_games
            background_tasks['analyze']['current'] = 0
            background_tasks['analyze']['percentage'] = 0
            background_tasks['analyze']['messages'].append(f"Processing {total_games} games...")
            
            # Set up a callback function to update progress
            def progress_callback(current, total):
                background_tasks['analyze']['current'] = current
                background_tasks['analyze']['percentage'] = (current / total * 100) if total > 0 else 0
            
            # Add progress callback to analyzer
            if hasattr(chessy_service.analyzer, 'set_progress_callback'):
                chessy_service.analyzer.set_progress_callback(progress_callback)
            
            # Trigger game analysis
            results = chessy_service.process_new_games()
            
            background_tasks['analyze']['messages'].append(f"Completed: {results['analyzed_games']} games analyzed")
            background_tasks['analyze']['status'] = f"Completed: {results['analyzed_games']} games analyzed"
            background_tasks['analyze']['result'] = results
            background_tasks['analyze']['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            end_time = datetime.datetime.now()
            background_tasks['analyze']['elapsed_seconds'] = (end_time - background_tasks['analyze']['start_time']).total_seconds()
            background_tasks['analyze']['current'] = total_games  # Ensure we show 100% at the end
            background_tasks['analyze']['percentage'] = 100
                
        except Exception as e:
            error_msg = f"Analysis error: {str(e)}"
            emoji_log(logger, logging.ERROR, error_msg, "❌")
            background_tasks['analyze']['status'] = f"Error: {str(e)}"
            background_tasks['analyze']['messages'].append(error_msg)
            
            # Log detailed traceback
            traceback_text = traceback.format_exc()
            logger.error(f"Detailed error:\n{traceback_text}")
            
        finally:
            background_tasks['analyze']['running'] = False

################################################################################
# IV. ROUTE HANDLERS
################################################################################
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
    
    # For AJAX requests, return JSON
    if request.is_json:
        return jsonify({
            "status": "success",
            "message": "Download started"
        })
    
    # For form submissions, redirect with flash message
    flash("Download started in background. Refresh page to check status.", "info")
    return redirect(url_for("index"))

@app.route("/download", methods=["POST"])
def download_games():
    """Download games from Chess.com."""
    if not chessy_service:
        if request.is_json:
            return jsonify({
                "status": "error",
                "message": "Service not available. Check configuration and try again."
            })
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
        
    if background_tasks['download']['running']:
        if request.is_json:
            return jsonify({
                "status": "warning",
                "message": "Download already in progress. Please wait."
            })
        flash("Download already in progress. Please wait.", "warning")
        return redirect(url_for("index"))
        
    # Start background download
    thread = threading.Thread(
        target=download_thread, 
        args=(app.app_context(),)
    )
    thread.daemon = True
    thread.start()
    
    # For AJAX requests, return JSON
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "status": "success",
            "message": "Download started in background",
            "taskId": "download"
        })
    
    # For form submissions, redirect with flash message
    flash("Download started in background. Refresh page to check status.", "info")
    return redirect(url_for("index"))

@app.route("/analyze", methods=["POST"])
def analyze_games():
    """Analyze games with Stockfish."""
    if not chessy_service:
        if request.is_json:
            return jsonify({
                "status": "error",
                "message": "Service not available. Check configuration and try again."
            })
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
        
    if background_tasks['analyze']['running']:
        if request.is_json:
            return jsonify({
                "status": "warning",
                "message": "Analysis already in progress. Please wait."
            })
        flash("Analysis already in progress. Please wait.", "warning")
        return redirect(url_for("index"))
    
    # Verify we have games data to analyze
    if not os.path.exists(PARSED_GAMES_FILE) or os.path.getsize(PARSED_GAMES_FILE) <= 5:  # Just contains [] or empty
        if request.is_json:
            return jsonify({
                "status": "error",
                "message": "No game data available. Please download games first."
            })
        flash("No game data available. Please download games first.", "error")
        return redirect(url_for("index"))
        
    # Start background analysis
    thread = threading.Thread(
        target=analyze_thread, 
        args=(app.app_context(),)
    )
    thread.daemon = True
    thread.start()
    
    # For AJAX requests, return JSON
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            "status": "success",
            "message": "Analysis started in background",
            "taskId": "analyze"
        })
    
    # For form submissions, redirect with flash message
    flash("Analysis started in background. Refresh page to check status.", "info")
    return redirect(url_for("index"))

@app.route("/errors/download")
def download_error():
    """Display download error page."""
    return render_template("errors/download.html", username=USERNAME)


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
    
    # For AJAX requests, return JSON
    if request.is_json:
        return jsonify({
            "status": "success",
            "message": "Analysis started"
        })
    
    # For form submissions, redirect with flash message
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
        # Try to load from ECO codes module
        try:
            from chessy.utils.ECO_codes_library import get_eco_descriptions
            eco_descriptions = get_eco_descriptions()
        except ImportError:
            # Fall back to common examples
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
    inaccuracy_data = {}
    total_inaccuracies = 0
    avg_inaccuracies = 0
    common_phase = "Opening"
    inaccuracy_games = []
    
    try:
        if os.path.exists(GAME_ANALYSIS_FILE):
            with open(GAME_ANALYSIS_FILE, "r") as f:
                games_data = json.load(f)
                
            if games_data:
                # Calculate totals
                total_inaccuracies = sum(game.get("inaccuracies", 0) for game in games_data)
                total_games = len(games_data)
                avg_inaccuracies = round(total_inaccuracies / total_games, 2) if total_games > 0 else 0
                
                # Add inaccuracy count to game data for display
                for game in games_data:
                    inaccuracies = game.get("inaccuracies", 0)
                    if inaccuracies > 0:
                        game_copy = game.copy()
                        game_copy["inaccuracies"] = inaccuracies
                        inaccuracy_games.append(game_copy)
                
                # Sort games by number of inaccuracies (most first)
                inaccuracy_games = sorted(
                    inaccuracy_games,
                    key=lambda x: x.get("inaccuracies", 0),
                    reverse=True
                )[:20]  # Show only top 20
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading inaccuracies data: {str(e)}", "❌")
    
    return render_template(
        "inaccuracies.html",
        username=USERNAME,
        total_inaccuracies=total_inaccuracies,
        avg_inaccuracies=avg_inaccuracies,
        common_phase=common_phase,
        inaccuracy_games=inaccuracy_games
    )

@app.route("/errors/analysis")
def analysis_error():
    """Display analysis error page."""
    return render_template("errors/analysis.html", username=USERNAME)

@app.route("/errors/not_found")
def not_found_error():
    """Display 404 page."""
    return render_template("errors/not_found.html", username=USERNAME)

################################################################################
# V. API ENDPOINTS
################################################################################
@app.route("/api/progress")
def get_progress():
    """Get current progress of background tasks."""
    # Update elapsed time
    if background_tasks['download']['running'] and background_tasks['download']['start_time']:
        elapsed = datetime.datetime.now() - background_tasks['download']['start_time']
        background_tasks['download']['elapsed_seconds'] = int(elapsed.total_seconds())
        
    if background_tasks['analyze']['running'] and background_tasks['analyze']['start_time']:
        elapsed = datetime.datetime.now() - background_tasks['analyze']['start_time']
        background_tasks['analyze']['elapsed_seconds'] = int(elapsed.total_seconds())
    
    # Determine which task is active
    active_task = None
    if background_tasks['download']['running']:
        active_task = 'download'
    elif background_tasks['analyze']['running']:
        active_task = 'analyze'
    
    if active_task:
        task_data = background_tasks[active_task]
        return jsonify({
            "active": True,
            "task": active_task,
            "status": task_data['status'],
            "messages": task_data['messages'],
            "elapsed_seconds": task_data['elapsed_seconds'],
            "total": task_data['total'],
            "current": task_data['current'],
            "percentage": task_data['percentage']
        })
    else:
        return jsonify({
            "active": False
        })

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

@app.route("/api/eco_description/<eco_code>")
def get_eco_description(eco_code):
    """Get description for a specific ECO code."""
    try:
        # Try to use the ECO codes library if available
        try:
            from chessy.utils.ECO_codes_library import get_eco_description
            description = get_eco_description(eco_code)
            return jsonify({"description": description})
        except ImportError:
            # Fallback to basic descriptions
            descriptions = {
                "A00": "Irregular Openings",
                "B20": "Sicilian Defence",
                "C00": "French Defense",
                "D00": "Queen's Pawn Game",
                # Add more as needed
            }
            return jsonify({"description": descriptions.get(eco_code, "Unknown opening")})
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error retrieving ECO description: {str(e)}", "❌")
        return jsonify({"description": "Error retrieving description"})

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
            """Parse time control into standardized categories."""
            try:
                if not tc:
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
            except Exception:
                # If we couldn't parse it, use the original value
                return tc if tc else "Unknown"
        
        # Prepare time control groups
        if 'TimeControl' in df.columns:
            df['TimeControlGroup'] = df['TimeControl'].apply(parse_time_control)
            
            # Calculate win rates by time control
            tc_stats = {}
            for group, group_df in df.groupby('TimeControlGroup'):
                if group == "Unknown" and len(group_df) < 5:  # Skip Unknown if it's just a few games
                    continue
                    
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
                
            # Sort by number of games (descending)
            chart_data = sorted(chart_data, key=lambda x: x['games'], reverse=True)
                
            return jsonify(chart_data)
        else:
            return jsonify([])
            
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error generating win rate chart: {str(e)}", "❌")
        return jsonify([])

@app.route("/mistakes")
def mistakes():
    """View comprehensive mistakes statistics."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
    
    # Get game analysis data if available
    analysis_data = {}
    top_mistake_games = []
    
    try:
        if os.path.exists(GAME_ANALYSIS_FILE):
            with open(GAME_ANALYSIS_FILE, "r") as f:
                games_data = json.load(f)
                
            if games_data:
                # Calculate total mistakes
                total_blunders = sum(game.get("blunders", 0) for game in games_data)
                total_inaccuracies = sum(game.get("inaccuracies", 0) for game in games_data)
                total_mistakes = total_blunders + total_inaccuracies
                total_games = len(games_data)
                
                # Calculate game phase statistics (approximation)
                opening_mistakes = 0
                middlegame_mistakes = 0
                endgame_mistakes = 0
                
                for game in games_data:
                    # Simple approximation - distribute mistakes by phase
                    # In a real implementation, this would use actual phase data from the analysis
                    moves = game.get("move_count", 0)
                    blunders = game.get("blunders", 0)
                    inaccuracies = game.get("inaccuracies", 0)
                    total = blunders + inaccuracies
                    
                    if moves <= 0:
                        continue
                        
                    # Estimate phase distribution
                    if moves <= 10:
                        # Mostly opening
                        opening_mistakes += total
                    elif moves <= 30:
                        # Split between opening and middlegame
                        opening_mistakes += total * 0.3
                        middlegame_mistakes += total * 0.7
                    else:
                        # Distribute across all phases
                        opening_mistakes += total * 0.2
                        middlegame_mistakes += total * 0.5
                        endgame_mistakes += total * 0.3
                
                # Calculate mistakes by time control
                tc_stats = {}
                for game in games_data:
                    tc = game.get("TimeControl", "Unknown")
                    
                    # Parse time control into standard categories
                    try:
                        if "+" in tc:
                            base_time = int(tc.split("+")[0])
                        else:
                            base_time = int(tc)
                            
                        if base_time < 180:
                            tc_category = "Bullet"
                        elif base_time < 600:
                            tc_category = "Blitz"
                        elif base_time < 1800:
                            tc_category = "Rapid"
                        else:
                            tc_category = "Classical"
                    except:
                        tc_category = tc if tc else "Unknown"
                    
                    mistakes = game.get("blunders", 0) + game.get("inaccuracies", 0)
                    
                    if tc_category not in tc_stats:
                        tc_stats[tc_category] = 0
                    tc_stats[tc_category] += mistakes
                
                # Sort games by total mistakes and get top 10
                for game in games_data:
                    game["total_mistakes"] = game.get("blunders", 0) + game.get("inaccuracies", 0)
                
                top_mistake_games = sorted(
                    games_data,
                    key=lambda x: x.get("total_mistakes", 0),
                    reverse=True
                )[:10]
                
                # Create trend data by month
                month_data = {}
                for game in games_data:
                    date_str = game.get("date", "")
                    if date_str and date_str != "????-??-??":
                        month = date_str[:7]  # YYYY-MM format
                        mistakes = game.get("blunders", 0) + game.get("inaccuracies", 0)
                        
                        if month not in month_data:
                            month_data[month] = {"games": 0, "mistakes": 0}
                        
                        month_data[month]["games"] += 1
                        month_data[month]["mistakes"] += mistakes
                
                # Calculate averages for trend data
                trend_data = []
                for month, data in sorted(month_data.items()):
                    if data["games"] > 0:
                        avg = data["mistakes"] / data["games"]
                        trend_data.append((month, round(avg, 2)))
                
                analysis_data = {
                    "blunders": total_blunders,
                    "inaccuracies": total_inaccuracies,
                    "total_mistakes": total_mistakes,
                    "phase_stats": {
                        "opening": int(opening_mistakes),
                        "middlegame": int(middlegame_mistakes),
                        "endgame": int(endgame_mistakes)
                    },
                    "time_control_stats": tc_stats,
                    "trend_data": trend_data
                }
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading mistakes data: {str(e)}", "❌")
    
    return render_template(
        "mistakes_overview.html",
        username=USERNAME,
        analysis_data=analysis_data,
        top_mistake_games=top_mistake_games
    )

@app.route("/api/inaccuracies_data")
def get_inaccuracies_data():
    """Return inaccuracies data for charts."""
    try:
        if not os.path.exists(GAME_ANALYSIS_FILE):
            return jsonify({"error": "No analysis data available"})
            
        with open(GAME_ANALYSIS_FILE, "r") as f:
            games_data = json.load(f)
            
        if not games_data:
            return jsonify({"error": "No games found"})
            
        # Group by ECO code
        inaccuracies_by_opening = {}
        for game in games_data:
            eco = game.get("ECO", "Unknown")
            if not eco:
                eco = "Unknown"
                
            inaccuracies = game.get("inaccuracies", 0)
            
            if eco not in inaccuracies_by_opening:
                inaccuracies_by_opening[eco] = {"count": 0, "games": 0}
                
            inaccuracies_by_opening[eco]["count"] += inaccuracies
            inaccuracies_by_opening[eco]["games"] += 1
            
        # Format for chart
        opening_data = [{"opening": eco, "count": data["count"]} 
                        for eco, data in inaccuracies_by_opening.items() 
                        if data["count"] > 0]
                        
        # Sort by count and take top 10
        opening_data = sorted(opening_data, key=lambda x: x["count"], reverse=True)[:10]
        
        # Create dummy phase data (this would come from actual analysis in a real implementation)
        phase_data = {
            "Opening": 45,
            "Middlegame": 35,
            "Endgame": 20
        }
        
        # Create dummy monthly data
        monthly_data = [
            {"month": "Jan", "average": 3.2},
            {"month": "Feb", "average": 2.9},
            {"month": "Mar", "average": 2.5},
            {"month": "Apr", "average": 2.7},
            {"month": "May", "average": 2.3}
        ]
        
        return jsonify({
            "inaccuracies_by_opening": opening_data,
            "inaccuracies_by_phase": phase_data,
            "avg_inaccuracies_by_month": monthly_data
        })
        
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error generating inaccuracies data: {str(e)}", "❌")
        return jsonify({"error": str(e)})

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

        if not filtered_data:
            return jsonify({"warning": "No games match the selected filters"}), 200
        
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

@app.route("/api/toggle_theme", methods=["POST"])
def toggle_theme():
    """Toggle between light and dark mode."""
    current_theme = session.get("theme", "light")
    
    if current_theme == "light":
        session["theme"] = "dark"
    else:
        session["theme"] = "light"
        
    return jsonify({"theme": session["theme"]})

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template("errors/not_found.html", username=USERNAME), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    logger.error(f"Server error: {str(e)}")
    return render_template("errors/server_error.html", username=USERNAME), 500

@app.route("/api/eco/all")
def get_all_eco_codes():
    """Return all ECO codes and descriptions as JSON, using python-chess."""
    try:
        import chess.pgn
        
        # python-chess includes a comprehensive ECO database
        eco_data = {}
        
        # Iterate through the ECO database
        for eco in chess.pgn.ECO_CODES:
            eco_data[eco] = chess.pgn.ECO_NAMES[eco]
            
        return jsonify(eco_data)
    except ImportError:
        # Fallback to basic descriptions if python-chess is not available
        eco_data = {
            "A00": "Irregular Openings",
            "B20": "Sicilian Defence",
            "C00": "French Defense",
            "D00": "Queen's Pawn Game",
            "E00": "Queen's Pawn, Indian Defenses"
        }
        emoji_log(logger, logging.WARNING, 
                 "python-chess not available. Using fallback ECO data.", "⚠️")
        return jsonify(eco_data)
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error retrieving ECO descriptions: {str(e)}", "❌")
        return jsonify({"error": str(e)}), 500

@app.route("/api/notifications")
def get_notifications():
    """Endpoint for retrieving pending notifications."""
    notifications = get_pending_notifications()
    return jsonify(notifications)

@app.route("/api/task_history/<task_type>")
def task_history(task_type):
    """Get history of a specific task type."""
    if task_type not in ['download', 'analyze']:
        return jsonify({"error": "Invalid task type"}), 400
        
    history_file = os.path.join(OUTPUT_DIR, f"{task_type}_history.json")
    if not os.path.exists(history_file):
        return jsonify([])
        
    try:
        with open(history_file, "r") as f:
            history = json.load(f)
        return jsonify(history)
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading task history: {str(e)}", "❌")
        return jsonify({"error": str(e)}), 500

@app.route("/api/cancel_task/<task_type>", methods=["POST"])
def cancel_task(task_type):
    """Cancel a running background task (preparation for interruptible analysis)."""
    if task_type not in ['download', 'analyze']:
        return jsonify({"error": "Invalid task type"}), 400
        
    if not background_tasks[task_type]['running']:
        return jsonify({"error": "Task is not running"}), 400
        
    # Mark task for cancellation
    # Note: Full implementation requires making the tasks check for cancellation
    background_tasks[task_type]['cancel_requested'] = True
    
    return jsonify({
        "status": "success",
        "message": f"Cancellation requested for {task_type} task"
    })

@app.route("/api/task_status")
def get_all_task_status():
    """Get status of all background tasks."""
    status = {}
    
    for task_type in ['download', 'analyze']:
        task_data = background_tasks[task_type]
        status[task_type] = {
            'running': task_data.get('running', False),
            'status': task_data.get('status', None),
            'percentage': task_data.get('percentage', 0),
            'current': task_data.get('current', 0),
            'total': task_data.get('total', 0),
            'elapsed_seconds': task_data.get('elapsed_seconds', 0),
            'last_message': task_data.get('messages', [])[-1] if task_data.get('messages') else None
        }
    
    return jsonify(status)

################################################################################
# III. BACKGROUND TASKS
################################################################################
def download_thread(app_context):
    """Background thread for downloading games."""
    with app_context:
        try:
            background_tasks['download']['running'] = True
            background_tasks['download']['status'] = "Running"
            background_tasks['download']['messages'] = ["Starting download..."]
            background_tasks['download']['start_time'] = datetime.datetime.now()
            background_tasks['download']['total'] = 0
            background_tasks['download']['current'] = 0
            background_tasks['download']['percentage'] = 0
            
            # Trigger game download
            background_tasks['download']['messages'].append("Checking for new games...")
            new_games = chessy_service.check_for_updates()
            
            if new_games > 0:
                background_tasks['download']['messages'].append(f"Found {new_games} new games")
                background_tasks['download']['status'] = f"Downloaded {new_games} new games"
                background_tasks['download']['result'] = new_games
                
                # If games were downloaded, parse them immediately to avoid empty JSON errors
                background_tasks['download']['messages'].append("Parsing downloaded games...")
                if os.path.exists(ARCHIVE_FILE):
                    try:
                        games_data = chessy_service.parser.parse_games(ARCHIVE_FILE)
                        if games_data:
                            background_tasks['download']['messages'].append(f"Successfully parsed {len(games_data)} games")
                    except Exception as e:
                        background_tasks['download']['messages'].append(f"Error parsing games: {str(e)}")
            else:
                background_tasks['download']['messages'].append("No new games found")
                background_tasks['download']['status'] = "No new games found"
                background_tasks['download']['result'] = 0
                
            background_tasks['download']['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            end_time = datetime.datetime.now()
            background_tasks['download']['elapsed_seconds'] = (end_time - background_tasks['download']['start_time']).total_seconds()
            
            # New: Push notification to user
            background_tasks['download']['notification'] = {
                'type': 'success',
                'title': 'Download Complete',
                'message': f"Successfully downloaded {new_games} new games"
            }
                
        except Exception as e:
            error_msg = f"Download error: {str(e)}"
            emoji_log(logger, logging.ERROR, error_msg, "❌")
            background_tasks['download']['status'] = f"Error: {str(e)}"
            background_tasks['download']['messages'].append(error_msg)
            
            # New: Push error notification
            background_tasks['download']['notification'] = {
                'type': 'error',
                'title': 'Download Error',
                'message': str(e)
            }
            
            # Log detailed traceback
            traceback_text = traceback.format_exc()
            logger.error(f"Detailed error:\n{traceback_text}")
            
        finally:
            background_tasks['download']['running'] = False
            # New: Save task history
            save_task_history('download', background_tasks['download'])

def analyze_thread(app_context):
    """Background thread for analyzing games."""
    with app_context:
        try:
            background_tasks['analyze']['running'] = True
            background_tasks['analyze']['status'] = "Running"
            background_tasks['analyze']['messages'] = ["Starting analysis..."]
            background_tasks['analyze']['start_time'] = datetime.datetime.now()
            
            # Get the total number of games for progress tracking
            total_games = 0
            if os.path.exists(PARSED_GAMES_FILE):
                try:
                    with open(PARSED_GAMES_FILE, "r") as f:
                        parsed_games = json.load(f)
                        total_games = len(parsed_games)
                except Exception as e:
                    emoji_log(logger, logging.ERROR, f"Error loading parsed games: {str(e)}", "❌")
            
            background_tasks['analyze']['total'] = total_games
            background_tasks['analyze']['current'] = 0
            background_tasks['analyze']['percentage'] = 0
            background_tasks['analyze']['messages'].append(f"Processing {total_games} games...")
            
            # Set up a callback function to update progress
            def progress_callback(current, total):
                background_tasks['analyze']['current'] = current
                background_tasks['analyze']['percentage'] = (current / total * 100) if total > 0 else 0
                
                # New: Add incremental milestone messages
                milestone_percentage = 25
                current_percentage = int(background_tasks['analyze']['percentage'])
                
                if current_percentage > 0 and current_percentage % milestone_percentage == 0:
                    # Check if we've already recorded this milestone
                    milestone_message = f"Completed {current_percentage}% ({current}/{total} games)"
                    if not any(milestone_message in msg for msg in background_tasks['analyze']['messages']):
                        background_tasks['analyze']['messages'].append(milestone_message)
                        
                        # New: Update estimated time remaining (if we have enough data)
                        if current > 10:  # Wait until we have processed enough games for a good estimate
                            elapsed = (datetime.datetime.now() - background_tasks['analyze']['start_time']).total_seconds()
                            games_per_second = current / elapsed if elapsed > 0 else 0
                            if games_per_second > 0:
                                remaining_games = total - current
                                est_remaining_seconds = remaining_games / games_per_second
                                
                                # Format time remaining
                                if est_remaining_seconds > 60:
                                    est_minutes = int(est_remaining_seconds // 60)
                                    est_seconds = int(est_remaining_seconds % 60)
                                    background_tasks['analyze']['messages'].append(
                                        f"Estimated time remaining: {est_minutes}m {est_seconds}s"
                                    )
            
            # Add progress callback to analyzer
            if hasattr(chessy_service.analyzer, 'set_progress_callback'):
                chessy_service.analyzer.set_progress_callback(progress_callback)
            
            # Trigger game analysis
            results = chessy_service.process_new_games()
            
            background_tasks['analyze']['messages'].append(f"Completed: {results['analyzed_games']} games analyzed")
            background_tasks['analyze']['status'] = f"Completed: {results['analyzed_games']} games analyzed"
            background_tasks['analyze']['result'] = results
            background_tasks['analyze']['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            end_time = datetime.datetime.now()
            background_tasks['analyze']['elapsed_seconds'] = (end_time - background_tasks['analyze']['start_time']).total_seconds()
            background_tasks['analyze']['current'] = total_games  # Ensure we show 100% at the end
            background_tasks['analyze']['percentage'] = 100
            
            # New: Push notification to user
            background_tasks['analyze']['notification'] = {
                'type': 'success',
                'title': 'Analysis Complete',
                'message': f"Successfully analyzed {results['analyzed_games']} games"
            }
                
        except Exception as e:
            error_msg = f"Analysis error: {str(e)}"
            emoji_log(logger, logging.ERROR, error_msg, "❌")
            background_tasks['analyze']['status'] = f"Error: {str(e)}"
            background_tasks['analyze']['messages'].append(error_msg)
            
            # New: Push error notification
            background_tasks['analyze']['notification'] = {
                'type': 'error',
                'title': 'Analysis Error',
                'message': str(e)
            }
            
            # Log detailed traceback
            traceback_text = traceback.format_exc()
            logger.error(f"Detailed error:\n{traceback_text}")
            
        finally:
            background_tasks['analyze']['running'] = False
            # New: Save task history
            save_task_history('analyze', background_tasks['analyze'])

# New: Task history management
def save_task_history(task_type, task_data):
    """Save task history to a file for resumption and tracking."""
    try:
        history_file = os.path.join(OUTPUT_DIR, f"{task_type}_history.json")
        
        # Load existing history if available
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    history = json.load(f)
            except Exception as e:
                logger.error(f"Error reading task history: {str(e)}")
        
        # Create history entry (excluding large data fields)
        history_entry = {
            'timestamp': task_data.get('timestamp', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            'status': task_data.get('status', 'Unknown'),
            'elapsed_seconds': task_data.get('elapsed_seconds', 0),
            'result': task_data.get('result', None),
            'success': task_data.get('status', '').startswith('Completed')
        }
        
        # Add to history (limit to last 10 entries)
        history.append(history_entry)
        if len(history) > 10:
            history = history[-10:]
        
        # Save updated history
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
            
    except Exception as e:
        logger.error(f"Error saving task history: {str(e)}")

# New: Notification system for background tasks
def get_pending_notifications():
    """Check for notifications from background tasks."""
    notifications = []
    
    for task_type in ['download', 'analyze']:
        task_data = background_tasks[task_type]
        if 'notification' in task_data and task_data['notification']:
            notifications.append(task_data['notification'])
            # Clear notification after retrieving it
            task_data['notification'] = None
    
    return notifications
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

        if not filtered_data:
            return jsonify({"warning": "No games match the selected filters"}), 200
        
        # Generate filename
        filename = f"{USERNAME}_games_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create output directory if it doesn't exist
        export_dir = os.path.join(OUTPUT_DIR, "exports")
        os.makedirs(export_dir, exist_ok=True)
        
        # Format data based on requested format
        if format_type == "csv":
            export_path = os.path.join(export_dir, f"{filename}.csv")
            
            # Create CSV with pandas for proper handling of all data types
            df = pd.DataFrame(filtered_data)
            df.to_csv(export_path, index=False)
            
            return jsonify({
                "status": "success",
                "message": f"Exported {len(filtered_data)} games as CSV",
                "filename": f"{filename}.csv",
                "download_url": f"/download/export/{filename}.csv"
            })
            
        elif format_type == "excel":
            export_path = os.path.join(export_dir, f"{filename}.xlsx")
            
            # Create Excel file with pandas
            df = pd.DataFrame(filtered_data)
            
            # Use openpyxl engine for better formatting
            with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="Games", index=False)
                
                # Auto-fit column widths
                workbook = writer.book
                worksheet = writer.sheets["Games"]
                for i, col in enumerate(df.columns):
                    max_width = max(df[col].astype(str).apply(len).max(), len(col)) + 2
                    worksheet.column_dimensions[chr(65 + i)].width = min(max_width, 30)  # Cap at 30 for readability
            
            return jsonify({
                "status": "success",
                "message": f"Exported {len(filtered_data)} games as Excel",
                "filename": f"{filename}.xlsx",
                "download_url": f"/download/export/{filename}.xlsx"
            })
            
        elif format_type == "text":
            export_path = os.path.join(export_dir, f"{filename}.txt")
            
            # Create a nicely formatted text file
            with open(export_path, "w") as f:
                f.write(f"Chess.com Game Export for {USERNAME}\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Games: {len(filtered_data)}\n")
                f.write("=" * 80 + "\n\n")
                
                for i, game in enumerate(filtered_data, 1):
                    f.write(f"Game #{i}\n")
                    f.write(f"Date: {game.get('date', 'Unknown')}\n")
                    f.write(f"White: {game.get('white', 'Unknown')}\n")
                    f.write(f"Black: {game.get('black', 'Unknown')}\n")
                    f.write(f"Result: {game.get('Result', 'Unknown')}\n")
                    f.write(f"Opening: {game.get('opening', 'Unknown')} (ECO: {game.get('ECO', 'Unknown')})\n")
                    f.write(f"Time Control: {game.get('TimeControl', 'Unknown')}\n")
                    f.write(f"Moves: {game.get('NumMoves', 'Unknown')}\n")
                    
                    # Add analysis data if available
                    if 'blunders' in game or 'inaccuracies' in game:
                        f.write(f"Analysis:\n")
                        f.write(f"  Blunders: {game.get('blunders', 0)}\n")
                        f.write(f"  Inaccuracies: {game.get('inaccuracies', 0)}\n")
                    
                    f.write("\n" + "-" * 40 + "\n\n")
            
            return jsonify({
                "status": "success",
                "message": f"Exported {len(filtered_data)} games as text",
                "filename": f"{filename}.txt",
                "download_url": f"/download/export/{filename}.txt"
            })
            
        else:
            return jsonify({"error": "Unsupported export format"}), 400
            
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error exporting games: {str(e)}", "❌")
        return jsonify({"error": str(e)}), 500

@app.route("/download/export/<filename>")
def download_export_file(filename):
    """Serve an exported file for download."""
    try:
        export_dir = os.path.join(OUTPUT_DIR, "exports")
        return send_from_directory(
            export_dir, 
            filename, 
            as_attachment=True,
            attachment_filename=filename
        )
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error serving export file: {str(e)}", "❌")
        flash("Error downloading file.", "error")
        return redirect(url_for("games"))
    


@app.route("/api/config")
def get_config():
    """Return a subset of configuration info."""
    # Only return non-sensitive configuration
    config_data = {
        "version": "0.2.0",
        "username": USERNAME,
        "stockfish_available": bool(STOCKFISH_PATH and os.path.exists(STOCKFISH_PATH)),
        "output_dir": OUTPUT_DIR,
        "has_data": os.path.exists(ARCHIVE_FILE) and os.path.getsize(ARCHIVE_FILE) > 0,
        "games_count": 0,
        "last_download": None,
        "last_analysis": None
    }
    
    # Add game count if available
    if os.path.exists(PARSED_GAMES_FILE):
        try:
            with open(PARSED_GAMES_FILE, "r") as f:
                games_data = json.load(f)
                config_data["games_count"] = len(games_data)
        except Exception:
            pass
    
    # Add last download time if available
    if os.path.exists(LAST_DOWNLOADED_FILE):
        try:
            with open(LAST_DOWNLOADED_FILE, "r") as f:
                config_data["last_download"] = f.read().strip()
        except Exception:
            pass
    
    # Add last analysis time
    if os.path.exists(GAME_ANALYSIS_FILE):
        try:
            config_data["last_analysis"] = datetime.fromtimestamp(
                os.path.getmtime(GAME_ANALYSIS_FILE)
            ).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    
    return jsonify(config_data)

@app.route("/api/logs")
@admin_required
def get_logs():
    """Return recent log entries for troubleshooting."""
    try:
        log_files = []
        
        # Find all log files
        if os.path.exists(OUTPUT_DIR):
            for filename in os.listdir(OUTPUT_DIR):
                if filename.endswith(".log"):
                    log_path = os.path.join(OUTPUT_DIR, filename)
                    log_files.append({
                        "name": filename,
                        "path": log_path,
                        "size": os.path.getsize(log_path),
                        "modified": datetime.fromtimestamp(os.path.getmtime(log_path)).strftime("%Y-%m-%d %H:%M:%S")
                    })
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda x: x["modified"], reverse=True)
        
        # Get content of most recent log file
        recent_logs = []
        if log_files:
            most_recent = log_files[0]["path"]
            with open(most_recent, "r") as f:
                recent_logs = f.readlines()[-100:]  # Last 100 lines
        
        return jsonify({
            "log_files": log_files,
            "recent_logs": recent_logs
        })
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error retrieving logs: {str(e)}", "❌")
        return jsonify({"error": str(e)}), 500

@app.route("/api/logs/<filename>")
@admin_required
def get_log_file(filename):
    """Return a specific log file."""
    try:
        log_path = os.path.join(OUTPUT_DIR, filename)
        
        # Security check to prevent path traversal
        if not os.path.normpath(log_path).startswith(os.path.normpath(OUTPUT_DIR)):
            return jsonify({"error": "Invalid log file path"}), 403
            
        if not os.path.exists(log_path):
            return jsonify({"error": "Log file not found"}), 404
            
        with open(log_path, "r") as f:
            content = f.readlines()
            
        return jsonify({
            "filename": filename,
            "content": content
        })
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error retrieving log file: {str(e)}", "❌")
        return jsonify({"error": str(e)}), 500

@app.route("/api/analytics/mistake_trends")
def get_mistake_trends():
    """Get mistake trends over time."""
    try:
        if not os.path.exists(GAME_ANALYSIS_FILE):
            return jsonify({"error": "No analysis data available"}), 404
            
        with open(GAME_ANALYSIS_FILE, "r") as f:
            games_data = json.load(f)
            
        if not games_data:
            return jsonify({"error": "No games found"}), 404
            
        # Prepare data structure for trend analysis by month
        monthly_data = {}
        
        for game in games_data:
            date_str = game.get("date", "")
            if not date_str or date_str == "????-??-??":
                continue
                
            # Extract year-month from date
            try:
                if "-" in date_str:
                    year_month = date_str[:7]  # Format: YYYY-MM
                else:
                    # Try to parse Chess.com date format
                    date_obj = datetime.strptime(date_str, "%Y.%m.%d")
                    year_month = date_obj.strftime("%Y-%m")
            except Exception:
                continue
                
            # Initialize month data if needed
            if year_month not in monthly_data:
                monthly_data[year_month] = {
                    "games": 0,
                    "blunders": 0,
                    "inaccuracies": 0,
                    "white_games": 0,
                    "black_games": 0,
                    "wins": 0,
                    "losses": 0,
                    "draws": 0
                }
                
            # Update game counts
            monthly_data[year_month]["games"] += 1
            monthly_data[year_month]["blunders"] += game.get("blunders", 0)
            monthly_data[year_month]["inaccuracies"] += game.get("inaccuracies", 0)
            
            # Update color counts
            if game.get("PlayedAs") == "White":
                monthly_data[year_month]["white_games"] += 1
            else:
                monthly_data[year_month]["black_games"] += 1
                
            # Update result counts
            result = game.get("Result", "")
            played_as = game.get("PlayedAs", "")
            
            if result == "1/2-1/2":
                monthly_data[year_month]["draws"] += 1
            elif (result == "1-0" and played_as == "White") or (result == "0-1" and played_as == "Black"):
                monthly_data[year_month]["wins"] += 1
            else:
                monthly_data[year_month]["losses"] += 1
        
        # Calculate averages and format for chart display
        trend_data = []
        for month, data in sorted(monthly_data.items()):
            if data["games"] > 0:
                trend_data.append({
                    "month": month,
                    "games": data["games"],
                    "avg_blunders": round(data["blunders"] / data["games"], 2),
                    "avg_inaccuracies": round(data["inaccuracies"] / data["games"], 2),
                    "avg_total_mistakes": round((data["blunders"] + data["inaccuracies"]) / data["games"], 2),
                    "win_rate": round(data["wins"] / data["games"] * 100, 1),
                    "white_percentage":

################################################################################
# IV. SETUP WIZARD AND CONFIGURATION HELPERS
################################################################################
def create_env_file(username, email, stockfish_path=None):
    """Create a .env file with user configuration."""
    try:
        env_content = [
            "# Chess.com user settings",
            f"CHESSCOM_USERNAME={username}",
            f"CHESSCOM_CONTACT_EMAIL={email}",
        ]
        
        if stockfish_path:
            env_content.append(f"STOCKFISH_PATH={stockfish_path}")
        
        with open(".env", "w") as f:
            f.write("\n".join(env_content))
            
        emoji_log(logger, logging.INFO, f"Created .env file for user: {username}", "✅")
        return True
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error creating .env file: {str(e)}", "❌")
        return False

def detect_stockfish():
    """Attempt to detect Stockfish installation on the system."""
    common_paths = [
        # Windows paths
        "C:/Program Files/Stockfish/stockfish.exe",
        "C:/Program Files (x86)/Stockfish/stockfish.exe",
        # macOS paths
        "/usr/local/bin/stockfish",
        "/opt/homebrew/bin/stockfish",
        # Linux paths
        "/usr/bin/stockfish",
        "/usr/local/bin/stockfish"
    ]
    
    # Check common paths
    for path in common_paths:
        if os.path.exists(path):
            return path
    
    # Try to find in PATH
    try:
        import subprocess
        which_result = subprocess.run(
            ["which", "stockfish"] if os.name != "nt" else ["where", "stockfish"],
            capture_output=True, text=True, check=False
        )
        if which_result.returncode == 0:
            return which_result.stdout.strip()
    except Exception:
        pass
    
    return None

@app.route("/setup", methods=["GET", "POST"])
def setup_wizard():
    """First-time setup wizard."""
    # Redirect if already configured
    if validate_config() and USERNAME:
        flash("Configuration already exists.", "info")
        return redirect(url_for("index"))
    
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        stockfish_path = request.form.get("stockfish_path")
        
        if not username:
            flash("Chess.com username is required.", "error")
            return render_template(
                "setup.html", 
                detected_stockfish=detect_stockfish()
            )
        
        # Create .env file
        success = create_env_file(username, email, stockfish_path)
        
        if success:
            flash("Setup completed successfully! Restarting application...", "success")
            # In a production environment, you might want to restart the app
            # For development, just redirect to force config reload
            return redirect(url_for("index"))
        else:
            flash("Error creating configuration. Please check permissions.", "error")
    
    return render_template(
        "setup.html", 
        detected_stockfish=detect_stockfish()
    )

@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    """Settings configuration page."""
    # Handle settings update
    if request.method == "POST":
        username = request.form.get("username", USERNAME)
        email = request.form.get("email", CONTACT_EMAIL)
        stockfish_path = request.form.get("stockfish_path", STOCKFISH_PATH)
        
        # Create .env file
        success = create_env_file(username, email, stockfish_path)
        
        if success:
            flash("Settings updated successfully! Changes will take effect after restart.", "success")
        else:
            flash("Error saving settings. Please check permissions.", "error")
            
        return redirect(url_for("settings_page"))
    
    # Display current settings
    current_settings = {
        "username": USERNAME,
        "email": CONTACT_EMAIL,
        "stockfish_path": STOCKFISH_PATH
    }
    
    return render_template(
        "settings.html",
        settings=current_settings,
        detected_stockfish=detect_stockfish()
    )
################################################################################
# VI. MAIN ENTRY POINT
################################################################################
def main():
    # Validate config before starting
    if not validate_config():
        emoji_log(logger, logging.WARNING, 
                 "Configuration validation failed. Application may not function correctly.", "⚠️")
    
    emoji_log(logger, logging.INFO, f"Starting Chessy server for user: {USERNAME}", "🚀")
    app.run(debug=True)
    
if __name__ == "__main__":
    main()