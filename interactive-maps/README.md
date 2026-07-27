# tokyo-bousai-map — 東京・防災・生態 另類旅遊地圖

〈環境資訊中心〉東京近郊防災與生態另類旅遊景點的**可內嵌互動地圖**（單一自足 HTML，無圖磚＝無道路、只留行政界線）。

## 成品（兩支就好）
- `tokyo-bousai-map.html` — 地圖本體（內嵌行政區 GeoJSON）。放個網址、用 `<iframe src>` 嵌（手動複製貼上）。
- `article-preview.html` — 仿 e-info 文章版面的內嵌示意（依 720 / 528 / 352.8 三檔位並排對照）。

## 內嵌
```html
<div style="position:relative;max-width:720px;margin:auto;aspect-ratio:720/476">
  <iframe src="你的網址/tokyo-bousai-map.html" loading="lazy" allowfullscreen
          style="position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:16px"></iframe>
</div>
```

## 技術棧
Leaflet + 內嵌 GeoJSON（都縣界 dataofjapan/land、東京 23 區＋鄰縣市町村 smartnews-smri/japan-topography）。
6 景點、繁中地名自動位移避讓、輪播說明卡＋輪到圖釘脈動高亮；斷點對齊 e-info 三檔嵌入寬度（桌機 720／平板 528／手機 352.8，吃 iframe 自身寬度）。
起始 720×476、圓角無框、瓦紙(washi)固定配色。照片為 e-info 各景點實照（換圖改 `build/gen_final.py` 各 spot 的 `img` 欄）。
**不要改用 MapLibre**（曾試、owner 端渲染異常）。

## 重產（改地圖）
成品 HTML 已自足、可直接手改；要從來源重產：
```
python build/gen_final.py    # 改景點/地名/樣式/斷點在此 → 產 tokyo-bousai-map.html
```
界線 GeoJSON 已放 `build/`（`kanto/tokyo_ku/others_muni.geojson`）；要重抓界線跑 `build/build_*.py`。
`build/verify_map.py`、`build/render_labels.py` 是「用 Python 算圖自我核對」的工具（看不到瀏覽器時用）。

## 供出路由（本機審核 app，`scripts/review_app.py`）
`/tokyo-map`（看）、`/tokyo-map/download`（下載地圖檔）、`/tokyo-map/article`（三檔位示意）。
臨時公開網址：本機 `python -m http.server 8791 -d einfo-scratch/tokyo-bousai-map` ＋ `cloudflared tunnel --url http://127.0.0.1:8791`。
