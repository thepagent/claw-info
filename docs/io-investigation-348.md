# 深入調查：loadSessionStore() 在 cron 頻繁執行下的 I/O 開銷 (#348)

本文件針對 `loadSessionStore()` 在高頻 cron 執行場景下的 I/O 效能瓶頸進行初步分析與實驗設計。

## 問題定義
當 cron 任務頻繁執行時，`loadSessionStore()` 頻繁進行磁盤讀寫操作，可能導致：
1. **I/O 寫入爭搶**：多個並發任務同時讀寫 `sessions.json`。
2. **鎖等待**：SQLite/檔案鎖導致延遲增加。
3. **磁盤壽命**：過高的寫入頻率影響 VM 環境的 disk I/O。

## 初步建議
1. **讀取快取**：在 memory 中維護 `sessions.json` 的快取，而非每次呼叫都讀取磁盤。
2. **批次處理**：將多次 I/O 寫入合併為單次 Batch 寫入。
3. **檢查機制**：增加「僅在狀態發生變更時」才寫入磁盤的邏輯。

