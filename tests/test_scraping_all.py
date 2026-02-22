#!/usr/bin/env python3
from scraper import search_multiple_books
from config import ScraperConfig


def main():
    isbns = ["9781234567890"]  # заведомо несуществующий ISBN
    config = ScraperConfig()
    config.verbose = True
    config.headless = False
    config.max_tabs = 2
    config.api_max_concurrent = 2
    results = search_multiple_books(isbns, config)
    for isbn, res in zip(isbns, results):
        print(f"{isbn}: {res}")


if __name__ == "__main__":
    main()
