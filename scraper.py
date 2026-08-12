"""Generic Playwright scraper driven entirely by CLI args / env vars.

Intended to be run headlessly from a GitHub Actions workflow_dispatch job.
No target URL, selector, or output path is ever hard-coded here.
"""

import argparse
import csv
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("scraper")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape a page with Playwright and write results to CSV.")
    parser.add_argument(
        "--url",
        default=os.environ.get("TARGET_URL"),
        help="Target URL to scrape. Falls back to the TARGET_URL env var.",
    )
    parser.add_argument(
        "--selector",
        default=os.environ.get("SELECTOR"),
        help="CSS selector for the elements to extract. Falls back to the SELECTOR env var.",
    )
    parser.add_argument(
        "--wait-selector",
        default=os.environ.get("WAIT_SELECTOR") or None,
        help="Optional CSS selector to wait for before scraping (for dynamic pages). "
        "Falls back to the WAIT_SELECTOR env var.",
    )
    parser.add_argument(
        "--scroll-times",
        type=int,
        default=int(os.environ.get("SCROLL_TIMES", "0")),
        help="Number of times to scroll to the bottom of the page to trigger lazy-loading (default: 0).",
    )
    parser.add_argument(
        "--scroll-wait-ms",
        type=int,
        default=int(os.environ.get("SCROLL_WAIT_MS", "1000")),
        help="Milliseconds to wait after each scroll for new content to load (default: 1000).",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=int(os.environ.get("TIMEOUT_MS", "30000")),
        help="Navigation / wait timeout in milliseconds (default: 30000).",
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("OUTPUT_PATH", "output/result.csv"),
        help="Path to the output CSV file (default: output/result.csv).",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not args.url:
        raise ValueError("Missing target URL. Pass --url or set the TARGET_URL env var.")
    parsed = urlparse(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"Invalid target URL: {args.url!r}")
    if not args.selector:
        raise ValueError("Missing CSS selector. Pass --selector or set the SELECTOR env var.")


def scroll_page(page, times: int, wait_ms: int) -> None:
    if times <= 0:
        return
    log.info("Scrolling page up to %d time(s) to load more content...", times)
    previous_height = page.evaluate("document.body.scrollHeight")
    for i in range(1, times + 1):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(wait_ms)
        new_height = page.evaluate("document.body.scrollHeight")
        log.info("Scroll %d/%d: page height %d -> %d", i, times, previous_height, new_height)
        if new_height == previous_height:
            log.info("Page height stopped changing, stopping scroll early.")
            break
        previous_height = new_height


def scrape(args: argparse.Namespace) -> list[dict]:
    rows: list[dict] = []
    with sync_playwright() as p:
        log.info("Launching headless Chromium...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            log.info("Navigating to %s", args.url)
            page.goto(args.url, timeout=args.timeout_ms, wait_until="domcontentloaded")

            if args.wait_selector:
                log.info("Waiting for selector: %s", args.wait_selector)
                page.wait_for_selector(args.wait_selector, timeout=args.timeout_ms)

            scroll_page(page, args.scroll_times, args.scroll_wait_ms)

            log.info("Querying selector: %s", args.selector)
            elements = page.query_selector_all(args.selector)
            log.info("Found %d element(s) matching selector.", len(elements))

            for el in elements:
                text = (el.text_content() or "").strip()
                href = el.get_attribute("href")
                rows.append({"text": text, "href": href or ""})

        except PlaywrightTimeoutError as exc:
            log.error("Timed out while loading/waiting on the page: %s", exc)
            raise
        except PlaywrightError as exc:
            log.error("Playwright error while scraping: %s", exc)
            raise
        finally:
            save_debug_screenshot(page, args.output)
            browser.close()

    return rows


def save_debug_screenshot(page, output_path: str) -> None:
    screenshot_path = Path(output_path).parent / "debug_screenshot.png"
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        log.info("Saved debug screenshot to %s", screenshot_path)
    except PlaywrightError as exc:
        log.warning("Failed to save debug screenshot: %s", exc)


def write_csv(rows: list[dict], output_path: str) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "href"])
        writer.writeheader()
        writer.writerows(rows)
    log.info("Wrote %d row(s) to %s", len(rows), out)


def main() -> int:
    args = parse_args()
    try:
        validate_args(args)
    except ValueError as exc:
        log.error("Invalid arguments: %s", exc)
        return 2

    log.info(
        "Starting scrape: url=%s selector=%s wait_selector=%s scroll_times=%d",
        args.url,
        args.selector,
        args.wait_selector,
        args.scroll_times,
    )

    try:
        rows = scrape(args)
    except Exception:
        log.error("Scraping failed.")
        return 1

    if not rows:
        log.warning("No elements matched the selector; writing an empty CSV.")

    write_csv(rows, args.output)
    log.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
