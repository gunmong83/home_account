import os
import sys
import asyncio
from typing import Dict, List, Any
from playwright.async_api import async_playwright

# Add parent directory to sys.path to allow importing from 'parser'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import parser to use its HTML parsing logic after fetching
import parser.naverpay as naverpay_parser
import config

class NaverPayFetcher:
    def __init__(self, owner: str):
        self.owner = owner
        self.user_data_dir = f"/tmp/naverpay_{owner}"
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    async def launch_and_wait_login(self):
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            self.user_data_dir,
            headless=False,
            args=["--remote-debugging-port=9222"] if self.owner == "taewoo" else [],
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        print(f"[{self.owner}] Navigating to Naver Login...")
        await self.page.goto("https://nid.naver.com/nidlogin.login")
        
        print(f"[{self.owner}] Please log in within the browser window.")
        print(f"[{self.owner}] Once logged in, the script will auto-detect OR you can press ENTER here to start fetching.")
        
        # Use an event to signal when to proceed
        proceed_event = asyncio.Event()

        # Task 1: Auto-detection via URL/DOM
        async def auto_detect():
            while not proceed_event.is_set():
                try:
                    url = self.page.url
                    if "pay.naver.com" in url or "www.naver.com" in url:
                        if "pay.naver.com" in url:
                            print(f"[{self.owner}] Login detected via Pay URL.")
                            proceed_event.set()
                            break
                        
                        try:
                            # Naver Home profile check
                            logout_btn = await self.page.query_selector("a#gnb_logout_button")
                            if logout_btn:
                                print(f"[{self.owner}] Login detected via Naver Home profile.")
                                proceed_event.set()
                                break
                        except: pass
                    
                    if self.context.pages == []:
                        proceed_event.set()
                        break
                    await asyncio.sleep(1)
                except: break

        # Task 2: Manual Enter key
        async def manual_wait():
            # This is a bit tricky with stdin in async, but for a one-off it's okay
            # We use a thread to not block the event loop
            await asyncio.to_thread(input, f"[{self.owner}] Press ENTER after logging in if not auto-detected...")
            proceed_event.set()

        # Run both tasks and wait for the first one to set the event
        detect_task = asyncio.create_task(auto_detect())
        input_task = asyncio.create_task(manual_wait())
        
        await proceed_event.wait()
        
        # Cleanup tasks
        detect_task.cancel()
        input_task.cancel()
        
        print(f"[{self.owner}] Proceeding to fetch...")

    async def fetch_payments(self, max_pages: int = 1) -> List[Dict[str, Any]]:
        print(f"[{self.owner}] Fetching Payments (up to {max_pages} pages)...")
        await self.page.goto("https://pay.naver.com/pc/history")
        await self.page.wait_for_load_state("networkidle")
        
        all_payments = []
        for page_num in range(1, max_pages + 1):
            print(f"[{self.owner}] Processing Payment page {page_num}...")
            await asyncio.sleep(2) 
            
            html = await self.page.content()
            items = naverpay_parser._parse_payment_list_from_html(html)
            for item in items:
                item["owner"] = self.owner
            all_payments.extend(items)
            
            if page_num < max_pages:
                # Track current page value to detect transition
                curr_page_elem = await self.page.query_selector("[class*='PcPagination_current']")
                curr_page_val = await curr_page_elem.inner_text() if curr_page_elem else str(page_num)
                
                next_btn = await self.page.query_selector("button.PcPagination_next__bKui2")
                if next_btn:
                    # Check if next button is disabled
                    is_disabled_attr = await next_btn.get_attribute("disabled")
                    class_attr = await next_btn.get_attribute("class") or ""
                    if is_disabled_attr is not None or "PcPagination_disabled" in class_attr:
                        print(f"[{self.owner}] No more payment pages (Next button disabled).")
                        break
                        
                    await next_btn.click()
                    
                    # Wait for page indicator to change
                    try:
                        await self.page.wait_for_function(
                            f"document.querySelector('[class*=\"PcPagination_current\"]')?.innerText.trim() !== '{curr_page_val.strip()}'",
                            timeout=5000
                        )
                    except Exception as e:
                        print(f"[{self.owner}] Warning: Page transition check timed out: {e}")
                    
                    await self.page.wait_for_load_state("networkidle")
                    await asyncio.sleep(1) 
                else:
                    print(f"[{self.owner}] Next button (PcPagination) not found.")
                    break
                    
        return all_payments

    async def fetch_points(self) -> List[Dict[str, Any]]:
        scroll_count = config.NAVERPAY_SCROLL_COUNT_POINTS
        print(f"[{self.owner}] Fetching Points with {scroll_count} scrolls...")
        await self.page.goto("https://new-m.pay.naver.com/pointshistory/list?depth2Slug=depth2_all")
        await self.page.wait_for_load_state("networkidle")
        
        for i in range(scroll_count):
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            
        html = await self.page.content()
        items = naverpay_parser.parse_points_html(html, self.owner)
        return items

    async def fetch_money(self) -> List[Dict[str, Any]]:
        scroll_count = config.NAVERPAY_SCROLL_COUNT_MONEY
        print(f"[{self.owner}] Fetching Money with {scroll_count} scrolls...")
        await self.page.goto("https://new-m.pay.naver.com/paymoney/history")
        await self.page.wait_for_load_state("networkidle")
        
        for i in range(scroll_count):
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            
        html = await self.page.content()
        items = naverpay_parser.parse_money_html(html, self.owner)
        return items

    async def close(self):
        if self.context: await self.context.close()
        if self.playwright: await self.playwright.stop()

async def fetch_naverpay(owner: str, pages: int = 1) -> Dict[str, List[Dict[str, Any]]]:
    fetcher = NaverPayFetcher(owner)
    try:
        await fetcher.launch_and_wait_login()
        payments = await fetcher.fetch_payments(max_pages=pages)
        points = await fetcher.fetch_points()
        money = await fetcher.fetch_money()
        return {
            "payments": payments,
            "points": points,
            "money": money
        }
    finally:
        await fetcher.close()

if __name__ == "__main__":
    import argparse
    import csv
    parser = argparse.ArgumentParser(description="Naver Pay Crawler")
    parser.add_argument("--owner", required=True, help="taewoo or chaeyoung")
    parser.add_argument("--output", help="Output prefix", default="naverpay")
    
    parser.add_argument("--pages", type=int, default=config.NAVERPAY_PAGES_TO_FETCH, help="Number of payment pages to fetch")
    
    args = parser.parse_args()
    
    data = asyncio.run(fetch_naverpay(args.owner, pages=args.pages))
    for key, rows in data.items():
        if rows:
            csv_path = f"{args.output}_{args.owner}_{key}.csv"
            with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            print(f"Saved {len(rows)} {key} rows to {csv_path}")
