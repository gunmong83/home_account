import os
import sys
import asyncio
import argparse
from playwright.async_api import async_playwright
from datetime import datetime

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import existing parser
import parser.naverpay as naverpay_parser
import config

async def check_login_status(page) -> bool:
    """Check if user has logged in by checking for specific elements."""
    try:
        # Check for logout button (appears when logged in)
        try:
            logout_btn = await page.wait_for_timeout('a#gnb_logout_button', 5000)
        if logout_btn:
                return True
        except:
            pass
        
        # Check for Naver Pay specific indicators
        url = page.url
        if "pay.naver.com" in url or "www.naver.com" in url:
            # Check for profile menu on Naver Pay page
            try:
                my_menu = await page.wait_for_timeout('[class*="MyMenu"]', 5000)
                if my_menu:
                    return True
            except:
                pass
        
        return False
    except:
        return False

async def fetch_points_with_filter(page, owner: str) -> list:
    """
    Fetch points from Naver Pay with date filter support.
    Handles:
    1. Period filter (기간선택) - specific month/year range
    2. Date range (날짜 범위) - All
    3. "All" (전체) button to get all history
    """
    print(f"[{owner}] Navigating to Points page...")
    await page.goto("https://new-m.pay.naver.com/pointshistory/list?depth2Slug=depth2_all")
    await page.wait_for_load_state("networkidle")
    
    # Check for "전체" (All) button to show entire history
    try:
        all_button = await page.wait_for_timeout('button:has-text("전체")', 10000)
        if all_button:
            print(f"[{owner}] Found '전체' (All) button")
            await all_button.click()
            await asyncio.sleep(3)
            await page.wait_for_load_state("networkidle")
    except:
        print(f"[{owner}] '전체' button not found or click failed")
    finally:
        await page.wait_for_load_state("networkidle")
        finally:
            await page.wait_for_load_state("networkidle")
    
    # Scroll to load more points
    scroll_count = config.NAVERPAY_SCROLL_COUNT_POINTS
    print(f"[{owner}] Scrolling {scroll_count} times to load all points...")
    for i in range(scroll_count):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)
    
    # Get HTML and parse
    html = await page.content()
    items = naverpay_parser.parse_points_html(html, owner)
    
    print(f"[{owner}] Extracted {len(items)} points")
    return items

async def main():
    parser = argparse.ArgumentParser(description="Naver Pay Points Fetcher with Date Filter")
    parser.add_argument("--owner", required=True, help="taewoo or chaeyoung")
    parser.add_argument("--filter", choices=["all", "period"], default="all", 
                       help="Filter type: all (전체), period (기간선택)")
    parser.add_argument("--period", help="Period: e.g., 2026-01 (for period filter)")
    
    args = parser.parse_args()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--remote-debugging-port=9222"] if args.owner == "taewoo" else []
        )
        page = await browser.new_page()
        
        try:
            # Check login status first
            is_logged_in = await check_login_status(page)
            
            if not is_logged_in:
                print(f"[{args.owner}] Not logged in. Please log in first.")
                print(f"[{args.owner}] Press ENTER after logging in to continue...")
                # Wait for user to press ENTER
                await asyncio.to_thread(input, f"[{args.owner}] Logged in? Press ENTER to continue...")
            else:
                print(f"[{args.owner}] Already logged in. Proceeding to fetch points...")
            
            # Navigate to points page
            if args.filter == "period" and args.period:
                # User specified a period, use the existing approach
                await page.goto("https://new-m.pay.naver.com/pointshistory/list?depth2Slug=depth2_all")
                await page.wait_for_load_state("networkidle")
                print(f"[{args.owner}] Period filter specified, fetching data...")
                
                # Scroll to load more points
                scroll_count = config.NAVERPAY_SCROLL_COUNT_POINTS
                print(f"[{args.owner}] Scrolling {scroll_count} times...")
                for i in range(scroll_count):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1)
                
                html = await page.content()
                items = naverpay_parser.parse_points_html(html, args.owner)
            else:
                # Fetch all points with "전체" (All) button
                items = await fetch_points_with_filter(page, args.owner)
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if items:
                filename = f"naverpay_{args.owner}_points_{timestamp}.csv"
                output_path = f"naverpay_{args.owner}_points.csv"
            else:
                filename = f"naverpay_{args.owner}_points_empty.csv"
                output_path = f"naverpay_{args.owner}_points.csv"
            
            import csv
            with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=items[0].keys() if items else [])
                writer.writeheader()
                writer.writerows(items)
            print(f"[{args.owner}] Saved {len(items)} points to {output_path}")
            
            # Save HTML for reference
            html_path = f"naverpay_{args.owner}_points_{timestamp}.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[{args.owner}] Saved HTML to {html_path}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
