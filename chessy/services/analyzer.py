"""
Chess game analysis service for evaluating games with Stockfish and generating statistics.
"""
import os
import json
import csv
import logging
import chess
import chess.pgn
import chess.engine
import io
from collections import defaultdict, Counter
from ..utils.logging import emoji_log

class GameAnalyzer:
    """
    Analyzes chess games using Stockfish and generates statistics.
    """
    
    def __init__(self, config):
        """
        Initialize with configuration.
        
        Args:
            config: Application configuration including Stockfish path
        """
        self.config = config
        self.stockfish_path = config.STOCKFISH_PATH
        self.analysis_file = config.GAME_ANALYSIS_FILE
        self.eco_csv_file = config.ECO_CSV_FILE
        self.username = config.USERNAME
        self.logger = logging.getLogger(__name__)
        
        # Ensure analysis directory exists
        os.makedirs(os.path.dirname(self.analysis_file), exist_ok=True)
        
    def analyze_games(self, games_data):
        """
        Analyze a list of parsed games using Stockfish.
        
        Args:
            games_data: List of game data dictionaries
            
        Returns:
            list: Analysis results
        """
        analysis_results = []
        
        # Check if Stockfish is available
        if not self.stockfish_path or not os.path.exists(self.stockfish_path):
            emoji_log(self.logger, logging.WARNING, 
                     "Stockfish not available. Skipping detailed move analysis.", "⚠️")
            return analysis_results
        
        try:
            # Track error statistics
            error_counts = Counter({"Opening": 0, "Middlegame": 0, "Endgame": 0})
            time_trouble_blunders = 0
            
            with chess.engine.SimpleEngine.popen_uci(self.stockfish_path) as engine:
                for game_info in games_data:
                    # Get PGN text from source file
                    pgn_file = game_info.get("source_file")
                    if not pgn_file or not os.path.exists(pgn_file):
                        continue
                    
                    # Find this specific game in the file
                    with open(pgn_file, "r") as f:
                        pgn_text = f.read()
                    
                    pgn_io = io.StringIO(pgn_text)
                    while True:
                        game = chess.pgn.read_game(pgn_io)
                        if game is None:
                            break
                            
                        # Check if this is the right game by matching headers
                        headers = game.headers
                        if headers.get("Site") == game_info.get("site") and \
                           headers.get("Date") == game_info.get("date") and \
                           headers.get("White") == game_info.get("white") and \
                           headers.get("Black") == game_info.get("black"):
                            
                            # This is our game - analyze it
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
                            
                            # Add analysis results to game info
                            analysis_result = {
                                **game_info,
                                "blunders": blunders,
                                "inaccuracies": inaccuracies,
                                "move_count": move_count
                            }
                            analysis_results.append(analysis_result)
                            break  # Found and analyzed the game, move to next
            
            # Save analysis
            self._save_analysis_results(analysis_results)
            
            # Log summary
            emoji_log(self.logger, logging.INFO, f"Analyzed {len(analysis_results)} games", "✅")
            emoji_log(self.logger, logging.INFO, f"Blunders by phase: {dict(error_counts)}", "📊")
            emoji_log(self.logger, logging.INFO, f"Time-trouble blunders: {time_trouble_blunders}", "⏱️")
            
            return analysis_results
            
        except Exception as e:
            emoji_log(self.logger, logging.ERROR, f"Analysis error: {str(e)}", "❌")
            self.logger.exception("Detailed exception:")
            return []
    
    def _save_analysis_results(self, analysis_results):
        """
        Save analysis results to JSON file.
        
        Args:
            analysis_results: List of analysis result dictionaries
        """
        try:
            with open(self.analysis_file, "w") as f:
                json.dump(analysis_results, f, indent=4)
            emoji_log(self.logger, logging.INFO, 
                     f"Analysis results saved to {self.analysis_file}", "💾")
        except Exception as e:
            emoji_log(self.logger, logging.ERROR, 
                     f"Error saving analysis results: {str(e)}", "❌")
    
    def generate_eco_statistics(self, games_data):
        """
        Generate ECO code performance statistics.
        
        Args:
            games_data: List of parsed game data
            
        Returns:
            dict: ECO performance statistics
        """
        # Data structure: {ECO_code: {"White": [games, wins, draws, losses], "Black": [games, wins, draws, losses]}}
        eco_performance = defaultdict(lambda: {"White": [0,0,0,0], "Black": [0,0,0,0]})
        
        for game in games_data:
            eco = game.get("ECO", "")
            played_as = game.get("PlayedAs", "")
            result = game.get("Result", "")
            
            if not eco or not played_as or not result:
                continue
                
            if played_as == "White":
                eco_performance[eco]["White"][0] += 1  # games
                if result == "1-0":
                    eco_performance[eco]["White"][1] += 1  # wins
                elif result == "1/2-1/2":
                    eco_performance[eco]["White"][2] += 1  # draws
                elif result == "0-1":
                    eco_performance[eco]["White"][3] += 1  # losses
                    
            elif played_as == "Black":
                eco_performance[eco]["Black"][0] += 1  # games
                if result == "0-1":
                    eco_performance[eco]["Black"][1] += 1  # wins
                elif result == "1/2-1/2":
                    eco_performance[eco]["Black"][2] += 1  # draws
                elif result == "1-0":
                    eco_performance[eco]["Black"][3] += 1  # losses
        
        # Save to CSV
        try:
            with open(self.eco_csv_file, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Header
                writer.writerow([
                    "ECO",
                    "White_Games", "White_Wins", "White_Draws", "White_Losses",
                    "Black_Games", "Black_Wins", "Black_Draws", "Black_Losses",
                    "Total_Games"
                ])
                
                for eco_code, data in sorted(eco_performance.items()):
                    w_games, w_wins, w_draws, w_losses = data["White"]
                    b_games, b_wins, b_draws, b_losses = data["Black"]
                    total = w_games + b_games
                    writer.writerow([
                        eco_code,
                        w_games, w_wins, w_draws, w_losses,
                        b_games, b_wins, b_draws, b_losses,
                        total
                    ])
                
            emoji_log(self.logger, logging.INFO, 
                     f"ECO statistics saved to {self.eco_csv_file}", "💾")
        except Exception as e:
            emoji_log(self.logger, logging.ERROR, 
                     f"Error saving ECO statistics: {str(e)}", "❌")
        
        return dict(eco_performance)
    
    def get_statistics(self):
        """
        Get comprehensive game statistics from analysis results.
        
        Returns:
            dict: Various game statistics
        """
        if not os.path.exists(self.analysis_file):
            return {"total_games": 0}
            
        try:
            with open(self.analysis_file, "r") as f:
                analysis_results = json.load(f)
                
            total_games = len(analysis_results)
            wins = sum(1 for game in analysis_results 
                      if (game.get("PlayedAs") == "White" and game.get("Result") == "1-0") or
                         (game.get("PlayedAs") == "Black" and game.get("Result") == "0-1"))
            losses = sum(1 for game in analysis_results 
                        if (game.get("PlayedAs") == "White" and game.get("Result") == "0-1") or
                           (game.get("PlayedAs") == "Black" and game.get("Result") == "1-0"))
            draws = sum(1 for game in analysis_results if game.get("Result") == "1/2-1/2")
            
            # Calculate other statistics
            blunders = sum(game.get("blunders", 0) for game in analysis_results)
            inaccuracies = sum(game.get("inaccuracies", 0) for game in analysis_results)
            
            return {
                "total_games": total_games,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "blunders": blunders,
                "inaccuracies": inaccuracies,
                "win_percentage": round(wins / total_games * 100, 1) if total_games > 0 else 0
            }
        except Exception as e:
            self.logger.error(f"Error getting statistics: {str(e)}")
            return {"total_games": 0}
    
    def get_eco_performance(self):
        """
        Get ECO performance statistics from CSV file.
        
        Returns:
            list: List of ECO performance records
        """
        if not os.path.exists(self.eco_csv_file):
            return []
            
        try:
            eco_data = []
            with open(self.eco_csv_file, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    eco_data.append(row)
            return eco_data
        except Exception as e:
            self.logger.error(f"Error reading ECO statistics: {str(e)}")
            return []
