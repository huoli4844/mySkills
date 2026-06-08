#!/usr/bin/env bash
# verify_domain_agnostic.sh — 验证所有 Python 脚本中无硬编码领域专有词
# 用法: bash scripts/verify_domain_agnostic.sh [scripts_dir]
# 默认: 脚本所在目录的上级 scripts/ 目录

set -euo pipefail

SCRIPTS_DIR="${1:-$(cd "$(dirname "$0")/../scripts" && pwd)}"

echo "=== 领域无关审计 ==="
echo "检查目录: $SCRIPTS_DIR"
echo ""

# 已知领域单位/缩写（EMC/电子学）— 不应出现在静态列表中
DOMAIN_PATTERNS=(
  'dB'
  'kHz' 'MHz' 'GHz' 'THz'
  'V/m' 'A/m' 'W/m'
  'dBi' 'dBm' 'dBuV' 'dBμV'
  'pF' 'nH' 'μH' 'μF'
  'FDTD' 'MoM' 'FEM' 'PEEC'
  'PCB' 'EMC' 'EMI' 'RF'
  '电平' '限值'
)

found=0
for pattern in "${DOMAIN_PATTERNS[@]}"; do
  matches=$(grep -rn "$pattern" "$SCRIPTS_DIR"/*.py 2>/dev/null || true)
  if [ -n "$matches" ]; then
    # 筛选出定义在常量/列表中的行（排除注释、docstring、运行时提取逻辑）
    const_matches=$(echo "$matches" | grep -E '^\s*[A-Z_]+\s*[=:]|\[.*'"$pattern"'.*\]|'"$pattern"',' 2>/dev/null || true)
    if [ -n "$const_matches" ]; then
      echo "⚠️  发现领域词 '$pattern' 在静态列表中:"
      echo "$const_matches" | sed 's/^/    /'
      ((found++))
    fi
  fi
done

echo ""
if [ "$found" -eq 0 ]; then
  echo "✅ 通过: 所有脚本中无硬编码领域专有词"
else
  echo "❌ 失败: 发现 $found 个领域词泄漏到静态列表"
  echo "   请将这些词转移到 _extract_domain_signals() 的运行时提取路径"
  exit 1
fi
