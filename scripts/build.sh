#!/usr/bin/env bash
# csvsift 一键打包脚本：测试 → 构建 wheel/sdist → 生成校验和
# 用法: bash scripts/build.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> [1/3] 运行全量单元测试"
python3 -m unittest discover -s tests

echo "==> [2/3] 构建发行包"
python3 -m pip install --quiet build
python3 -m build --sdist --wheel

echo "==> [3/3] 生成 SHA256 校验和"
cd dist
sha256sum *.whl *.tar.gz > SHA256SUMS.txt
cat SHA256SUMS.txt
echo "==> 完成，产物位于 dist/"
