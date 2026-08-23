# 多代理儲存庫工作流程

一個小型、可重複使用的工作流程，讓多個程式開發代理在同一個儲存庫內協作，而不會依賴過期的對話脈絡、互相覆寫，或讓維護者淹沒在 Git 操作細節裡。

核心設計與工具無關。此儲存庫同時提供 Codex Skill、起始檔案，以及零依賴的 Python 驗證工具。

## 解決什麼問題

- 需要長期保存的專案指令放在儲存庫中，而不是留在某個聊天視窗。
- 每個並行寫入者都有明確的目標和獨占的寫入範圍。
- 共用的整合檔案有明確負責人和預定的合併順序。
- 安全限制、產品預設值和驗證關卡各自獨立管理。
- 驗證規模隨變更範圍調整，而不是每次都跑所有昂貴的檢查。
- 維護者報告以產品行為、使用者影響、驗證結果和剩餘缺口為主；分支和 PR 細節只放在簡短的 Git 稽核資訊中。

## 選擇最輕量可行的模式

| 模式 | 適用情境 | 協調成本 |
| --- | --- | --- |
| `solo` | 只有一個寫入者，不可能發生重疊 | 最低；只需長期保存的指令，並依變更範圍執行驗證 |
| `adaptive` | 通常只有一個寫入者，但可能出現平行視窗或其他機器 | 只有在並行或工作區狀態不明時，才要求任務認領和隔離工作區 |
| `strict` | 預期多個寫入者同時作業 | 每個寫入者都需要任務、分支、工作區、交接、獨占範圍，以及可供審查的變更 |

`adaptive` 是預設值。嚴格流程是應對真實碰撞風險的工具，不是工程品質的通用指標。

## 快速開始

預覽將新增或更新的檔案：

```shell
python skills/multi-agent-repo-workflow/scripts/bootstrap.py /path/to/project \
  --project-name "我的專案" --mode adaptive --tracker github --dry-run
```

若要連同每個檔案的完整內容一起檢查：

```shell
python skills/multi-agent-repo-workflow/scripts/bootstrap.py /path/to/project \
  --project-name "我的專案" --mode adaptive --tracker github \
  --dry-run --show-content
```

套用它們：

```shell
python skills/multi-agent-repo-workflow/scripts/bootstrap.py /path/to/project \
  --project-name "我的專案" --mode adaptive --tracker github
```

對已有自己的 `AGENTS.md` 的儲存庫，只加入受管理的區塊：

```shell
python skills/multi-agent-repo-workflow/scripts/bootstrap.py /path/to/project \
  --project-name "我的專案" --mode adaptive --tracker github --merge-agents
```

然後把通用的驗證範例替換為專案的真實指令，並確認安裝結果：

```shell
python skills/multi-agent-repo-workflow/scripts/validate_setup.py /path/to/project
```

安裝腳本會在寫入前完成衝突預檢。除非提供 `--force`，否則不會覆寫任何已存在的檔案；`--dry-run` 只預演，不會寫入檔案。若準備使用 `--force`，請先搭配 `--dry-run --show-content` 檢查所有內容。

## Codex Skill

可安裝的 Skill 位於 [`skills/multi-agent-repo-workflow`](skills/multi-agent-repo-workflow)。把那個資料夾複製到你的 Codex skills 目錄，然後呼叫：

```text
$multi-agent-repo-workflow 為這個儲存庫設定 adaptive 多代理工作流程。保留現有指令，從真實的建置和 CI 推導驗證方式，寫入前先預覽每個檔案。
```

這個 Skill 也可以稽核現有的工作流程、簡化不降低風險卻增加繁文縟節的規則，或者把 adaptive 專案升級為 strict 並行模式。

## 交接檢查

任務交接使用 issue 或任務描述中的 JSON 區塊。驗證一個已儲存的內容：

```shell
python skills/multi-agent-repo-workflow/scripts/handoff_check.py --body-file issue-body.md
```

驗證已儲存的 GitHub issue 清單回應並偵測重疊範圍：

```shell
python skills/multi-agent-repo-workflow/scripts/handoff_check.py \
  --issues-json open-issues.json --mode strict
```

在已登入 GitHub CLI 的情況下，`--github --repo OWNER/REPO` 會讀取開放中的 issue，但不會修改它們。在被指派的 Git 檢出目錄中加上 `--issue N --check-git`，即可驗證分支、祖先關係和變更路徑。

## 設計邊界

- 本專案不替你決定產品架構、法律限制、測試指令或發布政策。
- 除非使用者明確要求，否則不會寫入 GitHub、建立分支、安裝軟體或變更本機環境。
- 只有當並行寫入、分支已被使用或責任歸屬不明而產生具體衝突風險時，才需要工作樹。
- 排隊中或正在執行的檢查不算通過；`smoke test` 只能證明它實際測到的環境與層次。
- 長期目標仍然需要一個結果、一個驗證迴圈和一個停止或暫停條件。

## 開發

工具需要 Python 3.10 以上版本，且僅使用標準函式庫。

```shell
python -m unittest discover -s tests -v
```

貢獻指引請見 [CONTRIBUTING.md](CONTRIBUTING.md)。授權條款請見 [MIT License](LICENSE)。
