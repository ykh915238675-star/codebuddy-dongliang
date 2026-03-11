#!/bin/bash
# ETF动量轮动策略 - 启动脚本

cd "$(dirname "$0")"

echo "========================================="
echo "  ETF动量轮动策略 - Web应用"
echo "========================================="

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

echo "📦 Python版本: $(python3 --version)"

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📦 安装依赖..."
pip install -r requirements.txt -q

# 创建数据目录
mkdir -p data

echo ""
echo "🚀 启动Web应用..."
echo "📌 访问地址: http://localhost:5000"
echo "📌 默认账号: admin / admin123"
echo "📌 按 Ctrl+C 停止"
echo ""

python3 app.py
