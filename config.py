"""
Application Configuration 
"""

from pathlib import Path

# root directory 
BASE_DIR = Path(__file__).resolve().parent

# project folders 
LOG_DIR = BASE_DIR / "logs"
OUTPUT_DIR = BASE_DIR / "output"

# network 
TIMEOUT = 30

# user agent 
USER_AGENT = (
 "Partner Intelligence Bot/1.0"
)