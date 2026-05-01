# PChome 24h 限量商品搶購工具 🎯

自動監控 PChome 24h 商品狀態，開賣瞬間自動加入購物車。

## 安裝

建議使用 Python 虛擬環境 (venv) 進行安裝，避免影響系統其他套件。

```bash
cd pchome-sniper

# 1. 建立虛擬環境
python -m venv venv

# 2. 啟動虛擬環境 (Windows)
.\venv\Scripts\activate

# 3. 安裝依賴套件
pip install -r requirements.txt
```

> **注意**: 需要已安裝 Edge 或 Chrome 瀏覽器。Selenium 4+ 會自動下載對應的 WebDriver。

## 使用方式

請確保在執行前已經**啟動虛擬環境** (`.\venv\Scripts\activate`)。

### 基本用法
```bash
python pchome_sniper.py https://24h.pchome.com.tw/prod/DRADD4-A900IDYBY
```

### 使用商品 ID
```bash
python pchome_sniper.py DRADD4-A900IDYBY
```

### 自訂監控間隔 (更快)
```bash
python pchome_sniper.py DRADD4-A900IDYBY -i 0.2
```

### 使用 Chrome 瀏覽器
```bash
python pchome_sniper.py DRADD4-A900IDYBY -b chrome
```

## 運作流程

1. **啟動** → 透過 API 取得商品資訊與狀態
2. **開啟瀏覽器** → 自動開啟 Edge/Chrome
3. **登入** → 你需要在瀏覽器中手動登入 PChome 帳號
4. **監控** → 高頻輪詢 API 檢查 `ButtonType` 是否變為 `ForSale`
5. **搶購** → 偵測到開賣，自動點擊「加入購物車」
6. **結帳** → 跳轉至購物車頁面，請手動完成付款

## 商品狀態說明

| ButtonType | 說明 |
|------------|------|
| `NotReady` | 尚未開賣 |
| `ForSale`  | 可購買 ✅ |
| `SoldOut`  | 已售完 |
| `Disable`  | 已下架 |

## 參數一覽

| 參數 | 簡寫 | 預設 | 說明 |
|------|------|------|------|
| `url` | - | (必填) | 商品網址或 ID |
| `--interval` | `-i` | 0.3 | 監控間隔 (秒) |
| `--browser` | `-b` | edge | 瀏覽器 (edge/chrome) |
| `--qty` | `-q` | 1 | 購買數量 |

## 注意事項

- 監控間隔建議不低於 0.1 秒，避免被 PChome 封鎖 IP
- 確保網路穩定，建議使用有線網路
- 搶購成功後需手動完成結帳（選擇付款方式、輸入驗證碼等）
- 本工具僅供學習用途
