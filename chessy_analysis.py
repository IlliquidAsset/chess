import chess
import chess.pgn
import chess.engine
import io
import os
import json
from collections import defaultdict, Counter
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# 🔹 LOAD CONFIGURATION & STOCKFISH
# -----------------------------------------------------------------------------

load_dotenv()
STOCKFISH_PATH = os.getenv("STOCKFISH_PATH")

if not STOCKFISH_PATH or not os.path.exists(STOCKFISH_PATH):
    print("⚠️ Stockfish path is missing or incorrect! Set it in `.env`")
    exit()

# -----------------------------------------------------------------------------
# 📥 PGN ANALYSIS FUNCTION
# -----------------------------------------------------------------------------

def analyze_games(pgn_file):
    """
    Parses a PGN file and analyzes move accuracy, blunders, and game phases.
    Uses Stockfish to determine best moves and evaluates mistakes.
    """
    games_data = []
    error_counts = Counter({"Opening": 0, "Middlegame": 0, "Endgame": 0})
    time_trouble_blunders = 0

    if not os.path.exists(pgn_file):
        print(f"⚠️ PGN file not found: {pgn_file}")
        return

    with open(pgn_file, "r") as file:
        pgn_text = file.read()

    pgn_io = io.StringIO(pgn_text)

    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        while True:
            game = chess.pgn.read_game(pgn_io)
            if game is None:
                break

            headers = game.headers
            result = headers.get("Result", "N/A")
            eco = headers.get("ECO", "Unknown")
            termination = headers.get("Termination", "Unknown")

            board = game.board()
            move_count = 0
            blunders = 0
            inaccuracies = 0

            for move in game.mainline_moves():
                move_count += 1
                board.push(move)

                # Classify phase
                phase = (
                    "Opening" if move_count <= 10 else
                    "Middlegame" if move_count <= 30 else
                    "Endgame"
                )

                # Stockfish analysis
                info = engine.analyse(board, chess.engine.Limit(depth=18))
                score = info.get("score")

                # Ensure score exists and has a valid relative value
                if score and hasattr(score, "relative") and score.relative is not None:
                    score_change = abs(score.relative.score())
                else:
                    score_change = 0  # Default to 0 if no valid score available

                if score_change >= 300:
                    blunders += 1
                    error_counts[phase] += 1
                elif score_change >= 100:
                    inaccuracies += 1

                # Track time-trouble blunders (last 5 moves)
                if move_count >= len(list(game.mainline_moves())) - 5 and score_change >= 300:
                    time_trouble_blunders += 1

            games_data.append({
                "ECO": eco,
                "Result": result,
                "Termination": termination,
                "Blunders": blunders,
                "Inaccuracies": inaccuracies,
                "TotalMoves": move_count
            })

    # Save analysis
    analysis_file = os.path.join("output", "game_analysis.json")
    with open(analysis_file, "w") as json_file:
        json.dump(games_data, json_file, indent=4)

    # Print summary
    print("\n🎯 Game Analysis Summary:")
    print(f"✅ Total Games: {len(games_data)}")
    print(f"✅ Blunders by Phase: {dict(error_counts)}")
    print(f"✅ Time-Trouble Blunders: {time_trouble_blunders}")

    return games_data