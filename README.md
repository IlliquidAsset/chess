# Chessy - Chess.com Game Analysis Tool

A powerful Python application for downloading, analyzing, and visualizing your Chess.com games.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-alpha-orange.svg)

## 🔹 Features

- 🏆 **Comprehensive Game Download**: Fetches all your Chess.com games, automatically skipping duplicates
- 📊 **Advanced Analysis**: Identifies blunders, inaccuracies, and patterns in your play
- 🎮 **Opening Statistics**: Tracks your performance with different chess openings
- 📈 **Visualizations**: Win rates, mistake frequency, and performance over time
- 🎯 **Stockfish Integration**: Optional engine analysis for deeper insights

## 🔹 Quick Start

1. **Install**
   ```bash
   # Clone repository
   git clone https://github.com/yourusername/chessy.git
   cd chessy
   
   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Configure**
   ```bash
   # Create .env file with your username
   echo "CHESSCOM_USERNAME=your_username" > .env
   echo "CHESSCOM_CONTACT_EMAIL=your_email@example.com" >> .env
   
   # Optional: Add Stockfish path for analysis
   echo "STOCKFISH_PATH=/path/to/stockfish" >> .env
   ```

3. **Run**
   ```bash
   python chessy/server.py
   ```

4. **Use**
   - Open your browser to `http://localhost:5000`
   - Click "Download New Games" to fetch your history
   - Click "Analyze Games" to process and generate insights

## 🔹 Documentation

- [User Guide](docs/USER_GUIDE.md) - Detailed instructions for using Chessy
- [Developer Guide](docs/DEVELOPER_GUIDE.md) - Architecture and contribution information
- [Roadmap](docs/ROADMAP.md) - Upcoming features and development plan

## 🔹 Screenshots

<table>
  <tr>
    <td><img src="docs/img/dashboard.png" alt="Dashboard" width="100%"/></td>
    <td><img src="docs/img/openings.png" alt="Opening Analysis" width="100%"/></td>
  </tr>
  <tr>
    <td><img src="docs/img/games.png" alt="Game List" width="100%"/></td>
    <td><img src="docs/img/mistakes.png" alt="Mistake Analysis" width="100%"/></td>
  </tr>
</table>

## 🔹 Requirements

- Python 3.8+
- Flask 2.0+
- python-chess 1.5+
- requests 2.25+
- Optional: Stockfish chess engine for move analysis

## 🔹 Contributing

Contributions are welcome! See our [Developer Guide](docs/DEVELOPER_GUIDE.md) and [Roadmap](docs/ROADMAP.md) for details on how to get started.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🔹 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔹 Acknowledgments

- [python-chess](https://python-chess.readthedocs.io/) for PGN parsing and chess utilities
- [Chess.com API](https://www.chess.com/news/view/published-data-api) for game data access
- [Stockfish](https://stockfishchess.org/) for chess position evaluation