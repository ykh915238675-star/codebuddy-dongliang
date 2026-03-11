"""应用配置"""
import os

# 检测是否在 Vercel 环境
IS_VERCEL = os.environ.get('VERCEL', '') == '1'

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'quant-strategy-secret-key-2024')
    
    # 数据库
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///quant_strategy.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 调度器
    SCHEDULER_API_ENABLED = True
    
    # 默认用户（首次运行自动创建）
    DEFAULT_USERNAME = os.environ.get('DEFAULT_USERNAME', 'admin')
    DEFAULT_PASSWORD = os.environ.get('DEFAULT_PASSWORD', 'admin123')
    
    # 数据缓存目录（Vercel 环境使用 /tmp，本地使用 data/）
    if IS_VERCEL:
        DATA_DIR = '/tmp/data'
    else:
        DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
