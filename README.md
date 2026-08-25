# einfo-widgets

〈環境資訊中心〉可嵌進文章的互動內容，透過 GitHub Pages 提供。

首頁：<https://tnf-einfo.github.io/einfo-widgets/>

## 內容

- **`interactive-maps/`** — 可內嵌互動地圖（任意城市）。單一自足 HTML，Leaflet ＋ 內嵌行政區
  GeoJSON；無圖磚（沒有道路），只留行政界線與水域，繁中地名自動位移避讓。互動全部關閉，
  嵌在文章裡不會攔走讀者的捲動。
  - `tokyo/` — 東京・防災・生態 另類旅遊地圖
  - `demo-kaohsiung/` — 高雄示範（證明產生器適用於任意城市）
  - `template/` — 產生器。要開一座新城市的地圖看 `interactive-maps/README.md`

## 嵌進文章

用 `src=` 指到這裡，**不要把地圖的 HTML 貼進文章內文**：

```html
<iframe src="https://tnf-einfo.github.io/einfo-widgets/interactive-maps/tokyo/tokyo-bousai-map.html"
        title="東京・防災・生態 另類旅遊地圖" loading="lazy"
        style="width:100%;max-width:720px;aspect-ratio:720/476;border:0;border-radius:16px;display:block;margin:24px auto">
</iframe>
```

各資料夾裡的 `*.embed.html` 是舊做法（把整份地圖包成 `srcdoc` 供整段複製），保留供對照，
**新文章請用上面那一行**。

## 收錄規則

這個 repo 是公開的，所以收東西要嚴：

1. 自足靜態：無金鑰、無後端。
2. 資料來源可公開（政府開放資料、OSM 等）。
3. 不得含 e-info 文章內容鏡像。
4. 每個子資料夾要有自己的 `README.md`，標明資料來源與授權。

## 沿革

`interactive-maps/` 由 `einfo-scratch` 的 `tokyo-bousai-map/` 以 `git filter-repo` 搬入，
逐檔歷史保留（28 個 commit），並改為現名（它是通用地圖產生器，不只東京一張）。
