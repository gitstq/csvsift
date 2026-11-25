# 🤝 贡献指南（CONTRIBUTING）

感谢关注 csvsift！欢迎以任何形式参与贡献：报告缺陷、提议功能、完善文档、提交代码。

## 🐛 报告缺陷

提交 Issue 时请尽量包含：

1. csvsift 版本（`csvsift --version`）
2. 操作系统与 Python 版本
3. 完整的复现命令与输出（**注意脱敏**，不要附带真实敏感数据）
4. 期望行为与实际行为的差异

## ✨ 提议功能

- 先在 Issue 中描述使用场景，达成共识后再动手实现；
- 新子命令需说明与现有命令（info / stats / filter / sort / dedupe / sample / convert / validate）的边界，避免功能重叠。

## 💻 提交代码

### 环境准备

```bash
git clone https://github.com/gitstq/csvsift.git
cd csvsift
python -m unittest discover -s tests -v   # 先确认基线全绿
```

### 规范要求

1. **提交信息**遵循 [Angular 规范](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit)：
   - `feat:` 新功能　`fix:` 缺陷修复　`docs:` 文档　`refactor:` 重构
   - `test:` 测试　`chore:` 构建/杂项　`perf:` 性能优化
   - 示例：`feat(filter): 支持 between 区间比较`
2. **测试**：每个新功能或修复必须附带单元测试，`python -m unittest discover -s tests` 全绿后方可提交；
3. **架构红线**：
   - 核心功能保持**零强制第三方依赖**（可选依赖只能以 extras 形式引入，如 `[xlsx]`）；
   - 保持**流式处理**：新增命令不允许一次性把整个文件读入内存（排序/去重等必须物化的操作除外，需在文档注明）；
   - 过滤表达式严禁引入 `eval`，一律走 `filter_expr.py` 的 AST 白名单机制。

## 📄 协议

提交即表示同意代码以 [MIT](LICENSE) 协议发布。
