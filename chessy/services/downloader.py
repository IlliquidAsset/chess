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
# II. DOWNLOADER CLASS
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
        
    def log(self, level, message, emoji=""):
        """
        Log a message with an optional emoji prefix.
        """
        if emoji:
            message = f"{emoji} {message}"
        
        if level == logging.DEBUG:
            self.logger.debug(message)
        elif level == logging.INFO:
            self.logger.info(message)
        elif level == logging.WARNING:
            self.logger.warning(message)
        elif level == logging.ERROR:
            self.logger.error(message)
        elif level == logging.CRITICAL:
            self.logger.critical(message)
    
    ################################################################################
    # III. ARCHIVE MANAGEMENT
    ################################################################################
    def fetch_archives(self):
        """
        Fetches available game archives from Chess.com.
        Returns a list of archive URLs or an empty list if an error occurs.
        """
        url = f"https://api.chess.com/pub/player/{self.username}/games/archives"
        
        try:
            # Create a dedicated session for this request
            session = requests.Session()
            response = session.get(url, headers=self.headers, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            
            archives = response.json().get('archives', [])
            self.log(logging.INFO, f"Found {len(archives)} archives for {self.username}", "📚")
            return archives
            
        except requests.exceptions.RequestException as e:
            self.log(logging.ERROR, f"Error fetching archives: {str(e)}", "❌")
            return []
        except requests.exceptions.JSONDecodeError:
            self.log(logging.ERROR, "Invalid JSON response received", "❌")
            return []
        finally:
            session.close()
    
    def get_last_downloaded_datetime(self):
        """
        Reads the last downloaded archive date from file.
        If no file exists, returns None (fetches all archives).
        """
        if os.path.exists(self.last_downloaded_file):
            with open(self.last_downloaded_file, "r") as f:
                return f.read().strip()
        return None
    
    def save_last_downloaded_datetime(self):
        """
        Saves the most recent timestamp (YYYY.MM.DD-HH.MM.SS) to prevent duplicate downloads.
        """
        timestamp = datetime.now().strftime("%Y.%m.%d-%H.%M.%S")
        with open(self.last_downloaded_file, "w") as f:
            f.write(timestamp)
    
    ################################################################################
    # IV. NETWORK OPERATIONS
    ################################################################################
    def download_archive(self, archive_url, last_downloaded_date=None):
        """
        Downloads a single archive with retries and error handling.
        Returns the PGN text or None if it couldn't be downloaded.
        """
        archive_date = archive_url.split("/")[-2] + "/" + archive_url.split("/")[-1]  # Extract YYYY/MM format
        
        if last_downloaded_date and archive_date <= last_downloaded_date:
            self.log(logging.INFO, f"Skipping already downloaded archive: {archive_date}", "⏭️")
            return None
            
        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                # Create a dedicated session for this request
                session = requests.Session()
                
                response = session.get(f"{archive_url}/pgn", 
                                       headers=self.headers, 
                                       timeout=DEFAULT_TIMEOUT)
                
                if response.status_code == 200:
                    self.log(logging.INFO, f"Downloaded PGNs from {archive_date}", "📥")
                    return response.text
                elif response.status_code == 429:
                    wait_time = 60 * (retry_count + 1)  # Exponential backoff
                    self.log(logging.WARNING, 
                             f"Rate limit exceeded. Waiting {wait_time} seconds...", "⏱️")
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    self.log(logging.ERROR, 
                             f"Failed to fetch PGNs: HTTP {response.status_code}", "❌")
                    retry_count += 1
                    time.sleep(RETRY_DELAY * (2 ** retry_count))  # Exponential backoff
                    
            except requests.exceptions.RequestException as e:
                self.log(logging.ERROR, 
                         f"Error downloading archive {archive_url}: {str(e)}", "❌")
                retry_count += 1
                time.sleep(RETRY_DELAY * (2 ** retry_count))  # Exponential backoff
            finally:
                session.close()
        
        # If we've exhausted all retries
        self.log(logging.ERROR, 
                 f"Failed to download archive after {MAX_RETRIES} attempts: {archive_url}", "❌")
        return None
    
    def download_archives_parallel(self, archive_urls, last_downloaded_date=None, max_workers=5):
        """
        Downloads multiple archives in parallel for improved performance.
        Returns a list of successful PGN texts.
        """
        pgn_texts = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks
            future_to_url = {
                executor.submit(self.download_archive, url, last_downloaded_date): url 
                for url in archive_urls
            }
            
            # Process completed tasks
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    pgn_text = future.result()
                    if pgn_text:
                        pgn_texts.append(pgn_text)
                except Exception as e:
                    self.log(logging.ERROR, 
                             f"Exception while downloading {url}: {str(e)}", "❌")
                    
        return pgn_texts
    
    ################################################################################
    # V. PUBLIC API
    ################################################################################
    def fetch_and_save_games(self):
        """
        Downloads new PGNs from Chess.com and saves them to the archive.
        - Appends new games to the archive file
        - Saves newly fetched games separately in output directory
        - Tracks last download date to avoid duplicates
        
        Returns:
            str or None: Path to the file containing newly downloaded games, or None if no new games
        """
        self.log(logging.INFO, f"Checking for new games for {self.username}...", "🔍")
        
        archives = self.fetch_archives()
        if not archives:
            self.log(logging.WARNING, "No archives found or error fetching archives", "⚠️")
            return None
            
        last_downloaded_date = self.get_last_downloaded_datetime()
        
        # Download archives in parallel
        pgn_texts = self.download_archives_parallel(archives, last_downloaded_date)
        
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