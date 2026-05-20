#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo ""
echo " ============================================================"
echo "   TalentScope - AI 简历智能匹配评分系统"
echo " ============================================================"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "[X] 未检测到 python3，请先安装 Python 3.10+"
    exit 1
fi

python3 bootstrap.py
python3 -m streamlit run src/talentscope/ui/app.py --server.port 8501 --browser.gatherUsageStats false
