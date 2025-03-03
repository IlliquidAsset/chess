"""
Centralized configuration for Chessy application with improved folder structure.
"""
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration container with all app settings."""
    
    def __init__(self):
        # User Configuration
        self.USERNAME = os.getenv("CHESSCOM_USERNAME")
        self.CONTACT_EMAIL = os.getenv("CHESSCOM_CONTACT_EMAIL", "Not Provided")
        self.STOCKFISH_PATH = os.getenv("STOCKFISH_PATH")
        
        # Directory Configuration
        self.OUTPUT_DIR = "output"
        self.GAMES_DIR = os.path.join(self.OUTPUT_DIR, "games")
        self.ANALYSIS_DIR = os.path.join(self.OUTPUT_DIR, "analysis")
        self.LOGS_DIR = os.path.join(self.OUTPUT_DIR, "logs")
        
        # Create directories
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.GAMES_DIR, exist_ok=True)
        os.makedirs(self.ANALYSIS_DIR, exist_ok=True)
        os.makedirs(self.LOGS_DIR, exist_ok=True)
        
        # File Paths
        self.ARCHIVE_FILE = os.path.join(self.GAMES_DIR, f"{self.USERNAME}_GameArchive.pgn")
        self.PARSED_GAMES_FILE = os.path.join(self.ANALYSIS_DIR, f"{self.USERNAME}_games_parsed.json")
        self.GAME_ANALYSIS_FILE = os.path.join(self.ANALYSIS_DIR, "game_analysis.json")
        self.ECO_CSV_FILE = os.path.join(self.ANALYSIS_DIR, f"{self.USERNAME}_eco_performance.csv")
        self.LAST_DOWNLOADED_FILE = os.path.join(self.GAMES_DIR, "last_downloaded.txt")
        
        # API Configuration
        self.HEADERS = {
            'User-Agent': f'Chessy Downloader (username: {self.USERNAME}; contact: {self.CONTACT_EMAIL})',
            'Accept-Encoding': 'gzip',
            'Accept': 'application/json, text/plain, */*'
        }
        
        # Analysis Configuration
        self.STOCKFISH_ANALYSIS_DEPTH = 18  # Default analysis depth

# Create a singleton configuration instance
config = Config()

# Export variables for backward compatibility
USERNAME = config.USERNAME
CONTACT_EMAIL = config.CONTACT_EMAIL
STOCKFISH_PATH = config.STOCKFISH_PATH
OUTPUT_DIR = config.OUTPUT_DIR
GAMES_DIR = config.GAMES_DIR
ANALYSIS_DIR = config.ANALYSIS_DIR
LOGS_DIR = config.LOGS_DIR
ARCHIVE_FILE = config.ARCHIVE_FILE
PARSED_GAMES_FILE = config.PARSED_GAMES_FILE
GAME_ANALYSIS_FILE = config.GAME_ANALYSIS_FILE
ECO_CSV_FILE = config.ECO_CSV_FILE
LAST_DOWNLOADED_FILE = config.LAST_DOWNLOADED_FILE
HEADERS = config.HEADERS

def validate_config():
    """Validate essential configuration elements."""
    if not config.USERNAME:
        logging.error("CHESSCOM_USERNAME not set in .env file")
        return False
    
    if not config.STOCKFISH_PATH:
        logging.warning("STOCKFISH_PATH not set in .env file. Analysis features will be limited.")
    elif not os.path.exists(config.STOCKFISH_PATH):
        logging.warning(f"Stockfish not found at {config.STOCKFISH_PATH}. Analysis features will be limited.")
    
    return True