# einfo-widgets

〈環境資訊中心〉可嵌進文章的互動內容，透過 GitHub Pages 提供。

首頁：<https://tnf-einfo.github.io/einfo-widgets/>

## 內容

- **`interactive-maps/`** — 可內嵌互動地圖。單一自足 HTML，Leaflet ＋ 內嵌行政區 GeoJSON；
  無圖磚（沒有道路），只留行政界線與水域。互動全部關閉，嵌在文章裡不會攔走讀者的捲動。
  - **`tokyo-map-stable/` — 東京・防災・生態 另類旅遊地圖（目前的交付版，發稿用這個）**。
    標籤手動排好、不會重疊，也是文章 node/243698 實際採用的那一版。**無法重生**（標籤寫在產出的
    HTML 上、不在 `spots.py` 裡）。
  - `tokyo-autolayout-test/` — 同一份內容、標籤改由 `gen_map.py` 自動排。**測試中，先不要發稿**：
    排出來的位置與手調版不一樣（owner 2026-08-25 決定發稿仍用手調版）。這個資料夾才是產生器的
    實例（`spots.py` 是輸入）。
  - `template/` — 產生器（可吃任意城市）。開一座新城市的地圖看 `interactive-maps/README.md`。
  - `video/` — 地圖→直式短影音（puppeteer 驅動地圖逐幀）。**刻意留在這裡不搬去 `data-shorts`**：
    它依賴 `gen_map.py` 產出的內部介面（`layoutPinNames`／`placeLabels` 等已明文定為不可動的固定
    介面就是為了它），而且規則會雙向回流（2026-08-04 就把影片版的標籤避讓規則寫回產生器）。

## 嵌進文章

用 `src=` 指到這裡，**不要把地圖的 HTML 貼進文章內文**。首頁每張地圖旁邊有「複製嵌入碼」，
產出的就是下面這一段：

```html
<div style="max-width:720px;margin:32px auto">
  <div style="position:relative;aspect-ratio:720/476">
    <iframe src="https://tnf-einfo.github.io/einfo-widgets/interactive-maps/tokyo-map-stable/tokyo-bousai-map.html"
            title="東京・防災・生態 另類旅遊地圖" loading="lazy" allowfullscreen
            style="position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:16px">
    </iframe>
  </div>
</div>
```

**尺寸與比例不要自己改**：`max-width` 720、`aspect-ratio` 720/476，外層 `position:relative`
＋ iframe 絕對定位填滿。地圖內部的響應式斷點吃的是 **iframe 自身寬度**，且已對齊 e-info 的
三檔嵌入寬度（桌機 **720**／平板 **528**／手機 **352.8**）並實測過三個檔位；把 iframe 鎖成
別的寬度，內層會挑錯檔位。圖說請自己另外加一行 `<p>` 在這段下面。

各資料夾裡的 `*.embed.html` 是舊做法（把整份地圖包成 `srcdoc` 供整段複製），保留供對照，
**新文章請用上面那一行**。

## 收錄規則

這個 repo 是公開的，所以收東西要嚴：

1. 自足靜態：無金鑰、無後端。
2. 資料來源可公開（政府開放資料、OSM 等）。
3. 不得含 e-info 文章內容鏡像。
4. 每個子資料夾要有自己的 `README.md`，標明資料來源與授權。

## 沿革

`interactive-maps/` 由 `einfo-scratch` 的 `tokyo-bousai-map/` 以 `git filter-repo` 搬入，
逐檔歷史保留（28 個 commit），並改為現名（它是通用地圖產生器，不只東京一張）。
