"""
Chess PGN parser module for extracting game metadata.
"""
import chess.pgn
import io
import json
import os
import logging
from ..utils.logging import emoji_log

class GameParser:
    """
    Parses PGN files and extracts game metadata.
    """
    
    def __init__(self, username, parsed_games_file):
        """
        Initialize with required parameters.
        
        Args:
            username: Chess.com username
            parsed_games_file: Path to save parsed game data
        """
        self.username = username
        self.parsed_games_file = parsed_games_file
        self.logger = logging.getLogger(__name__)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(parsed_games_file), exist_ok=True)
    
    def parse_games(self, pgn_file):
        """
        Parse a PGN file and extract game metadata.
        
        Args:
            pgn_file: Path to the PGN file
            
        Returns:
            list: List of dictionaries with game metadata
        """
        if not os.path.exists(pgn_file):
            emoji_log(self.logger, logging.ERROR, f"PGN file not found: {pgn_file}", "❌")
            return []
            
        games_data = []
        
        try:
            with open(pgn_file, "r") as file:
                pgn_text = file.read()
                
            pgn_io = io.StringIO(pgn_text)
            
            # Game counter for logging
            game_count = 0
            
            while True:
                game = chess.pgn.read_game(pgn_io)
                if game is None:
                    break
                    
                game_count += 1
                
                # Extract headers
                headers = game.headers
                white = headers.get("White", "Unknown")
                black = headers.get("Black", "Unknown")
                result = headers.get("Result", "N/A")
                date = headers.get("Date", "????-??-??")
                time_control = headers.get("TimeControl", "Unknown")
                eco = headers.get("ECO", "Unknown")
                opening = headers.get("Opening", "Unknown")
                termination = headers.get("Termination", "Unknown")
                
                # Determine which color the user played
                played_as = "White" if white == self.username else "Black"
                
                # Count moves
                num_moves = len(list(game.mainline_moves()))
                
                # Create game data dictionary
                game_data = {
                    "white": white,
                    "black": black,
                    "Result": result,
                    "date": date,
                    "TimeControl": time_control,
                    "ECO": eco,
                    "opening": opening,
                    "Termination": termination,
                    "NumMoves": num_moves,
                    "PlayedAs": played_as,
                    "source_file": pgn_file,
                    "site": headers.get("Site", "Unknown")
                }
                
                games_data.append(game_data)
                
            emoji_log(self.logger, logging.INFO, f"Parsed {game_count} games from {pgn_file}", "📊")
            
            # Save parsed data
            self.save_parsed_data(games_data)
            
            return games_data
            
        except Exception as e:
            emoji_log(self.logger, logging.ERROR, f"Error parsing PGN file: {str(e)}", "❌")
            self.logger.exception("Detailed error information:")
            return []
    
    def save_parsed_data(self, games_data):
        """
        Save parsed game data to a JSON file.
        
        Args:
            games_data: List of game data dictionaries
        """
        try:
            with open(self.parsed_games_file, "w") as json_file:
                json.dump(games_data, json_file, indent=4)
                
            emoji_log(self.logger, logging.INFO, 
                     f"Saved {len(games_data)} parsed games to {self.parsed_games_file}", "💾")
                     
        except Exception as e:
            emoji_log(self.logger, logging.ERROR, 
                     f"Error saving parsed game data: {str(e)}", "❌")
    
    def append_to_parsed_data(self, new_games_data):
        """
        Append new parsed game data to existing data file.
        
        Args:
            new_games_data: List of new game data dictionaries
            
        Returns:
            list: Combined game data list
        """
        if not new_games_data:
            return []
            
        # Read existing data if available
        existing_data = []
        if os.path.exists(self.parsed_games_file):
            try:
                with open(self.parsed_games_file, "r") as json_file:
                    existing_data = json.load(json_file)
            except Exception as e:
                emoji_log(self.logger, logging.WARNING, 
                         f"Could not read existing parsed data: {str(e)}", "⚠️")
        
        # Combine data (avoiding duplicates)
        existing_games = {self._game_identifier(game): game for game in existing_data}
        new_games = {self._game_identifier(game): game for game in new_games_data}
        
        # Merge dictionaries (new games will overwrite existing ones with same ID)
        all_games = {**existing_games, **new_games}
        combined_data = list(all_games.values())
        
        # Save combined data
        try:
            with open(self.parsed_games_file, "w") as json_file:
                json.dump(combined_data, json_file, indent=4)
                
            emoji_log(self.logger, logging.INFO, 
                     f"Updated parsed data with {len(new_games_data)} new games. Total: {len(combined_data)}", "📈")
                     
        except Exception as e:
            emoji_log(self.logger, logging.ERROR, 
                     f"Error saving updated parsed data: {str(e)}", "❌")
        
        return combined_data
    
    def _game_identifier(self, game):
        """
        Create a unique identifier for a game.
        
        Args:
            game: Game data dictionary
            
        Returns:
            str: Unique game identifier
        """
        # Combine site, date, white player, black player as unique ID
        site = game.get("site", "")
        date = game.get("date", "")
        white = game.get("white", "")
        black = game.get("black", "")
        
        return f"{site}_{date}_{white}_{black}"
