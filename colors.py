"""
Color utilities for terminal output
Uses ANSI escape codes for terminal colors
"""

# ANSI color codes
class Colors:
    """ANSI color escape sequences"""
    # Reset
    RESET = '\033[0m'
    
    # Text colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright text colors
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Background colors
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'
    
    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'


def colorize(text: str, color: str, reset: bool = True) -> str:
    """
    Add color to text
    
    Args:
        text: Text to colorize
        color: Color code from Colors class
        reset: Whether to reset color after text (default: True)
    
    Returns:
        Colored text string
    """
    if reset:
        return f"{color}{text}{Colors.RESET}"
    return f"{color}{text}"


# Convenience functions for common use cases
def header(text: str) -> str:
    """Format header text (bold cyan)"""
    return colorize(text, Colors.BOLD + Colors.CYAN)


def title(text: str) -> str:
    """Format title text (bold bright blue)"""
    return colorize(text, Colors.BOLD + Colors.BRIGHT_BLUE)


def scraper_name(text: str) -> str:
    """Format scraper name (bold magenta)"""
    return colorize(text, Colors.BOLD + Colors.MAGENTA)


def price(text: str) -> str:
    """Format price (bright green)"""
    return colorize(text, Colors.BRIGHT_GREEN)


def url(text: str) -> str:
    """Format URL (cyan, underlined)"""
    return colorize(text, Colors.CYAN + Colors.UNDERLINE)


def error(text: str) -> str:
    """Format error message (bright red)"""
    return colorize(text, Colors.BRIGHT_RED)


def warning(text: str) -> str:
    """Format warning message (yellow)"""
    return colorize(text, Colors.YELLOW)


def success(text: str) -> str:
    """Format success message (green)"""
    return colorize(text, Colors.GREEN)


def info(text: str) -> str:
    """Format info message (blue)"""
    return colorize(text, Colors.BLUE)


def dim(text: str) -> str:
    """Format dim text (dim)"""
    return colorize(text, Colors.DIM)

