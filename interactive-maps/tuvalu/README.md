# tuvalu — 吐瓦魯・富納富提 互動地圖

〈環境資訊中心〉吐瓦魯報導用的長型互動地圖。**測試中（2026-09-29），先不要發稿。** 說明文字 09-30 已換成 owner 改好的圖說；分類 owner 只改了 TTCAP 一項，其餘還是暫定。

## 檔案
- `spots.py`：12 個地點、分類、照片、說明文字。要改內容只改這個檔。
- `build_land.py`：抓富納富提環礁的島嶼與礁盤，寫成 `boundaries/land.geojson`、`boundaries/reef.geojson`（插畫風底圖用）。
- `photos/`：12 張照片，縮成 800px 寬、不帶 EXIF。
- `basemap/`：Sentinel-2 靜態底圖（見「底圖」）。
- `build_video_basemap.py`：影片專用底圖（整個環礁），寫進 `basemap/video/`，不進 repo（見「短影音」）。
- `tuvalu-map.html`（產出的地圖）、`article-preview.html`（桌機／平板／手機三檔寬度對照）。

## 說明文字
2026-09-30 起照 owner 在地點表格那份 Google 文件「行銷討論」分頁改好的圖說，逐字照用，表格裡分兩段的在卡片上併成一段。
改之前的版本取自〈吐瓦魯：海浪帶不走的家〉專題（<https://www.e-info.org.tw/feature/36>）六篇報導、只寫報導裡寫過的事，
`spots.py` 每個點的行尾註解是當時出處的 node 編號。主島 Fongafale 照報導譯作「豐阿法萊」。
同一天 owner 把 ⑦ TTCAP 的分類從氣候調適改成台灣援助（owner 原話是「TCAP 改成台灣援助」，照台灣協助的 TTCAP 理解；TCap 1、2 的圖說寫的是聯合國支援）。

## 底圖
- **現行：Sentinel-2 2026-01-05 單景（`basemap/s2_20260105_2x.webp`）**，10 公尺影像放大兩倍並銳化成 Web Mercator 靜態圖，
  範圍 lon 179.14–179.24、lat -8.575～-8.415，用 `IMAGE` 設定鋪上去（一個請求、280 KB）。看得到 TCAP 新生地、整片色調一致，
  放大比 Esri 軟。影像由 Planetary Computer 的渲染 API 輸出，挑片與比較圖在母層 `logs/tuvalu-design-refs/s2/`。
  owner 看了比較圖說「換銳化的看看」，試過後定案（09-29 20:43：「現在的底圖可以」）。
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
- 放大後可以拖曳移動（owner 09-29）：手機放大後單指拖；拖不出地圖邊界，放手照樣停 1.5 秒再彈回。沒放大時單指照樣捲文章。
- owner 看過後說桌機不要放大，只留觸控（手機、平板）的捏開放大；桌機按住放大的版本在 `8ebbddb`。手機標題放大一號（16→19px）。
- owner 發現放手或手動縮小時畫面會跑回原本放大的地方，改成原地縮放：捏的那一點底下的地圖一直留在兩指中間
  （改前縮放中心固定在第一次捏的位置）；放手後等待時間 1.5 秒改 0.5 秒。
- owner 再試：放大後拖到畫面外的地方，放手彈回又回到最初那一段（頁面沒捲，彈回後看到的當然是原本那段）。
  先改成「放大時只能在看得到的那一段裡移動」，owner 說做反了（`707cdd0`）；改成彈回時頁面跟著捲：
  畫面正中間那塊地圖彈回後還在中間，停在移動後的地方。用 `scrollIntoView`，嵌在文章的 iframe 裡也捲得動外頁。
- 友誼農場（②）的名字固定放圖釘左邊（owner 09-29：放右邊會被擋），用 spot 的 `"label": "left"`。
- 放大中小地圖淡出（owner 09-29 傳截圖：放大移動後地名跑到小地圖上、圖釘被它蓋住，在上面也拖不動），彈回後再出現。
- 輪播時頁面跟著捲到正在介紹的點（owner 09-29）：讀者按著、捲動、放大時先不捲，放開 0.5 秒後才捲；地圖只露出不到螢幕六成
  （嵌在文章裡、讀者在看文字）時不捲。直接開網址時一載入就定在第一個點（南端那一群），不先停在北端再滑下去；
  嵌在文章裡則不在載入時硬跳，等讀者捲到地圖停下來才跟過去。手機說明卡預設貼下緣，會蓋到圖釘或名稱就往上挪，
  正在介紹的點重罰、幾乎不會被蓋；讀者拖過卡片就照他放的位置（owner：「要記得不要被遮到」）。
- 09-30（owner 看了測試站專題頁）：輪播時頁面跟著捲拿掉（「感覺不需要自動捲動找位置了」）；友誼農場的名字往上挪 8px（`label_dy`），
  手機寬度原本跟 TCap 2 疊到約 7px。
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
尺寸跟東京那張不同，外框用固定高度，不用 `aspect-ratio`。最外層不留上下 margin（owner 09-30）：e-info 的嵌入框自己有 32px，
再加一層地圖上下會空到約 64px。

```html
<div style="max-width:720px;margin:0 auto">
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

## 橫版（`wide/`，2026-09-30）
owner 看了測試站專題頁：「嵌在專題中的改成橫的如何？多做一版」。主島南北長約 9 公里、東西不到 3 公里，北朝上排成橫幅會縮成一條，
南端那群點擠在一起，所以整張圖順時針轉 90 度：島橫躺、北朝右（左下角畫指北箭頭），潟湖在上、外海在下。
- 地點與敘述照讀直版的 `spots.py`，改直版就會跟著變；座標、底圖、小地圖輪廓照 `wide/spots.py` 的 `rot()` 換算成轉過的經緯度，
  產生器不知道有轉。直版手調的名字位置（`label`）轉過之後不適用，拿掉交給自動排；潟湖的地名另外挪了位置（照換算會被圖例蓋到）。
- 版面：720×480，說明卡改成照片在左的橫式（`CARD = "row"`）放左上的潟湖，標題與圖例在右上，小地圖在右下。
  上方留 200px 給它們（`FIT_PAD`），左右只留 30px，主島才撐得滿寬度。
- 取捨：比例尺只有直版的七成多，南端最密的地方放不下所有名字：桌機藏了集會所、友誼農場，平板藏了政府大樓、友誼農場
  （只留編號，點了照樣開說明卡）；⑧⑥兩個圖釘邊緣碰在一起。手機寬度（350px）會擠成一團，嵌入時要換回直版，見下面的嵌入碼。
```
python interactive-maps/tuvalu/wide/build_wide.py        # 轉好的底圖與小地圖輪廓；已存在就跳過，加 --force 重做
python interactive-maps/template/gen_map.py tuvalu/wide  # 產 wide/tuvalu-map-wide.html
```
嵌入碼（畫面 700px 以下換回直版；藏起來的 iframe 有 `loading="lazy"`，不會載入）：
```html
<style>.tv-wide{display:block}.tv-tall{display:none}@media (max-width:700px){.tv-wide{display:none}.tv-tall{display:block}}</style>
<div class="tv-wide">
<div style="max-width:720px;margin:0 auto">
  <div style="position:relative;aspect-ratio:720/480">
    <iframe src="https://tnf-einfo.github.io/einfo-widgets/interactive-maps/tuvalu/wide/tuvalu-map-wide.html"
            title="吐瓦魯・富納富提" loading="lazy" allowfullscreen
            style="position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:16px">
    </iframe>
  </div>
</div>
</div>
<div class="tv-tall">
（直版嵌入碼，見上面「嵌入」）
</div>
```

## 短影音（2026-09-30）
owner 要照東京那支的安全區拍：1080×1920，上 12%、下 15%、左右 9% 不放東西（社群平台的介面會蓋住），不畫框線。
鏡頭跟東京一樣：大遠景 → 拉近 ① → 依序到 ⑫ → 拉回大遠景，每點停 2 秒，全長約 50 秒。
```
python interactive-maps/tuvalu/build_video_basemap.py   # 影片專用底圖（整個環礁），已存在就跳過；需連網
cd interactive-maps/video        # 第一次先 npm ci；要有 Chrome 與 ffmpeg
node make_video.mjs --map ../tuvalu/tuvalu-map.html --zoom 16 --estab-out 0.65 --height 1920 \
  --image ../tuvalu/basemap/video/s2_20260105_atoll_2x.webp
```
成品在 `video/out/tuvalu_1080x1920.mp4`，不進 repo。加 `--preview` 只輸出大遠景、每點特寫與飛越中點的 PNG，先看構圖用。
跟東京那支不一樣的地方：
- 卡片、標題、地名照這張地圖的衛星主題：深色無框卡片、照片滿版、白字描邊，正在介紹的點放大、地名變黃。
- 南端八個點太密，地名分成遠景、特寫兩套排，縮放時在兩套之間滑動：只照遠景排的話，特寫時「政府大樓」會貼在 ① 旁邊。
  遠景那套把南端的名字疊成左右兩欄，看錯是哪個點的罰分最重；友誼農場在遠景左邊怎麼放都會貼到 ⑤ 或 ③，改放右下，特寫照舊放左邊。
  第二版曾把遠景放不下的名字先藏起來，owner 看了說有些地名不見了，改成現在這樣。
- ⑧→⑨ 相隔約 6.5 公里（特寫縮放下 2897px，東京最遠一段 1344px），平移中途先拉遠再推近，免得像甩鏡頭。
- ⑫ 富納法拉：鏡頭直接飛過去（owner 09-30：「富那法拉可以直接移動過去，僅限影片版」），互動地圖照舊畫在右下角小地圖。
  影片版把它的圖釘也畫上主圖，底圖換成 `build_video_basemap.py` 切的整個環礁（同一景 2026-01-05、同樣放大兩倍銳化，
  跟主圖重疊的部分平均只差 2～3 階），不進 repo。⑪→⑫ 約 22 公里，中途拉遠到看得到整個環礁再推近，3.1 秒；
  最後從 ⑫ 拉回大遠景也一樣，2.5 秒。飛越途中說明卡與地名先收起。小地圖在影片裡不出現。
- 這一景環礁南半部有一片積雲：飛越時會入鏡，富納法拉特寫的上方與右邊也有雲，島本身沒被蓋到。
- 特寫是 zoom 16，一個 10 公尺像素放大成約 4 個螢幕像素，看得出糊，跟地圖上雙指放大到底差不多。
- Copernicus 出處放大到 17px 留在右下角（授權條件要讀得到），那裡在下方安全區外，可能被平台介面蓋到。

## 資料來源與授權
- 衛星影像：Contains modified Copernicus Sentinel data 2026（Sentinel-2，2026-01-05；裁切、重投影、放大銳化過，依 Copernicus 法律聲明標示）。
  換回 Esri 時：Imagery © Esri, Vantor, Earthstar Geographics, and the GIS User Community（用在新聞網站的條件見「底圖」一節）。
- 島嶼、礁盤（小地圖與插畫風底圖）：© OpenStreetMap contributors（ODbL）。
- 說明文字：改寫自環境資訊中心〈吐瓦魯：海浪帶不走的家〉專題報導。
- 地點座標：採訪團隊整理的 Google 地圖連結，取地點本身的座標。
- 照片：環境資訊中心，版權所有，未經同意請勿轉用。
