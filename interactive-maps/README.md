# tokyo-bousai-map — 可內嵌互動地圖模板（任意城市）

〈環境資訊中心〉風格的**可內嵌互動地圖**（單一自足 HTML，無圖磚＝無道路、只留行政界線＋水域）。
**模板化完成**：在一個實例資料夾裡編「地點＋敘述」，跑一行就產出地圖——界線自動抓、標籤自動避讓。

## 結構
```
tokyo-bousai-map/
  template/               引擎（可重用）
    gen_map.py            產生器：讀 {instance}/spots.py → 補座標→抓界線→自動排標籤→產地圖＋文章預覽
    fetch_boundaries.py   任意城市界線抓取（Nominatim 定位 + Overpass 抓行政界 + osm2geojson 組多邊形）
    article_preview.tpl.html  文章預覽模板（地圖 base64 內嵌、複製鈕本地解碼）
    build_*.py / verify_map.py / render_labels.py   舊工具（東京界線來源／Python 自我核對）
  tokyo/                  實例：東京（手調三層界線＋手列地名，設了 BOUNDARIES 故不自動抓）
  demo-kaohsiung/         實例：高雄示範（無 BOUNDARIES→自動抓界線，證明任意城市可用）
    spots.py             ★ 只編這個：TITLE/MARK + CAT 分類 + SPOTS（地點名/敘述，座標可省→自動編碼）
    boundaries/          自動抓後快取於此（land/subdiv.geojson + places.json + geocode.json）
    <MAP_FILE> + article-preview.html   ← 產生
```

## 開一張新城市地圖（給同事／未來 MCP）
1. 複製 `demo-kaohsiung/` 成 `<yourcity>/`，只改 `spots.py`：`TITLE`、`MAP_FILE`、`CAT`、`SPOTS`
   （每個 spot 給 `zh` 名＋`desc`＋`cat`；`lat`/`lng` 可省略→自動地理編碼，或給 `geo` 當查詢字串）。
   **不要**設 `BOUNDARIES`（留空才會自動抓那一帶的行政界線）。
2. `python template/gen_map.py <yourcity>` → 首次會抓界線（需連網、快取進 boundaries/），之後離線可重跑。
3. 開 `<yourcity>/article-preview.html` 按「📋 複製完整嵌入碼」貼進文章。
> ⚠ 若某城市所有景點**擠在很小範圍**，手機/平板檔位 popup 可能壓到少數 pin（桌機不受影響）；景點散布全市（如東京）則各檔位皆乾淨。

## 重產（東京）
```
python template/gen_map.py tokyo      # 讀 tokyo/spots.py → 產 tokyo/tokyo-bousai-map.html
```

## 內嵌（交付＝不上傳檔案）
開 `article-preview.html`（或審核 app `/tokyo-map/article`）→ 按「📋 複製完整嵌入碼」→ 貼進 e-info 文章 HTML。
按鈕會把整張地圖轉成自足的 `<iframe srcdoc>`（樣式隔離、不需 hosting）。

## 技術棧
Leaflet + 內嵌 GeoJSON。斷點對齊 e-info 三檔嵌入寬度（桌機 720／平板 528／手機 352.8，吃 iframe 自身寬度）；
輪播說明卡＋圖釘脈動高亮；起始 720×476、圓角無框、瓦紙(washi)固定配色。
東京實例界線來源：都縣界 dataofjapan/land、東京 23 區＋鄰縣市町村 smartnews-smri/japan-topography。
**不要改用 MapLibre**（曾試、owner 端渲染異常）。

## 供出路由（本機審核 app，`scripts/review_app.py`）
`/tokyo-map`（看）、`/tokyo-map/download`（下載地圖檔）、`/tokyo-map/article`（三檔位示意＋複製鈕）。

## 模板化路線
- **Stage 1（完成）**：拆成 `template/` + 實例夾，把地點/敘述抽到 `spots.py`；東京輸出與手調版一致。
- **Stage 2（完成）**：任意城市 → 由 SPOTS 座標範圍自動抓行政界線（Nominatim + Overpass + osm2geojson），
  快取進實例；缺座標的 spot 自動地理編碼。demo-kaohsiung 證明可用（桌機 0 重疊、海岸線自動）。
- **Stage 3（完成）**：標籤**自動避讓**——量測法（`getBoundingClientRect`）碰撞引擎，圖釘名候選右中→上下→換邊、
  全清優先否則挑重疊最小；popup 自動選圖釘最少的角落；避開 pin圖示＋popup＋彼此。無手動移標籤。
- 依賴：`pip install osm2geojson`（抓界線用）。驗證器：puppeteer-core headless（見 owner 開發筆記）。
- **未做**：包成 MCP（同事輸入地點+敘述即生成）——待另行；目前功能完好、命令列可用。
