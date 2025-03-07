# Chessy - Developer Guide

## Architecture Overview

Chessy is a Flask-based web application for analyzing Chess.com games with the following architecture:

```
chessy/
├── config.py           # Configuration management
├── server.py           # Main Flask app & routes
├── downloader.py       # Chess.com API client
├── api/                # API endpoints
├── services/           # Core business logic
│   ├── analyzer.py     # Chess position analysis
│   ├── downloader.py   # Enhanced downloader
│   └── parser.py       # PGN parsing
├── static/             # Static assets
│   ├── css/            # Stylesheets
│   ├── js/             # JavaScript
│   └── img/            # Images
├── templates/          # Jinja2 templates
└── utils/              # Utility functions
    └── logging.py      # Logging helpers
```

## Core Components

### 1. Config (`config.py`)

Manages application configuration using environment variables and `.env` file:
- User configuration (Chess.com username, contact email)
- File paths and directory structure
- API request headers
- Stockfish integration settings

### 2. Server (`server.py`)

The Flask application handling:
- HTTP routes and templates
- Background task management for long-running processes
- API endpoints for frontend data access
- Error handling

### 3. Downloader (`downloader.py` and `services/downloader.py`)

Handles communication with the Chess.com API:
- Fetches archives of user games
- Downloads PGN files
- Tracks already downloaded content to avoid duplication
- Implements rate limiting and error handling

### 4. Analyzer (`services/analyzer.py`)

Processes chess games to extract insights:
- Identifies mistakes (blunders and inaccuracies)
- Generates opening statistics
- Tracks performance metrics
- Integrates with Stockfish for position evaluation

### 5. Parser (`services/parser.py`)

Parses PGN files and extracts structured data:
- Game metadata extraction
- Move extraction and counting
- ECO code handling

## Development Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/IlliquidAsset/chessy.git
   cd chessy
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -e .  # Install in development mode
   ```

3. Configure environment variables:
   ```bash
   cp example.env .env
   # Edit .env with your settings
   ```

4. Run the development server:
   ```bash
   python chessy/server.py
   ```

## Key Libraries and Dependencies

- **Flask**: Web framework
- **python-chess**: Chess game parsing and analysis
- **requests**: HTTP client for API interactions
- **python-dotenv**: Environment variable management
- **pandas**: Data manipulation
- **plotly**: Data visualization
- **stockfish**: Chess position evaluation (optional)

## Code Style and Best Practices

- Follow PEP 8 for Python code style
- Use clear docstrings in Google style format
- Organize CSS with BEM methodology
- Use modern ES6+ JavaScript
- Keep functions focused on a single responsibility
- Add appropriate error handling
- Include logging at critical points

## Background Processing

Long-running tasks like game downloading and analysis run as background threads:
- Implemented in `server.py` as `download_thread` and `analyze_thread`
- Progress tracking via shared state in `background_tasks` dictionary
- API endpoint `/api/progress` for frontend to monitor status

## Testing

Currently, the project lacks formal tests. Contributions in this area would be valuable:
- Unit tests for isolated components
- Integration tests for API endpoints
- End-to-end tests for critical workflows

## Adding New Features

When adding new features:

1. Create a new branch from `main`
2. Update required modules
3. Add necessary API endpoints in `server.py`
4. Create or update templates
5. Add any static assets
6. Update documentation
7. Submit a pull request

## Common Development Tasks

### Adding a New API Endpoint

```python
@app.route("/api/new_endpoint")
def new_endpoint():
    # Implementation
    return jsonify(result)
```

### Creating a New Module

1. Add your module to the appropriate directory
2. Import it in the relevant files
3. Initialize in `server.py` if needed

### Updating Frontend

1. Modify templates in `templates/`
2. Add/update JavaScript in `static/js/`
3. Update styles in `static/css/styles.css`

## Troubleshooting Development Issues

- **Flask debugging**: Enable debug mode for detailed error pages
- **API issues**: Check network tab in browser devtools
- **Dependencies**: Verify all requirements are installed
- **Configuration**: Ensure environment variables are set correctly