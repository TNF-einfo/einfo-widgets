# tokyo-map-stable — 東京・防災・生態 另類旅遊地圖（穩定版）

**改模板／auto-layout 之前、手動調校完成的可用版本**（地名標籤都是手動排好、不會重疊）。
從 commit `8fcb50e` 原樣取回，保存於此當作「隨時可交付」的安全版。

- `tokyo-bousai-map.html` — 地圖本體（手調標籤、無重疊）。
- `article-preview.html` — 三檔位示意＋「複製完整嵌入碼」鈕。

⚠️ 這版的複製鈕用 `fetch` 抓地圖檔，**請用審核 app 網址開**（`http://127.0.0.1:8787/tokyo-map/article`）；
直接 `file://` 開檔的話 fetch 會被瀏覽器擋。要改成 base64 內嵌（file:// 也能複製）跟我說一聲。

模板化＋標籤自動避讓（auto-layout）仍在隔壁 `tokyo-bousai-map/` 慢慢開發中（目前標籤會重疊、待調）。
