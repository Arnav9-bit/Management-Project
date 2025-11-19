import logging
import os
from datetime import datetime

# Makes the price recieved from the api readable
def safe_convert_price(price_str):
    if not price_str:
        return None
    try:
        return float(price_str.replace("₹", "").replace(",", ""))
    except Exception as e:
        logging.error(f"Error converting price: {e}")
        return None

def logging_setup():
    
    # Create a logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Log file name with timestamp
    LOG_FILE = f"logs/amazon_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),  # Log to file
            logging.StreamHandler()         # Log to console
        ]
    )

    # Example usage:
    logging.info("Logging is configured. Log file: %s", LOG_FILE)
