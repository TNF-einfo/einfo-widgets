# einfo-widgets

〈環境資訊中心〉可嵌進文章的小東西：互動地圖、圖表、小工具。
一個子資料夾一個主題，透過 **GitHub Pages** 對外提供，文章用一行 `<iframe>` 嵌入。

網址根目錄：<https://tnf-einfo.github.io/einfo-widgets/>

## 為什麼要有這個 repo

早期的做法是把整份地圖（HTML＋CSS＋JS＋圖資）用 `srcdoc` **內嵌進文章內文**。實測
[node/243698](https://e-info.org.tw/node/243698) 的結果：

| | 大小 |
|---|---|
| `iframe srcdoc` | **329 KB** |
| 頁面的 `__NEXT_DATA__`（同一張地圖又存了一份） | 1,125 KB |
| 整份文件 | 1,572 KB |

那 329 KB **不是附件，它就是文章 content 欄位的一部分**——CMS 編輯器每次按鍵都要重新
序列化它、undo 每一步存一份、自動存檔整包送出，編輯區因此變慢變卡。讀者也要為一篇
文章載 1.5 MB，而且同一張地圖下載兩次。

改成託管之後，文章裡只剩一行 `<iframe src="…">`（約 200 bytes），問題兩邊同時解決。

**通則：內嵌進 CMS 內文的東西，小的可以自足內嵌，大的一定要走託管 URL。**
（參考量級：前後對比滑動器 3.9 KB → 內嵌沒問題；互動地圖 329 KB → 一定要託管。）

## 現有的住戶

### `interactive-maps/` — 可內嵌互動地圖（任意城市）

單一自足 HTML，Leaflet ＋ 內嵌行政區 GeoJSON；**無圖磚＝無道路**，只留行政界線與水域，
繁中地名自動位移避讓。互動全部關閉（不吃滾輪、不吃拖曳），嵌在文章裡不會攔走捲動。

嵌入東京那張：

```html
<iframe src="https://tnf-einfo.github.io/einfo-widgets/interactive-maps/tokyo/tokyo-bousai-map.html"
        title="東京・防災・生態 另類旅遊地圖" loading="lazy"
        style="width:100%;max-width:720px;aspect-ratio:720/476;border:0;border-radius:16px;display:block;margin:24px auto">
</iframe>
```

> ⚠️ 資料夾裡的 `*.embed.html` 是**舊做法**：它把整張地圖包成 `srcdoc` 讓人整段複製，
> 也就是上面說的 329 KB 問題來源。**新文章請用上面那一行 `src=`，不要再貼 `.embed.html` 的內容。**
> 舊檔保留是為了對照與追溯。

要新增一座城市的地圖，看 `interactive-maps/README.md`（複製 `demo-kaohsiung/` 改 `spots.py`，跑一行產生器）。

## 收錄規則

這個 repo 是**公開**的（公開才有免費的 Pages），所以收東西要嚴：

1. **自足靜態**：無金鑰、無後端、不需要建置伺服器。
2. **資料來源可公開**：政府開放資料、OSM 這類沒問題。
3. **不得含 e-info 文章內容鏡像**——那類東西放私有的 `einfo-lab`。
4. **每個子資料夾要有自己的 `README.md`**，標明資料來源與授權。
5. 嵌進文章時**一律用 `src=` 指到這裡**，不要把內容貼進文章內文。

## 相關的 repo

| repo | 放什麼 |
|---|---|
| `einfo-cms-mcp`（private） | 上稿管線、MCP server、模板、CI |
| `data-shorts`（private） | 颱風短影音引擎 |
| `einfo-dist`（public） | 只有 Releases：binary ＋ manifest |
| `einfo-lab`（private） | 一次性成品與 POC（含不可公開的文章鏡像） |

歷史沿革：本 repo 的 `interactive-maps/` 由 `gassao1998/einfo-scratch` 的 `tokyo-bousai-map/`
以 `git filter-repo` 搬入，**逐檔歷史完整保留**（28 個 commit），並改名為現在這個比較正式的名字。
