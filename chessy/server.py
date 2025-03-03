# ////////////////////////////////////////////////////////////////////////////////
# // I. IMPORTS
# ////////////////////////////////////////////////////////////////////////////////
import os
import json
import csv
import logging
import threading
import datetime
import traceback
import hashlib
import hmac
import secrets
from functools import wraps
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session, send_from_directory
import pandas as pd

# Import chessy modules
from chessy.config import (
    USERNAME, HEADERS, ARCHIVE_FILE, LAST_DOWNLOADED_FILE, 
    GAME_ANALYSIS_FILE, PARSED_GAMES_FILE, ECO_CSV_FILE, 
    STOCKFISH_PATH, validate_config, OUTPUT_DIR, config, CONTACT_EMAIL
)
from chessy.services.downloader import ChessComDownloader
from chessy.services.parser import GameParser
from chessy.services.analyzer import GameAnalyzer
from chessy.services import ChessyService
from chessy.utils.logging import setup_logging, emoji_log

# ////////////////////////////////////////////////////////////////////////////////
# // II. APPLICATION INITIALIZATION
# ////////////////////////////////////////////////////////////////////////////////
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
        'percentage': 0,
        'notification': None
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
        'percentage': 0,
        'notification': None
    }
}

def init_services():
    """Initialize all required services."""
    try:
        valid = validate_config()
        if not valid:
            emoji_log(logger, logging.WARNING, 
                      "Configuration issues detected. Some features may be limited.", "⚠️")
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

chessy_service = init_services()

# ////////////////////////////////////////////////////////////////////////////////
# // III. UTILITY FUNCTIONS
# ////////////////////////////////////////////////////////////////////////////////
def ensure_required_files():
    """Ensure necessary files exist for the application to function."""
    if not chessy_service:
        return False
    if not os.path.exists(ARCHIVE_FILE):
        emoji_log(logger, logging.WARNING, "No game archive found. Will prompt user to download games.", "⚠️")
        return False
    if not os.path.exists(PARSED_GAMES_FILE):
        emoji_log(logger, logging.WARNING, "No parsed games file found. Will process on first request.", "⚠️")
        if os.path.exists(ARCHIVE_FILE) and chessy_service:
            try:
                with open(PARSED_GAMES_FILE, "w") as f:
                    f.write(json.dumps([]))
                emoji_log(logger, logging.INFO, f"Parsing games from existing archive: {ARCHIVE_FILE}", "📊")
                games_data = chessy_service.parser.parse_games(ARCHIVE_FILE)
                if games_data:
                    emoji_log(logger, logging.INFO, f"Successfully parsed {len(games_data)} games", "✅")
            except Exception as e:
                emoji_log(logger, logging.ERROR, f"Error parsing games: {str(e)}", "❌")
    if not os.path.exists(GAME_ANALYSIS_FILE):
        emoji_log(logger, logging.WARNING, "No game analysis found. Will run analysis on request.", "⚠️")
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
        dates = [game.get("date") for game in games_data if game.get("date") and game.get("date") != "????-??-??"]
        if not dates:
            return {"start": None, "end": None}
        dates.sort()
        return {"start": dates[0], "end": dates[-1]}
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error getting date range: {str(e)}", "❌")
        return {"start": None, "end": None}

# ////////////////////////////////////////////////////////////////////////////////
# // IV. BACKGROUND TASKS
# ////////////////////////////////////////////////////////////////////////////////
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
            background_tasks['download']['messages'].append("Checking for new games...")
            new_games = chessy_service.check_for_updates()
            if new_games > 0:
                background_tasks['download']['messages'].append(f"Found {new_games} new games")
                background_tasks['download']['status'] = f"Downloaded {new_games} new games"
                background_tasks['download']['result'] = new_games
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
            background_tasks['download']['notification'] = {
                'type': 'error',
                'title': 'Download Error',
                'message': str(e)
            }
            traceback_text = traceback.format_exc()
            logger.error(f"Detailed error:\n{traceback_text}")
        finally:
            background_tasks['download']['running'] = False
            save_task_history('download', background_tasks['download'])

def analyze_thread(app_context):
    """Background thread for analyzing games."""
    with app_context:
        try:
            background_tasks['analyze']['running'] = True
            background_tasks['analyze']['status'] = "Running"
            background_tasks['analyze']['messages'] = ["Starting analysis..."]
            background_tasks['analyze']['start_time'] = datetime.datetime.now()
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
            def progress_callback(current, total):
                background_tasks['analyze']['current'] = current
                background_tasks['analyze']['percentage'] = (current / total * 100) if total > 0 else 0
                milestone_percentage = 25
                current_percentage = int(background_tasks['analyze']['percentage'])
                if current_percentage > 0 and current_percentage % milestone_percentage == 0:
                    milestone_message = f"Completed {current_percentage}% ({current}/{total} games)"
                    if not any(milestone_message in msg for msg in background_tasks['analyze']['messages']):
                        background_tasks['analyze']['messages'].append(milestone_message)
                        if current > 10:
                            elapsed = (datetime.datetime.now() - background_tasks['analyze']['start_time']).total_seconds()
                            games_per_second = current / elapsed if elapsed > 0 else 0
                            if games_per_second > 0:
                                remaining_games = total - current
                                est_remaining_seconds = remaining_games / games_per_second
                                if est_remaining_seconds > 60:
                                    est_minutes = int(est_remaining_seconds // 60)
                                    est_seconds = int(est_remaining_seconds % 60)
                                    background_tasks['analyze']['messages'].append(
                                        f"Estimated time remaining: {est_minutes}m {est_seconds}s"
                                    )
            if hasattr(chessy_service.analyzer, 'set_progress_callback'):
                chessy_service.analyzer.set_progress_callback(progress_callback)
            results = chessy_service.process_new_games()
            background_tasks['analyze']['messages'].append(f"Completed: {results['analyzed_games']} games analyzed")
            background_tasks['analyze']['status'] = f"Completed: {results['analyzed_games']} games analyzed"
            background_tasks['analyze']['result'] = results
            background_tasks['analyze']['timestamp'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            end_time = datetime.datetime.now()
            background_tasks['analyze']['elapsed_seconds'] = (end_time - background_tasks['analyze']['start_time']).total_seconds()
            background_tasks['analyze']['current'] = total_games
            background_tasks['analyze']['percentage'] = 100
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
            background_tasks['analyze']['notification'] = {
                'type': 'error',
                'title': 'Analysis Error',
                'message': str(e)
            }
            traceback_text = traceback.format_exc()
            logger.error(f"Detailed error:\n{traceback_text}")
        finally:
            background_tasks['analyze']['running'] = False
            save_task_history('analyze', background_tasks['analyze'])

def save_task_history(task_type, task_data):
    """Save task history to a file for resumption and tracking."""
    try:
        history_file = os.path.join(OUTPUT_DIR, f"{task_type}_history.json")
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    history = json.load(f)
            except Exception as e:
                logger.error(f"Error reading task history: {str(e)}")
        history_entry = {
            'timestamp': task_data.get('timestamp', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            'status': task_data.get('status', 'Unknown'),
            'elapsed_seconds': task_data.get('elapsed_seconds', 0),
            'result': task_data.get('result', None),
            'success': task_data.get('status', '').startswith('Completed')
        }
        history.append(history_entry)
        if len(history) > 10:
            history = history[-10:]
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving task history: {str(e)}")

def get_pending_notifications():
    """Check for notifications from background tasks."""
    notifications = []
    for task_type in ['download', 'analyze']:
        task_data = background_tasks[task_type]
        if 'notification' in task_data and task_data['notification']:
            notifications.append(task_data['notification'])
            task_data['notification'] = None
    return notifications

# ////////////////////////////////////////////////////////////////////////////////
# // V. UI ENDPOINTS
# ////////////////////////////////////////////////////////////////////////////////
# // V.A - Main Pages
@app.route("/")
def index():
    """Main dashboard page."""
    has_data = ensure_required_files()
    stats = chessy_service.get_game_statistics() if chessy_service else {"total_games": 0}
    date_range = get_date_range()
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

@app.route("/games")
def games():
    """View game list and details."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
    games_data = []
    try:
        if os.path.exists(PARSED_GAMES_FILE):
            with open(PARSED_GAMES_FILE, "r") as f:
                games_data = json.load(f)
            games_data = sorted(
                games_data, 
                key=lambda x: x.get("date", "0000-00-00"), 
                reverse=True
            )
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading game data: {str(e)}", "❌")
    return render_template("games.html", username=USERNAME, games=games_data)

@app.route("/openings")
def openings():
    """View opening statistics."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
    eco_data = chessy_service.get_opening_performance() or []
    eco_descriptions = {}
    try:
        try:
            from chessy.utils.ECO_codes_library import get_eco_descriptions
            eco_descriptions = get_eco_descriptions()
        except ImportError:
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
    return render_template("openings.html", username=USERNAME, eco_data=eco_data, eco_descriptions=eco_descriptions)

@app.route("/blunders")
def blunders():
    """View blunders statistics."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
    blunders_data = {}
    try:
        if os.path.exists(GAME_ANALYSIS_FILE):
            with open(GAME_ANALYSIS_FILE, "r") as f:
                games_data = json.load(f)
            if games_data:
                total_blunders = sum(game.get("blunders", 0) for game in games_data)
                total_games = len(games_data)
                avg_blunders = total_blunders / total_games if total_games > 0 else 0
                blunders_by_tc = {}
                for game in games_data:
                    tc = game.get("TimeControl", "Unknown")
                    blunders = game.get("blunders", 0)
                    if tc not in blunders_by_tc:
                        blunders_by_tc[tc] = {"games": 0, "blunders": 0}
                    blunders_by_tc[tc]["games"] += 1
                    blunders_by_tc[tc]["blunders"] += blunders
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
    return render_template("blunders.html", username=USERNAME, blunders_data=blunders_data)

@app.route("/inaccuracies")
def inaccuracies():
    """View inaccuracies statistics."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
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
                total_inaccuracies = sum(game.get("inaccuracies", 0) for game in games_data)
                total_games = len(games_data)
                avg_inaccuracies = round(total_inaccuracies / total_games, 2) if total_games > 0 else 0
                for game in games_data:
                    inaccuracies_val = game.get("inaccuracies", 0)
                    if inaccuracies_val > 0:
                        game_copy = game.copy()
                        game_copy["inaccuracies"] = inaccuracies_val
                        inaccuracy_games.append(game_copy)
                inaccuracy_games = sorted(
                    inaccuracy_games,
                    key=lambda x: x.get("inaccuracies", 0),
                    reverse=True
                )[:20]
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading inaccuracies data: {str(e)}", "❌")
    return render_template("inaccuracies.html", username=USERNAME, total_inaccuracies=total_inaccuracies, avg_inaccuracies=avg_inaccuracies, common_phase=common_phase, inaccuracy_games=inaccuracy_games)

@app.route("/mistakes")
def mistakes():
    """View comprehensive mistakes statistics."""
    if not chessy_service:
        flash("Service not available. Check configuration and try again.", "error")
        return redirect(url_for("index"))
    analysis_data = {}
    top_mistake_games = []
    try:
        if os.path.exists(GAME_ANALYSIS_FILE):
            with open(GAME_ANALYSIS_FILE, "r") as f:
                games_data = json.load(f)
            if games_data:
                total_blunders = sum(game.get("blunders", 0) for game in games_data)
                total_inaccuracies = sum(game.get("inaccuracies", 0) for game in games_data)
                total_mistakes = total_blunders + total_inaccuracies
                total_games = len(games_data)
                opening_mistakes = 0
                middlegame_mistakes = 0
                endgame_mistakes = 0
                for game in games_data:
                    moves = game.get("move_count", 0)
                    blunders_val = game.get("blunders", 0)
                    inaccuracies_val = game.get("inaccuracies", 0)
                    total_val = blunders_val + inaccuracies_val
                    if moves <= 0:
                        continue
                    if moves <= 10:
                        opening_mistakes += total_val
                    elif moves <= 30:
                        opening_mistakes += total_val * 0.3
                        middlegame_mistakes += total_val * 0.7
                    else:
                        opening_mistakes += total_val * 0.2
                        middlegame_mistakes += total_val * 0.5
                        endgame_mistakes += total_val * 0.3
                tc_stats = {}
                for game in games_data:
                    tc = game.get("TimeControl", "Unknown")
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
                    mistakes_val = game.get("blunders", 0) + game.get("inaccuracies", 0)
                    if tc_category not in tc_stats:
                        tc_stats[tc_category] = 0
                    tc_stats[tc_category] += mistakes_val
                for game in games_data:
                    game["total_mistakes"] = game.get("blunders", 0) + game.get("inaccuracies", 0)
                top_mistake_games = sorted(
                    games_data,
                    key=lambda x: x.get("total_mistakes", 0),
                    reverse=True
                )[:10]
                month_data = {}
                for game in games_data:
                    date_str = game.get("date", "")
                    if date_str and date_str != "????-??-??":
                        month = date_str[:7]
                        mistakes_val = game.get("blunders", 0) + game.get("inaccuracies", 0)
                        if month not in month_data:
                            month_data[month] = {"games": 0, "mistakes": 0}
                        month_data[month]["games"] += 1
                        month_data[month]["mistakes"] += mistakes_val
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
    return render_template("mistakes_overview.html", username=USERNAME, analysis_data=analysis_data, top_mistake_games=top_mistake_games)

# ////////////////////////////////////////////////////////////////////////////////
# // V.B - Error Pages
# ////////////////////////////////////////////////////////////////////////////////
@app.route("/errors/download")
def download_error():
    """Display download error page."""
    return render_template("errors/download.html", username=USERNAME)

@app.route("/errors/analysis")
def analysis_error():
    """Display analysis error page."""
    return render_template("errors/analysis.html", username=USERNAME)

@app.route("/errors/not_found")
def not_found_error():
    """Display 404 page."""
    return render_template("errors/not_found.html", username=USERNAME)

# ////////////////////////////////////////////////////////////////////////////////
# // VI. API ENDPOINTS
# ////////////////////////////////////////////////////////////////////////////////
# // VI.A - General API Endpoints
@app.route("/api/progress")
def get_progress():
    """Get current progress of background tasks."""
    if background_tasks['download']['running'] and background_tasks['download']['start_time']:
        elapsed = datetime.datetime.now() - background_tasks['download']['start_time']
        background_tasks['download']['elapsed_seconds'] = int(elapsed.total_seconds())
    if background_tasks['analyze']['running'] and background_tasks['analyze']['start_time']:
        elapsed = datetime.datetime.now() - background_tasks['analyze']['start_time']
        background_tasks['analyze']['elapsed_seconds'] = int(elapsed.total_seconds())
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
        return jsonify({"active": False})

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
        try:
            from chessy.utils.ECO_codes_library import get_eco_description
            description = get_eco_description(eco_code)
            return jsonify({"description": description})
        except ImportError:
            descriptions = {
                "A00": "Irregular Openings",
                "B20": "Sicilian Defence",
                "C00": "French Defense",
                "D00": "Queen's Pawn Game",
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
        def parse_time_control(tc):
            try:
                if not tc:
                    return "Unknown"
                if "+" in tc:
                    base_time = int(tc.split("+")[0])
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
                return tc if tc else "Unknown"
        if 'TimeControl' in df.columns:
            df['TimeControlGroup'] = df['TimeControl'].apply(parse_time_control)
            tc_stats = {}
            for group, group_df in df.groupby('TimeControlGroup'):
                if group == "Unknown" and len(group_df) < 5:
                    continue
                tc_stats[group] = {
                    'games': len(group_df),
                    'wins': sum((group_df['PlayedAs'] == 'White') & (group_df['Result'] == '1-0') | 
                                (group_df['PlayedAs'] == 'Black') & (group_df['Result'] == '0-1')),
                    'losses': sum((group_df['PlayedAs'] == 'White') & (group_df['Result'] == '0-1') | 
                                  (group_df['PlayedAs'] == 'Black') & (group_df['Result'] == '1-0')),
                    'draws': sum(group_df['Result'] == '1/2-1/2')
                }
            chart_data = []
            for tc, stats in tc_stats.items():
                win_rate = stats['wins'] / stats['games'] * 100 if stats['games'] > 0 else 0
                chart_data.append({
                    'timeControl': tc,
                    'winRate': round(win_rate, 1),
                    'games': stats['games']
                })
            chart_data = sorted(chart_data, key=lambda x: x['games'], reverse=True)
            return jsonify(chart_data)
        else:
            return jsonify([])
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error generating win rate chart: {str(e)}", "❌")
        return jsonify([])

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
        opening_data = [{"opening": eco, "count": data["count"]} 
                        for eco, data in inaccuracies_by_opening.items() if data["count"] > 0]
        opening_data = sorted(opening_data, key=lambda x: x["count"], reverse=True)[:10]
        phase_data = {
            "Opening": 45,
            "Middlegame": 35,
            "Endgame": 20
        }
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
        filters = request.json.get("filters", {})
        format_type = request.json.get("format", "csv")
        if not os.path.exists(PARSED_GAMES_FILE):
            return jsonify({"error": "No game data available"}), 400
        with open(PARSED_GAMES_FILE, "r") as f:
            games_data = json.load(f)
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
        filename = f"{USERNAME}_games_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        export_dir = os.path.join(OUTPUT_DIR, "exports")
        os.makedirs(export_dir, exist_ok=True)
        if format_type == "csv":
            export_path = os.path.join(export_dir, f"{filename}.csv")
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
            df = pd.DataFrame(filtered_data)
            with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="Games", index=False)
                workbook = writer.book
                worksheet = writer.sheets["Games"]
                for i, col in enumerate(df.columns):
                    max_width = max(df[col].astype(str).apply(len).max(), len(col)) + 2
                    worksheet.column_dimensions[chr(65 + i)].width = min(max_width, 30)
            return jsonify({
                "status": "success",
                "message": f"Exported {len(filtered_data)} games as Excel",
                "filename": f"{filename}.xlsx",
                "download_url": f"/download/export/{filename}.xlsx"
            })
        elif format_type == "text":
            export_path = os.path.join(export_dir, f"{filename}.txt")
            with open(export_path, "w") as f:
                f.write(f"Chess.com Game Export for {USERNAME}\n")
                f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
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
                    if 'blunders' in game or 'inaccuracies' in game:
                        f.write("Analysis:\n")
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

@app.route("/api/toggle_theme", methods=["POST"])
def toggle_theme():
    """Toggle between light and dark mode."""
    current_theme = session.get("theme", "light")
    session["theme"] = "dark" if current_theme == "light" else "light"
    return jsonify({"theme": session["theme"]})

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

# ////////////////////////////////////////////////////////////////////////////////
# // VII. DOWNLOAD ENDPOINTS
# ////////////////////////////////////////////////////////////////////////////////
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

# ////////////////////////////////////////////////////////////////////////////////
# // VIII. MULTI-USER SUPPORT
# ////////////////////////////////////////////////////////////////////////////////
def load_users():
    """Load user data from file."""
    USER_DB_FILE = os.path.join(OUTPUT_DIR, "users.json")
    if not os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, "w") as f:
            json.dump([], f)
        return []
    try:
        with open(USER_DB_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error loading users: {str(e)}", "❌")
        return []

def save_users(users):
    """Save user data to file."""
    USER_DB_FILE = os.path.join(OUTPUT_DIR, "users.json")
    try:
        with open(USER_DB_FILE, "w") as f:
            json.dump(users, f, indent=2)
        return True
    except Exception as e:
        emoji_log(logger, logging.ERROR, f"Error saving users: {str(e)}", "❌")
        return False

def hash_password(password, salt=None):
    """Hash a password with a salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return f"{salt}${key}"

def verify_password(stored_hash, password):
    """Verify a password against a stored hash."""
    if not stored_hash or '$' not in stored_hash:
        return False
    salt, key = stored_hash.split('$', 1)
    return hash_password(password, salt) == stored_hash

def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        users = load_users()
        user = next((u for u in users if str(u.get('id')) == str(session.get('user_id'))), None)
        if not user or not user.get('is_admin'):
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration page."""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email")
        chess_username = request.form.get("chess_username")
        if not username or not password or not email:
            flash("All fields are required.", "error")
            return render_template("register.html")
        users = load_users()
        if any(u.get('username') == username for u in users):
            flash("Username already exists.", "error")
            return render_template("register.html")
        user = {
            "id": len(users) + 1,
            "username": username,
            "email": email,
            "password_hash": hash_password(password),
            "chess_username": chess_username,
            "created_at": datetime.datetime.now().isoformat(),
            "is_admin": len(users) == 0,
            "settings": {
                "theme": "light",
                "stockfish_path": detect_stockfish()
            }
        }
        users.append(user)
        if save_users(users):
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for("login"))
        else:
            flash("Error saving user data.", "error")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """User login page."""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("login.html")
        users = load_users()
        user = next((u for u in users if u.get('username') == username), None)
        if not user or not verify_password(user.get('password_hash'), password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['is_admin'] = user.get('is_admin', False)
        session['theme'] = user.get('settings', {}).get('theme', 'light')
        global USERNAME
        USERNAME = user.get('chess_username', USERNAME)
        flash(f"Welcome back, {user['username']}!", "success")
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        else:
            return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Log out the current user."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """User profile page."""
    users = load_users()
    user = next((u for u in users if str(u.get('id')) == str(session.get('user_id'))), None)
    if not user:
        session.clear()
        flash("User not found. Please log in again.", "error")
        return redirect(url_for("login"))
    if request.method == "POST":
        user['email'] = request.form.get("email", user.get('email'))
        user['chess_username'] = request.form.get("chess_username", user.get('chess_username'))
        new_password = request.form.get("new_password")
        if new_password:
            current_password = request.form.get("current_password")
            if not current_password or not verify_password(user.get('password_hash'), current_password):
                flash("Current password is incorrect.", "error")
                return render_template("profile.html", user=user)
            user['password_hash'] = hash_password(new_password)
        if 'settings' not in user:
            user['settings'] = {}
        user['settings']['theme'] = request.form.get("theme", user.get('settings', {}).get('theme', 'light'))
        user['settings']['stockfish_path'] = request.form.get("stockfish_path", user.get('settings', {}).get('stockfish_path'))
        if save_users(users):
            session['theme'] = user['settings'].get('theme', 'light')
            global USERNAME
            USERNAME = user.get('chess_username', USERNAME)
            flash("Profile updated successfully.", "success")
        else:
            flash("Error saving profile changes.", "error")
    return render_template("profile.html", user=user)

@app.route("/admin/users")
@admin_required
def admin_users():
    """Admin user management page."""
    users = load_users()
    return render_template("admin_users.html", users=users)

@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    """Delete a user."""
    if str(user_id) == str(session.get('user_id')):
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin_users"))
    users = load_users()
    users = [u for u in users if str(u.get('id')) != str(user_id)]
    if save_users(users):
        flash("User deleted successfully.", "success")
    else:
        flash("Error deleting user.", "error")
    return redirect(url_for("admin_users"))

@app.route("/admin/users/<int:user_id>/toggle_admin", methods=["POST"])
@admin_required
def toggle_admin(user_id):
    """Toggle admin status for a user."""
    if str(user_id) == str(session.get('user_id')):
        flash("You cannot change your own admin status.", "error")
        return redirect(url_for("admin_users"))
    users = load_users()
    user = next((u for u in users if str(u.get('id')) == str(user_id)), None)
    if user:
        user['is_admin'] = not user.get('is_admin', False)
        if save_users(users):
            flash(f"Admin status for {user['username']} updated.", "success")
        else:
            flash("Error updating admin status.", "error")
    else:
        flash("User not found.", "error")
    return redirect(url_for("admin_users"))

# ////////////////////////////////////////////////////////////////////////////////
# // IX. SETUP WIZARD AND CONFIGURATION HELPERS
# ////////////////////////////////////////////////////////////////////////////////
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
        "C:/Program Files/Stockfish/stockfish.exe",
        "C:/Program Files (x86)/Stockfish/stockfish.exe",
        "/usr/local/bin/stockfish",
        "/opt/homebrew/bin/stockfish",
        "/usr/bin/stockfish",
        "/usr/local/bin/stockfish"
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path
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
    if validate_config() and USERNAME:
        flash("Configuration already exists.", "info")
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        stockfish_path = request.form.get("stockfish_path")
        if not username:
            flash("Chess.com username is required.", "error")
            return render_template("setup.html", detected_stockfish=detect_stockfish())
        success = create_env_file(username, email, stockfish_path)
        if success:
            flash("Setup completed successfully! Restarting application...", "success")
            return redirect(url_for("index"))
        else:
            flash("Error creating configuration. Please check permissions.", "error")
    return render_template("setup.html", detected_stockfish=detect_stockfish())

@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    """Settings configuration page."""
    if request.method == "POST":
        username = request.form.get("username", USERNAME)
        email = request.form.get("email", CONTACT_EMAIL)
        stockfish_path = request.form.get("stockfish_path", STOCKFISH_PATH)
        success = create_env_file(username, email, stockfish_path)
        if success:
            flash("Settings updated successfully! Changes will take effect after restart.", "success")
        else:
            flash("Error saving settings. Please check permissions.", "error")
        return redirect(url_for("settings_page"))
    current_settings = {
        "username": USERNAME,
        "email": CONTACT_EMAIL,
        "stockfish_path": STOCKFISH_PATH
    }
    return render_template("settings.html", settings=current_settings, detected_stockfish=detect_stockfish())

# ////////////////////////////////////////////////////////////////////////////////
# // X. MAIN ENTRY POINT
# ////////////////////////////////////////////////////////////////////////////////
def main():
    if not validate_config():
        emoji_log(logger, logging.WARNING, 
                  "Configuration validation failed. Application may not function correctly.", "⚠️")
    emoji_log(logger, logging.INFO, f"Starting Chessy server for user: {USERNAME}", "🚀")
    app.run(debug=True)

if __name__ == "__main__":
    main()