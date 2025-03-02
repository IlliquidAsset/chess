import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# -----------------------------------------------------------------------------
# 📂 SET UP OUTPUT DIRECTORY
# -----------------------------------------------------------------------------
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# 🎯 CONFIGURATION VARIABLES
# -----------------------------------------------------------------------------
USERNAME = os.getenv("CHESSCOM_USERNAME")
CONTACT_EMAIL = os.getenv("CHESSCOM_CONTACT_EMAIL", "Not Provided")

ARCHIVE_FILE = os.path.join(OUTPUT_DIR, f"{USERNAME}_GameArchive.pgn")
LAST_DOWNLOADED_FILE = os.path.join(OUTPUT_DIR, "last_downloaded.txt")

HEADERS = {
    'User-Agent': f'Chessy Downloader (username: {USERNAME}; contact: {CONTACT_EMAIL})',
    'Accept-Encoding': 'gzip',
    'Accept': 'application/json, text/plain, */*'
}

# -----------------------------------------------------------------------------
# 📥 FETCH GAME ARCHIVES
# -----------------------------------------------------------------------------

def fetch_archives(username):
    """
    Fetches available game archives from Chess.com.
    Returns a list of archive URLs or an empty list if an error occurs.
    """
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        try:
            return response.json().get('archives', [])
        except requests.exceptions.JSONDecodeError:
            print("❌ Error: Invalid JSON response received.")
            print(response.text)
            return []
    else:
        print(f"❌ Error: Failed to fetch archives. Status Code: {response.status_code}")
        print(response.text)
        return []

# -----------------------------------------------------------------------------
# 🕒 TRACK LAST DOWNLOADED DATE
# -----------------------------------------------------------------------------

def get_last_downloaded_datetime():
    """
    Reads the last downloaded archive date from file.
    If no file exists, returns None (fetches all archives).
    """
    if os.path.exists(LAST_DOWNLOADED_FILE):
        with open(LAST_DOWNLOADED_FILE, "r") as f:
            return f.read().strip()
    return None

def save_last_downloaded_datetime():
    """
    Saves the most recent timestamp (YYYY.MM.DD-HH.MM.SS) to prevent duplicate downloads.
    """
    timestamp = datetime.now().strftime("%Y.%m.%d-%H.%M.%S")
    with open(LAST_DOWNLOADED_FILE, "w") as f:
        f.write(timestamp)

# -----------------------------------------------------------------------------
# 📥 FETCH NEW PGNs
# -----------------------------------------------------------------------------

def fetch_and_save_games():
    """
    Downloads new PGNs from Chess.com and saves them to the archive.
    - Appends new games to `ARCHIVE_FILE`
    - Saves newly fetched games separately in `output/`
    - Tracks last download date to avoid duplicates
    """
    print(f"🔍 Checking for new games for {USERNAME}...")

    archives = fetch_archives(USERNAME)
    last_downloaded_date = get_last_downloaded_datetime()
    new_pgns = ""

    for archive_url in archives:
        archive_date = archive_url.split("/")[-1]  # Extract YYYY/MM format
        if last_downloaded_date and archive_date <= last_downloaded_date:
            print(f"⏭ Skipping already downloaded archive: {archive_date}")
            continue

        time.sleep(1)  # Avoid rate limiting
        response = requests.get(f"{archive_url}/pgn", headers=HEADERS)

        if response.status_code == 200:
            print(f"📥 Downloading PGNs from {archive_date}...")
            new_pgns += response.text + "\n\n"
        elif response.status_code == 429:
            print(f"⚠️ Rate limit exceeded. Retrying after 60 seconds...")
            time.sleep(60)  # Wait before retrying
            response = requests.get(f"{archive_url}/pgn", headers=HEADERS)
            if response.status_code == 200:
                new_pgns += response.text + "\n\n"
        else:
            print(f"❌ Failed to fetch PGNs from {archive_url}")

    if not new_pgns.strip():
        print("⚠️ No new games found.")
        return None  # No new PGNs downloaded

    # Determine new file name
    from_date = datetime.now().strftime("%Y.%m.%d")
    new_pgn_file = os.path.join(OUTPUT_DIR, f"{USERNAME}_GameArchive_{from_date}.pgn")

    # Save newly downloaded games separately
    with open(new_pgn_file, "w") as recent_file:
        recent_file.write(new_pgns)
    
    print(f"✅ New games saved to: {new_pgn_file}")

    # Append new games to the archive file
    with open(ARCHIVE_FILE, "a") as archive:
        archive.write(new_pgns)

    print(f"✅ {len(new_pgns.split('[Event'))-1} games added to {ARCHIVE_FILE}")

    # Update last downloaded tracker
    save_last_downloaded_datetime()
    return new_pgn_file  # Return new PGN file path for further processing