# src/core/logging_setup.py
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from src.core.config import settings

def setup_logging():
    """
    Configures the standard Python logging module.
    - Console: INFO level (Clean output for you to see)
    - File: DEBUG level (Detailed output for debugging errors)
    """
    
    # 1. Create Log Directory if it doesn't exist
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    log_file_path = os.path.join(settings.LOG_DIR, "app.log")

    # 2. Define the Log Format
    # Format: [Time] [Level] [Module:Line] - Message
    log_format = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(module)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 3. Create Handlers
    
    # A. File Handler (Rotates after 5MB, keeps 3 backup files)
    file_handler = RotatingFileHandler(
        log_file_path, maxBytes=5*1024*1024, backupCount=3
    )
    file_handler.setLevel(logging.DEBUG) # Captures everything
    file_handler.setFormatter(log_format)

    # B. Console Handler (Standard Output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO) # Only shows important stuff
    console_handler.setFormatter(log_format)

    # 4. Apply to Root Logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG) # Set root to lowest level to capture all
    
    # Remove existing handlers to avoid duplicates if function is called twice
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Log a startup message to prove it's writing to file
    logging.info(f"Logging initialized. Writing to: {log_file_path}")