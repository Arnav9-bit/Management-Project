import logging
import requests
import json
from Database_codes import save_product_data, save_product_details, save_product_reviews

COUNTRY = "IN"  # India
LANGUAGE = "en_IN"
RAPIDAPI_KEY = "768437f4a7mshd0cb3a484b12e02p19a030jsn15b7afd49721"
RAPIDAPI_HOST = "real-time-amazon-data.p.rapidapi.com"
PRODUCTS = [
    {"name": "boAt Nirvana Zenith Pro (2025)", "asin": "B0DXPL5XHF"},
    {"name": "Noise Air Clips Wireless Open Ear Earbuds with Chrome Finish", "asin": "B0DGV56J6G"},
    {"name": "boAt Nirvana Ion ANC Pro", "asin": "	B0DN171184"},
    {"name": "Noise Newly Launched Air Buds Pro 6", "asin": "B0DHH96NBB"},
    {"name": "boAt Nirvana Ivy", "asin": "	B0DBHD2F5R"},
    {"name": "Noise Newly Launched Air Clips 2", "asin": "	B0F673HNLP"},
    {"name": "boAt Nirvana X TWS (2025)", "asin": "B0DQKY3R84"},
    {"name": "Noise Newly Launched Air Buds 6", "asin": "B0DGV55W2K"},
    {"name": "Noise Newly Launched Air Buds Pro 6 in Ear Truly Wireless Earbuds with Hybrid ANC (up to 49dB)", "asin": "B0DHHDW7FV"},
]

def get_product_data(asin):
    url = "https://real-time-amazon-data.p.rapidapi.com/product-details"
    querystring = {"asin": asin, "country": COUNTRY, "language": LANGUAGE}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        if response.status_code == 200:
            #print(f"API Response for ASIN {asin}:")
            #print(json.dumps(response.json(), indent=2))
            return response.json()
        else:
            logging.error(f"API Error for ASIN {asin}: {response.status_code} - {response.text}")
            print(f"API Error for ASIN {asin}: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.ReadTimeout:
        logging.error(f"Timeout for ASIN {asin}. Retrying with longer timeout...")
        print(f"Timeout for ASIN {asin}. Retrying with longer timeout...")
        try:
            response = requests.get(url, headers=headers, params=querystring, timeout=60)
            if response.status_code == 200:
                print(f"API Response for ASIN {asin} (retry):")
                print(json.dumps(response.json(), indent=2))
                return response.json()
            else:
                logging.error(f"API Error for ASIN {asin} (retry): {response.status_code} - {response.text}")
                print(f"API Error for ASIN {asin} (retry): {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logging.error(f"Request Error for ASIN {asin} (retry): {e}")
            print(f"Request Error for ASIN {asin} (retry): {e}")
            return None
    except Exception as e:
        logging.error(f"Request Error for ASIN {asin}: {e}")
        print(f"Request Error for ASIN {asin}: {e}")
        return None
    

def check_all_products():
    print("Starting product data check...")
    logging.info("Starting product data check...")
    for product in PRODUCTS:
        print(f"Fetching data for {product['name']} (ASIN: {product['asin']})...")
        data = get_product_data(product["asin"])
        if not data:
            logging.warning(f"No data found for {product['name']} (ASIN: {product['asin']})")
            print(f"No data found for {product['name']} (ASIN: {product['asin']})")
            continue
        try:
            save_product_data(product["name"], product["asin"], data)
            save_product_details(product["asin"], data)
            save_product_reviews(product["asin"], data)
        except Exception as e:
            logging.error(f"Error processing {product['name']}: {e}")
            print(f"Error processing {product['name']}: {e}")
    print("Product data check completed.")