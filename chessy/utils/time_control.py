"""
Time control utilities for chess game formats.
"""

def format_time_control(seconds):
    """
    Format time control from seconds to minutes.
    
    Args:
        seconds (str or int): Time control in seconds, possibly with increment (e.g. "300+2" or "3|2")
        
    Returns:
        str: Formatted time control (e.g. "5min +2sec (Blitz)")
    """
    if not seconds:
        return "Unknown"
    
    # Parse the time control
    base_time = 0
    increment = 0
    original_format = str(seconds)
    
    try:
        if isinstance(seconds, str):
            if '+' in seconds:
                parts = seconds.split('+')
                base_time = int(parts[0])
                increment = int(parts[1])
            elif '|' in seconds:  # Handle Chess.com's "3|2" format
                parts = seconds.split('|')
                base_time = int(parts[0]) * 60  # Convert minutes to seconds
                increment = int(parts[1])
            else:
                base_time = int(seconds)
        else:
            base_time = int(seconds)
    except (ValueError, TypeError):
        return original_format  # Return original if parsing fails
    
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
    
    # Add category
    category = categorize_time_control(seconds)
    if category != "unknown":
        result += f" ({category.title()})"
    
    return result

def categorize_time_control(seconds):
    """
    Categorize time control into Chess.com standard categories.
    
    Args:
        seconds (str or int): Time control in seconds or format like "180+2"
        
    Returns:
        str: Category (bullet, blitz, rapid, daily)
    """
    # Parse the time control
    base_time = 0
    
    try:
        if isinstance(seconds, str):
            if '+' in seconds:
                parts = seconds.split('+')
                base_time = int(parts[0])
            elif '|' in seconds:  # Handle Chess.com's "3|2" format (3 min + 2 sec increment)
                parts = seconds.split('|')
                base_time = int(parts[0]) * 60  # Convert minutes to seconds
            else:
                base_time = int(seconds)
        else:
            base_time = int(seconds)
    except (ValueError, TypeError):
        return "unknown"
    
    # Convert to minutes
    minutes = base_time / 60
    
    # Daily games have very long time controls (1+ days)
    if minutes >= 1440:  # 24 hours or more
        return "daily"
    
    # Chess.com categories
    if minutes < 3:
        return "bullet"
    elif minutes < 10:
        return "blitz"
    elif minutes < 30:
        return "rapid"
    else:
        return "classical"