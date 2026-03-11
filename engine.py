"""
量化策略引擎 - ETF动量轮动策略
将聚宽平台策略改写为独立运行版本，使用 akshare 获取行情数据
"""

import numpy as np
import math
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
import json
import os
import traceback

# ==================== ETF信息映射 ====================
ETF_NAME_MAP = {
    # 大宗商品ETF
    "518880": {"name": "黄金ETF", "market": "sh", "category": "大宗商品"},
    "159985": {"name": "豆粕ETF", "market": "sz", "category": "大宗商品"},
    "501018": {"name": "南方原油", "market": "sh", "category": "大宗商品"},
    "161226": {"name": "白银LOF", "market": "sz", "category": "大宗商品"},
    "159980": {"name": "有色ETF", "market": "sz", "category": "大宗商品"},
    "159981": {"name": "能源化工ETF", "market": "sz", "category": "大宗商品"},
    # 国际ETF
    "513100": {"name": "纳指ETF", "market": "sh", "category": "国际"},
    "159509": {"name": "纳指科技ETF", "market": "sz", "category": "国际"},
    "513290": {"name": "纳指生物ETF", "market": "sh", "category": "国际"},
    "513500": {"name": "标普500ETF", "market": "sh", "category": "国际"},
    "159529": {"name": "标普消费", "market": "sz", "category": "国际"},
    "513400": {"name": "道琼斯ETF", "market": "sh", "category": "国际"},
    "513520": {"name": "日经225ETF", "market": "sh", "category": "国际"},
    "513030": {"name": "德国30ETF", "market": "sh", "category": "国际"},
    "513080": {"name": "法国ETF", "market": "sh", "category": "国际"},
    "513310": {"name": "中韩半导体ETF", "market": "sh", "category": "国际"},
    "513730": {"name": "东南亚ETF", "market": "sh", "category": "国际"},
    # 香港ETF
    "159792": {"name": "港股互联ETF", "market": "sz", "category": "香港"},
    "513130": {"name": "恒生科技", "market": "sh", "category": "香港"},
    "513050": {"name": "中概互联网ETF", "market": "sh", "category": "香港"},
    "159920": {"name": "恒生ETF", "market": "sz", "category": "香港"},
    "513690": {"name": "港股红利", "market": "sh", "category": "香港"},
    # 指数ETF
    "510300": {"name": "沪深300ETF", "market": "sh", "category": "A股指数"},
    "510500": {"name": "中证500ETF", "market": "sh", "category": "A股指数"},
    "510050": {"name": "上证50ETF", "market": "sh", "category": "A股指数"},
    "510210": {"name": "上证ETF", "market": "sh", "category": "A股指数"},
    "159915": {"name": "创业板ETF", "market": "sz", "category": "A股指数"},
    "588080": {"name": "科创50", "market": "sh", "category": "A股指数"},
    "512100": {"name": "中证1000ETF", "market": "sh", "category": "A股指数"},
    "563360": {"name": "A500-ETF", "market": "sh", "category": "A股指数"},
    "563300": {"name": "中证2000ETF", "market": "sh", "category": "A股指数"},
    # 风格ETF
    "512890": {"name": "红利低波ETF", "market": "sh", "category": "风格"},
    "159967": {"name": "创业板成长ETF", "market": "sz", "category": "风格"},
    "512040": {"name": "价值ETF", "market": "sh", "category": "风格"},
    "159201": {"name": "自由现金流ETF", "market": "sz", "category": "风格"},
    # 债券ETF
    "511380": {"name": "可转债ETF", "market": "sh", "category": "债券"},
    "511010": {"name": "国债ETF", "market": "sh", "category": "债券"},
    "511220": {"name": "城投债ETF", "market": "sh", "category": "债券"},
    # 防御性ETF
    "511880": {"name": "货币基金ETF", "market": "sh", "category": "防御"},
    # 最高评分策略专用
    "159934": {"name": "黄金ETF(小)", "market": "sz", "category": "大宗商品"},
    "159941": {"name": "纳指100ETF", "market": "sz", "category": "国际"},
    "510180": {"name": "上证180ETF", "market": "sh", "category": "A股指数"},
}


def get_etf_name(code):
    """获取ETF名称"""
    pure_code = code.split('.')[0] if '.' in code else code
    info = ETF_NAME_MAP.get(pure_code, {})
    return info.get("name", f"ETF-{pure_code}")


def get_etf_category(code):
    """获取ETF分类"""
    pure_code = code.split('.')[0] if '.' in code else code
    info = ETF_NAME_MAP.get(pure_code, {})
    return info.get("category", "其他")


def get_etf_market(code):
    """获取ETF市场标识"""
    pure_code = code.split('.')[0] if '.' in code else code
    info = ETF_NAME_MAP.get(pure_code, {})
    return info.get("market", "sh")


def jq_code_to_pure(jq_code):
    """聚宽代码转纯数字代码: 518880.XSHG -> 518880"""
    return jq_code.split('.')[0]


def jq_code_to_ak(jq_code):
    """聚宽代码转akshare代码: 518880.XSHG -> sh518880 / sz159985"""
    pure_code = jq_code.split('.')[0]
    market = get_etf_market(pure_code)
    return f"{market}{pure_code}"


class QuantEngine:
    """量化策略引擎"""
    
    def __init__(self, data_dir='data'):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
        # ==================== ETF池设置 ====================
        self.etf_pool = [
            "518880.XSHG",  # 黄金ETF
            "159985.XSHE",  # 豆粕ETF
            "501018.XSHG",  # 南方原油
            "161226.XSHE",  # 白银LOF
            "513100.XSHG",  # 纳指ETF
            "159915.XSHE",  # 创业板ETF
            "511220.XSHG",  # 城投债ETF
        ]
        
        self.etf_pool_bak = [
            "518880.XSHG", "159980.XSHE", "159985.XSHE", "501018.XSHG",
            "161226.XSHE", "159981.XSHE",
            "513100.XSHG", "159509.XSHE", "513290.XSHG", "513500.XSHG",
            "159529.XSHE", "513400.XSHG", "513520.XSHG", "513030.XSHG",
            "513080.XSHG", "513310.XSHG", "513730.XSHG",
            "159792.XSHE", "513130.XSHG", "513050.XSHG", "159920.XSHE",
            "513690.XSHG",
            "510300.XSHG", "510500.XSHG", "510050.XSHG", "510210.XSHG",
            "159915.XSHE", "588080.XSHG", "512100.XSHG", "563360.XSHG",
            "563300.XSHG",
            "512890.XSHG", "159967.XSHE", "512040.XSHG", "159201.XSHE",
            "511380.XSHG", "511010.XSHG", "511220.XSHG",
        ]
        
        # ==================== 核心策略参数 ====================
        self.lookback_days = 25
        self.holdings_num = 1
        self.defensive_etf = "511880.XSHG"
        self.min_score_threshold = 0
        self.max_score_threshold = 500.0
        
        # 成交量过滤参数
        self.enable_volume_check = True
        self.volume_lookback = 5
        self.volume_threshold = 2
        self.volume_return_limit = 1
        
        # 短期动量过滤参数
        self.use_short_momentum_filter = True
        self.short_lookback_days = 10
        self.short_momentum_threshold = 0.0
        
        # RSI过滤参数
        self.use_rsi_filter = True
        self.rsi_period = 6
        self.rsi_lookback_days = 1
        self.rsi_threshold = 98
        
        # 止损参数
        self.stop_loss = 0.95
        self.loss = 0.97
        
        # 价格数据缓存
        self._price_cache = {}
    
    def get_etf_history(self, jq_code, days=60):
        """
        获取ETF历史行情数据
        使用akshare获取数据
        """
        pure_code = jq_code_to_pure(jq_code)
        cache_key = f"{pure_code}_{days}"
        
        # 检查缓存
        if cache_key in self._price_cache:
            cached_data, cached_time = self._price_cache[cache_key]
            # 缓存10分钟有效
            if (datetime.now() - cached_time).seconds < 600:
                return cached_data
        
        try:
            # 使用akshare获取ETF历史数据
            # fund_etf_hist_sina_em 获取ETF行情
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')
            
            df = ak.fund_etf_hist_sina(symbol=jq_code_to_ak(jq_code))
            
            if df is not None and not df.empty:
                df = df.copy()
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                
                # 只取最近需要的天数
                df = df.tail(days + 10)
                
                # 缓存数据
                self._price_cache[cache_key] = (df, datetime.now())
                return df
            
            return None
            
        except Exception as e:
            print(f"获取 {jq_code} ({get_etf_name(jq_code)}) 数据失败: {e}")
            # 尝试备选方案
            try:
                df = ak.fund_etf_hist_em(symbol=pure_code, adjust="qfq")
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        '日期': 'date', '开盘': 'open', '收盘': 'close',
                        '最高': 'high', '最低': 'low', '成交量': 'volume'
                    })
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').reset_index(drop=True)
                    df = df.tail(days + 10)
                    self._price_cache[cache_key] = (df, datetime.now())
                    return df
            except Exception as e2:
                print(f"备选方案也失败: {e2}")
            
            return None
    
    def calculate_rsi(self, prices, period=6):
        """计算RSI指标"""
        if len(prices) < period + 1:
            return np.array([])
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gains = np.zeros(len(prices))
        avg_losses = np.zeros(len(prices))
        avg_gains[period] = np.mean(gains[:period])
        avg_losses[period] = np.mean(losses[:period])
        
        rsi_values = np.zeros(len(prices))
        rsi_values[:period] = 50
        
        for i in range(period + 1, len(prices)):
            avg_gains[i] = (avg_gains[i-1] * (period - 1) + gains[i-1]) / period
            avg_losses[i] = (avg_losses[i-1] * (period - 1) + losses[i-1]) / period
            
            if avg_losses[i] == 0:
                rsi_values[i] = 100
            else:
                rs = avg_gains[i] / avg_losses[i]
                rsi_values[i] = 100 - (100 / (1 + rs))
        
        return rsi_values[period:]
    
    def get_annualized_returns(self, price_series, lookback_days):
        """计算年化收益率"""
        recent_price_series = price_series[-(lookback_days + 1):]
        y = np.log(recent_price_series)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        return annualized_returns
    
    def calculate_volume_ratio(self, df, lookback=5):
        """计算成交量比值"""
        if df is None or len(df) < lookback + 1:
            return None
        
        volumes = df['volume'].values
        avg_volume = np.mean(volumes[-(lookback+1):-1])
        current_volume = volumes[-1]
        
        if avg_volume > 0:
            ratio = current_volume / avg_volume
            if ratio > self.volume_threshold:
                return ratio
        return None
    
    def calculate_momentum_metrics(self, jq_code):
        """
        计算ETF的动量指标
        返回包含各项指标和过滤结果的字典
        """
        try:
            etf_name = get_etf_name(jq_code)
            
            # 获取历史数据
            lookback = max(self.lookback_days, self.short_lookback_days, 
                          self.rsi_period + self.rsi_lookback_days) + 30
            
            df = self.get_etf_history(jq_code, days=lookback)
            
            if df is None or len(df) < self.lookback_days:
                return None
            
            price_series = df['close'].values.astype(float)
            current_price = price_series[-1]
            
            # ========== 成交量过滤检查 ==========
            if self.enable_volume_check and len(price_series) > self.lookback_days:
                volume_ratio = self.calculate_volume_ratio(df, self.volume_lookback)
                if volume_ratio is not None:
                    volume_annualized = self.get_annualized_returns(price_series, self.lookback_days)
                    if volume_annualized > self.volume_return_limit:
                        return {
                            'etf': jq_code,
                            'etf_name': etf_name,
                            'filtered': True,
                            'filter_reason': f'高位放量 (量比:{volume_ratio:.2f}, 年化:{volume_annualized:.2f})',
                            'current_price': current_price,
                            'score': 0,
                        }
            
            # ========== RSI过滤检查 ==========
            rsi_filter_pass = True
            current_rsi = 0
            max_rsi = 0
            
            if self.use_rsi_filter and len(price_series) >= self.rsi_period + self.rsi_lookback_days:
                rsi_values = self.calculate_rsi(price_series, self.rsi_period)
                
                if len(rsi_values) >= self.rsi_lookback_days:
                    recent_rsi = rsi_values[-self.rsi_lookback_days:]
                    rsi_ever_above_threshold = np.any(recent_rsi > self.rsi_threshold)
                    
                    if len(price_series) >= 5:
                        ma5 = np.mean(price_series[-5:])
                        current_below_ma5 = current_price < ma5
                    else:
                        current_below_ma5 = True
                    
                    if rsi_ever_above_threshold and current_below_ma5:
                        rsi_filter_pass = False
                        max_rsi = float(np.max(recent_rsi))
                        current_rsi = float(recent_rsi[-1]) if len(recent_rsi) > 0 else 0
                    else:
                        max_rsi = float(np.max(recent_rsi)) if len(recent_rsi) > 0 else 0
                        current_rsi = float(recent_rsi[-1]) if len(recent_rsi) > 0 else 0
            
            if not rsi_filter_pass:
                return {
                    'etf': jq_code,
                    'etf_name': etf_name,
                    'filtered': True,
                    'filter_reason': f'RSI过滤 (RSI曾达{max_rsi:.1f}, 当前价<MA5)',
                    'current_price': current_price,
                    'current_rsi': current_rsi,
                    'score': 0,
                }
            
            # ========== 短期动量计算 ==========
            if len(price_series) >= self.short_lookback_days + 1:
                short_return = price_series[-1] / price_series[-(self.short_lookback_days + 1)] - 1
                short_annualized = (1 + short_return) ** (250 / self.short_lookback_days) - 1
            else:
                short_return = 0
                short_annualized = 0
            
            # ========== 短期动量过滤 ==========
            if self.use_short_momentum_filter and short_annualized < self.short_momentum_threshold:
                return {
                    'etf': jq_code,
                    'etf_name': etf_name,
                    'filtered': True,
                    'filter_reason': f'短期动量不足 ({short_annualized:.4f} < {self.short_momentum_threshold})',
                    'current_price': current_price,
                    'score': 0,
                }
            
            # ========== 长期动量计算（加权回归）==========
            recent_price_series = price_series[-(self.lookback_days + 1):]
            y = np.log(recent_price_series)
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            annualized_returns = math.exp(slope * 250) - 1
            
            # 计算R²（拟合优度）
            ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            r_squared = 1 - ss_res / ss_tot if ss_tot else 0
            
            # 综合得分
            score = annualized_returns * r_squared
            
            # ========== 短期风控过滤 ==========
            if len(price_series) >= 4:
                day1_ratio = price_series[-1] / price_series[-2]
                day2_ratio = price_series[-2] / price_series[-3]
                day3_ratio = price_series[-3] / price_series[-4]
                
                if min(day1_ratio, day2_ratio, day3_ratio) < self.loss:
                    score = 0
            
            # 计算近N日涨跌幅
            changes = []
            for i in range(1, min(6, len(price_series))):
                change = (price_series[-i] / price_series[-i-1] - 1) * 100
                changes.append(round(change, 2))
            
            return {
                'etf': jq_code,
                'etf_name': etf_name,
                'category': get_etf_category(jq_code),
                'annualized_returns': round(float(annualized_returns), 4),
                'r_squared': round(float(r_squared), 4),
                'score': round(float(score), 4),
                'slope': round(float(slope), 6),
                'current_price': round(float(current_price), 4),
                'short_return': round(float(short_return), 4),
                'short_annualized': round(float(short_annualized), 4),
                'current_rsi': round(float(current_rsi), 2),
                'max_recent_rsi': round(float(max_rsi), 2),
                'recent_changes': changes,
                'filtered': False,
                'filter_reason': '',
            }
            
        except Exception as e:
            print(f"计算 {jq_code} 动量指标时出错: {e}")
            traceback.print_exc()
            return None
    
    def get_ranked_etfs(self, use_large_pool=False):
        """
        获取符合条件的ETF排名
        """
        pool = self.etf_pool_bak if use_large_pool else self.etf_pool
        etf_metrics = []
        filtered_etfs = []
        errors = []
        
        for etf in pool:
            try:
                metrics = self.calculate_momentum_metrics(etf)
                if metrics is not None:
                    if metrics.get('filtered', False):
                        filtered_etfs.append(metrics)
                    elif 0 < metrics['score'] < self.max_score_threshold:
                        etf_metrics.append(metrics)
                    else:
                        filtered_etfs.append({
                            'etf': etf,
                            'etf_name': get_etf_name(etf),
                            'filtered': True,
                            'filter_reason': f'得分不满足要求 (score={metrics["score"]:.4f})',
                            'current_price': metrics.get('current_price', 0),
                            'score': metrics['score'],
                        })
            except Exception as e:
                errors.append({'etf': etf, 'error': str(e)})
        
        # 按得分降序排序
        etf_metrics.sort(key=lambda x: x['score'], reverse=True)
        
        return etf_metrics, filtered_etfs, errors
    
    def get_today_recommendation(self, use_large_pool=False):
        """
        获取今日推荐
        返回：应该买入的ETF、排名列表、被过滤的ETF
        """
        ranked_etfs, filtered_etfs, errors = self.get_ranked_etfs(use_large_pool)
        
        # 确定目标ETF
        target_etfs = []
        if ranked_etfs:
            for metrics in ranked_etfs[:self.holdings_num]:
                if metrics['score'] >= self.min_score_threshold:
                    target_etfs.append(metrics)
        
        # 如果没有符合条件的，推荐防御ETF
        defense_mode = False
        if not target_etfs:
            defense_mode = True
            defensive_name = get_etf_name(self.defensive_etf)
            target_etfs = [{
                'etf': self.defensive_etf,
                'etf_name': defensive_name,
                'category': '防御',
                'score': 0,
                'annualized_returns': 0,
                'r_squared': 0,
                'current_price': 0,
                'short_return': 0,
                'short_annualized': 0,
                'current_rsi': 0,
                'max_recent_rsi': 0,
                'recent_changes': [],
                'filtered': False,
                'filter_reason': '',
                'is_defensive': True,
            }]
        
        result = {
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'defense_mode': defense_mode,
            'target_etfs': target_etfs,
            'ranked_etfs': ranked_etfs,
            'filtered_etfs': filtered_etfs,
            'errors': errors,
            'pool_type': '大池' if use_large_pool else '小池',
            'pool_size': len(self.etf_pool_bak if use_large_pool else self.etf_pool),
            'params': {
                'lookback_days': self.lookback_days,
                'holdings_num': self.holdings_num,
                'short_lookback_days': self.short_lookback_days,
                'rsi_period': self.rsi_period,
                'rsi_threshold': self.rsi_threshold,
                'stop_loss': self.stop_loss,
                'loss': self.loss,
                'volume_threshold': self.volume_threshold,
            }
        }
        
        # 保存结果到文件
        self._save_result(result)
        
        return result
    
    def _save_result(self, result):
        """保存计算结果到文件"""
        try:
            date_str = datetime.now().strftime('%Y-%m-%d')
            filepath = os.path.join(self.data_dir, f'result_{date_str}.json')
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"保存结果失败: {e}")
    
    def get_cached_result(self):
        """获取今日的缓存结果"""
        try:
            date_str = datetime.now().strftime('%Y-%m-%d')
            filepath = os.path.join(self.data_dir, f'result_{date_str}.json')
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"读取缓存失败: {e}")
        return None
    
    def get_history_results(self, days=7):
        """获取历史计算结果"""
        results = []
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            filepath = os.path.join(self.data_dir, f'result_{date_str}.json')
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        results.append({
                            'date': date_str,
                            'target_etfs': data.get('target_etfs', []),
                            'defense_mode': data.get('defense_mode', False),
                            'pool_type': data.get('pool_type', '小池'),
                        })
                except:
                    pass
        return results
    
    def clear_cache(self):
        """清除价格数据缓存"""
        self._price_cache = {}

    # ==================== 回测引擎 ====================

    def get_etf_full_history(self, jq_code, start_date=None, end_date=None):
        """
        获取ETF完整历史数据（用于回测，不受缓存天数限制）
        返回 DataFrame，包含 date, open, close, high, low, volume
        """
        pure_code = jq_code_to_pure(jq_code)
        try:
            df = ak.fund_etf_hist_sina(symbol=jq_code_to_ak(jq_code))
            if df is not None and not df.empty:
                df = df.copy()
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                # 按日期过滤
                if start_date:
                    df = df[df['date'] >= pd.to_datetime(start_date)]
                if end_date:
                    df = df[df['date'] <= pd.to_datetime(end_date)]
                return df
            return None
        except Exception:
            try:
                df = ak.fund_etf_hist_em(symbol=pure_code, adjust="qfq")
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        '日期': 'date', '开盘': 'open', '收盘': 'close',
                        '最高': 'high', '最低': 'low', '成交量': 'volume'
                    })
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').reset_index(drop=True)
                    if start_date:
                        df = df[df['date'] >= pd.to_datetime(start_date)]
                    if end_date:
                        df = df[df['date'] <= pd.to_datetime(end_date)]
                    return df
            except Exception:
                pass
            return None

    def _calc_score_at(self, price_series, volume_series=None):
        """
        给定一段价格序列（至少 lookback_days+1 长），计算当日策略得分。
        返回 (score, filtered, filter_reason)
        """
        if len(price_series) < self.lookback_days + 1:
            return (0, True, '数据不足')

        current_price = price_series[-1]

        # ---- 成交量过滤 ----
        if self.enable_volume_check and volume_series is not None and len(volume_series) >= self.volume_lookback + 1:
            avg_vol = np.mean(volume_series[-(self.volume_lookback + 1):-1])
            cur_vol = volume_series[-1]
            if avg_vol > 0 and cur_vol / avg_vol > self.volume_threshold:
                ann = self.get_annualized_returns(price_series, self.lookback_days)
                if ann > self.volume_return_limit:
                    return (0, True, '高位放量')

        # ---- RSI过滤 ----
        if self.use_rsi_filter and len(price_series) >= self.rsi_period + self.rsi_lookback_days:
            rsi_values = self.calculate_rsi(price_series, self.rsi_period)
            if len(rsi_values) >= self.rsi_lookback_days:
                recent_rsi = rsi_values[-self.rsi_lookback_days:]
                if np.any(recent_rsi > self.rsi_threshold):
                    if len(price_series) >= 5:
                        ma5 = np.mean(price_series[-5:])
                        if current_price < ma5:
                            return (0, True, 'RSI过滤')

        # ---- 短期动量过滤 ----
        if self.use_short_momentum_filter and len(price_series) >= self.short_lookback_days + 1:
            short_ret = price_series[-1] / price_series[-(self.short_lookback_days + 1)] - 1
            short_ann = (1 + short_ret) ** (250 / self.short_lookback_days) - 1
            if short_ann < self.short_momentum_threshold:
                return (0, True, '短期动量不足')

        # ---- 加权回归动量 ----
        recent = price_series[-(self.lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1

        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0
        score = annualized_returns * r_squared

        # ---- 近3日跌幅风控 ----
        if len(price_series) >= 4:
            ratios = [price_series[-i] / price_series[-i - 1] for i in range(1, 4)]
            if min(ratios) < self.loss:
                score = 0

        if score <= 0 or score >= self.max_score_threshold:
            return (0, True, '得分不满足')

        return (score, False, '')

    def run_backtest(self, start_date, end_date):
        """
        运行回测：逐日模拟策略，每天选出得分最高的ETF进行轮动。
        返回：净值序列、统计指标、交易记录
        """
        import logging
        logger = logging.getLogger(__name__)

        pool = self.etf_pool  # 小池

        # 1. 获取所有ETF的完整历史数据
        # 需要向前多取一些天数用于指标计算
        warmup_days = max(self.lookback_days, self.short_lookback_days,
                         self.rsi_period + self.rsi_lookback_days) + 40
        fetch_start = (pd.to_datetime(start_date) - timedelta(days=warmup_days * 2)).strftime('%Y-%m-%d')

        all_data = {}
        for etf in pool:
            df = self.get_etf_full_history(etf, start_date=fetch_start, end_date=end_date)
            if df is not None and not df.empty:
                df = df.set_index('date').sort_index()
                all_data[etf] = df

        if not all_data:
            return {'error': '无法获取ETF历史数据'}

        # 同时获取防御ETF数据
        def_df = self.get_etf_full_history(self.defensive_etf, start_date=fetch_start, end_date=end_date)
        if def_df is not None and not def_df.empty:
            def_df = def_df.set_index('date').sort_index()
            all_data[self.defensive_etf] = def_df

        # 2. 建立公共交易日序列
        all_dates = set()
        for df in all_data.values():
            all_dates.update(df.index.tolist())
        all_dates = sorted(all_dates)
        # 过滤到回测区间
        bt_start = pd.to_datetime(start_date)
        bt_end = pd.to_datetime(end_date)
        trade_dates = [d for d in all_dates if bt_start <= d <= bt_end]

        if len(trade_dates) < 2:
            return {'error': '回测区间交易日不足'}

        # 3. 逐日模拟
        nav = 1.0  # 净值
        holding = None  # 当前持仓ETF代码
        buy_price = 0.0

        nav_series = []  # [{date, nav, holding, action}]
        trades = []      # 交易记录
        win_count = 0
        loss_count = 0
        max_nav = 1.0
        max_drawdown = 0.0

        for i, date in enumerate(trade_dates):
            # ---- 对每只ETF计算当日得分 ----
            best_etf = None
            best_score = -1

            for etf in pool:
                if etf not in all_data:
                    continue
                df = all_data[etf]
                # 取截止到当天的数据
                hist = df[df.index <= date]
                if len(hist) < self.lookback_days + 1:
                    continue
                prices = hist['close'].values.astype(float)
                volumes = hist['volume'].values.astype(float) if 'volume' in hist.columns else None
                score, filtered, _ = self._calc_score_at(prices, volumes)
                if not filtered and score > best_score:
                    best_score = score
                    best_etf = etf

            # 如果无合格标的，选防御ETF
            if best_etf is None:
                best_etf = self.defensive_etf

            # ---- 获取当日价格 ----
            def get_price(etf_code, d):
                if etf_code in all_data:
                    df = all_data[etf_code]
                    if d in df.index:
                        return float(df.loc[d, 'close'])
                    # 找最近的前一个交易日
                    prev = df[df.index <= d]
                    if not prev.empty:
                        return float(prev.iloc[-1]['close'])
                return None

            current_price = get_price(best_etf, date)
            holding_price = get_price(holding, date) if holding else None

            action = ''

            if i == 0:
                # 第一天建仓
                if current_price:
                    holding = best_etf
                    buy_price = current_price
                    action = 'buy'
                    trades.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'action': '买入',
                        'etf': holding,
                        'etf_name': get_etf_name(holding),
                        'price': round(buy_price, 4),
                    })
            else:
                # 计算持仓净值变动
                if holding and holding_price and buy_price > 0:
                    daily_return = holding_price / buy_price
                    # 更新 nav 需要基于上一次 buy 时的 nav 基准
                    pass  # 在下面统一计算

                # 判断是否换仓
                if best_etf != holding:
                    # 卖出旧持仓
                    if holding and holding_price and buy_price > 0:
                        trade_return = holding_price / buy_price - 1
                        if trade_return > 0:
                            win_count += 1
                        else:
                            loss_count += 1
                        trades.append({
                            'date': date.strftime('%Y-%m-%d'),
                            'action': '卖出',
                            'etf': holding,
                            'etf_name': get_etf_name(holding),
                            'price': round(holding_price, 4),
                            'return': round(trade_return * 100, 2),
                        })

                    # 买入新标的
                    if current_price:
                        holding = best_etf
                        buy_price = current_price
                        action = 'switch'
                        trades.append({
                            'date': date.strftime('%Y-%m-%d'),
                            'action': '买入',
                            'etf': holding,
                            'etf_name': get_etf_name(holding),
                            'price': round(buy_price, 4),
                        })

            # ---- 计算当日净值 ----
            if holding and buy_price > 0:
                hp = get_price(holding, date)
                if hp:
                    # nav_base 是上一次买入时的 nav
                    if len(nav_series) == 0:
                        nav = hp / buy_price
                    else:
                        # 找上一次买入时的 nav（即换仓当天更新前的 nav）
                        last_nav = nav_series[-1]['nav']
                        if action in ('buy', 'switch'):
                            nav = last_nav  # 换仓当天净值不变（假设同日换）
                        else:
                            # 持仓不变，按持仓涨跌更新净值
                            prev_hp = get_price(holding, trade_dates[i - 1]) if i > 0 else buy_price
                            if prev_hp and prev_hp > 0:
                                nav = last_nav * (hp / prev_hp)
                            else:
                                nav = last_nav

            # 最大回撤
            if nav > max_nav:
                max_nav = nav
            dd = (max_nav - nav) / max_nav
            if dd > max_drawdown:
                max_drawdown = dd

            # 收集当天的交易动作信息（用于图表标注买卖点）
            day_trades = [t for t in trades if t['date'] == date.strftime('%Y-%m-%d')]
            trade_actions = []
            for t in day_trades:
                ta = {
                    'action': t['action'],
                    'etf_name': t['etf_name'],
                    'etf': t['etf'],
                    'price': t['price'],
                }
                if 'return' in t:
                    ta['return'] = t['return']
                trade_actions.append(ta)

            nav_series.append({
                'date': date.strftime('%Y-%m-%d'),
                'nav': round(nav, 6),
                'holding': get_etf_name(holding) if holding else '-',
                'holding_code': holding or '',
                'trade_actions': trade_actions,
            })

        # 4. 计算统计指标
        if len(nav_series) < 2:
            return {'error': '回测数据不足'}

        total_return = nav_series[-1]['nav'] / nav_series[0]['nav'] - 1
        days_count = (pd.to_datetime(nav_series[-1]['date']) - pd.to_datetime(nav_series[0]['date'])).days
        annual_return = (1 + total_return) ** (365 / max(days_count, 1)) - 1 if days_count > 0 else 0

        # 计算夏普比率（简化版，无风险利率取2%）
        navs = [p['nav'] for p in nav_series]
        daily_returns = []
        for j in range(1, len(navs)):
            daily_returns.append(navs[j] / navs[j - 1] - 1)
        if daily_returns:
            avg_daily = np.mean(daily_returns)
            std_daily = np.std(daily_returns)
            sharpe = (avg_daily - 0.02 / 250) / std_daily * np.sqrt(250) if std_daily > 0 else 0
        else:
            sharpe = 0

        total_trades = win_count + loss_count
        win_rate = win_count / total_trades if total_trades > 0 else 0

        stats = {
            'total_return': round(total_return * 100, 2),
            'annual_return': round(annual_return * 100, 2),
            'max_drawdown': round(max_drawdown * 100, 2),
            'sharpe_ratio': round(sharpe, 2),
            'total_trades': total_trades,
            'win_rate': round(win_rate * 100, 1),
            'win_count': win_count,
            'loss_count': loss_count,
            'trade_days': len(nav_series),
            'start_date': nav_series[0]['date'],
            'end_date': nav_series[-1]['date'],
        }

        return {
            'nav_series': nav_series,
            'stats': stats,
            'trades': trades[-50:],  # 最多返回50条交易记录
        }


class TopScoreEngine:
    """
    最高评分策略引擎
    ETF池：黄金ETF、纳指100、创业板100、上证180
    特殊规则：上证180ETF评分最高时选择空仓
    无过滤器，纯动量评分选股
    """

    def __init__(self, data_dir='data'):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # ETF池
        self.etf_pool = [
            "159934.XSHE",  # 黄金ETF
            "159941.XSHE",  # 纳指100
            "159915.XSHE",  # 创业板100
            "510180.XSHG",  # 上证180
        ]

        # 上证180ETF - 信号为此时空仓
        self.empty_signal_etf = "510180.XSHG"

        # 防御性ETF（空仓时使用）
        self.defensive_etf = "511880.XSHG"

        self.m_days = 25  # 动量参考天数
        self.holdings_num = 1
        self.min_score = 0
        self.max_score = 5  # 得分安全区间上限

        # 价格数据缓存
        self._price_cache = {}

    def get_etf_history(self, jq_code, days=60):
        """获取ETF历史行情数据"""
        pure_code = jq_code_to_pure(jq_code)
        cache_key = f"ts_{pure_code}_{days}"

        if cache_key in self._price_cache:
            cached_data, cached_time = self._price_cache[cache_key]
            if (datetime.now() - cached_time).seconds < 600:
                return cached_data

        try:
            df = ak.fund_etf_hist_sina(symbol=jq_code_to_ak(jq_code))
            if df is not None and not df.empty:
                df = df.copy()
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                df = df.tail(days + 10)
                self._price_cache[cache_key] = (df, datetime.now())
                return df
            return None
        except Exception as e:
            print(f"获取 {jq_code} ({get_etf_name(jq_code)}) 数据失败: {e}")
            try:
                df = ak.fund_etf_hist_em(symbol=pure_code, adjust="qfq")
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        '日期': 'date', '开盘': 'open', '收盘': 'close',
                        '最高': 'high', '最低': 'low', '成交量': 'volume'
                    })
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').reset_index(drop=True)
                    df = df.tail(days + 10)
                    self._price_cache[cache_key] = (df, datetime.now())
                    return df
            except Exception as e2:
                print(f"备选方案也失败: {e2}")
            return None

    def calculate_mom_score(self, price_series):
        """
        计算动量评分（最高评分策略专用算法）
        score = annualized_returns * r_squared
        其中 annualized_returns = exp(slope)^250 - 1
        """
        if len(price_series) < self.m_days:
            return 0

        y = np.log(price_series[-self.m_days:])
        n = len(y)
        x = np.arange(n)
        weights = np.linspace(1, 2, n)

        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.pow(math.exp(slope), 250) - 1

        residuals = y - (slope * x + intercept)
        weighted_residuals = weights * residuals ** 2
        r_squared = 1 - (np.sum(weighted_residuals) / np.sum(weights * (y - np.mean(y)) ** 2))

        score = annualized_returns * r_squared
        return score

    def calculate_momentum_metrics(self, jq_code):
        """计算ETF的动量指标"""
        try:
            etf_name = get_etf_name(jq_code)
            df = self.get_etf_history(jq_code, days=self.m_days + 30)

            if df is None or len(df) < self.m_days:
                return None

            price_series = df['close'].values.astype(float)
            current_price = price_series[-1]
            score = self.calculate_mom_score(price_series)

            # 计算年化收益和R²用于展示
            y = np.log(price_series[-self.m_days:])
            x = np.arange(len(y))
            weights = np.linspace(1, 2, len(y))
            slope, intercept = np.polyfit(x, y, 1, w=weights)
            annualized_returns = math.pow(math.exp(slope), 250) - 1
            residuals = y - (slope * x + intercept)
            weighted_residuals = weights * residuals ** 2
            ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
            r_squared = 1 - (np.sum(weighted_residuals) / ss_tot) if ss_tot else 0

            # 计算近N日涨跌幅
            changes = []
            for i in range(1, min(6, len(price_series))):
                change = (price_series[-i] / price_series[-i - 1] - 1) * 100
                changes.append(round(change, 2))

            # 判断是否在安全区间内
            in_range = (score > self.min_score) and (score <= self.max_score)

            return {
                'etf': jq_code,
                'etf_name': etf_name,
                'category': get_etf_category(jq_code),
                'annualized_returns': round(float(annualized_returns), 4),
                'r_squared': round(float(r_squared), 4),
                'score': round(float(score), 4),
                'slope': round(float(slope), 6),
                'current_price': round(float(current_price), 4),
                'short_return': 0,
                'short_annualized': 0,
                'current_rsi': 0,
                'max_recent_rsi': 0,
                'recent_changes': changes,
                'filtered': not in_range,
                'filter_reason': '' if in_range else f'得分不在安全区间 (score={score:.4f}, 需0~{self.max_score})',
            }

        except Exception as e:
            print(f"计算 {jq_code} 动量指标时出错: {e}")
            traceback.print_exc()
            return None

    def get_ranked_etfs(self):
        """获取符合条件的ETF排名"""
        etf_metrics = []
        filtered_etfs = []
        errors = []

        for etf in self.etf_pool:
            try:
                metrics = self.calculate_momentum_metrics(etf)
                if metrics is not None:
                    if metrics.get('filtered', False):
                        filtered_etfs.append(metrics)
                    else:
                        etf_metrics.append(metrics)
            except Exception as e:
                errors.append({'etf': etf, 'error': str(e)})

        etf_metrics.sort(key=lambda x: x['score'], reverse=True)
        return etf_metrics, filtered_etfs, errors

    def get_today_recommendation(self):
        """获取今日推荐"""
        ranked_etfs, filtered_etfs, errors = self.get_ranked_etfs()

        target_etfs = []
        defense_mode = False
        empty_signal = False

        if ranked_etfs:
            top_etf = ranked_etfs[0]
            # 特殊规则：上证180ETF评分最高时选择空仓
            if top_etf['etf'] == self.empty_signal_etf:
                empty_signal = True
                defense_mode = True
            else:
                target_etfs.append(top_etf)

        if not target_etfs:
            defense_mode = True
            defensive_name = get_etf_name(self.defensive_etf)
            target_etfs = [{
                'etf': self.defensive_etf,
                'etf_name': defensive_name,
                'category': '防御',
                'score': 0,
                'annualized_returns': 0,
                'r_squared': 0,
                'current_price': 0,
                'short_return': 0,
                'short_annualized': 0,
                'current_rsi': 0,
                'max_recent_rsi': 0,
                'recent_changes': [],
                'filtered': False,
                'filter_reason': '',
                'is_defensive': True,
            }]

        result = {
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'defense_mode': defense_mode,
            'empty_signal': empty_signal,
            'target_etfs': target_etfs,
            'ranked_etfs': ranked_etfs,
            'filtered_etfs': filtered_etfs,
            'errors': errors,
            'strategy_name': '最高评分',
            'pool_size': len(self.etf_pool),
            'params': {
                'lookback_days': self.m_days,
                'holdings_num': self.holdings_num,
                'max_score': self.max_score,
                'empty_signal_etf': get_etf_name(self.empty_signal_etf),
            }
        }

        # 保存结果到文件
        self._save_result(result)
        return result

    def _save_result(self, result):
        """保存计算结果到文件"""
        try:
            date_str = datetime.now().strftime('%Y-%m-%d')
            filepath = os.path.join(self.data_dir, f'result_topscore_{date_str}.json')
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            print(f"保存结果失败: {e}")

    def get_cached_result(self):
        """获取今日的缓存结果"""
        try:
            date_str = datetime.now().strftime('%Y-%m-%d')
            filepath = os.path.join(self.data_dir, f'result_topscore_{date_str}.json')
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"读取缓存失败: {e}")
        return None

    def clear_cache(self):
        """清除价格数据缓存"""
        self._price_cache = {}

    # ==================== 回测引擎 ====================

    def get_etf_full_history(self, jq_code, start_date=None, end_date=None):
        """获取ETF完整历史数据（用于回测）"""
        pure_code = jq_code_to_pure(jq_code)
        try:
            df = ak.fund_etf_hist_sina(symbol=jq_code_to_ak(jq_code))
            if df is not None and not df.empty:
                df = df.copy()
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date').reset_index(drop=True)
                if start_date:
                    df = df[df['date'] >= pd.to_datetime(start_date)]
                if end_date:
                    df = df[df['date'] <= pd.to_datetime(end_date)]
                return df
            return None
        except Exception:
            try:
                df = ak.fund_etf_hist_em(symbol=pure_code, adjust="qfq")
                if df is not None and not df.empty:
                    df = df.rename(columns={
                        '日期': 'date', '开盘': 'open', '收盘': 'close',
                        '最高': 'high', '最低': 'low', '成交量': 'volume'
                    })
                    df['date'] = pd.to_datetime(df['date'])
                    df = df.sort_values('date').reset_index(drop=True)
                    if start_date:
                        df = df[df['date'] >= pd.to_datetime(start_date)]
                    if end_date:
                        df = df[df['date'] <= pd.to_datetime(end_date)]
                    return df
            except Exception:
                pass
            return None

    def _calc_score_at(self, price_series):
        """给定一段价格序列，计算当日策略得分"""
        if len(price_series) < self.m_days:
            return (0, True, '数据不足')

        score = self.calculate_mom_score(price_series)

        if score <= self.min_score or score > self.max_score:
            return (0, True, '得分不在安全区间')

        return (score, False, '')

    def run_backtest(self, start_date, end_date):
        """运行回测"""
        import logging
        logger = logging.getLogger(__name__)

        pool = self.etf_pool
        warmup_days = self.m_days + 40
        fetch_start = (pd.to_datetime(start_date) - timedelta(days=warmup_days * 2)).strftime('%Y-%m-%d')

        all_data = {}
        for etf in pool:
            df = self.get_etf_full_history(etf, start_date=fetch_start, end_date=end_date)
            if df is not None and not df.empty:
                df = df.set_index('date').sort_index()
                all_data[etf] = df

        if not all_data:
            return {'error': '无法获取ETF历史数据'}

        # 获取防御ETF数据
        def_df = self.get_etf_full_history(self.defensive_etf, start_date=fetch_start, end_date=end_date)
        if def_df is not None and not def_df.empty:
            def_df = def_df.set_index('date').sort_index()
            all_data[self.defensive_etf] = def_df

        # 建立公共交易日序列
        all_dates = set()
        for df in all_data.values():
            all_dates.update(df.index.tolist())
        all_dates = sorted(all_dates)

        bt_start = pd.to_datetime(start_date)
        bt_end = pd.to_datetime(end_date)
        trade_dates = [d for d in all_dates if bt_start <= d <= bt_end]

        if len(trade_dates) < 2:
            return {'error': '回测区间交易日不足'}

        # 逐日模拟
        nav = 1.0
        holding = None
        buy_price = 0.0
        nav_series = []
        trades = []
        win_count = 0
        loss_count = 0
        max_nav = 1.0
        max_drawdown = 0.0

        for i, date in enumerate(trade_dates):
            # 对每只ETF计算当日得分
            best_etf = None
            best_score = -1

            for etf in pool:
                if etf not in all_data:
                    continue
                df = all_data[etf]
                hist = df[df.index <= date]
                if len(hist) < self.m_days:
                    continue
                prices = hist['close'].values.astype(float)
                score, filtered, _ = self._calc_score_at(prices)
                if not filtered and score > best_score:
                    best_score = score
                    best_etf = etf

            # 特殊规则：上证180ETF评分最高时选择空仓（使用防御ETF）
            if best_etf == self.empty_signal_etf:
                best_etf = self.defensive_etf

            # 如果无合格标的，选防御ETF
            if best_etf is None:
                best_etf = self.defensive_etf

            # 获取当日价格
            def get_price(etf_code, d):
                if etf_code in all_data:
                    df = all_data[etf_code]
                    if d in df.index:
                        return float(df.loc[d, 'close'])
                    prev = df[df.index <= d]
                    if not prev.empty:
                        return float(prev.iloc[-1]['close'])
                return None

            current_price = get_price(best_etf, date)
            holding_price = get_price(holding, date) if holding else None
            action = ''

            if i == 0:
                if current_price:
                    holding = best_etf
                    buy_price = current_price
                    action = 'buy'
                    trades.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'action': '买入',
                        'etf': holding,
                        'etf_name': get_etf_name(holding),
                        'price': round(buy_price, 4),
                    })
            else:
                if best_etf != holding:
                    if holding and holding_price and buy_price > 0:
                        trade_return = holding_price / buy_price - 1
                        if trade_return > 0:
                            win_count += 1
                        else:
                            loss_count += 1
                        trades.append({
                            'date': date.strftime('%Y-%m-%d'),
                            'action': '卖出',
                            'etf': holding,
                            'etf_name': get_etf_name(holding),
                            'price': round(holding_price, 4),
                            'return': round(trade_return * 100, 2),
                        })

                    if current_price:
                        holding = best_etf
                        buy_price = current_price
                        action = 'switch'
                        trades.append({
                            'date': date.strftime('%Y-%m-%d'),
                            'action': '买入',
                            'etf': holding,
                            'etf_name': get_etf_name(holding),
                            'price': round(buy_price, 4),
                        })

            # 计算当日净值
            if holding and buy_price > 0:
                hp = get_price(holding, date)
                if hp:
                    if len(nav_series) == 0:
                        nav = hp / buy_price
                    else:
                        last_nav = nav_series[-1]['nav']
                        if action in ('buy', 'switch'):
                            nav = last_nav
                        else:
                            prev_hp = get_price(holding, trade_dates[i - 1]) if i > 0 else buy_price
                            if prev_hp and prev_hp > 0:
                                nav = last_nav * (hp / prev_hp)
                            else:
                                nav = last_nav

            if nav > max_nav:
                max_nav = nav
            dd = (max_nav - nav) / max_nav
            if dd > max_drawdown:
                max_drawdown = dd

            day_trades = [t for t in trades if t['date'] == date.strftime('%Y-%m-%d')]
            trade_actions = []
            for t in day_trades:
                ta = {
                    'action': t['action'],
                    'etf_name': t['etf_name'],
                    'etf': t['etf'],
                    'price': t['price'],
                }
                if 'return' in t:
                    ta['return'] = t['return']
                trade_actions.append(ta)

            nav_series.append({
                'date': date.strftime('%Y-%m-%d'),
                'nav': round(nav, 6),
                'holding': get_etf_name(holding) if holding else '-',
                'holding_code': holding or '',
                'trade_actions': trade_actions,
            })

        if len(nav_series) < 2:
            return {'error': '回测数据不足'}

        total_return = nav_series[-1]['nav'] / nav_series[0]['nav'] - 1
        days_count = (pd.to_datetime(nav_series[-1]['date']) - pd.to_datetime(nav_series[0]['date'])).days
        annual_return = (1 + total_return) ** (365 / max(days_count, 1)) - 1 if days_count > 0 else 0

        navs = [p['nav'] for p in nav_series]
        daily_returns = []
        for j in range(1, len(navs)):
            daily_returns.append(navs[j] / navs[j - 1] - 1)
        if daily_returns:
            avg_daily = np.mean(daily_returns)
            std_daily = np.std(daily_returns)
            sharpe = (avg_daily - 0.02 / 250) / std_daily * np.sqrt(250) if std_daily > 0 else 0
        else:
            sharpe = 0

        total_trades = win_count + loss_count
        win_rate = win_count / total_trades if total_trades > 0 else 0

        stats = {
            'total_return': round(total_return * 100, 2),
            'annual_return': round(annual_return * 100, 2),
            'max_drawdown': round(max_drawdown * 100, 2),
            'sharpe_ratio': round(sharpe, 2),
            'total_trades': total_trades,
            'win_rate': round(win_rate * 100, 1),
            'win_count': win_count,
            'loss_count': loss_count,
            'trade_days': len(nav_series),
            'start_date': nav_series[0]['date'],
            'end_date': nav_series[-1]['date'],
        }

        return {
            'nav_series': nav_series,
            'stats': stats,
            'trades': trades[-50:],
        }
