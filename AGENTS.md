# 多代理儲存庫工作流程——貢獻者規則

修改行為前，請先閱讀 `README.md`、`skills/multi-agent-repo-workflow/SKILL.md`，以及相關的參考文件或腳本。

## 不可妥協

- 保持工具組專案中立。產品特定的安全、平台、授權、帳號和發布規則屬於採用的儲存庫。
- 維護使用者授權邊界。唯讀檢查不代表允許 GitHub 寫入、建立分支、安裝軟體、購買，或變更本機環境。
- 安裝與驗證腳本必須具有確定性、零依賴、路徑安全，且預設不具破壞性。
- 不要靜默覆寫現有的專案指令。受管理的編輯需要明確標記、預檢和選擇性的覆寫路徑。

## 產品預設值

- `adaptive` 是建議的模式；`solo` 和 `strict` 仍是支援的選項。
- Codex Skill 應該引導判斷，而不是把每個範例變成通用規則。
- 提供給維護者的報告先說明結果、使用者影響、驗證和剩餘缺口。只有在必要時，才於結尾附上簡短的 Git 稽核資訊。
- 保持 `SKILL.md` 精簡。條件式細節放在 `references/`，產生的樣板放在 `assets/`。

## 驗證

行為變更後請執行：

```shell
python -m unittest discover -s tests -v
```

當其執行階段依賴可用時，也請執行 Codex Skill 驗證器：

```shell
python -X utf8 /path/to/skill-creator/scripts/quick_validate.py skills/multi-agent-repo-workflow
```
