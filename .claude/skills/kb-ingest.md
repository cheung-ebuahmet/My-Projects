---
name: kb-ingest
description: 灌注知識到 LLM Wiki——將書籍/集數中的新知識萃取寫入 entities 和 concepts
---
讀取「{source}」——提煉涉及的概念、人物、地點。檢查 wiki 中是否已有頁面：無則新建（entities/或concepts/）、有則只追加之（additive surgical edits，不重寫整頁）。在頁面中標註來源書目和對應集數。更新 wiki/log.md。
