# coast — 吐瓦魯，富納富提 海岸線變化

富納富提主島豐阿法萊（Fongafale）瓦伊阿庫村一帶，2022 到 2026 年五個時間點的 Sentinel-2 衛星影像疊在一起，
配字卡講填海造陸怎麼改寫潟湖這一側的海岸線。2026-10-02 開始做，設計參考吐瓦魯互動地圖、放上字卡，之後也可能做成影片，第一版先交極簡的。

**已刊出**：嵌在環資〈在一切沉沒之前——不願沉默的吐瓦魯〉<https://www.e-info.org.tw/node/243890>（2026-10-06 確認；
文章 09-29 刊出，嵌入碼跟下面「嵌入」那段一字不差）。iframe 直接指 GitHub Pages 上的 `tuvalu-coast.html`，**改這個檔就是改線上文章**，
字卡、地名、影像要動之前先跟地圖的維護者確認。

## 檔案
- `tuvalu-coast.html`：頁面本體，單一 HTML，不用 Leaflet。字卡文字、地名、畫框範圍都寫在檔內的 `STEPS`、`LABELS`、`WIN`。
- `build_images.py`：抓五張影像寫進 `img/`（`--selftest` 檢查調色函式）。
- `img/s2_<日期>.webp`：五張影像，各約 60～80 KB；`img/bounds.json` 是影像範圍，頁面的 `B` 要跟它一樣。
- `build_timelapse.py`、`img/timelapse/`：只給影片用的每月縮時圖（見「影片版」），圖不進 repo，`list.json` 進 repo。

## 畫面與操作
- 樣式照吐瓦魯互動地圖的衛星主題：深綠半透明無框卡片、黃色強調、白字深色描邊的地名、思源宋體標題、環資 logo。
  地圖上沒有圖釘、線或框，新生地本身的白沙就看得出來；正在講的那一塊，地名變黃。
- 字卡上排是五個日期，點了就淡入那一年的影像；也可以左右滑、按方向鍵。畫面露出六成以上時每 7 秒自動往下一步（播完從頭），
  讀者點、滑、按鍵之後就不再自動播；系統設定減少動態時不自動播。吐瓦魯互動地圖的輪播是 4.2 秒，這裡字卡比較長，放慢到 7 秒。
- 影像依晚的疊在上面，往後是淡入、往回是淡出，所以地名與影像不會錯開。
- 畫框比例依嵌入的欄寬換：欄寬 600px 以上是正方形（桌機 720×720），以下是 2:3（平板 528×792、手機 353×529）。
  頁面自己看 iframe 的長寬比排版：正方形時標題在左上（潟湖）、字卡在右下（外海）；直式時字卡橫跨下緣，
  直式的框比較鬆，新生地剛好夾在標題框與字卡之間。

## 選片（2026-10-02）
Planetary Computer 上這一帶雲量 60% 以下的 Sentinel-2 L2A 共 349 景，最早一景是 2019-10-24。每半年挑雲量最低的三景拉小圖，
再挑填海區上方沒雲、看得出那個階段的：

| 步驟 | 日期 | 景號 | 為什麼挑它 |
|---|---|---|---|
| 填海之前 | 2022-08-09 | S2A_MSIL2A_20220809T222811_R072_T60LYR_20220811T084851 | 開工前最乾淨的一景 |
| 第一階段施工中 | 2023-06-05 | S2A_MSIL2A_20230605T222801_R072_T60LYR_20230606T031347 | 新生地填到一半 |
| 第一階段完工 | 2024-08-28 | S2A_MSIL2A_20240828T222751_R072_T60LYR_20240829T015044 | 第二階段（2024-10 動工）之前 |
| 第二階段完工 | 2026-01-05 | S2B_MSIL2A_20260105T222759_R072_T60LYR_20260106T011006 | 跟互動地圖底圖同一景；2025-09-27 那景有霧和雲 |
| 往北繼續填 | 2026-09-17 | S2C_MSIL2A_20260917T222801_R072_T60LYR_20260918T005311 | 最新一景，潟湖西側有兩小片雲 |

- 北段那塊新填地：2026-01、02 月的影像上還是淺綠色的淺灘，2026-04-15 已經填滿白沙，9 月更完整。
  ⚠ 字卡把它跟「第三階段 2026 年 1 月啟動、往北再填 4 到 7 公頃」並列，但**影像上這塊是不是第三階段，沒有來源直接寫到**，
  要請記者確認（他們 8 月在當地）。確認之前字卡只寫「影像上多了一片白色填地」，地名寫「北段新填地」。
- 各景的大氣、海況不同，原樣疊起來切換會整張忽明忽暗，所以每張都照 2026-01-05 那景做直方圖匹配（只調色）。
- 放大兩倍與銳化的參數跟互動地圖底圖一樣（UnsharpMask 半徑 1.6、55%）。10 公尺解析度，新生地約 100 公尺寬，桌機上約 18px。

## 字卡出處
2026-10-02 查的。字卡只改寫事實，不照抄報導段落（repo 收錄規則：不得含環資文章內容鏡像）。

1. **填海之前**：平均海拔約 2 公尺、NASA 2023 年評估海平面比 30 年前高將近 15 公分：
   環資〈在一切沉沒之前——不願沉默的吐瓦魯〉<https://www.e-info.org.tw/node/243890>、
   NASA〈NASA-UN Partnership Gauges Sea Level Threat to Tuvalu〉2023-08-15 <https://sealevel.nasa.gov/news/265/nasa-un-partnership-gauges-sea-level-threat-to-tuvalu>
   （中央社 2024-09-25〈吐瓦魯難抵海平面上升 聯大會議力爭國際支持保主權〉也引同一組數字 <https://www.cna.com.tw/news/aopl/202409250208.aspx>）。
   IPCC 最壞情境下 2050 到 2060 年富納富提將近一半土地每月大潮時淹水：UNDP TCAP 計畫頁 <https://www.undp.org/pacific/tcap>。
2. **第一階段施工中**：2017 年展開（環資 node/243890；聯合國駐太平洋協調辦公室〈From Ocean to Land〉2025-10-14
   <https://pacific.un.org/en/303495-ocean-land-tuvalu-reclaims-its-future-against-rising-seas>，綠色氣候基金 3600 萬美元也在這篇）；
   UNDP 執行、潟湖砂土、人口最密集的瓦伊阿庫村旁：環資 node/243890。
3. **第一階段完工**：2023 年底完工、長約 730 公尺、寬約 100 公尺、約 7.3 公頃、依 UNDP 設計標準可抵禦 2100 年以前的海平面上升：環資 node/243890；
   7.3 公頃也見 UNDP〈Official Handing Over of Reclaimed Land to the Government of Tuvalu〉<https://www.undp.org/pacific/stories/official-handing-over-reclaimed-land-government-tuvalu>。
4. **第二階段完工**：2024-10-29 動工、南側潟湖約 800 公尺、8 公頃、澳洲紐西蘭美國出資：UNDP〈Groundbreaking Ceremony Marks New Chapter in Tuvalu's Climate Resilience Journey〉
   <https://www.undp.org/pacific/press-releases/groundbreaking-ceremony-marks-new-chapter-tuvalus-climate-resilience-journey>；
   2025 年 10 月完工：UNDP 2025-10-15 新聞稿 <https://www.undp.org/pacific/press-releases/tuvalu-and-partners-deliver-landmark-coastal-adaptation-project-creating-new-land-future>、環資 node/243890；
   兩期合計約 15 公頃：環資〈老派智慧之必要 吐瓦魯如何維繫逐漸消失的傳統？〉<https://www.e-info.org.tw/node/243894>。
5. **往北繼續填**：第三階段 2026 年 1 月啟動、往北再填 4 到 7 公頃、2028 年中完工：環資 node/243890；
   UNDP 2025-10-15 新聞稿也寫了下一期（TCAP 1B）要往主島北段的海岸延伸。影像上那塊填地是不是第三階段見上一節。

UNDP 的頁面擋 WebFetch，是用 crawl4ai 渲染抓的。中央社的 MCP 當天連不上（401），改用網頁搜尋。

## 嵌入
首頁 <https://tnf-einfo.github.io/einfo-widgets/> 這一列的「複製嵌入碼」產出的就是這段。外框比例用 container query 看**欄寬**
（不看視窗寬），平板的 528 欄寬也會換成直式；不支援 container query 的舊瀏覽器一律正方形，照樣能用。

```html
<style>.eic-tuvalu-coast{container-type:inline-size;max-width:720px;margin:0 auto}.eic-tuvalu-coast>div{position:relative;aspect-ratio:1/1}@container (max-width:600px){.eic-tuvalu-coast>div{aspect-ratio:2/3}}</style>
<div class="eic-tuvalu-coast">
  <div>
    <iframe src="https://tnf-einfo.github.io/einfo-widgets/interactive-maps/tuvalu/coast/tuvalu-coast.html"
            title="吐瓦魯，富納富提 海岸線變化" loading="lazy" allowfullscreen
            style="position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:16px">
    </iframe>
  </div>
</div>
```

## 待確認
- 北段新填地是不是第三階段（見「選片」）。
- 字卡文字與標題（「海岸線變化 2022–2026」）：照中文寫作規則寫的，還沒確認過。
- 要不要加的東西（都還沒做，先問）：TTCAP（台灣協助的那段在港口一帶，10 公尺影像上看不出變化）、新生地描邊或上色、
  左右拖曳的前後對照。
- 影片版字卡內文要不要只留標題與日期（10-12 起待決定，見下一節）。

## 影片版（2026-10-12）
直式 1080×1920、約 17 秒的縮時，安全區照 `video/make_video.mjs`：上 12%、下 15%、左右 9%。
同一天改了好幾版：鏡頭不動、每步停 7 秒、41 秒（`b878d55`）→ 每步 5 秒加慢慢推近（`e17204f`）→
每月一張的縮時、階段停 3 秒、左下跑年月（`a8be750`）→ 現在這版
（左下的年月拿掉、改在字卡上排的分頁跟著跳，縮時加密到一秒五張，字卡不停、時間都給縮時，修了調色變暗與畫質，鏡頭固定不推近）。
```
python interactive-maps/tuvalu/coast/build_timelapse.py   # 縮時用圖，照 img/timelapse/list.json 補抓缺的（需連網）
cd interactive-maps/video        # 第一次先 npm ci；要有 Chrome 與 ffmpeg
node make_coast_video.mjs --preview   # 五個階段各一張 PNG，看構圖
node make_coast_video.mjs             # → out/tuvalu-coast_v2_1080x1920.mp4（不進 repo；版號是檔頭的 VERSION，重產新版就加一）
```
- 直接開這一頁、注入影片用的 CSS（標題框置中、字卡放大到 1080 寬的字級），**頁面檔本身不改**（它就是線上文章）。
- 縮時用圖（`build_timelapse.py`）：相鄰兩個階段之間切成 16 格，每格挑離中點最近、雲量 3% 以下、眼睛看過沒雲的一天，整格都沒有就空著。
  目前 14 張，四段各 2、2、4、1 張，加五個階段（10-12 那版是雲量 25% 以下、59 張，10-19 改成抽掉有雲的，見下一條）。
  放大銳化跟 `build_images.py` 相同；調色一樣對齊 2026-01-05 那景，但分布只拿 SCL 判為沒雲的像素算（`match_clear`）。
  整張一起算的話大片雲占掉亮部，陸地和海會被壓暗，像晚上。
  影片用的圖存無損 PNG（五個階段也照同樣做法另做一張，不用互動頁的有損 WebP），14 張約 17 MB。
  圖、原始解析度的 RGB 與 SCL（`raw/`）、算雲量用的 SCL 小圖（`scl/`，347 景約 45 MB）都不進 repo，挑片結果 `img/timelapse/list.json` 進 repo；
  要重挑加 `--reselect`（SCL 小圖抓過的不再抓），調色改了加 `--force` 重做。
- 抽掉有雲的影格（10-19，v2）：10-12 那份清單裁成影片畫面看，59 張裡 47 張看得到雲、雲影或霧。改法：
  - 雲量只算影片畫面露出的那塊（`VIEW`，`make_coast_video.mjs` 會印出來），並扣掉前後 90 天內其他景有三成以上也判成雲的像素
    （浪花、白沙、填好的地這些不會動的）。晴天在畫面裡原本有 1～9%，扣掉後多半剩 0.1～0.7%。門檻定 3%：施工中剛填的白沙與濁水變得快、扣不掉，
    晴天也會到 2.5%（2025-02-14）。整幅雲量不再先篩（2026-09-07 整幅 59% 是雲，這一小塊是晴的），這段期間 347 景都抓了 SCL 小圖。
  - SCL 抓不到小積雲、雲影和薄霧，扣掉後只剩 0.2% 的也可能有雲，所以門檻內的候選逐張裁成影片畫面看過，看到的 53 天記在 `REJECT`（日期與看到什麼）。
  - 結果：原本 59 張留下 12 張；同一格裡換上更晴的兩天（2023-10-13 → 2023-09-28、2025-01-15 → 2024-12-31），其餘有雲的格整格都找不到晴天，空著。
  - 階段影像：2026-09-17 潟湖上有兩團雲，影片改用同月的 2026-09-07（`SWAP`；09-02 雲更多，九月其他景整幅都是雲），互動頁照舊用 09-17。
    09-07 右側外海還有一小片很淡的灰影。2026-01-05 下緣右側外海有一道很淡的彩色條紋（疑似小雲，在字卡下方），同月只有 01-20 可換、雲更多，所以留著。
  - 影片腳本改照 `list.json` 的 `key` 認第幾個階段（09-07 的檔名對不上頁面的 09-17），輸出檔名加版號。節奏照舊，每段 3.5 秒由那段的圖平分，
    一段只剩 2 到 5 張，0.7 到 1.75 秒換一張，不再是一秒 5 張。10-12 那版（`out/tuvalu-coast_1080x1920.mp4`，檔名沒有版號）留著沒蓋掉。
- 畫質：影片壓縮用 CRF 17、preset slow（預設 CRF 23 在縮時那段會糊成方塊），10-12 那版 16.5 秒約 13 MB，v2 16.0 秒約 8 MB（圖少，壓起來比較小）。剩下的軟是 Sentinel-2 本身的 10 公尺解析度，
  1080 寬的畫面上一格要放大成三四個像素；要更清楚得用高解析商用影像，Esri 的不准截圖做成影片，要環資書面申請（見 `../README.md`「底圖」）。
- 播法：第一張停 0.5 秒；每段 3.5 秒，那段的縮時圖連同下一個階段那張平分（17 張就是一秒 5 張，每張六成時間淡入、四成停住），
  字卡到了階段那張就換（文字在淡入的前四分之一淡出、換字、再淡入），不停；最後多停 1.5 秒，整支 16 秒左右。兩個階段之間字卡維持上一段，
  上排目前那一格顯示縮時的年月，到下一個階段跳下一格、原來那格變回它的日期。沒有 `list.json` 就只播五個階段那五張。
- 字卡內文一兩秒讀不完，影片版要不要只留標題與日期還待決定（10-12 起）。
- 鏡頭固定：縮放取剛好把新生地（`FOCUS`，北到北段新填地、南到第二階段的尾巴）放進標題框與最高那張字卡之間的大小，
  但不小於影像鋪滿畫面，目前 1.755 倍；放得越小，10 公尺的影像看起來越不糊。推近的版本在 `9a2f361`。逐幀截，整支一兩分鐘產完。
- 「太平洋」在頁面上的位置到 1080 寬會落到右緣安全區外，影片版往內、往上移到離岸約 400 公尺（`OCEAN`）。
- Copernicus 出處放大到 17px 留在左下角，跟吐瓦魯地圖那支一樣在下方安全區外，可能被平台介面蓋到。

## 重產
```
python interactive-maps/tuvalu/coast/build_images.py          # 五張都在就跳過；加 --force 重抓（需連網）
python interactive-maps/tuvalu/coast/build_images.py --selftest
```
改字卡或地名直接改 `tuvalu-coast.html`，不用重跑。

## 資料來源與授權
- 衛星影像：Contains modified Copernicus Sentinel data 2022–2026（Sentinel-2 L2A，經 Microsoft Planetary Computer 取得；
  裁切、重投影、調色、放大銳化過，依 Copernicus 法律聲明標示）。
- 字卡：改寫自環境資訊中心〈吐瓦魯：海浪帶不走的家〉專題、聯合國開發計劃署、聯合國駐太平洋協調辦公室、NASA（見「字卡出處」）。
