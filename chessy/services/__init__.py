"""
Core service module for managing Chess.com game processing pipeline.
"""
import logging
import os
from ..utils.logging import emoji_log

class ChessyService:
    """
    Core service class to orchestrate the chess game processing workflow.
    Acts as a facade to coordinate downloading, parsing, and analysis.
    """
    
    def __init__(self, downloader, parser, analyzer, config):
        """
        Initialize the service with required components.
        
        Args:
            downloader: ChessComDownloader instance
            parser: GameParser instance
            analyzer: GameAnalyzer instance
            config: Application configuration
        """
        self.downloader = downloader
        self.parser = parser
        self.analyzer = analyzer
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def check_for_updates(self, filters=None):
        """
        Check for new games and return the number of new games found.
        
        Args:
            filters (dict, optional): Filtering criteria like date range and time control
            
        Returns:
            int: Number of new games found
        """
        emoji_log(self.logger, logging.INFO, f"Checking for new games for {self.config.USERNAME}...", "🔍")
        
        # Apply filters if provided
        if filters:
            filter_msg = []
            if 'start_date' in filters and 'end_date' in filters:
                filter_msg.append(f"date range: {filters['start_date']} to {filters['end_date']}")
            if 'time_control' in filters:
                filter_msg.append(f"time control: {filters['time_control']}")
            
            if filter_msg:
                emoji_log(self.logger, logging.INFO, f"Using filters: {', '.join(filter_msg)}", "🔍")
        
        new_pgn_file = self.downloader.fetch_and_save_games(filters=filters)
        
        if new_pgn_file and os.path.exists(new_pgn_file):
            # Count number of games in the file (approximate by counting [Event tags)
            with open(new_pgn_file, 'r') as f:
                content = f.read()
                game_count = content.count('[Event "')
            return game_count
        return 0
    
    def process_new_games(self):
        """
        Process games through the full pipeline.
        
        Returns:
            dict: Processing results with metrics
        """
        emoji_log(self.logger, logging.INFO, "Starting game processing pipeline", "🚀")
        results = {
            "new_games": 0,
            "parsed_games": 0,
            "analyzed_games": 0,
            "openings_analyzed": 0
        }
        
        # For analysis, use the full archive file, not just new games
        main_archive = self.config.ARCHIVE_FILE
        
        if not os.path.exists(main_archive):
            emoji_log(self.logger, logging.WARNING, "No game archive found. Please download games first.", "⚠️")
            return results
            
        # Step 1: Parse games from the main archive
        emoji_log(self.logger, logging.INFO, f"Parsing games from main archive: {main_archive}", "📊")
        games_data = self.parser.parse_games(main_archive)
        results["parsed_games"] = len(games_data)
        
        # Step 2: Analyze games
        if games_data:
            emoji_log(self.logger, logging.INFO, f"Analyzing {len(games_data)} games...", "🧠")
            analysis_results = self.analyzer.analyze_games(games_data)
            results["analyzed_games"] = len(analysis_results) if analysis_results else 0
            
            # Step 3: Generate ECO statistics
            emoji_log(self.logger, logging.INFO, "Generating opening statistics...", "📈")
            eco_stats = self.analyzer.generate_eco_statistics(games_data)
            results["openings_analyzed"] = len(eco_stats) if eco_stats else 0
        
        emoji_log(self.logger, logging.INFO, "Game processing completed successfully", "✅")
        return results
    
    def get_game_statistics(self):
        """
        Get comprehensive game statistics for dashboard display.
        
        Returns:
            dict: Various game statistics
        """
        return self.analyzer.get_statistics()
    
    def get_opening_performance(self):
        """
        Get opening (ECO) performance statistics.
        
        Returns:
            dict: ECO performance data
        """
        return self.analyzer.get_eco_performance()
    
    def get_game_counts(self):
        """
        Get counts of total games, wins, losses, and draws.
        
        Returns:
            dict: Game count statistics
        """
        stats = self.analyzer.get_statistics()
        return {
            "total": stats.get("total_games", 0),
            "wins": stats.get("wins", 0),
            "losses": stats.get("losses", 0),
            "draws": stats.get("draws", 0)
        }