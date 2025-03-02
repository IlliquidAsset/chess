import chess.pgn
import io
import json

# -----------------------------------------------------------------------------
# 📥 PARSE PGNs
# -----------------------------------------------------------------------------

def parse_games(pgn_file, username):
    games_data = []

    with open(pgn_file, "r") as file:
        pgn_text = file.read()

    pgn_io = io.StringIO(pgn_text)

    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break

        headers = game.headers
        result = headers.get("Result", "N/A")
        white = headers.get("White", "Unknown")
        black = headers.get("Black", "Unknown")
        eco = headers.get("ECO", "Unknown")
        termination = headers.get("Termination", "Unknown")
        num_moves = len(list(game.mainline_moves()))
        time_control = headers.get("TimeControl", "Unknown")

        played_as = "White" if white == username else "Black"

        games_data.append({
            "PlayedAs": played_as,
            "Result": result,
            "TimeControl": time_control,
            "ECO": eco,
            "Termination": termination,
            "NumMoves": num_moves
        })

    with open(f"{username}_games_parsed.json", "w") as json_file:
        json.dump(games_data, json_file, indent=4)

    return games_data