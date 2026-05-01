#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════╗
║   PChome 24h 限量商品搶購工具 v1.0              ║
║   Flash Sale Sniper                              ║
╚══════════════════════════════════════════════════╝

使用方式:
    python pchome_sniper.py <商品網址>
    python pchome_sniper.py https://24h.pchome.com.tw/prod/DRADD4-A900IDYBY

選項:
    --interval, -i   監控間隔秒數 (預設 0.3)
    --browser,  -b   瀏覽器類型 edge/chrome (預設 edge)
    --qty,      -q   購買數量 (預設 1)
"""

import re
import sys
import time
import json
import argparse
import threading
import requests
from datetime import datetime

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException,
    ElementClickInterceptedException, WebDriverException
)

# ─── 顏色輸出 ───────────────────────────────────────────────
class Color:
    BLUE    = '\033[94m'
    GREEN   = '\033[92m'
    YELLOW  = '\033[93m'
    RED     = '\033[91m'
    CYAN    = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD    = '\033[1m'
    RESET   = '\033[0m'


# ─── 主要類別 ───────────────────────────────────────────────
class PChomeSniper:
    """PChome 24h 限量商品搶購器"""

    # === PChome API 端點 ===
    BUTTON_API = (
        "https://ecapi.pchome.com.tw/ecshop/prodapi/v2/prod/button"
        "&id={prod_id}"
        "&fields=Seq,Id,Price,Qty,ButtonType,SaleStatus"
    )
    PROD_API = (
        "https://ecapi.pchome.com.tw/ecshop/prodapi/v2/prod"
        "&id={prod_id}"
        "&fields=Id,Name,Price,Qty,ButtonType,SaleStatus"
    )
    CART_URL = "https://ecpay.pchome.com.tw/cart/index"
    PROD_PAGE = "https://24h.pchome.com.tw/prod/{prod_id}"

    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0'
        ),
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        'Referer': 'https://24h.pchome.com.tw/',
        'Origin': 'https://24h.pchome.com.tw',
    }

    def __init__(self, url, interval=0.3, browser='edge', qty=1, use_user_profile=False, connect_mode=False):
        self.url = url
        self.prod_id = self._extract_prod_id(url)
        self.interval = interval
        self.browser_type = browser
        self.qty = qty
        self.use_user_profile = use_user_profile
        self.connect_mode = connect_mode
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.driver = None
        self.prod_name = "未知"
        self.prod_price = "未知"

    # ─── 工具方法 ────────────────────────────────────────────

    @staticmethod
    def _extract_prod_id(url):
        """從 PChome 網址提取商品 ID"""
        match = re.search(r'/prod/([A-Za-z0-9-]+)', url)
        if match:
            return match.group(1)
        if re.match(r'^[A-Za-z0-9-]+$', url):
            return url
        raise ValueError(f"無法從 URL 提取商品 ID: {url}")

    @staticmethod
    def _log(msg, level='INFO'):
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        color_map = {
            'INFO':    Color.BLUE,
            'OK':      Color.GREEN,
            'WARN':    Color.YELLOW,
            'ERROR':   Color.RED,
            'MONITOR': Color.CYAN,
            'ACTION':  Color.MAGENTA,
        }
        c = color_map.get(level, '')
        print(f"{c}[{ts}] [{level:7s}] {msg}{Color.RESET}")

    @staticmethod
    def _beep(times=5):
        """非同步發出嗶聲，不阻塞主程式"""
        import threading
        def run_beep():
            if HAS_WINSOUND:
                for _ in range(times):
                    winsound.Beep(1000, 200)
                    time.sleep(0.05)
            else:
                print('\a' * times)
        threading.Thread(target=run_beep, daemon=True).start()

    # ─── API 操作 ────────────────────────────────────────────

    def fetch_product_info(self):
        """取得商品名稱與價格"""
        try:
            url = self.PROD_API.format(prod_id=self.prod_id)
            resp = self.session.get(url, timeout=5)
            data = resp.json()
            item = data[0] if isinstance(data, list) else data
            self.prod_name = item.get('Name', '未知')
            price_info = item.get('Price', {})
            if isinstance(price_info, dict):
                self.prod_price = price_info.get('P', price_info.get('M', '未知'))
            else:
                self.prod_price = price_info
            return item
        except Exception as e:
            self._log(f"取得商品資訊失敗: {e}", 'WARN')
            return None

    def check_availability(self):
        """透過 API 檢查商品是否可購買
        回傳: (是否可買, 狀態描述字串)
        """
        try:
            url = self.BUTTON_API.format(prod_id=self.prod_id)
            resp = self.session.get(url, timeout=3)
            data = resp.json()
            item = data[0] if isinstance(data, list) else data

            btn_type = item.get('ButtonType', '')
            sale_st  = item.get('SaleStatus', '')
            qty      = item.get('Qty', 0)

            available = (btn_type == 'ForSale') and (int(qty) > 0)
            status = f"ButtonType={btn_type}  SaleStatus={sale_st}  Qty={qty}"
            return available, status
        except requests.exceptions.Timeout:
            return False, "Request timeout"
        except Exception as e:
            return False, f"Error: {e}"

    # ─── 瀏覽器操作 ──────────────────────────────────────────

    def setup_browser(self):
        """啟動瀏覽器"""
        import os
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        
        if getattr(self, 'connect_mode', False):
            self._log("使用接管模式連線至現有 Chrome (Port 9223)...", 'INFO')
            options = ChromeOptions()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
            try:
                self.driver = webdriver.Chrome(options=options)
                self._log("✅ 成功接管 Chrome 瀏覽器！", 'OK')
                return
            except Exception as e:
                self._log(f"接管失敗: {e}", 'ERROR')
                self._log("請確認您有先執行 launch_chrome.bat 開啟瀏覽器！", 'ERROR')
                raise e

        user_data_dir = None
        if getattr(self, 'use_user_profile', False):
            user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
            self._log(f"載入現有 Chrome 設定檔: {user_data_dir}", 'WARN')
            self._log("⚠ 警告: 必須完全關閉所有 Chrome 視窗(包含背景)才能載入登入狀態！", 'WARN')
            ans = input(f"{Color.YELLOW}>>> 是否要讓程式自動強制關閉所有 Chrome 視窗？(y/n) [預設: y]: {Color.RESET}").strip().lower()
            if ans != 'n':
                self._log("正在強制關閉 Chrome...", 'ACTION')
                os.system("taskkill /F /IM chrome.exe /T >nul 2>&1")
                import time
                time.sleep(2)  # 等待程序完全終止
                self._log("Chrome 已關閉，繼續啟動...", 'OK')

        # 嘗試使用 undetected-chromedriver
        try:
            import undetected_chromedriver as uc
            self._log("嘗試使用 undetected-chromedriver 啟動 Chrome...", 'INFO')
            
            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-popup-blocking')
            if user_data_dir:
                options.add_argument(f'--user-data-dir={user_data_dir}')
            
            self.driver = uc.Chrome(options=options)
            self._log("✅ undetected-chromedriver 啟動成功", 'OK')
            return
        except Exception as e:
            self._log(f"undetected-chromedriver 啟動失敗 ({e})，降級為一般 Selenium", 'WARN')

        # 降級為一般 Selenium
        options = ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--start-maximized')
        options.add_argument('--disable-popup-blocking')
        
        # 移除防偵測參數，避免閃退
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        if user_data_dir:
            options.add_argument(f'--user-data-dir={user_data_dir}')
            
        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        })
        self._log("✅ 一般 Selenium Chrome 啟動完成", 'OK')

    def wait_for_login(self):
        """處理登入狀態。如果是接管模式，則跳過手動確認。"""
        if getattr(self, 'connect_mode', False):
            self._log("接管模式：延用瀏覽器現有登入狀態，跳過手動登入確認。", 'OK')
            return

        self.driver.get("https://24h.pchome.com.tw/")
        self._log("嘗試從本機 Chrome/Edge 讀取登入狀態...", 'INFO')
        
        try:
            import browser_cookie3
            cj = None
            try:
                cj = browser_cookie3.chrome(domain_name='pchome.com.tw')
            except:
                pass
            if not cj:
                try:
                    cj = browser_cookie3.edge(domain_name='pchome.com.tw')
                except:
                    pass
            
            if cj:
                count = 0
                for c in cj:
                    cookie_dict = {'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path}
                    try:
                        self.driver.add_cookie(cookie_dict)
                        count += 1
                    except:
                        pass
                if count > 0:
                    self._log(f"✅ 成功從你的瀏覽器匯入 {count} 個登入憑證！", 'OK')
                    self.driver.refresh()
                    time.sleep(2)
                    self._log("如果網頁右上角顯示已登入，就不需要手動登入了。", 'OK')
                    return
        except Exception as e:
            self._log(f"無法自動讀取本機登入狀態: {e}", 'WARN')

        self.driver.get("https://24h.pchome.com.tw/sign/in")
        self._log("⚠  請在跳出的瀏覽器視窗中登入 PChome 帳號", 'WARN')
        self._log("⚠  登入完成後，請回到此視窗按 Enter", 'WARN')
        input(f"{Color.YELLOW}>>> 登入完成後按 Enter 繼續...{Color.RESET}")
        self._log("登入確認完成", 'OK')

    def sync_cookies_to_session(self):
        """將瀏覽器 cookies 同步到 requests session"""
        for cookie in self.driver.get_cookies():
            self.session.cookies.set(cookie['name'], cookie['value'])

    def add_to_cart_via_browser(self):
        """用瀏覽器自動點擊加入購物車"""
        self._log("嘗試瀏覽器方式加入購物車...", 'ACTION')
        try:
            self.driver.get(self.PROD_PAGE.format(prod_id=self.prod_id))
            wait = WebDriverWait(self.driver, 8)

            # PChome 加入購物車按鈕的各種可能 selector
            btn_selectors = [
                (By.CSS_SELECTOR, "button[data-qa='add_cart']"),
                (By.CSS_SELECTOR, "button.btn-cart"),
                (By.CSS_SELECTOR, "#ButtonContainer button"),
                (By.CSS_SELECTOR, "button[class*='cart']"),
                (By.XPATH, "//button[contains(text(),'入購物車')]"),
                (By.XPATH, "//button[contains(text(),'搶購')]"),
                (By.XPATH, "//button[contains(text(),'立即購買')]"),
                (By.XPATH, "//a[contains(text(),'入購物車')]"),
            ]

            for by, selector in btn_selectors:
                try:
                    btn = wait.until(EC.element_to_be_clickable((by, selector)))
                    btn.click()
                    self._log("✅ 已點擊加入購物車按鈕！", 'OK')
                    time.sleep(0.1)
                    return True
                except (TimeoutException, NoSuchElementException,
                        ElementClickInterceptedException):
                    continue

            # 最後嘗試: 用 JavaScript 點擊所有看起來像購物車按鈕的元素
            clicked = self.driver.execute_script("""
                var buttons = document.querySelectorAll('button, a');
                for (var b of buttons) {
                    var text = b.textContent || '';
                    if (text.includes('購物車') || text.includes('搶購')
                        || text.includes('立即購買')) {
                        b.click();
                        return true;
                    }
                }
                return false;
            """)
            if clicked:
                self._log("✅ JS 點擊加入購物車成功！", 'OK')
                time.sleep(1)
                return True

            self._log("找不到加入購物車按鈕", 'ERROR')
            return False

        except Exception as e:
            self._log(f"瀏覽器加入購物車失敗: {e}", 'ERROR')
            return False

    def navigate_to_cart(self):
        """導航至購物車頁面"""
        try:
            self.driver.get(self.CART_URL)
            self._log("✅ 已跳轉至購物車結帳頁面", 'OK')
        except Exception as e:
            self._log(f"跳轉購物車失敗: {e}", 'ERROR')

    # ─── 主流程 ──────────────────────────────────────────────

    def run(self):
        """主執行流程"""
        print(f"""
{Color.BOLD}{Color.CYAN}
╔══════════════════════════════════════════════════╗
║     PChome 24h 限量商品搶購工具  v1.0           ║
║     Flash Sale Sniper                            ║
╚══════════════════════════════════════════════════╝
{Color.RESET}""")

        # 1. 取得商品資訊
        self._log(f"商品 ID : {self.prod_id}")
        self.fetch_product_info()
        self._log(f"商品名稱: {self.prod_name}")
        self._log(f"商品價格: NT$ {self.prod_price}")

        # 2. 檢查目前狀態
        avail, status = self.check_availability()
        self._log(f"目前狀態: {status}")
        if avail:
            self._log("商品目前已經可以購買！", 'OK')

        # 3. 啟動瀏覽器
        self._log("正在啟動瀏覽器...", 'ACTION')
        self.setup_browser()

        # 4. 登入
        self.wait_for_login()
        self.sync_cookies_to_session()

        # 5. 預先載入商品頁面 (加速後續操作)
        self._log("預先載入商品頁面...", 'ACTION')
        self.driver.get(self.PROD_PAGE.format(prod_id=self.prod_id))
        time.sleep(1)

        # 6. 開始監控
        self._log(f"🔍 開始監控商品 (間隔: {self.interval}s)", 'MONITOR')
        self._log("按 Ctrl+C 可中斷監控", 'WARN')
        print("─" * 55)

        check_count = 0
        start_time = time.time()

        try:
            while True:
                check_count += 1
                avail, status = self.check_availability()

                # 每 20 次顯示一次狀態
                if check_count % 20 == 0:
                    elapsed = time.time() - start_time
                    self._log(
                        f"第 {check_count} 次 | 已等待 {elapsed:.0f}s | {status}",
                        'MONITOR'
                    )

                if avail:
                    self._log("🎯🎯🎯  商品可購買！立即搶購！", 'OK')
                    self._beep(3) # 非同步嗶聲，不佔用時間

                    # 嘗試加入購物車
                    success = self.add_to_cart_via_browser()

                    if success:
                        # 跳轉到結帳頁面
                        self._log("正在跳轉至結帳頁面...", 'ACTION')
                        self.driver.get("https://eccart.pchome.com.tw/cart/v1/container/24H")
                        self._beep(5)
                        self._log("已跳轉至購物車，請『立刻』完成最後結帳步驟！", 'OK')
                        self._log("══════════════════════════════════", 'OK')
                        self._log("  🎉 搶購完成！請儘速完成結帳！  ", 'OK')
                        self._log("══════════════════════════════════", 'OK')
                        break
                    else:
                        # 失敗則重試
                        self._log("加入購物車失敗，0.5 秒後重試...", 'WARN')
                        time.sleep(0.5)
                        continue

                time.sleep(self.interval)

        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            self._log(
                f"使用者中斷 | 共檢查 {check_count} 次 | 耗時 {elapsed:.1f}s",
                'WARN'
            )
        finally:
            if self.driver:
                self._log("瀏覽器保持開啟，請手動完成結帳", 'WARN')
                input(f"{Color.YELLOW}>>> 完成後按 Enter 關閉瀏覽器...{Color.RESET}")
                self.driver.quit()


# ─── CLI 入口 ───────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='PChome 24h 限量商品搶購工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python pchome_sniper.py https://24h.pchome.com.tw/prod/DRADD4-A900IDYBY
  python pchome_sniper.py DRADD4-A900IDYBY -i 0.2 -b chrome
        """
    )
    parser.add_argument('url', help='PChome 商品網址或商品 ID')
    parser.add_argument(
        '--interval', '-i', type=float, default=0.3,
        help='監控間隔秒數 (預設: 0.3)'
    )
    parser.add_argument(
        '--browser', '-b', choices=['edge', 'chrome'], default='edge',
        help='使用的瀏覽器 (預設: edge)'
    )
    parser.add_argument(
        '--qty', '-q', type=int, default=1,
        help='購買數量 (預設: 1)'
    )
    parser.add_argument(
        '--user-profile', '-u', action='store_true',
        help='使用本機的 Chrome 設定檔 (可直接套用已登入的狀態，但須先關閉所有 Chrome 視窗)'
    )
    parser.add_argument(
        '--connect', '-c', action='store_true',
        help='接管模式：連接到已經開啟除錯模式的 Chrome (搭配 launch_chrome.bat 使用)'
    )

    args = parser.parse_args()

    try:
        sniper = PChomeSniper(
            url=args.url,
            interval=args.interval,
            browser=args.browser,
            qty=args.qty,
            use_user_profile=args.user_profile,
            connect_mode=args.connect,
        )
        sniper.run()
    except ValueError as e:
        print(f"{Color.RED}[錯誤] {e}{Color.RESET}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}已中斷{Color.RESET}")
        sys.exit(0)


if __name__ == '__main__':
    main()
