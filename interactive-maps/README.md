# tokyo-bousai-map — 可內嵌互動地圖（模板 + 實例）

〈環境資訊中心〉風格的**可內嵌互動地圖**（單一自足 HTML，無圖磚＝無道路、只留行政界線＋水域）。
正在改造成**模板**：之後只要在一個實例資料夾裡編「地點＋敘述」，跑一行就產出地圖。

## 結構
```
tokyo-bousai-map/
  template/            引擎（可重用）
    gen_map.py         產生器：讀 {instance}/spots.py + {instance}/boundaries/*.geojson → 產地圖
    build_*.py         抓/建界線 GeoJSON 的工具
    verify_map.py, render_labels.py   用 Python 算圖自我核對（看不到瀏覽器時用）
  tokyo/               一個實例（東京防災地圖）
    spots.py           ★ 只編這個：TITLE/MARK + CAT 分類 + SPOTS 地點敘述 + PLACES 地名
    boundaries/        kanto / tokyo_ku / others_muni .geojson
    tokyo-bousai-map.html   ← 產生（地圖本體）
    article-preview.html    ← 仿 e-info 文章版面的內嵌示意（三檔位並排＋「複製完整嵌入碼」鈕）
```
未來每張新地圖 = 新增一個實例資料夾（自己的 `spots.py` + `boundaries/`）。

## 重產
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

## 模板化路線（進行中）
- **Stage 1（完成）**：拆成 `template/` + `tokyo/`，把地點/敘述抽到 `tokyo/spots.py`；東京輸出與手調版逐位元一致。
- **Stage 2**：任意城市 → 由 SPOTS 的座標範圍自動抓行政界線（Nominatim 定位 + Overpass 抓 `boundary=administrative`，快取進實例）。
- **Stage 3**：地名/圖釘標籤**自動避讓**（把圖釘名收進既有的 `placeLabels()` 碰撞引擎），不再手動移標籤。
