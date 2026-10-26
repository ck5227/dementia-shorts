# 失智預防實證 Daily Dementia EBM

每個平日自動產出一支 60 秒內的中英雙語 YouTube Short，整理最新的失智預防實證研究。

- `episodes/YYYY-MM-DD.json`：每集腳本（標題、說明、投影片內容、來源）
- `make_video.py`：把腳本渲染成 1080×1920 影片，背景音樂由程式自行合成（無版權素材）
- 影片檔放在 `videos/`（超過 60 天的舊檔會清掉），由 Metricool 抓取並發布到 YouTube

用法：

```
python3 make_video.py episodes/2026-10-27.json out/2026-10-27.mp4
```

本頻道內容為衛教資訊，不取代個人醫療建議。For education only; not medical advice.
