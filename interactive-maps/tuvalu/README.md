# tuvalu — 吐瓦魯・富納富提 互動地圖

〈環境資訊中心〉吐瓦魯報導用的長型互動地圖。**第一版（2026-09-29），分類與說明文字還沒定，先不要發稿。**

## 檔案
- `spots.py`：12 個地點、分類、照片。要改內容只改這個檔。
- `build_land.py`：抓富納富提環礁的島嶼與礁盤，寫成 `boundaries/land.geojson`、`boundaries/reef.geojson`。
- `photos/`：12 張照片，縮成 800px 寬。
- `tuvalu-map.html`（產出的地圖）、`article-preview.html`（桌機／平板／手機三檔寬度對照）。

## 跟東京那張不一樣的地方
- 底圖用島嶼輪廓加礁盤，不用行政界。Funafuti 的行政區多邊形把整個潟湖包進去，照東京的做法畫會變成一整塊陸地。
- 固定高度 1080px，寬度跟著文章欄寬走（`HEIGHT`）。手機上比螢幕高，讀者往下捲著看，比例尺不會跟著縮小。
- 說明卡固定在左側中段，也就是潟湖那片空白（`POPUP_SIDE`），不去擠南端那一群點。
- 富納法拉離主島約 16 公里，框進來會把主島縮到點都疊在一起，所以設成 `offmap`：畫在畫面邊緣、朝真實方位，名稱寫上距離；說明卡照樣用真實位置。

## 嵌入
尺寸跟東京那張不同，外框用固定高度，不用 `aspect-ratio`：

```html
<div style="max-width:720px;margin:32px auto">
  <div style="position:relative;height:1080px">
    <iframe src="https://tnf-einfo.github.io/einfo-widgets/interactive-maps/tuvalu/tuvalu-map.html"
            title="吐瓦魯・富納富提" loading="lazy" allowfullscreen
            style="position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:16px">
    </iframe>
  </div>
</div>
```

## 重產
```
python interactive-maps/tuvalu/build_land.py        # 底圖；需連網，已存在就跳過，加 --force 重抓
python interactive-maps/template/gen_map.py tuvalu   # 讀 spots.py 產地圖
```

## 資料來源與授權
- 島嶼、礁盤：© OpenStreetMap contributors（ODbL）。
- 地點座標：採訪團隊整理的 Google 地圖連結，取地點本身的座標。
- 照片：環境資訊中心，版權所有，未經同意請勿轉用。
