# Chessy - User Guide

## Overview

Chessy is a tool for downloading, analyzing, and visualizing your Chess.com games. It provides insights into your playing patterns, helps identify strengths and weaknesses, and tracks your progress over time.

## Getting Started

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/chessy.git
   cd chessy
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your configuration:
   - Create a `.env` file in the root directory
   - Add your Chess.com username:
     ```
     CHESSCOM_USERNAME=your_username
     CHESSCOM_CONTACT_EMAIL=your_email@example.com
     ```
   - Optional: Set path to Stockfish for move analysis:
     ```
     STOCKFISH_PATH=/path/to/stockfish
     ```

4. Start the server:
   ```bash
   python chessy/server.py
   ```

5. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Features

### Dashboard

The dashboard provides an overview of your chess performance:
- Total games, wins, losses, and draws statistics
- Win rate by time control
- Mistakes overview

### Downloading Games

Click the "Download New Games" button on the dashboard to fetch your latest Chess.com games. This process:
- Downloads all available games from your Chess.com account
- Ensures only new games are downloaded on each run
- Stores games in PGN format for future analysis

### Game Analysis

Click the "Analyze Games" button to perform detailed analysis of your chess games. This will:
- Process each game to identify blunders and inaccuracies
- Generate statistics about your play in different phases (opening, middlegame, endgame)
- Create opening repertoire statistics

The analysis process may take several minutes for large collections of games. A progress bar shows completion status.

### Game List

The Games tab displays a list of all your downloaded games with:
- Date, opponent, result, ECO code, and time control
- Filtering and sorting options
- Ability to search games

### Opening Analysis

The Openings tab provides statistics about your performance with different chess openings:
- Win rates by ECO code
- Performance as White vs. Black
- Games played with each opening

### Mistake Analysis

The Analysis menu provides detailed information about mistakes in your games:
- Blunders tab: Shows most common blunders and problematic time controls
- Inaccuracies tab: Tracks less serious mistakes
- Mistakes Overview: Comprehensive view of error patterns

## Tips

1. **First-time setup**: On first run, click "Download New Games" to fetch your complete game history.
2. **Regular updates**: Run "Download New Games" periodically to keep your database current.
3. **Stockfish integration**: For detailed analysis, ensure Stockfish is installed and configured.
4. **Large collections**: For users with thousands of games, the initial download and analysis may take significant time.

## Troubleshooting

- **Download errors**: Check your internet connection and Chess.com username in .env
- **Analysis errors**: Verify Stockfish path if configured
- **Application not starting**: Ensure all dependencies are installed correctly
- **Empty statistics**: Run "Download New Games" followed by "Analyze Games"