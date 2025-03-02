import os
from dotenv import load_dotenv
from chessy_downloader import fetch_and_save_games
from chessy_parser import parse_games
from chessy_analysis import analyze_games, generate_eco_csv

# Ensure "output" directory exists
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
            
# -----------------------------------------------------------------------------
# 📌 SETUP: Load Configuration from .env
# -----------------------------------------------------------------------------

load_dotenv()

USERNAME = os.getenv("CHESSCOM_USERNAME")
CONTACT_EMAIL = os.getenv("CHESSCOM_CONTACT_EMAIL", "Not Provided")

# Main Archive & Downloaded Games Naming
ARCHIVE_FILE = f"{USERNAME}_GameArchive.pgn"
LAST_DOWNLOADED_FILE = "last_downloaded.txt"

# -----------------------------------------------------------------------------
# 🚀 MAIN EXECUTION
# -----------------------------------------------------------------------------

def main():
    """
    Handles full Chess.com game retrieval, parsing, and analysis pipeline.
    - Downloads new games and appends to archive
    - Parses PGN metadata
    - Generates statistical insights
    """
    print(f"🔍 Fetching new games for {USERNAME}...")

    new_pgn_file = fetch_and_save_games()

    if new_pgn_file:
        games_data = parse_games(new_pgn_file, USERNAME)
        analyze_games(games_data)
        generate_eco_csv(games_data, USERNAME)

    print("✅ Chessy process complete!")

if __name__ == "__main__":
    main()