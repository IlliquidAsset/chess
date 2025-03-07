"""
Chess.com game downloader for fetching PGN files.
"""
import requests
import time
import os
from datetime import datetime
import logging
from urllib.parse import urlparse
import concurrent.futures
import threading
from queue import Queue
import re

################################################################################
# I. CONSTANTS AND CONFIGURATION
################################################################################
# Default timeout for HTTP requests
DEFAULT_TIMEOUT = 30

# Maximum number of retries for failed requests
MAX_RETRIES = 3

# Base delay (in seconds) between retries
RETRY_DELAY = 2

# Thread-local storage for maintaining context
thread_local = threading.local()

################################################################################
# II. DOWNLOADER CLASS UPDATE
################################################################################
class ChessComDownloader:
    def __init__(self, username, headers, archive_file, last_downloaded_file):
        """
        Initialize with required parameters.
        
        Args:
            username: Chess.com username
            headers: HTTP headers for API requests
            archive_file: Path to save the complete archive
            last_downloaded_file: Path to save the last download timestamp
        """
        self.username = username
        self.headers = headers
        self.archive_file = archive_file
        self.last_downloaded_file = last_downloaded_file
        self.output_dir = os.path.dirname(archive_file)
        os.makedirs(self.output_dir, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        
        # Queue for storing downloaded PGNs
        self.pgn_queue = Queue()
    
    def fetch_and_save_games(self, filters=None):
        """
        Downloads new PGNs from Chess.com and saves them to the archive.
        - Appends new games to the archive file
        - Saves newly fetched games separately in output directory
        - Tracks last download date to avoid duplicates
        
        Args:
            filters (dict, optional): Filtering criteria, can include:
                - start_date (str): Start date in YYYY-MM-DD format
                - end_date (str): End date in YYYY-MM-DD format
                - time_control (str): Time control category (bullet, blitz, rapid, classical)
        
        Returns:
            str or None: Path to the file containing newly downloaded games, or None if no new games
        """
        self.log(logging.INFO, f"Checking for new games for {self.username}...", "🔍")
        
        # Log filters if present
        if filters:
            filter_list = []
            if 'start_date' in filters and 'end_date' in filters:
                filter_list.append(f"Date range: {filters['start_date']} to {filters['end_date']}")
            if 'time_control' in filters:
                filter_list.append(f"Time control: {filters['time_control']}")
            
            if filter_list:
                self.log(logging.INFO, f"Applying filters: {', '.join(filter_list)}", "🔍")
        
        archives = self.fetch_archives()
        if not archives:
            self.log(logging.WARNING, "No archives found or error fetching archives", "⚠️")
            return None
            
        last_downloaded_date = self.get_last_downloaded_datetime()
        
        # If date filters are provided, override the last_downloaded_date
        if filters and 'start_date' in filters:
            # Convert YYYY-MM-DD to YYYY/MM format
            try:
                date_obj = datetime.strptime(filters['start_date'], "%Y-%m-%d")
                # Convert to YYYY/MM format (used by Chess.com API)
                filters['start_date_api'] = date_obj.strftime("%Y/%m")
            except ValueError:
                self.log(logging.WARNING, f"Invalid start date format: {filters['start_date']}", "⚠️")
        
        if filters and 'end_date' in filters:
            try:
                date_obj = datetime.strptime(filters['end_date'], "%Y-%m-%d")
                # Convert to YYYY/MM format (used by Chess.com API)
                filters['end_date_api'] = date_obj.strftime("%Y/%m")
            except ValueError:
                self.log(logging.WARNING, f"Invalid end date format: {filters['end_date']}", "⚠️")
        
        # Filter archives by date if date filters are provided
        if filters and 'start_date_api' in filters:
            archives = [url for url in archives if self._extract_month(url) >= filters['start_date_api']]
        
        if filters and 'end_date_api' in filters:
            archives = [url for url in archives if self._extract_month(url) <= filters['end_date_api']]
        
        # Download archives in parallel
        pgn_texts = self.download_archives_parallel(archives, last_downloaded_date)
        
        # Filter games by time control if needed
        if filters and 'time_control' in filters and pgn_texts:
            filtered_pgn_texts = []
            
            for pgn_text in pgn_texts:
                # Filter games by time control
                filtered_games = self._filter_games_by_time_control(pgn_text, filters['time_control'])
                if filtered_games:
                    filtered_pgn_texts.append(filtered_games)
            
            pgn_texts = filtered_pgn_texts
        
        if not pgn_texts:
            self.log(logging.INFO, "No new games found", "ℹ️")
            return None
            
        # Combine all PGN texts
        combined_pgns = "\n\n".join(pgn_texts)
        
        # Save newly downloaded games to a separate file
        date_str = datetime.now().strftime("%Y.%m.%d")
        new_pgn_file = os.path.join(self.output_dir, f"{self.username}_GameArchive_{date_str}.pgn")
        
        with open(new_pgn_file, "w") as recent_file:
            recent_file.write(combined_pgns)
        
        # Append to archive file
        with open(self.archive_file, "a") as archive:
            archive.write(combined_pgns)
        
        # Count games (approximate by counting [Event tags)
        game_count = combined_pgns.count('[Event "')
        self.log(logging.INFO, f"Added {game_count} games to archive", "✅")
        
        # Update last downloaded tracker
        self.save_last_downloaded_datetime()
        
        return new_pgn_file
    
    def _extract_month(self, archive_url):
        """
        Extract the month in YYYY/MM format from an archive URL.
        
        Args:
            archive_url (str): Archive URL
            
        Returns:
            str: Month in YYYY/MM format
        """
        # URLs are in format: https://api.chess.com/pub/player/{username}/games/{YYYY}/{MM}
        parts = archive_url.split('/')
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        return ""
    
    def _filter_games_by_time_control(self, pgn_text, time_control_category):
        """
        Filter games in a PGN text by time control category.
        
        Args:
            pgn_text (str): PGN text containing multiple games
            time_control_category (str): Time control category (bullet, blitz, rapid, classical)
            
        Returns:
            str: Filtered PGN text
        """
        # Split the PGN text into individual games
        games = pgn_text.split('\n\n[Event "')
        
        # First element won't start with [Event, so we need to handle it separately
        header = games[0]
        games = games[1:]
        games = ['[Event "' + game for game in games]
        
        # Filter games by time control
        filtered_games = []
        
        for game in games:
            # Extract TimeControl tag
            time_control_match = re.search(r'\[TimeControl "([^"]+)"\]', game)
            
            if time_control_match:
                tc = time_control_match.group(1)
                game_category = self._categorize_time_control(tc)
                
                # Add game if it matches the requested category
                if game_category == time_control_category:
                    filtered_games.append(game)
            else:
                # If no TimeControl tag, skip this game
                continue
        
        # If any games were filtered, combine them
        if filtered_games:
            return '\n\n'.join(filtered_games)
        
        return ""
    
    def _categorize_time_control(self, seconds):
        """
        Categorize time control into standard categories.
        
        Args:
            seconds (str): Time control in seconds
            
        Returns:
            str: Category (bullet, blitz, rapid, classical)
        """
        # Parse the time control
        base_time = 0
        
        try:
            if isinstance(seconds, str):
                if '+' in seconds:
                    parts = seconds.split('+')
                    base_time = int(parts[0])
                else:
                    base_time = int(seconds)
            else:
                base_time = int(seconds)
        except (ValueError, TypeError):
            return "unknown"
        
        # Convert to minutes
        minutes = base_time / 60
        
        # Categorize
        if minutes < 3:
            return "bullet"
        elif minutes < 10:
            return "blitz"
        elif minutes < 30:
            return "rapid"
        else:
            return "classical"