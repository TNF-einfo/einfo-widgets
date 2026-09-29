# tuvalu — 吐瓦魯・富納富提 互動地圖

〈環境資訊中心〉吐瓦魯報導用的長型互動地圖。**測試中（2026-09-29），分類與說明文字待 owner 確認，先不要發稿。**

## 檔案
- `spots.py`：12 個地點、分類、照片、說明文字。要改內容只改這個檔。
- `build_land.py`：抓富納富提環礁的島嶼與礁盤，寫成 `boundaries/land.geojson`、`boundaries/reef.geojson`（插畫風底圖用）。
- `photos/`：12 張照片，縮成 800px 寬、不帶 EXIF。
- `basemap/`：Sentinel-2 靜態底圖（見「底圖」）。
- `tuvalu-map.html`（產出的地圖）、`article-preview.html`（桌機／平板／手機三檔寬度對照）。

## 說明文字
取自〈吐瓦魯：海浪帶不走的家〉專題（<https://www.e-info.org.tw/feature/36>）六篇報導，只寫報導裡寫過的事，
`spots.py` 每個點的行尾註解是出處的 node 編號。主島 Fongafale 照報導譯作「豐阿法萊」。

## 底圖
- **現行：Sentinel-2 2026-01-05 單景（`basemap/s2_20260105_2x.webp`）**，10 公尺影像放大兩倍並銳化成 Web Mercator 靜態圖，
  範圍 lon 179.14–179.24、lat -8.575～-8.415，用 `IMAGE` 設定鋪上去（一個請求、280 KB）。看得到 TCAP 新生地、整片色調一致，
  放大比 Esri 軟。影像由 Planetary Computer 的渲染 API 輸出，挑片與比較圖在母層 `logs/tuvalu-design-refs/s2/`。
  owner 看了比較圖說「換銳化的看看」（09-29），還在試。
- 拿掉 `spots.py` 的 `IMAGE` 就回到 Esri Wayback 2024-11-18 版（#49849）：高解析、看得到 TCAP 1 新生地，
  但北段潟湖上空有雲，中段海面有一大塊拼接的灰色色塊（2024-12 與 2026 版也有）。
- 經過（09-29 同一天換了五次）：
  1. Esri 最新版：南端灰帶與左右暗塊，是這一帶影像本身的拼接，換縮放層級也在。
  2. owner 從四張比較圖挑了 Sentinel-2 無雲鑲嵌 2024（EOX）：整片均勻，但 10 公尺解析度，owner 嫌「底圖太模糊」。
  3. 掃了 Wayback 25 個版本（10 種不同影像，截圖在母層 `logs/tuvalu-design-refs/`），用最乾淨的 2022-06 版（#44710）：
     沒有雲、沒有灰帶，但拍攝時間早於 TCAP 1 開工（2022-12），看不到新生地。2024-03 版有雲，2024-12 與 2026 版有大塊拼接。
  4. owner 說「Esri 有雲沒差」，改用 TCAP 1 新生地完整的 2024-11 版。要回 2022-06 版，把 `spots.py` 網址裡的 `49849` 改回 `44710`、
     出處日期改回 2022-06-08 就好（那版每張圖磚會先轉址一次，載入較慢）。
  5. 查完授權（見下一點），owner 從 Sentinel-2 與 Esri 的比較圖選了 Sentinel-2 銳化版。
- ⚠ **授權**（09-29 查證，原文與出處在母層 `logs/tuvalu-design-refs/license/license-findings.md`）：Esri 圖磚不能自己存成檔案，
  截圖用在新聞稿要先向 Esri 申請，非營利沒有免申請特例；像現在這樣不登入帳號直接串圖磚，條款沒寫清楚，要問 Esri。
  Sentinel-2 可散布，要標「Contains modified Copernicus Sentinel data [年份]」。發稿前要定案。
- 出處照 Esri 圖層現行的寫法（Maxar 已改名 Vantor）。
- 之前的版本在 git 歷史：Sentinel-2 版（`800cae8`）、Esri 最新版（`d6d7516`）、插畫風對照檔（`6fd3fdf`）。
  拿掉 `TILES` 就回到插畫風的島嶼輪廓加礁盤（不用行政界，因為 Funafuti 的行政區多邊形把整個潟湖包進去）。

## 載入速度（09-29 owner 問能不能加速）
圖磚層級改成依畫面縮放與螢幕密度挑「剛好夠清楚」的一級（產生器的做法見 `interactive-maps/README.md` 的 `TILES`），
並先連線到圖磚主機。實測（不用快取、從台灣連線）：

| 畫面 | 改前 | 改後 |
|---|---|---|
| 桌機 720、一般螢幕 | 70 張，5.3 秒 | 20 張，1.3 秒 |
| 桌機 720、視網膜 | 247 張，15.6 秒 | 70 張，2.6 秒 |
| 手機 353、3 倍螢幕 | 192 張，12.0 秒 | 52 張，1.9 秒 |

改前的 2022-06 版每張圖磚還會先轉址到它實際所在的版本（301），請求數是張數的兩倍。
Esri 圖磚不能自己拼成一張靜態圖來加速（授權不允許，見上一節）。現行的 Sentinel-2 靜態圖只要一個請求（280 KB）。

## 圖釘與說明卡的設計（09-29 改了兩輪）
- 第一輪：owner 說「字體的白底怪怪的」，東京插畫風的白底膠囊和白卡片放在擬真影像上像貼紙。改成衛星主題，
  方向照 owner 說不錯的颱風短影音（深綠＋黃），以及路透〈Concrete and coral〉在衛星影像上的白字標註。
- 第二輪：owner 要拿掉經緯度與卡片到圖釘的連線，並嫌圖示「包太多框線」。參考 pbakaus/impeccable 的 distill、quieter
  兩份指引（能拿掉的框線、陰影、光暈都拿掉，效果只留一層），圖釘只剩實心圓點＋一層淡陰影，
  正在介紹的點改成放大＋地名變黃；說明卡、標題框也拿掉細框。
- 第三輪（owner）：照片不要裁太扁（改 3:2、相機原圖比例）；標題框移到右邊、疊在圖例上面；
  說明卡可以按住拖曳、往下捲時跟著停在畫面裡（`POPUP_FLOAT`）。
- 第四輪（owner）：按住照片也要能拖卡片（照片加 `draggable="false"`，iOS 長按不跳選單）；標題框與圖例也跟著捲動、但不能拖；
  富納法拉太遠，改畫在右下角的小地圖（見下一節）。順手修了直接開網址、視窗比 1080 矮時地圖上緣被切掉的問題。
- 第五輪（owner）：加放大，桌機按住不放、手機雙指捏開就放大，放手後停 1.5 秒再彈回原尺寸
  （只放大底圖，圖釘與名稱維持原大小、跟著位置走；第一版連字一起放大，owner 說會糊）；
  手機、平板也放標題（縮小一號，圖例照樣藏）；手機說明卡從四成寬放大到五成。小地圖 owner 說先不要移，維持右下。
  順手修了換成 Sentinel-2 靜態圖後圖釘畫偏的問題（圖示錨點只看 `TILES`，落回插畫風水滴針的錨點，整排往上偏 13px）。
- 手機說明卡預設貼在看得到那一段的左下角（owner 09-29），捲到底時停在出處上面；桌機、平板照舊停在正中間。
  捲到最底時會蓋到 TCap 1、政府大樓、TCap 2 的名字，卡片可拖開。
- 分類色：黃、珊瑚紅、米白、天藍，在藍海、青綠潟湖、綠植被上跳得出來，圖釘數字一律深綠字（對比都在 6:1 以上）。
- 設計參考清單：母層 `logs/tuvalu-design-refs/design-refs-20260929.md`（本機）。

## 跟東京那張不一樣的地方
- 固定高度 1080px，寬度跟著文章欄寬走（`HEIGHT`）。手機上比螢幕高，讀者往下捲著看，比例尺不會跟著縮小。
- 說明卡固定在左側中段，也就是潟湖那片空白（`POPUP_SIDE`），不去擠南端那一群點。
- 富納法拉離主島約 16 公里，框進來會把主島縮到點都疊在一起，所以設成 `offmap`，畫在右下角的小地圖（`INSET`）上：
  整個富納富提環礁的礁盤與島嶼（`boundaries/` 那兩個 geojson），白框是主圖範圍，⑫ 點了照樣開說明卡。
  原本畫在主圖左下角、寫「↙ 富納法拉 16 公里」，owner 說太遠（09-29）。

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
- 衛星影像：Contains modified Copernicus Sentinel data 2026（Sentinel-2，2026-01-05；裁切、重投影、放大銳化過，依 Copernicus 法律聲明標示）。
  換回 Esri 時：Imagery © Esri, Vantor, Earthstar Geographics, and the GIS User Community（用在新聞網站的條件見「底圖」一節）。
- 島嶼、礁盤（小地圖與插畫風底圖）：© OpenStreetMap contributors（ODbL）。
- 說明文字：改寫自環境資訊中心〈吐瓦魯：海浪帶不走的家〉專題報導。
- 地點座標：採訪團隊整理的 Google 地圖連結，取地點本身的座標。
- 照片：環境資訊中心，版權所有，未經同意請勿轉用。
