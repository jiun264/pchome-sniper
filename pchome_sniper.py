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
        """啟動或連線至瀏覽器 (還原最簡連線版)"""
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        
        if getattr(self, 'connect_mode', False):
            self._log("準備連線至現有 Chrome (Port 9223)...", 'INFO')
            options = ChromeOptions()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
            try:
                # 還原成最簡單、原本會通的連線方式
                self.driver = webdriver.Chrome(options=options)
                self._log("✅ 成功接管 Chrome 瀏覽器！", 'OK')
                return
            except Exception as e:
                self._log(f"接管失敗: {e}", 'ERROR')
                self._log("請確認 launch_chrome.bat 開啟的視窗還在。", 'ERROR')
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
        """處理登入狀態。如果是接管模式，則跳過。"""
        if getattr(self, 'connect_mode', False):
            self._log("接管模式：延用瀏覽器現有登入狀態。", 'OK')
            return

        self.driver.get("https://24h.pchome.com.tw/sign/in")
        self._log("⚠ 請在瀏覽器中登入 PChome，完成後回到此視窗按 Enter", 'WARN')
        input(f"{Color.YELLOW}>>> 登入完成後按 Enter 繼續...{Color.RESET}")

    def sync_cookies_to_session(self):
        """將瀏覽器 cookies 同步到 requests session"""
        try:
            for cookie in self.driver.get_cookies():
                self.session.cookies.set(cookie['name'], cookie['value'])
        except:
            pass

    def add_to_cart_via_browser(self):
        """用瀏覽器點擊加入購物車 (三連擊穩健版)"""
        self._log("⚡ 啟動連擊 (立即購買 -> 結帳 -> 排除彈窗)...", 'ACTION')
        try:
            self.driver.execute_script("""
                // 1. 點擊規格 (優先第一個)
                var specSelectors = ['.spec-item', 'li[data-value]', '.c-dropdown__item', '.spec_btn'];
                specSelectors.forEach(s => {
                    var el = document.querySelector(s);
                    if(el && el.offsetParent !== null) el.click();
                });

                // 2. 第一擊：點擊「立即購買」
                var allBtns = document.querySelectorAll('button, a, .btn-buy');
                for (var b of allBtns) {
                    var txt = (b.innerText || '').trim();
                    if ((txt.includes('立即購買') || txt.includes('直接購買')) && b.offsetParent !== null) {
                        b.click();
                        break;
                    }
                }

                // 3. 第二擊：等候 0.2 秒點擊右側抽屜的「結帳」按鈕
                setTimeout(() => {
                    var checkoutBtns = document.querySelectorAll('.c-miniCart__btn--checkout, button.btn-checkout, a[href*="cart/index"]');
                    checkoutBtns.forEach(cb => {
                        if(cb.offsetParent !== null) cb.click();
                    });
                }, 200);

                // 4. 自動排除障礙：監控並點掉彈窗
                var dismissInterval = setInterval(() => {
                    var popups = document.querySelectorAll('.ui-dialog-buttonset button, .btn-confirm, button:contains("確定")');
                    popups.forEach(p => {
                        if(p.offsetParent !== null) p.click();
                    });
                }, 150);
                setTimeout(() => clearInterval(dismissInterval), 5000);
            """)
            
            # 稍微等待跳轉啟動
            time.sleep(0.5) 
            return True
        except Exception as e:
            self._log(f"連擊過程異常: {e}", 'WARN')
            return False

    def navigate_to_cart(self):
        """導航至結帳入口 (守株待兔版)"""
        self._log("正在等待瀏覽器自動跳轉至結帳頁面...", 'ACTION')
        
        for attempt in range(25): # 5 秒監控
            time.sleep(0.2)
            current_url = self.driver.current_url
            
            if "cart" in current_url or "ecpay" in current_url or "payinfo" in current_url:
                self._log("✅ 成功抵達結帳/付款頁面！", 'OK')
                return True
                
            if attempt == 15 and "prod" in current_url: # 3秒後還在商品頁
                self.driver.get("https://shopping.pchome.com.tw/cart/view/24h")
            
        return False

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
        self._log("正在同步瀏覽器登入狀態至監控模組...", 'ACTION')
        self.sync_cookies_to_session()
        self._log("登入狀態同步完成", 'OK')

        # 5. 預先載入商品頁面 (加速後續操作)
        if not getattr(self, 'connect_mode', False):
            self._log("預先載入商品頁面...", 'ACTION')
            self.driver.get(self.PROD_PAGE.format(prod_id=self.prod_id))
            time.sleep(1)
        else:
            self._log("接管模式：保留目前瀏覽器頁面狀態與規格選擇。", 'OK')

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

                # 每 3 次顯示一次狀態 (約 1 秒顯示一次)
                if check_count % 3 == 0:
                    elapsed = time.time() - start_time
                    self._log(
                        f"第 {check_count} 次 | 已等待 {elapsed:.0f}s | {status}",
                        'MONITOR'
                    )

                if avail:
                    self._log("🎯🎯🎯  商品可購買！立即搶購！", 'OK')
                    self._beep(3) # 非同步嗶聲，不佔用時間

                    # 嘗試點擊
                    if self.add_to_cart_via_browser():
                        # 執行跳轉與檢查
                        is_in_cart = self.navigate_to_cart()
                        
                        if is_in_cart:
                            self._log("🎉 成功進入結帳頁面！請立刻手動完成最後步驟！", 'OK')
                            self._beep(5)
                            self._log("══════════════════════════════════", 'OK')
                            self._log("   搶購動作完成，請人工接手結帳   ", 'OK')
                            self._log("══════════════════════════════════", 'OK')
                            break # 成功才跳出迴圈
                        else:
                            self._log("❌ 三次跳轉購物車都失敗，可能沒點到按鈕或被系統阻擋。", 'ERROR')
                            self._log("🔄 回到商品頁重新嘗試...", 'WARN')
                            # 回到商品頁面繼續下一輪監控
                            self.driver.get(self.PROD_PAGE.format(prod_id=self.prod_id))
                            time.sleep(1)
                            continue
                    else:
                        # 失敗則重試
                        self._log("加入購物車腳本執行失敗，0.5 秒後重試...", 'WARN')
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
