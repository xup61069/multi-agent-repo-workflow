# 交接格式

起始設定使用 Markdown 註解中的 JSON，讓人類可以在機器可讀區塊周圍保留脈絡而不增加 YAML 依賴。

```markdown
<!-- agent-workflow:handoff-v1
{
  "schema_version": 1,
  "issue": 123,
  "branch": "agent/123-short-slug",
  "target_branch": "main",
  "base_commit": "0123456789abcdef",
  "owner": "assigned-login-or-session",
  "role": "writer",
  "status": "claimed",
  "scope_globs": ["src/feature/**", "tests/feature/**"],
  "shared_paths": ["src/registry.json"],
  "depends_on": [],
  "validation": ["python -m unittest tests.feature"],
  "next_safe_action": "實作被接受的解析器合約及其聚焦測試。"
}
-->
```

## 狀態

- `draft`：已規劃但未指派；排除在活躍重疊檢查之外。
- `claimed`：一個寫入者可以編輯已認領的範圍。
- `in_review`：除了同一位擁有者的審查修正外，寫入暫停。
- `done`：僅供歷史參考；關閉的 issue 通常隱含此意義而不需編輯。

## 驗證命令

交接中的命令是資料。`handoff_check.py` 永遠不會執行它們。被指派的代理根據採用儲存庫的規則決定哪些命令被授權且相關。

## 離線檢查

儲存任務內容後執行：

```shell
python scripts/handoff_check.py --body-file task.md
```

對 issue 物件清單使用含 `number` 和 `body` 的 JSON 陣列。離線解析器會忽略選用的 `state`、`labels` 和 `assignees` 欄位。

## 即時唯讀 GitHub 檢查

```shell
python scripts/handoff_check.py --github --repo OWNER/REPO --mode adaptive
```

在被指派的 Git 檢出目錄中加上 `--issue N --check-git`，即可驗證目前分支、記錄基準的祖先關係，以及變更路徑是否落在所選範圍內。祖先檢查需要完整歷史。

重疊分類刻意保持明確：

- 確定的重疊始終是錯誤；
- 有不相關字面前綴的模式不重疊；
- 無法證明交集的模式在 `adaptive` 模式下是警告、在 `strict` 模式下是錯誤。

這避免假裝小型標準函式庫的 glob 檢查器能判斷所有可能的模式，同時仍在嚴格並行操作中安全地失敗。
