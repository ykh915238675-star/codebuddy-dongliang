#!/bin/bash
# ETF动量轮动策略 - 后台服务启动脚本
# 用于 macOS LaunchAgent 开机自启

PROJECT_DIR="/Users/kun/CodeBuddy/dongliangcelue"
PYTHON="/usr/bin/python3"
LOG="/tmp/dongliangcelue.log"
PORT=8088

cd "$PROJECT_DIR"

# 如果已经在运行，先停掉
lsof -ti :$PORT | xargs kill -9 2>/dev/null
sleep 1

# 启动 Flask 服务（用完整 Python 路径）
nohup $PYTHON app.py >> "$LOG" 2>&1 &

echo "$(date): 服务已启动，PID: $!" >> "$LOG"
