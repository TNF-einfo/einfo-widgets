# tuvalu — 吐瓦魯・富納富提 互動地圖

〈環境資訊中心〉吐瓦魯報導用的長型互動地圖。**測試中（2026-09-29），分類與說明文字待 owner 確認，先不要發稿。**

## 檔案
- `spots.py`：12 個地點、分類、照片、說明文字。要改內容只改這個檔。
- `build_land.py`：抓富納富提環礁的島嶼與礁盤，寫成 `boundaries/land.geojson`、`boundaries/reef.geojson`（插畫風底圖用）。
- `photos/`：12 張照片，縮成 800px 寬、不帶 EXIF。
- `tuvalu-map.html`（產出的地圖）、`article-preview.html`（桌機／平板／手機三檔寬度對照）。

## 說明文字
取自〈吐瓦魯：海浪帶不走的家〉專題（<https://www.e-info.org.tw/feature/36>）六篇報導，只寫報導裡寫過的事，
`spots.py` 每個點的行尾註解是出處的 node 編號。主島 Fongafale 照報導譯作「豐阿法萊」。

## 底圖
- **定案：Sentinel-2 無雲鑲嵌 2024**（EOX，`spots.py` 的 `TILES`，不調色）。owner 09-29 嫌衛星圖不夠清楚，
  從四個比較選項（Esri 高解析、Esri 調色、Sentinel-2、Sentinel-2 調色）挑了這個。
  Esri World Imagery 在吐瓦魯一帶拼了不同來源的影像，南端灰帶與左右暗塊換縮放層級、換 2026-08 的歷史版本都去不掉；
  Sentinel-2 整片同一套處理、沒有拼接。解析度 10 公尺，全景的顯示比例一個像素約 15 公尺，抓細一級（`zoomOffset: 1`）就夠。
  代價：房子看不到細節；影像是 2024 年的，TCAP 2（2025 年 10 月移交）那時還在施工。
  ⚠ **授權是 CC BY-NC-SA 4.0（非商業使用）**，環資是非營利媒體，發稿前由 owner 判斷；署名照 EOX 要求的字樣。
- 之前的版本在 git 歷史：Esri 衛星版（`d6d7516`）、插畫風對照檔（`6fd3fdf`）。拿掉 `TILES` 就回到插畫風的島嶼輪廓加礁盤
  （不用行政界，因為 Funafuti 的行政區多邊形把整個潟湖包進去）。

## 圖釘與說明卡的設計（09-29 改了兩輪）
- 第一輪：owner 說「字體的白底怪怪的」，東京插畫風的白底膠囊和白卡片放在擬真影像上像貼紙。改成衛星主題，
  方向照 owner 說不錯的颱風短影音（深綠＋黃），以及路透〈Concrete and coral〉在衛星影像上的白字標註。
- 第二輪：owner 要拿掉經緯度與卡片到圖釘的連線，並嫌圖示「包太多框線」。參考 pbakaus/impeccable 的 distill、quieter
  兩份指引（能拿掉的框線、陰影、光暈都拿掉，效果只留一層），圖釘只剩實心圓點＋一層淡陰影，
  正在介紹的點改成放大＋地名變黃；說明卡、標題框也拿掉細框。
- 分類色：黃、珊瑚紅、米白、天藍，在藍海、青綠潟湖、綠植被上跳得出來，圖釘數字一律深綠字（對比都在 6:1 以上）。
- 設計參考清單：母層 `logs/tuvalu-design-refs/design-refs-20260929.md`（本機）。

## 跟東京那張不一樣的地方
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
- 衛星影像：Sentinel-2 cloudless – s2maps.eu by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2024)，CC BY-NC-SA 4.0。
- 島嶼、礁盤（插畫風底圖）：© OpenStreetMap contributors（ODbL）。
- 說明文字：改寫自環境資訊中心〈吐瓦魯：海浪帶不走的家〉專題報導。
- 地點座標：採訪團隊整理的 Google 地圖連結，取地點本身的座標。
- 照片：環境資訊中心，版權所有，未經同意請勿轉用。
