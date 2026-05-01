# PChome 24h 限量商品搶購工具 🎯

自動監控 PChome 24h 商品狀態，開賣瞬間自動加入購物車，並支援繞過 Google 登入驗證。

## 🚀 快速開始 (推薦：接管模式)

這是最穩定、100% 繞過 Google 登入偵測的方法。

### 1. 啟動除錯瀏覽器
連按兩下執行資料夾中的 `launch_chrome.bat`。
*   這會開啟一個獨立的 Chrome 視窗。
*   請在這個視窗中手動登入你的 PChome 帳號（支援 Google 登入）。
*   **登入後請維持視窗開啟，不要關閉。**

### 2. 啟動搶購腳本
打開 PowerShell，進入專案目錄並啟動虛擬環境：
```powershell
cd c:\Users\brian\Desktop\Code\pchome-sniper
.\venv\Scripts\activate
```

執行搶購指令 (加上 `-c` 參數)：
```powershell
python pchome_sniper.py [商品網址或ID] -c
```
*例如：*
`python pchome_sniper.py [商品網址或ID] -c`

---

## 🛠️ 安裝說明

如果你是第一次使用，請先執行以下步驟：

```powershell
# 1. 建立虛擬環境
python -m venv venv

# 2. 啟動虛擬環境
.\venv\Scripts\activate

# 3. 安裝必要套件
pip install -r requirements.txt
```

---

## 💡 進階參數說明

| 參數 | 簡寫 | 預設 | 說明 |
|------|------|------|------|
| `url` | - | (必填) | 商品網址或 ID |
| `--connect` | `-c` | False | **接管模式** (推薦)：連接至 `launch_chrome.bat` 開啟的瀏覽器 |
| `--interval` | `-i` | 0.3 | 監控間隔 (秒)，建議不低於 0.1 |
| `--qty` | `-q` | 1 | 購買數量 |
| `--user-profile` | `-u` | False | 使用本機現有的 Chrome 設定檔 (須關閉所有 Chrome) |

---

## ⚖️ 免責聲明
本工具僅供技術研究與學習使用，請勿用於任何違反 PChome 使用條款之行為。使用本工具所衍生之任何風險需由使用者自行承擔。
