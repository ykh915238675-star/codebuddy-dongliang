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

    # 企业微信群机器人通知（通过Web界面配置，此处仅为环境变量覆盖入口）
    WECHAT_WORK_WEBHOOK = os.environ.get('WECHAT_WORK_WEBHOOK', '')

    # 自动监控调度配置（默认每天14:30执行一次）
    AUTO_CHECK_HOUR = int(os.environ.get('AUTO_CHECK_HOUR', '14'))
    AUTO_CHECK_MINUTE = int(os.environ.get('AUTO_CHECK_MINUTE', '30'))
