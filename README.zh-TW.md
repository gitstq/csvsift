<div align="center">

# 🧰 csvsift

**串流 CSV 命令列工具箱 —— 零依賴、低記憶體、編碼友善**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/badge/Release-v1.0.0-green.svg)](../../releases)

[简体中文](README.md) | [English](README.en.md) | 繁體中文

</div>

---

## 🎉 介紹

**csvsift** 是一個完全以 Python 標準函式庫打造的 CSV 命令列處理工具集。它把日常表格處理最常見的操作——預覽、畫像、統計、過濾、排序、去重、抽樣、格式互轉、結構驗證——收斂成一條命令，全程串流處理，記憶體佔用與檔案大小無關。

三大設計信念：

- **零負擔**：核心功能不依賴任何第三方套件，`pip install csvsift` 即裝即用；
- **大檔無感**：讀取、過濾、抽樣皆為單趟串流，數百 MB 的 CSV 也能秒級回應；
- **編碼友善**：自動偵測 UTF-8 / UTF-8-BOM / GBK / Big5 等編碼與中英文分隔符，無須手動指定。

## ✨ 特性

| 特性 | 說明 |
|------|------|
| 🔍 自動偵測 | 自動識別編碼（UTF-8 / BOM / GBK / Big5 / Shift-JIS…）與分隔符（`,` `;` `\t` `\|`） |
| 📊 資料畫像 | `info` 一條命令輸出行列數、型別推斷、空值率、唯一值、高頻值 |
| 📈 統計摘要 | `stats` 針對數值欄位輸出 min / max / mean / median / std |
| 🪄 安全過濾 | `filter` 以 AST 白名單求值，**絕不使用 eval**，從機制上杜絕注入 |
| 🔀 數值感知排序 | `sort` 自動識別數值欄位，混合型別不亂序 |
| 🎯 蓄水庫抽樣 | `sample` 單趟串流隨機抽樣，支援種子重現 |
| 🔁 格式互轉 | `convert` 在 CSV / JSON / JSONL / XLSX 之間自由轉換 |
| ✅ 結構驗證 | `validate` 檢查欄位數漂移與空值率，非零結束碼可直接接進 CI |
| 🖥️ 優雅輸出 | 終端機對齊表格 + 自適應著色，`NO_COLOR` 與 `--no-color` 皆可關閉 |

## 🚀 快速開始

**安裝：**

```bash
# 從原始碼安裝
pip install git+https://github.com/gitstq/csvsift.git

# 需要匯出 XLSX 時加裝選用依賴
pip install "csvsift[xlsx]"
```

**30 秒上手：**

```bash
# 資料畫像：列數、欄數、型別、空值率一目瞭然
csvsift info sales.csv

# 過濾：留下金額大於 1000 的訂單
csvsift filter -w 'amount > 1000' sales.csv -o big_orders.csv

# 轉成 JSON 交給下游程式
csvsift convert -t jsonl -o sales.jsonl sales.csv
```

也可以免安裝直接執行：`python -m csvsift info sales.csv`

## 📖 使用指南

### 子命令一覽

| 命令 | 功能 | 範例 |
|------|------|------|
| `info` | 資料畫像 | `csvsift info data.csv` |
| `stats` | 數值欄位統計 | `csvsift stats data.csv` |
| `head` / `tail` | 預覽首尾 N 列 | `csvsift tail -n 5 data.csv` |
| `select` | 選欄（支援欄名與 `1,3-5` 序號） | `csvsift select -c name,amount data.csv` |
| `filter` | 表達式過濾 | `csvsift filter -w 'age > 30 and city == "台北"' data.csv` |
| `sort` | 數值感知排序 | `csvsift sort -k amount --desc data.csv` |
| `dedupe` | 整列 / 按鍵欄去重 | `csvsift dedupe -k id data.csv -o clean.csv` |
| `sample` | 隨機抽樣 | `csvsift sample -n 100 --seed 42 data.csv -o s.csv` |
| `convert` | 格式互轉 | `csvsift convert -t xlsx -o out.xlsx data.csv` |
| `validate` | 結構驗證（CI 友善） | `csvsift validate --strict data.csv` |

### 過濾表達式語法

僅允許欄名、字面量、比較、四則運算與 `and / or / not / in`，語法非法或含危險呼叫會被直接拒絕：

```bash
csvsift filter -w 'score >= 60 and not (name == "test")' exams.csv
csvsift filter -w 'price * qty > 10000' orders.csv        # 支援四則運算
csvsift filter -w 'city in ("台北", "台中", "高雄")' users.csv
```

### 通用選項

- `-e/--encoding`、`-d/--delimiter`：手動指定編碼 / 分隔符（預設自動偵測）；
- `-o/--output`：寫入檔案；缺省時輸出到終端機；
- `-f/--format csv|json|jsonl`：輸出格式；
- `--no-color`：關閉著色。

> 💡 **記憶體提示**：`sort` 與 `dedupe` 需要全量物化結果，超大檔案請先過濾或抽樣；其餘命令皆為串流。

## 💡 設計迭代

- **v1.0.0（目前）**：首發版本，涵蓋預覽 / 畫像 / 統計 / 過濾 / 排序 / 去重 / 抽樣 / 互轉 / 驗證九大能力，25 個單元測試全覆蓋；
- **規劃中**：
  - `join` 子命令：按鍵欄連接兩個 CSV（串流雜湊連接）；
  - `filter` 支援 `between` 區間與字串函式；
  - 大檔排序外排（external sort）以進一步降低記憶體峰值；
  - 正式發布至 PyPI。

歡迎在 [Issues](../../issues) 提出你期待的功能。

## 📦 打包部署

```bash
# 一鍵打包（測試 → wheel/sdist → SHA256 校驗和）
bash scripts/build.sh

# 產物位於 dist/，可直接上傳至 Release 或私有源
pip install dist/csvsift-1.0.0-py3-none-any.whl
```

也可從 [Releases](../../releases) 頁面直接下載 wheel / sdist 與 `SHA256SUMS.txt` 校驗和檔案。

## 🤝 貢獻

Issue 與 PR 皆受歡迎！提交前請先閱讀 [CONTRIBUTING.md](CONTRIBUTING.md)，確保：

- 提交訊息遵循 Angular 規範（`feat:` / `fix:` / `docs:` …）；
- 新功能附帶單元測試，`python -m unittest discover -s tests` 全綠；
- 遵守零強制依賴與串流處理兩條架構紅線。

## 📄 授權條款

本專案以 [MIT License](LICENSE) 開源，可自由用於個人與商業場景。
