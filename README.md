<div align="center">

# 🧰 csvsift

**流式 CSV 命令行工具箱 —— 零依赖、低内存、中文编码友好**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Release](https://img.shields.io/badge/Release-v1.0.0-green.svg)](../../releases)

简体中文 | [English](README.en.md) | [繁體中文](README.zh-TW.md)

</div>

---

## 🎉 介绍

**csvsift** 是一个纯 Python 标准库实现的 CSV 命令行处理工具集。它把日常表格处理中最常见的操作——预览、画像、统计、过滤、排序、去重、抽样、格式互转、结构校验——收敛到一条命令里，全程流式处理，内存占用与文件大小无关。

它的三大设计信条：

- **零负担**：核心功能不依赖任何第三方库，`pip install csvsift` 即用；
- **大文件无感**：读入、过滤、抽样全部单遍流式，几百 MB 的 CSV 也能秒级响应；
- **中文友好**：自动嗅探 UTF-8 / UTF-8-BOM / GBK / Big5 等编码与中英文分隔符，无需手动指定。

## ✨ 特性

| 特性 | 说明 |
|------|------|
| 🔍 自动嗅探 | 编码（UTF-8 / BOM / GBK / Big5 / Shift-JIS…）与分隔符（`,` `;` `\t` `\|`）自动识别 |
| 📊 数据画像 | `info` 一条命令输出行列数、类型推断、空值率、唯一值、高频值 |
| 📈 统计摘要 | `stats` 对数值列输出 min / max / mean / median / std |
| 🪄 安全过滤 | `filter` 基于 AST 白名单表达式求值，**绝不使用 eval**，杜绝注入 |
| 🔀 数值感知排序 | `sort` 自动识别数值列，混合类型不乱序 |
| 🎯 蓄水池抽样 | `sample` 单遍流式随机抽样，支持种子复现 |
| 🔁 格式互转 | `convert` 在 CSV / JSON / JSONL / XLSX 之间自由转换 |
| ✅ 结构校验 | `validate` 检查列数漂移与空值率，非零退出码可直接接入 CI |
| 🖥️ 优雅输出 | 终端对齐表格 + 自适应着色，`NO_COLOR` 与 `--no-color` 均可关闭 |

## 🚀 快速开始

**安装：**

```bash
# 从源码安装
pip install git+https://github.com/gitstq/csvsift.git

# 需要导出 XLSX 时加装可选依赖
pip install "csvsift[xlsx]"
```

**30 秒上手：**

```bash
# 数据画像：行数、列数、类型、空值率一目了然
csvsift info sales.csv

# 过滤：留下金额大于 1000 的北京订单
csvsift filter -w 'amount > 1000 and city == "北京"' sales.csv -o big_orders.csv

# 转成 JSON 给下游程序
csvsift convert -t jsonl -o sales.jsonl sales.csv
```

也可以免安装直接运行：`python -m csvsift info sales.csv`

## 📖 使用指南

### 子命令一览

| 命令 | 功能 | 示例 |
|------|------|------|
| `info` | 数据画像 | `csvsift info data.csv` |
| `stats` | 数值列统计 | `csvsift stats data.csv` |
| `head` / `tail` | 预览首尾 N 行 | `csvsift tail -n 5 data.csv` |
| `select` | 选列（支持列名与 `1,3-5` 序号） | `csvsift select -c name,amount data.csv` |
| `filter` | 表达式过滤 | `csvsift filter -w 'age > 30 and city in ("北京","上海")' data.csv` |
| `sort` | 数值感知排序 | `csvsift sort -k amount --desc data.csv` |
| `dedupe` | 整行 / 按键列去重 | `csvsift dedupe -k id data.csv -o clean.csv` |
| `sample` | 随机抽样 | `csvsift sample -n 100 --seed 42 data.csv -o s.csv` |
| `convert` | 格式互转 | `csvsift convert -t xlsx -o out.xlsx data.csv` |
| `validate` | 结构校验（CI 友好） | `csvsift validate --strict data.csv` |

### 过滤表达式语法

只允许列名、字面量、比较、四则运算与 `and / or / not / in`，语法非法或包含危险调用会被直接拒绝：

```bash
csvsift filter -w 'score >= 60 and not (name == "test")' exams.csv
csvsift filter -w 'price * qty > 10000' orders.csv        # 支持四则运算
csvsift filter -w 'city in ("北京", "上海", "广州")' users.csv
```

### 通用选项

- `-e/--encoding`、`-d/--delimiter`：手动指定编码 / 分隔符（默认自动嗅探）；
- `-o/--output`：写入文件；缺省时输出到终端；
- `-f/--format csv|json|jsonl`：输出格式；
- `--no-color`：关闭着色。

> 💡 **内存提示**：`sort` 与 `dedupe` 需要全量物化结果，超大文件请先过滤或抽样；其余命令均为流式。

## 💡 设计迭代

- **v1.0.0（当前）**：首发版本，覆盖预览 / 画像 / 统计 / 过滤 / 排序 / 去重 / 抽样 / 互转 / 校验九大能力，25 个单元测试全覆盖；
- **规划中**：
  - `join` 子命令：按键列连接两个 CSV（流式哈希连接）；
  - `filter` 支持 `between` 区间与字符串函数；
  - 大文件排序外排（external sort）以进一步降低内存峰值；
  - 通过 PyPI 正式发布。

欢迎在 [Issues](../../issues) 中提出你希望出现的功能。

## 📦 打包部署

```bash
# 一键打包（测试 → wheel/sdist → SHA256 校验和）
bash scripts/build.sh

# 产物位于 dist/，可直接上传至 Release 或私有源
pip install dist/csvsift-1.0.0-py3-none-any.whl
```

也可从 [Releases](../../releases) 页面直接下载 wheel / sdist 及 `SHA256SUMS.txt` 校验和文件。

## 🤝 贡献

Issue 与 PR 均受欢迎！提交前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，确保：

- 提交信息遵循 Angular 规范（`feat:` / `fix:` / `docs:` …）；
- 新功能附带单元测试，`python -m unittest discover -s tests` 全绿；
- 保持零强制依赖与流式处理两条架构红线。

## 📄 协议

本项目基于 [MIT License](LICENSE) 开源，可自由用于个人与商业场景。
