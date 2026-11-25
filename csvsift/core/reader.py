"""编码与分隔符嗅探模块。

设计目标：
- 自动识别常见编码（UTF-8 / UTF-8-SIG / GBK / Big5 / Shift-JIS / Latin-1 等），
  对中文场景（GBK/UTF-8-BOM 混用）尤其友好；
- 自动嗅探分隔符（逗号 / 分号 / 制表符 / 竖线）；
- 全程流式，仅读取文件头部有限字节做探测，不影响大文件性能。
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from pathlib import Path

# 候选编码，按优先级排列（顺序即置信度顺序）
CANDIDATE_ENCODINGS = (
    "utf-8-sig",   # 带 BOM 的 UTF-8（Excel 导出的 CSV 常见）
    "utf-8",
    "gb18030",     # 国标超集，向下兼容 GBK/GB2312
    "big5",        # 繁体中文
    "shift_jis",   # 日文
    "euc-kr",      # 韩文
    "cp1252",      # 西欧 Windows 默认
    "latin-1",     # 兜底：任何字节序列都不会解码失败
)

# 候选分隔符
CANDIDATE_DELIMITERS = (",", ";", "\t", "|")

SNIFF_SAMPLE_BYTES = 64 * 1024  # 探测时最多读取的头部字节数


@dataclass
class FormatProfile:
    """嗅探结果：编码 + 分隔符。"""

    encoding: str
    delimiter: str


def detect_encoding(path: Path) -> str:
    """探测文件编码。

    依次尝试候选编码解码头部样本，返回第一个完全成功的编码；
    latin-1 作为最后兜底永远成功。
    """
    with open(path, "rb") as fh:
        raw = fh.read(SNIFF_SAMPLE_BYTES)

    # BOM 快速通道
    if raw.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if raw.startswith(codecs.BOM_UTF16_LE) or raw.startswith(codecs.BOM_UTF16_BE):
        return "utf-16"

    for enc in CANDIDATE_ENCODINGS:
        try:
            raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        return enc
    return "latin-1"


def detect_delimiter(path: Path, encoding: str) -> str:
    """探测分隔符：取解码样本首个非空行中各候选符号出现次数最多者。"""
    with open(path, "r", encoding=encoding, newline="") as fh:
        sample = fh.read(SNIFF_SAMPLE_BYTES)

    # 取前几行非空行参与计数，避免注释/空行干扰
    lines = [ln for ln in sample.splitlines() if ln.strip()][:5]
    if not lines:
        return ","

    best, best_score = ",", -1
    for cand in CANDIDATE_DELIMITERS:
        # 引号内计数会失真，但头部样本级别足够可靠
        score = sum(ln.count(cand) for ln in lines)
        if score > best_score:
            best, best_score = cand, score
    # 所有候选都为 0（单列文件）时退回逗号
    return best if best_score > 0 else ","


def sniff(path: Path, encoding: str | None = None, delimiter: str | None = None) -> FormatProfile:
    """综合嗅探入口：显式指定则尊重用户输入，否则自动探测。"""
    enc = encoding or detect_encoding(path)
    delim = delimiter or detect_delimiter(path, enc)
    return FormatProfile(encoding=enc, delimiter=delim)
