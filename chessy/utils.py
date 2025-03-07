import logging
import os
import sys
from datetime import datetime

def setup_logging(output_dir="output", log_level=logging.INFO):
    """
    Configure logging to both file and console with appropriate formatting.
    
    Args:
        output_dir: Directory to store log files
        log_level: Logging level (default: INFO)
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(output_dir, f"chessy_{timestamp}.log")
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with a higher log level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_format)
    
    # Create file handler which logs even debug messages
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    
    # Add the handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    logging.info(f"Logging initialized. Log file: {log_file}")
    return logger

def emoji_log(logger, level, message, emoji=""):
    """
    Log a message with an optional emoji prefix.
    
    Args:
        logger: Logger instance
        level: Logging level (e.g., logging.INFO)
        message: Message to log
        emoji: Optional emoji prefix
    """
    if emoji:
        message = f"{emoji} {message}"
    
    if level == logging.DEBUG:
        logger.debug(message)
    elif level == logging.INFO:
        logger.info(message)
    elif level == logging.WARNING:
        logger.warning(message)
    elif level == logging.ERROR:
        logger.error(message)
    elif level == logging.CRITICAL:
        logger.critical(message)

        ################################################################################
# IV. UTILITY FUNCTIONS
################################################################################

def format_time_control(seconds):
    """
    Format time control from seconds to minutes.
    
    Args:
        seconds (str or int): Time control in seconds, possibly with increment (e.g. "300+2")
        
    Returns:
        str: Formatted time control (e.g. "5min +2sec")
    """
    if not seconds:
        return "Unknown"
    
    # Parse the time control
    base_time = 0
    increment = 0
    
    try:
        if isinstance(seconds, str):
            if '+' in seconds:
                parts = seconds.split('+')
                base_time = int(parts[0])
                increment = int(parts[1])
            else:
                base_time = int(seconds)
        else:
            base_time = int(seconds)
    except (ValueError, TypeError):
        return str(seconds)  # Return original if parsing fails
    
    # Convert to minutes and seconds
    minutes = base_time // 60
    remaining_seconds = base_time % 60
    
    # Format the display
    display = []
    if minutes > 0:
        display.append(f"{minutes}min")
    
    if remaining_seconds > 0 or minutes == 0:
        display.append(f"{remaining_seconds}sec")
    
    result = " ".join(display)
    
    if increment > 0:
        result += f" +{increment}sec"
    
    return result

def categorize_time_control(seconds):
    """
    Categorize time control into standard categories.
    
    Args:
        seconds (str or int): Time control in seconds
        
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