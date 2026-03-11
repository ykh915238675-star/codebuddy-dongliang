"""
Vercel Serverless 入口 - 将 Flask 应用适配为 Serverless Function
"""
import sys
import os

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel 需要的入口变量
app.debug = False
