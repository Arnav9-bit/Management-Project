import csv
import logging
import json
import os
from datetime import datetime
from miscalaneous import safe_convert_price

# CSV file names
PRODUCT_DATA_CSV = 'amazon_product_data.csv'
PRODUCT_DETAILS_CSV = 'amazon_product_details.csv'
PRODUCT_REVIEWS_CSV = 'amazon_product_reviews.csv'

def init_dbs():
    """Initialize CSV files with headers if they don't exist."""
    # Product Data CSV
    if not os.path.exists(PRODUCT_DATA_CSV):
        with open(PRODUCT_DATA_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'id', 'product_name', 'asin', 'price', 'original_price', 'currency',
                'rating', 'review_count', 'url', 'image_url', 'availability',
                'sales_volume', 'date', 'raw_data'
            ])
    # Product Details CSV
    if not os.path.exists(PRODUCT_DETAILS_CSV):
        with open(PRODUCT_DETAILS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'id', 'asin', 'product_title', 'product_details', 'product_information',
                'product_photos', 'product_videos', 'date'
            ])
    # Product Reviews CSV
    if not os.path.exists(PRODUCT_REVIEWS_CSV):
        with open(PRODUCT_REVIEWS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'id', 'asin', 'review_id', 'review_title', 'review_comment',
                'review_star_rating', 'review_link', 'review_author', 'review_date',
                'is_verified_purchase', 'helpful_vote_statement', 'review_images', 'date'
            ])
    logging.info("All CSV files initialized.")

def save_product_data(product_name, asin, data):
    """Save product data to CSV."""
    try:
        data_dict = data.get("data", {})
        if not data_dict:
            logging.error(f"No product data found in API response for ASIN {asin}.")
            print(f"No product data found in API response for ASIN {asin}.")
            return

        price = safe_convert_price(data_dict.get("product_price", ""))
        original_price = safe_convert_price(data_dict.get("product_original_price", ""))
        currency = data_dict.get("currency", "")
        rating = float(data_dict.get("product_star_rating", 0)) if data_dict.get("product_star_rating") else None
        review_count = int(data_dict.get("product_num_ratings", 0)) if data_dict.get("product_num_ratings") else None
        url = data_dict.get("product_url", "")
        image_url = data_dict.get("product_photo", "")
        availability = data_dict.get("product_availability", "")
        sales_volume = data_dict.get("sales_volume", "")

        # Generate a unique ID (you can use a better method if needed)
        id = int(datetime.now().timestamp())

        with open(PRODUCT_DATA_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                id, product_name, asin, price, original_price, currency, rating,
                review_count, url, image_url, availability, sales_volume,
                datetime.now().isoformat(), json.dumps(data)
            ])
        logging.info(f"Saved to product_data: {product_name} at {price} {currency}, Rating: {rating}, Reviews: {review_count}")
        print(f"Saved to product_data: {product_name} at {price} {currency}, Rating: {rating}, Reviews: {review_count}")
    except Exception as e:
        logging.error(f"CSV Error (product_data): {e}")
        print(f"CSV Error (product_data): {e}")

import csv
import json
import os
from datetime import datetime

def save_product_details(asin, data):
    """Save product details to CSV, only if they don't exist or are different."""
    try:
        data_dict = data.get("data", {})
        if not data_dict:
            logging.error(f"No product details found in API response for ASIN {asin}.")
            print(f"No product details found in API response for ASIN {asin}.")
            return

        product_title = data_dict.get("product_title", "")
        new_product_details = json.dumps(data_dict.get("product_details", {}))
        new_product_information = json.dumps(data_dict.get("product_information", {}))
        new_product_photos = json.dumps(data_dict.get("product_photos", []))
        new_product_videos = json.dumps(data_dict.get("product_videos", []))

        # Check if the product already exists in the CSV
        existing_rows = []
        if os.path.exists(PRODUCT_DETAILS_CSV):
            with open(PRODUCT_DETAILS_CSV, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                existing_rows = [row for row in reader if row['asin'] == asin]

        # If the product exists, compare the details
        if existing_rows:
            existing_row = existing_rows[0]
            if (existing_row['product_details'] == new_product_details and
                existing_row['product_information'] == new_product_information and
                existing_row['product_photos'] == new_product_photos and
                existing_row['product_videos'] == new_product_videos):
                logging.info(f"Product details for ASIN {asin} are unchanged. Skipping.")
                print(f"Product details for ASIN {asin} are unchanged. Skipping.")
                return

        # If the product doesn't exist or details are different, append the new data
        with open(PRODUCT_DETAILS_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write header if the file is empty
            if os.stat(PRODUCT_DETAILS_CSV).st_size == 0:
                writer.writerow([
                    'id', 'asin', 'product_title', 'product_details',
                    'product_information', 'product_photos', 'product_videos', 'date'
                ])
            # Append the new data
            writer.writerow([
                int(datetime.now().timestamp()), asin, product_title,
                new_product_details, new_product_information,
                new_product_photos, new_product_videos, datetime.now().isoformat()
            ])
        logging.info(f"Saved to product_details: {product_title}")
        print(f"Saved to product_details: {product_title}")
    except Exception as e:
        logging.error(f"CSV Error (product_details): {e}")
        print(f"CSV Error (product_details): {e}")

def save_product_reviews(asin, data):
    """Save product reviews to CSV, only if they don't already exist."""
    try:
        reviews = data.get("data", {}).get("top_reviews", [])
        if not reviews:
            logging.info(f"No reviews found for ASIN {asin}.")
            print(f"No reviews found for ASIN {asin}.")
            return

        # Read existing reviews for this ASIN
        existing_review_ids = set()
        if os.path.exists(PRODUCT_REVIEWS_CSV):
            with open(PRODUCT_REVIEWS_CSV, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['asin'] == asin:
                        existing_review_ids.add(row['review_id'])

        # Append only new reviews
        new_reviews_count = 0
        with open(PRODUCT_REVIEWS_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write header if the file is empty
            if os.stat(PRODUCT_REVIEWS_CSV).st_size == 0:
                writer.writerow([
                    'id', 'asin', 'review_id', 'review_title', 'review_comment',
                    'review_star_rating', 'review_link', 'review_author', 'review_date',
                    'is_verified_purchase', 'helpful_vote_statement', 'review_images', 'date'
                ])
            for review in reviews:
                review_id = review.get("review_id", "")
                if review_id in existing_review_ids:
                    continue  # Skip if review already exists
                review_title = review.get("review_title", "")
                review_comment = review.get("review_comment", "")
                review_star_rating = float(review.get("review_star_rating", 0)) if review.get("review_star_rating") else None
                review_link = review.get("review_link", "")
                review_author = review.get("review_author", "")
                review_date = review.get("review_date", "")
                is_verified_purchase = 1 if review.get("is_verified_purchase") else 0
                helpful_vote_statement = review.get("helpful_vote_statement", "")
                review_images = json.dumps(review.get("review_images", []))

                # Append the new review
                writer.writerow([
                    int(datetime.now().timestamp()), asin, review_id, review_title,
                    review_comment, review_star_rating, review_link, review_author,
                    review_date, is_verified_purchase, helpful_vote_statement,
                    review_images, datetime.now().isoformat()
                ])
                new_reviews_count += 1

        logging.info(f"Saved {new_reviews_count} new reviews for ASIN {asin}.")
        print(f"Saved {new_reviews_count} new reviews for ASIN {asin}.")
    except Exception as e:
        logging.error(f"CSV Error (product_reviews): {e}")
        print(f"CSV Error (product_reviews): {e}")
