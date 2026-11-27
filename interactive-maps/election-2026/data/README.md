# data — 2026 縣市長選舉地圖的測試資料

下載日期一律 2026-11-17。請求匿名（User-Agent 只寫用途 `einfo-election-map/0.1`），每個請求間隔 2 秒。
`raw/` 裡是原樣下載的檔案，只當資料讀；整理好的檔案在這一層。

## 檔案

| 檔案 | 內容 | 怎麼來的 |
|---|---|---|
| `mayor_2022.json` | 2022 年 22 縣市首長選舉結果：每縣市的選舉人數、投票數、有效票、無效票、投票率，以及每位候選人的姓名、政黨、得票數、得票率、是否當選，依得票數排序 | `scripts/fetch_cec.py` |
| `referendum21_2025.json` | 2025-08-23 全國性公投第 21 案（核三繼續運轉）22 縣市的同意、不同意、有效、無效、投票權人數、投票率，與環資 2025 年地圖用的指標 `margin`＝（同意－不同意）／投票數（含無效票）×100 | `scripts/fetch_cec.py` |
| `counties.geojson` | 22 縣市界，已簡化（容差 0.001 度、座標留 4 位小數），313 KB，gzip 後 78 KB；0.002 度在臺北市拉近時看得出折角，11-17 截圖比過改用 0.001 度。屬性只有 `code`（跟中選會同一套代碼）與 `name` | `scripts/build_counties.py` |
| `raw/cec_live_2022/` | 2022 年中選會開票網頁的兩段 HTML（Wayback 存檔）：屏東縣長候選人得票數（`TC_`）、臺北市長選舉概況（`SC_`），寫開票夜解析程式時拿來測 | Wayback Machine |
| `worst_case.json` | 最壞資料（break-ui 用，只在本機切換），格式同 `mayor_2022.json`，另加 `status`、`stations`、`updated`、`note` 欄位，說明見檔內 `meta.note` | 一次性產生 |
| `tags.csv` | 六都兩位候選人的環境政見標籤（`code,county,candidate,tags`，標籤用「、」分隔）；地圖只顯示當選人那一列，只用在 2026 年的結果；`county` 欄只給人看，對應用 `code` | 編輯提供 |
| `party_codes_2026.json` | 2026 才出現、2022 中選會政黨代碼表沒有的 5 個小黨（`party_code,party_name,color_code`，代碼 90001 起自訂，地圖塗灰）；`fetch_live.py` 與 `build_map.py` 都把它併進代碼表，「台」「臺」兩種寫法都認。開票夜若中選會頁面的黨名跟這裡不同，在這裡補 | 從 `candidates_2026.csv` 對代碼表找出（11-27） |
| `candidates_2026.csv` | 2026 年 22 縣市的候選人與推薦政黨（`code,county,name,party`，照 115 年選舉公報，前兩位的順序是測試用的、不是號次）；首頁版字型預先收這些字（開票夜名字才從 `live.json` 進來），假中選會 `scripts/fake_cec.py` 也讀它 | 從 `preview/make_test_2026.py` 的名單抄出 |
| `results_2026_template.csv`、`referendum22_2026_template.csv` | 開票夜手動輸入的空白範本（22 縣市的代碼與名稱已填），欄位見 SPEC「開票夜步驟」 | 手寫 |
| `results_2026.csv`／`.json`、`referendum22_2026.csv`／`.json` | 開票夜才有：抓下來或手動抄的結果，與轉給產生器的 JSON | `scripts/fetch_live.py` |
| `raw/cec_live_2026/` | 開票夜才有：抓到的開票頁原樣 | `scripts/fetch_live.py` |

重產：

```
python -I scripts/fetch_cec.py            # 原始檔已在 raw/ 就不重抓，加 --force 重抓
python -I scripts/build_counties.py 0.001 # 印出各種容差的大小，寫出指定容差那一份
python -I build_referendum.py             # 公投地圖：data/referendum21_2025.json → referendum-2026.html；開票夜加 --data 指到第 22 案的資料檔
```

`referendum21_2025.json` 的 `case` 是案號、地圖標題用的簡稱、主文、投票日、投票權人總額（null＝22 縣市加總），`fetch_cec.py` 從 `raw/cec_db/ref_list_N.json` 寫入，簡稱是手寫的。

各種容差量到的大小（22 縣市、裁掉東沙南沙釣魚臺後）：

| 容差（度） | 頂點數 | GeoJSON | gzip |
|---|---|---|---|
| 0（原始） | 306,011 | 5,617 KB | 851 KB |
| 0.0005 | 29,341 | 543 KB | 138 KB |
| 0.001 | 16,830 | 313 KB | 78 KB |
| 0.002 | 9,884 | 186 KB | 47 KB |
| 0.004 | 6,044 | 116 KB | 28 KB |

## 來源與授權

### 中央選舉委員會 選舉及公投資料庫
- 網站：<https://db.cec.gov.tw/>。資料是網站自己讀的靜態 JSON，路徑規則（從網站的 JS 讀出來的）：
  `https://db.cec.gov.tw/static/elections/data/{tickets|profiles}/ELC/{C1|C2}/00/{主題代碼}/C/00_000_00_000_0000.json`，
  公投是 `https://db.cec.gov.tw/static/referendums/data/{tickets|profiles}/N/{主題代碼}/C/00_000_00_000_0000.json`。
  C1＝直轄市長、C2＝縣市長（`/static/elections/configs/ELC_subjects.json`）；主題代碼查 `/static/elections/list/ELC_C1.json`、`ELC_C2.json`、`/static/referendums/list/N.json`。
- 用到的主題：111年直轄市長選舉 `05cc7b904c7a30cc7c88d5b10898c98e`、111年縣市長選舉 `63615098f5afa8ec53159c4a86fc01d3`、
  111年嘉義市長重行選舉 `1275d73551f2c0caf202e803b1766057`（2022-12-18）、公投第 21 案 `67e0b4764145bc1edb0eb02f11b383ff`。
- 政黨配色參考：`/static/webs/configs/party_colors.json`（存在 `raw/cec_db/`）。
- 授權：中選會上架到政府資料開放平臺的資料集都標「政府資料開放授權條款－第1版」（例：<https://data.gov.tw/dataset/168990>）。
  選舉資料庫網站本身的授權頁沒找到，推定同一條款，不清楚需查找。整包資料庫另有下載檔 <https://data.cec.gov.tw/選舉資料庫/votedata.zip>（110 MB，2026-01-26 更新，沒有下載）。
- 標示：「資料來源：中央選舉委員會」。

### 內政部國土測繪中心 直轄市、縣市界線(TWD97經緯度)
- 資料集：<https://data.gov.tw/dataset/7442>，提供機關內政部國土測繪中心，版本 1140318（詮釋資料 2025-03-18）。
- 下載：SHP <https://www.tgos.tw/tgos/VirtualDir/Product/1cd4f4c9-6b01-4cf9-bf6c-23a73aa17d24/直轄市、縣(市)界線1140318.zip>
  （存在 `raw/nlsc_county_1140318/`，3.7 MB，可重抓，建議不進 repo）。座標 TWD97 經緯度，跟 WGS84 差不到 1 公尺，Leaflet 直接用。
- 授權：政府資料開放授權條款－第1版（<https://data.gov.tw/license>）。顯名聲明照條款附件寫：
  > 內政部國土測繪中心 2025 直轄市、縣市界線(TWD97經緯度) 1140318版
  > 此開放資料依政府資料開放授權條款 (Open Government Data License) 進行公眾釋出，使用者於遵守本條款各項規定之前提下，得利用之。
  > 政府資料開放授權條款：https://data.gov.tw/license
- 東沙、南沙、釣魚臺在裁切範圍（經度 118.0–122.1、緯度 21.8–26.5）外，不畫。

### 中選會公告（公投第 22 案）
- `raw/cec_referendum22/cec_3ea9497f.pdf`：中選會 115-08-28 中選務字第 1153150284 號公告，取自
  <https://web.cec.gov.tw/api/file/3ea9497f-7945-49a2-bd4b-375e3d6f1ddf.pdf>。

## 讀資料時要注意
- 罕用字：中選會把字型裡沒有的字寫成 `@碼位@`，例如宜蘭縣 2022 年的「江@2F97F@淵」。換回字元要先轉碼位再做 NFC 正規化：
  U+2F97F 是相容表意文字，NFC 後是 U+8070「聰」，顯示成「江聰淵」。
- 嘉義市 2022-11-26 那場停止選舉（縣市長那份資料裡嘉義市的有效票是 0），結果用 12-18 重行選舉，`vote_date` 有標。
- 連江縣 2022 年前兩名在中選會資料裡都是「中國國民黨」，資訊欄前兩名可能同色。
- 中選會的政黨代碼：國民黨 1、民進黨 16、民眾黨 350、無黨籍 999（顯示名稱「無黨籍及未經政黨推薦」）。腳本照這三個代碼分藍、綠、眾，其他一律灰。
- 2022 結果（中選會資料）：國民黨 14、民進黨 5、民眾黨 1（新竹市）、無黨籍 2（苗栗縣、金門縣）。
- 公投第 21 案全國同意 4,341,432、不同意 1,511,693，跟環資 2025 年那張圖一致。
