from Database_codes import init_dbs
from Api_connector import check_all_products
from miscalaneous import logging_setup

if __name__ == "__main__":
    logging_setup()
    init_dbs()
    check_all_products()