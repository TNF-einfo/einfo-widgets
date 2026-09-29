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
- **現行：Esri 歷史影像庫（Wayback）2022-06-08 版（#44710），高解析**。一般螢幕抓細一級、視網膜螢幕抓細兩級（`detectRetina`）。
- 經過（09-29 同一天換了三次）：
  1. Esri 最新版：南端灰帶與左右暗塊，是這一帶影像本身的拼接，換縮放層級也在。
  2. owner 從四張比較圖挑了 Sentinel-2 無雲鑲嵌 2024（EOX）：整片均勻，但 10 公尺解析度，owner 嫌「底圖太模糊」。
  3. 掃了 Wayback 25 個版本（10 種不同影像，截圖在母層 `logs/tuvalu-design-refs/`），2022-06 這版最乾淨：沒有雲、沒有灰帶。
     2024-03 版有雲，2024-12 與 2026 版有大塊拼接。
- 代價：拍攝時間早於 TCAP 1 開工（2022-12），圖上看不到新生地（Esri 各版都看不到；Sentinel-2 2024 看得到 TCAP 1 但模糊）。
- ⚠ **發稿前要確認 Esri 影像用在新聞網站的授權條件，還沒查。**
- 之前的版本在 git 歷史：Sentinel-2 版（`800cae8`）、Esri 最新版（`d6d7516`）、插畫風對照檔（`6fd3fdf`）。
  拿掉 `TILES` 就回到插畫風的島嶼輪廓加礁盤（不用行政界，因為 Funafuti 的行政區多邊形把整個潟湖包進去）。

## 圖釘與說明卡的設計（09-29 改了兩輪）
- 第一輪：owner 說「字體的白底怪怪的」，東京插畫風的白底膠囊和白卡片放在擬真影像上像貼紙。改成衛星主題，
  方向照 owner 說不錯的颱風短影音（深綠＋黃），以及路透〈Concrete and coral〉在衛星影像上的白字標註。
- 第二輪：owner 要拿掉經緯度與卡片到圖釘的連線，並嫌圖示「包太多框線」。參考 pbakaus/impeccable 的 distill、quieter
  兩份指引（能拿掉的框線、陰影、光暈都拿掉，效果只留一層），圖釘只剩實心圓點＋一層淡陰影，
  正在介紹的點改成放大＋地名變黃；說明卡、標題框也拿掉細框。
- 第三輪（owner）：照片不要裁太扁（改 3:2、相機原圖比例）；標題框移到右邊、疊在圖例上面；
  說明卡可以按住拖曳、往下捲時跟著停在畫面裡（`POPUP_FLOAT`）。
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
- 衛星影像：Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community（World Imagery Wayback 2022-06-08；用在新聞網站的條件待查）。
- 島嶼、礁盤（插畫風底圖）：© OpenStreetMap contributors（ODbL）。
- 說明文字：改寫自環境資訊中心〈吐瓦魯：海浪帶不走的家〉專題報導。
- 地點座標：採訪團隊整理的 Google 地圖連結，取地點本身的座標。
- 照片：環境資訊中心，版權所有，未經同意請勿轉用。
