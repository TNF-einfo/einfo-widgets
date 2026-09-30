# interactive-maps — 可內嵌互動地圖（任意城市）

〈環境資訊中心〉風格的**可內嵌互動地圖**（單一自足 HTML，無圖磚＝無道路、只留行政界線＋水域）。
在一個實例資料夾裡編「地點＋敘述」，跑一行就產出地圖——界線自動抓、標籤自動排。

> **哪一份是交付版**：發稿請用 **`tokyo-map-stable/`**（標籤手動排好、文章 node/243698 就是這一版）。
> `tokyo-autolayout-test/` 是自動排版的測試，位置與手調版不同，**先不要拿去發稿**
> （owner 2026-08-25 決定）。

## 結構
```
interactive-maps/
  template/               引擎（可重用）
    gen_map.py            產生器：讀 {instance}/spots.py → 補座標→抓界線→自動排標籤→產地圖＋文章預覽
    fetch_boundaries.py   任意城市界線抓取（Nominatim 定位 + Overpass 抓行政界 + osm2geojson 組多邊形）
    article_preview.tpl.html  文章預覽模板（地圖 base64 內嵌、複製鈕本地解碼）
    build_*.py / verify_map.py / render_labels.py   舊工具（東京界線來源／Python 自我核對）
  tokyo-map-stable/       ★ 交付版：手調標籤、無法重生（標籤寫在產出的 HTML 上，不在 spots.py）
  tokyo-autolayout-test/  自動排版測試＝產生器的實例（手調三層界線＋手列地名，設了 BOUNDARIES 故不自動抓）
    spots.py             ★ 只編這個：TITLE/MARK + CAT 分類 + SPOTS（地點名/敘述，座標可省→自動編碼）
    boundaries/          自動抓後快取於此（land/subdiv.geojson + places.json + geocode.json）
    <MAP_FILE> + article-preview.html   ← 產生
  tuvalu/                 吐瓦魯・富納富提（第一版、測試中）：長型、環礁底圖、用到下面的選用設定
  video/                  地圖 → 直式短影音（見母 README 為何不搬去 data-shorts）
```

## 開一張新城市地圖（給同事／未來 MCP）
1. 開一個 `<yourcity>/` 資料夾，裡面只放一個 `spots.py`：`TITLE`、`MAP_FILE`、`CAT`、`SPOTS`
   （每個 spot 給 `zh` 名＋`desc`＋`cat`；`lat`/`lng` 可省略→自動地理編碼，或給 `geo` 當查詢字串）。
   **不要**設 `BOUNDARIES`（留空才會自動抓那一帶的行政界線）。
   > 現成的範本：原本有一份 `demo-kaohsiung/`（無 `BOUNDARIES`、自動抓界線，證明任意城市可用），
   > owner 2026-08-25 決定從這個公開 repo 移除。要照抄的話，它還在 git 歷史裡
   > （`git log --diff-filter=D -- interactive-maps/demo-kaohsiung`），也還在 `gassao1998/einfo-scratch`。
   > 注意**不要**複製 `tokyo-autolayout-test/` 當範本——那個實例設了 `BOUNDARIES`，不會自動抓界線。
2. `python template/gen_map.py <yourcity>` → 首次會抓界線（需連網、快取進 boundaries/），之後離線可重跑。
3. 嵌入碼到 <https://tnf-einfo.github.io/einfo-widgets/> 按「複製嵌入碼」拿（尺寸規則已固定，別自己改）。
> ⚠ 若某城市所有景點**擠在很小範圍**，手機/平板檔位 popup 可能壓到少數 pin（桌機不受影響）；景點散布全市（如東京）則各檔位皆乾淨。

### 選用設定（`spots.py` 裡，不設就照東京的預設）
- `HEIGHT`：固定畫框高度（px），寬度跟文章欄寬走。長型地圖用：手機上照樣這麼高、往下捲著看，不會整張縮小。
  設了它，嵌入碼外框要改用 `height:<HEIGHT>px`，不用 `aspect-ratio`（見 `tuvalu/README.md`）。
- `ASPECT`：固定比例，預設 `720/476`。
- `UNDERLAY`：畫在陸地下面的填色層（`boundaries/` 裡的 geojson），例如環礁的礁盤。
- `TILES`：`{"url", "attribution", "maxNativeZoom"}`，改用圖磚底圖（例如衛星影像）。選用 `filter`（CSS filter 字串，影像調色）。
  抓哪一級圖磚由頁面自己算：一個圖磚像素對到 1～2 個螢幕實體像素，視網膜算到 2 倍為止（09-29 起；之前的 `zoomOffset`／`tileSize`／
  `detectRetina` 固定多抓一兩級，吐瓦魯在視網膜螢幕要載 247 張、改完 70 張）。頁首會先連線到圖磚主機（preconnect）。
- `IMAGE`：`{"url", "bounds": [[南, 西], [北, 東]], "attribution"}`，改用一張地理對齊的靜態影像當底圖（Web Mercator 投影，
  照四角拉伸就對得上），一個請求載完。設了它就不用 `TILES`，其餘跟 `TILES` 一樣換成衛星主題。
  衛星主題下標題框疊在圖例上面、都靠右。
  設了它就不畫向量陸地、不抓界線、拿掉紙紋，並換成「衛星主題」（CSS 都在 `.frame.tiles` 底下，插畫風地圖不受影響）：
  配色取自環資颱風短影音（深綠＋黃 `#f0b429`）；能拿掉的框線都拿掉：圖釘只剩 20px 實心圓點＋一層淡陰影，
  地名白字深色描邊、不用底，說明卡與標題框只靠陰影分邊；正在介紹的點放大、地名變黃；
  說明卡照片滿版、標題用思源宋體（Google Fonts 用 `text=` 只載用到的字）。圖磚的授權要自己確認（見 `tuvalu/README.md`）。
  衛星主題另有「放大」（只有觸控，owner 說桌機不要）：雙指捏開最多 4 倍、原地縮放（捏的那一點留在兩指中間）；
  放大中單指拖就移動畫面，拖不出地圖邊界；放手後停 0.5 秒再彈回，彈回前再捏或拖會接著目前的狀態。
  彈回時頁面跟著捲（`scrollIntoView`，iframe 裡也捲得動外頁），畫面正中間那塊地圖彈回後還在中間，長型地圖不會跳回最初放大的那一段。
  放大中小地圖（`INSET`）淡出、不接觸控，彈回後再出現（不然放大的地名會疊在它上面、在它上面也拖不動）。
  桌機按住放大的做法留在 git 歷史 `8ebbddb`。
  只用 CSS scale 放大底圖（圖磚、影像），圖釘與地名不放大、只照放大後的位置移動（字才不糊）；不動 Leaflet 的縮放級，彈回後不必重排標籤。
  衛星主題的判斷一律看 `TILES` 或 `IMAGE`（JS 的 `SAT`），只看 `TILES` 會讓 `IMAGE` 底圖的圖釘錨點跑掉。
  手機、平板檔也顯示標題（縮小一號），圖例照樣藏；手機說明卡寬五成。

圖釘名稱還有一條規則：名字離別的圖釘比離自己的近時重罰（讀者會看錯是誰的名字），所以會換邊擺。
spot 加 `"label": "right"／"up"／"left"／"down"` 就固定放那一邊、也不會被藏起來（owner 點名要調的名字用，例如吐瓦魯的友誼農場）；
再加 `"label_dy"`（px，負＝往上）可以在那一邊上下微調。
- `POPUP_SIDE`：`"left"`／`"right"`，說明卡固定在該側中段；不設就自動挑圖釘最少的角落。
- `POPUP_FLOAT`：`True` 時說明卡可按住拖曳（照片上也行），文章往下捲時跟著停在地圖「看得到的那一段」正中間（拖過就保留偏移）；
  標題框＋圖例也跟著停在看得到那一段的上緣，但不能拖。手機檔（≤527.98px）的說明卡改貼看得到那一段的下緣，一律不蓋住出處；
  會蓋到圖釘或名稱就往上挪到不蓋的地方（正在介紹的點重罰），讀者拖過就照他放的位置。
  輪播時頁面跟著捲到正在介紹的點，owner 09-30 說不需要了、已拿掉（做法在 git 歷史 `7c17240` 的 `followSpot`）。
  放大彈回時照樣會捲頁面，一律用放在 body 底下的探針 `scrollIntoView`：探針放在 overflow:hidden 的地圖裡，會連地圖容器本身一起捲走。
  做法是沿地圖高度鋪 108 條看不見的細條、用 IntersectionObserver 看哪幾條在畫面裡，跨網域 iframe 裡也拿得到、不必外頁配合。
  浮動卡片不當地名的障礙物；標題框＋圖例一律用它們回到頂端時的位置當障礙物，捲到一半重排也不會避錯地方。
- `INSET`：`{"title", "layers": {geojson: 填色}}`，右下角的小地圖（疊在出處上面）。geojson 依序疊畫、跟主圖同一個投影，
  頁面會框出主圖現在的範圍（主圖比小地圖寬時把視窗放大，框不會被切掉）。
- spot 加 `"offmap": 1`：這個點不參與縮放範圍、不畫在主圖，畫在小地圖上，點了照樣開說明卡。離其他點太遠、框進來會讓其他點擠成一團時用；
  要搭配 `INSET`，沒設會報錯。

圖釘名稱的排法（2026-09-29 起）：出框的代價比壓到別人高，名字優先留在框內；六個候選位置都會壓到別人超過一成時，
名字先藏、只留編號，點圖釘照樣開說明卡。`tokyo-autolayout-test/` 重產時，平板與手機檔會因此少幾個原本被切掉的名字。

## 短影音（`video/make_video.mjs`）
吃 `gen_map.py` 產的任何地圖，逐幀截圖接 ffmpeg 出直式影片：1080×1920，或 `--height 1305` 的 4:5 版。
社群安全區上 12%、下 15%（4:5 是 8.5%）、左右 9%。用法見檔頭；範圍小的地圖要自己給 `--zoom`（特寫的縮放，東京 12.2）
與 `--estab-out`（大遠景在 fit 之外再拉遠多少，預設 0.55）。
衛星主題（`TILES`／`IMAGE`）的地圖另外照衛星主題的卡片與地名樣式；地名分遠景、特寫兩套排，縮放時在兩套之間滑動（點很密時兩個縮放下的最佳位置不同）。
offmap 的點影片版也畫上主圖、鏡頭直接飛過去，所以底圖要鋪得到它：`--image <webp>` 換掉地圖的 `IMAGE`，範圍讀同名 `.json`。
兩點距離（用兩端縮放的中間值量）超過 2000px 的一段中途會先拉遠再推近、說明卡先收起，任何地圖都一樣（東京每段都不到）。
實例見 `tuvalu/README.md` 的「短影音」。

## 重產（自動排版測試版）
```
python template/gen_map.py tokyo-autolayout-test    # 讀該夾 spots.py → 重產它的 tokyo-bousai-map.html
```
`tokyo-map-stable/` **不能**用這個方式重產（標籤是手排在產出檔上的）。

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
