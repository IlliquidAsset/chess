import requests
import time
import os
from datetime import datetime
import logging

class ChessComDownloader:
    def __init__(self, username, headers, archive_file, last_downloaded_file):
        self.username = username
        self.headers = headers
        self.archive_file = archive_file
        self.last_downloaded_file = last_downloaded_file
        self.output_dir = os.path.dirname(archive_file)
        os.makedirs(self.output_dir, exist_ok=True)
        
    def fetch_archives(self):
        """
        Fetches available game archives from Chess.com.
        Returns a list of archive URLs or an empty list if an error occurs.
        """
        url = f"https://api.chess.com/pub/player/{self.username}/games/archives"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()  # Raise exception for 4XX/5XX responses
            
            return response.json().get('archives', [])
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching archives: {e}")
            return []
        except requests.exceptions.JSONDecodeError:
            logging.error("Invalid JSON response received")
            return []
    
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
    
    def fetch_and_save_games(self):
        """
        Downloads new PGNs from Chess.com and saves them to the archive.
        - Appends new games to the archive file
        - Saves newly fetched games separately in output directory
        - Tracks last download date to avoid duplicates
        
        Returns:
            str or None: Path to the file containing newly downloaded games, or None if no new games
        """
        logging.info(f"Checking for new games for {self.username}...")
        
        archives = self.fetch_archives()
        last_downloaded_date = self.get_last_downloaded_datetime()
        new_pgns = ""
        
        for archive_url in archives:
            archive_date = archive_url.split("/")[-2] + "/" + archive_url.split("/")[-1]  # Extract YYYY/MM format
            
            if last_downloaded_date and archive_date <= last_downloaded_date:
                logging.info(f"Skipping already downloaded archive: {archive_date}")
                continue
            
            try:
                # Respect rate limits
                time.sleep(1)
                
                response = requests.get(f"{archive_url}/pgn", headers=self.headers)
                
                if response.status_code == 200:
                    logging.info(f"Downloaded PGNs from {archive_date}")
                    new_pgns += response.text + "\n\n"
                elif response.status_code == 429:
                    logging.warning("Rate limit exceeded. Waiting 60 seconds...")
                    time.sleep(60)
                    
                    # Retry after waiting
                    retry_response = requests.get(f"{archive_url}/pgn", headers=self.headers)
                    if retry_response.status_code == 200:
                        new_pgns += retry_response.text + "\n\n"
                    else:
                        logging.error(f"Failed to fetch PGNs after retry: {retry_response.status_code}")
                else:
                    logging.error(f"Failed to fetch PGNs: {response.status_code}")
            
            except Exception as e:
                logging.error(f"Error downloading archive {archive_url}: {e}")
        
        if not new_pgns.strip():
            logging.info("No new games found")
            return None
        
        # Save newly downloaded games to a separate file
        date_str = datetime.now().strftime("%Y.%m.%d")
        new_pgn_file = os.path.join(self.output_dir, f"{self.username}_GameArchive_{date_str}.pgn")
        
        with open(new_pgn_file, "w") as recent_file:
            recent_file.write(new_pgns)
        
        # Append to archive file
        with open(self.archive_file, "a") as archive:
            archive.write(new_pgns)
        
        # Count games (approximate by counting [Event tags)
        game_count = new_pgns.count('[Event "')
        logging.info(f"Added {game_count} games to archive")
        
        # Update last downloaded tracker
        self.save_last_downloaded_datetime()
        
        return new_pgn_file