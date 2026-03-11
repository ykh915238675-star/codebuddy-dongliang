"""
ETF动量轮动策略 - Web应用
"""
import os
import json
import logging
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify

from config import Config
from engine import QuantEngine

# ==================== 应用初始化 ====================
app = Flask(__name__)
app.config.from_object(Config)

# 确保数据目录存在
os.makedirs(Config.DATA_DIR, exist_ok=True)

# 初始化量化引擎
engine = QuantEngine(data_dir=Config.DATA_DIR)


# ==================== 页面路由 ====================
@app.route('/')
def dashboard():
    return render_template('dashboard.html')


# ==================== API路由 ====================
@app.route('/api/recommendation', methods=['GET'])
def api_recommendation():
    """获取今日推荐（仅小池）"""
    use_cache = request.args.get('cache', 'true') == 'true'

    # 先尝试读取缓存
    if use_cache:
        cached = engine.get_cached_result()
        if cached:
            cached['from_cache'] = True
            return jsonify(cached)

    try:
        result = engine.get_today_recommendation(use_large_pool=False)
        result['from_cache'] = False
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    """强制刷新数据（仅小池）"""
    try:
        engine.clear_cache()
        result = engine.get_today_recommendation(use_large_pool=False)
        result['from_cache'] = False
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/strategy', methods=['GET'])
def api_strategy():
    """获取策略描述"""
    return jsonify({
        'name': 'ETF动量轮动策略',
        'description': '基于加权回归计算动量得分，从ETF池中筛选趋势最强的标的进行轮动配置。当市场无明显趋势时，自动切换至防御性资产。',
        'etf_pool': [
            {'code': '518880', 'name': '黄金ETF', 'category': '大宗商品'},
            {'code': '159985', 'name': '豆粕ETF', 'category': '大宗商品'},
            {'code': '501018', 'name': '南方原油', 'category': '大宗商品'},
            {'code': '161226', 'name': '白银LOF', 'category': '大宗商品'},
            {'code': '513100', 'name': '纳指ETF', 'category': '国际'},
            {'code': '159915', 'name': '创业板ETF', 'category': 'A股指数'},
            {'code': '511220', 'name': '城投债ETF', 'category': '债券'},
        ],
        'defensive_etf': {'code': '511880', 'name': '货币基金ETF'},
        'core_logic': [
            '以25个交易日为窗口，对收盘价取对数后进行加权线性回归，计算年化收益率',
            '用R²（拟合优度）衡量趋势稳定性，综合得分 = 年化收益 × R²',
            '选取得分最高的1只ETF作为今日推荐买入标的',
        ],
        'filters': [
            {'name': 'RSI过滤', 'desc': '近期RSI超过98且价格跌破5日均线时过滤，防止追高'},
            {'name': '成交量过滤', 'desc': '近5日量比超2倍且年化收益过高时过滤，规避放量见顶'},
            {'name': '短期动量过滤', 'desc': '近10日年化收益为负时过滤，确保短期趋势向上'},
            {'name': '近3日跌幅风控', 'desc': '连续3日中有单日跌幅超3%则得分清零，规避急跌'},
        ],
        'defense_trigger': '当所有ETF均不满足筛选条件时，自动切换至货币基金ETF（511880）防御',
    })


@app.route('/api/backtest', methods=['POST'])
def api_backtest():
    """运行回测"""
    data = request.json or {}
    start_date = data.get('start_date', '')
    end_date = data.get('end_date', '')

    if not start_date or not end_date:
        return jsonify({'error': '请提供起止日期'}), 400

    # 校验日期格式
    try:
        sd = datetime.strptime(start_date, '%Y-%m-%d')
        ed = datetime.strptime(end_date, '%Y-%m-%d')
        if sd >= ed:
            return jsonify({'error': '开始日期须早于结束日期'}), 400
        if (ed - sd).days > 365 * 5:
            return jsonify({'error': '回测区间不能超过5年'}), 400
    except ValueError:
        return jsonify({'error': '日期格式错误，请使用 YYYY-MM-DD'}), 400

    try:
        result = engine.run_backtest(start_date, end_date)
        if 'error' in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        logging.exception("回测出错")
        return jsonify({'error': str(e)}), 500


# ==================== 启动 ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8088))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
