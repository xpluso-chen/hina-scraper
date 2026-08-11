# hina-scraper

私人爬蟲測試。用 Python + Playwright 撰寫，透過 GitHub Actions 手動觸發執行，
不用開自己的電腦，在網頁上點按鈕、填網址就能爬資料並下載 CSV。

## 檔案結構

```
hina-scraper/
├── requirements.txt          # Python 套件需求
├── scraper.py                 # 爬蟲主程式
└── .github/
    └── workflows/
        └── scrape.yml         # GitHub Actions workflow 設定
```

## 使用方式（在 GitHub 網頁上執行）

### 1. 找到 Run workflow

1. 打開這個 repo 的頁面 → 上方分頁點 **Actions**
2. 左側工作流程清單點選 **Scrape**
3. 右上角會有 **Run workflow** 下拉按鈕（分支選 `main`）
4. 展開後會看到輸入表單，填好後按綠色 **Run workflow** 送出

### 2. 表單欄位怎麼填

| 欄位 | 必填 | 說明 |
|---|---|---|
| `target_url` | ✅ | 要爬的網址，例如 `https://example.com/list` |
| `selector` | ✅ | 要抓取的 CSS 選擇器 |
| `wait_selector` | 選填 | 動態網站要先等待出現的 CSS 選擇器 |
| `scroll_times` | 選填 | 捲動載入更多內容的次數，預設 `0`（不捲動） |

#### `selector`（必填）— 決定要抓哪些元素

scraper.py 會對每個符合這個選擇器的元素，抓取它的**文字內容**與 **href 屬性**（若有，例如 `<a>` 標籤），輸出成 CSV 的 `text` / `href` 兩欄。

**怎麼找選擇器：**
1. 用 Chrome/Edge 打開目標網站，按 `F12` 開開發者工具
2. 點左上角箭頭圖示（Inspect 模式），滑鼠移到你要抓的內容上點一下，該元素會在 Elements 面板反白
3. 右鍵該元素 → **Copy** → **Copy selector**，即可拿到完整的 CSS 選擇器

**範例：**
- 抓新聞標題列表（`<a class="title">...</a>`）→ `a.title`
- 抓商品名稱（在 `<div class="product-card"><h3>...</h3></div>` 裡）→ `.product-card h3`
- 抓所有連結 → `a`

**先在瀏覽器 Console 測試選擇器是否正確**（`F12` → Console）：
```js
document.querySelectorAll('你的選擇器')
```
確認回傳的元素數量、內容是你要的，再填到表單裡，比較不會浪費 workflow 執行次數。

#### `wait_selector`（選填）— 決定「等到什麼出現才開始抓」

用於**動態網站**：頁面一開始是空的，內容要等 JavaScript 執行完、API 回傳資料後才會出現在 DOM 裡。如果不等就直接抓，會抓到空結果。

- 通常填跟 `selector` 一樣的值，或填它的共同父層容器（例如 `selector` 是 `.product-card h3`，`wait_selector` 填 `.product-card`）
- 如果是靜態網站（View Source 能直接看到你要的內容），留空即可

#### `scroll_times`（選填）— 無限捲動 / Lazy Load 網站

如果網站要滾動到底部才會載入更多內容（例如社群動態牆），可以填一個數字（例如 `5`），程式會自動捲動到底部最多 5 次，每次間隔等待新內容載入，直到頁面高度不再變化就提前停止。

### 3. 下載結果

執行完成後，點進該次 run（Actions 頁面的執行紀錄），畫面最下方 **Artifacts** 區塊會有 `scrape-results.zip`，下載解壓後就是 `output/result.csv`。

如果執行失敗，可以點開步驟的 log（尤其是 **Run scraper** 這一步）看詳細錯誤訊息，scraper.py 有記錄清楚的 log 方便除錯。

## 本機測試（選用）

如果想在自己電腦先測試：

```bash
pip install -r requirements.txt
playwright install chromium

python scraper.py --url "https://example.com" --selector "a.title" --wait-selector ".list" --scroll-times 2
```

結果會輸出到 `output/result.csv`（此資料夾已加入 `.gitignore`，不會被誤 commit）。

## GitHub Actions 免費額度

- **Public repo**：完全免費、無限分鐘數
- **Private repo**：免費帳號每月 **2,000 分鐘**（`ubuntu-latest` 是最省的計費比率）

這個爬蟲一次執行（裝環境 + 裝 Chromium + 爬取 + 上傳結果）大約 **1.5～3 分鐘**，
Private repo 免費額度大約可以跑 **600～1000 次/月**，個人使用相當夠用。

`scrape.yml` 有設定 `timeout-minutes: 15`，避免網站卡住或選擇器一直等不到而浪費額度。

## 疑難排解

| 狀況 | 可能原因 / 解法 |
|---|---|
| CSV 是空的 | `selector` 沒抓對，先用瀏覽器 Console 的 `document.querySelectorAll()` 測試 |
| 執行超時 / 卡住 | `wait_selector` 填的元素一直沒出現，確認選擇器正確，或該網站有反爬蟲機制擋掉 headless 瀏覽器 |
| 抓到的內容跟預期不同 | 部分網站對不同地區/裝置回傳不同內容，可在 log 裡確認實際抓到的 HTML 結構 |