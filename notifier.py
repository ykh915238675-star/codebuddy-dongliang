"""
企业微信群机器人通知模块
当策略推荐的ETF发生买卖变动时，自动发送通知
"""

import json
import os
import requests
from datetime import datetime


class WeChatWorkNotifier:
    """企业微信群机器人通知"""

    def __init__(self, data_dir='data'):
        self.data_dir = data_dir
        self.config_file = os.path.join(data_dir, 'notify_config.json')
        self._load_config()

    def _load_config(self):
        """加载通知配置"""
        self.webhook_url = ''
        self.enabled = False
        self.auto_check = False
        self.check_hour = 14   # 默认14:30执行
        self.check_minute = 30
        self.check_strategies = ['momentum', 'topscore']  # 默认监控所有策略
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    self.webhook_url = cfg.get('webhook_url', '')
                    self.enabled = cfg.get('enabled', False)
                    self.auto_check = cfg.get('auto_check', False)
                    self.check_hour = cfg.get('check_hour', 14)
                    self.check_minute = cfg.get('check_minute', 30)
                    self.check_strategies = cfg.get('check_strategies', ['momentum', 'topscore'])
        except Exception as e:
            print(f"[通知] 加载配置失败: {e}")

    def save_config(self, webhook_url, enabled, auto_check=None, check_hour=None, check_minute=None, check_strategies=None):
        """保存通知配置"""
        self.webhook_url = webhook_url
        self.enabled = enabled
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            # 先读取已有配置，避免丢失字段
            existing = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            existing['webhook_url'] = webhook_url
            existing['enabled'] = enabled
            if auto_check is not None:
                existing['auto_check'] = auto_check
                self.auto_check = auto_check
            if check_hour is not None:
                existing['check_hour'] = check_hour
                self.check_hour = check_hour
            if check_minute is not None:
                existing['check_minute'] = check_minute
                self.check_minute = check_minute
            if check_strategies is not None:
                existing['check_strategies'] = check_strategies
                self.check_strategies = check_strategies
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[通知] 保存配置失败: {e}")
            return False

    def get_config(self):
        """获取当前通知配置"""
        self._load_config()
        return {
            'webhook_url': self.webhook_url,
            'enabled': self.enabled,
            'auto_check': self.auto_check,
            'check_hour': self.check_hour,
            'check_minute': self.check_minute,
            'check_strategies': self.check_strategies,
        }

    def _get_last_recommendation(self, strategy='momentum'):
        """获取上一次的推荐结果（用于对比变动）"""
        filepath = os.path.join(self.data_dir, f'last_notify_{strategy}.json')
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _save_last_recommendation(self, strategy, target_etf_code, defense_mode):
        """保存本次推荐结果供下次对比"""
        filepath = os.path.join(self.data_dir, f'last_notify_{strategy}.json')
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'target_etf': target_etf_code,
                    'defense_mode': defense_mode,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[通知] 保存上次推荐失败: {e}")

    def check_and_notify(self, strategy, result):
        """
        检查策略推荐是否有变动，无论是否变动都发送通知。
        有变动时特殊醒目提醒，无变动时发送日常报告。
        
        参数:
            strategy: 策略名称 ('momentum' 或 'topscore')
            result: 策略计算结果字典
        
        返回:
            dict: {'changed': bool, 'notified': bool, 'message': str}
        """
        if not self.enabled or not self.webhook_url:
            return {'changed': False, 'notified': False, 'message': '通知未启用'}

        # 获取当前推荐
        target_etfs = result.get('target_etfs', [])
        defense_mode = result.get('defense_mode', False)
        current_etf_code = target_etfs[0]['etf'] if target_etfs else ''
        strategy_name = '动量轮动' if strategy == 'momentum' else '最高评分'
        current_etf_name = target_etfs[0].get('etf_name', '') if target_etfs else ''
        current_score = target_etfs[0].get('score', 0) if target_etfs else 0
        now = datetime.now().strftime('%Y-%m-%d %H:%M')

        # 获取上次推荐
        last = self._get_last_recommendation(strategy)

        # 判断是否有变动
        changed = False
        change_type = ''  # 'switch', 'to_defense', 'from_defense'

        if last is not None:
            last_etf = last.get('target_etf', '')
            last_defense = last.get('defense_mode', False)

            if current_etf_code != last_etf:
                changed = True
                if last_defense and not defense_mode:
                    change_type = 'from_defense'
                elif not last_defense and defense_mode:
                    change_type = 'to_defense'
                else:
                    change_type = 'switch'
        else:
            last_etf = ''
            last_defense = False

        from engine import get_etf_name
        last_etf_name = get_etf_name(last_etf) if last_etf else '无'

        # ==================== 构建通知消息 ====================
        if changed:
            # ⚠️ 有变动 —— 醒目提醒
            if change_type == 'to_defense':
                title = f"🚨🛡️ 【{strategy_name}】⚠️ 变动提醒：切换至防御模式！"
                detail = (
                    f"**原持仓**: {last_etf_name}（{last_etf}）\n"
                    f"**当前建议**: <font color=\"warning\">空仓 / 持有货币基金ETF</font>\n"
                )
                if result.get('empty_signal'):
                    detail += f"**原因**: 上证180ETF评分最高，市场偏防御\n"
                else:
                    detail += f"**原因**: 所有ETF均不满足筛选条件\n"

            elif change_type == 'from_defense':
                title = f"🚨🚀 【{strategy_name}】⚠️ 变动提醒：发现买入信号！"
                detail = (
                    f"**原状态**: 防御模式（空仓）\n"
                    f"**建议买入**: <font color=\"info\">{current_etf_name}（{current_etf_code}）</font>\n"
                    f"**综合得分**: {current_score:.4f}\n"
                )

            else:  # switch
                title = f"🚨🔄 【{strategy_name}】⚠️ 变动提醒：持仓需调整！"
                detail = (
                    f"**卖出**: <font color=\"warning\">{last_etf_name}（{last_etf}）</font>\n"
                    f"**买入**: <font color=\"info\">{current_etf_name}（{current_etf_code}）</font>\n"
                    f"**综合得分**: {current_score:.4f}\n"
                )

            message = f"{title}\n\n{detail}\n> 📌 请注意操作！推荐已发生变更\n\n⏰ {now}"

        else:
            # ✅ 无变动 —— 日常平安报告
            if defense_mode:
                status_text = '🛡️ 防御模式（空仓）'
                hold_info = '当前建议空仓 / 持有货币基金ETF'
            else:
                status_text = f'📈 持有中'
                hold_info = f'继续持有 **{current_etf_name}**（{current_etf_code}）· 得分 {current_score:.4f}'

            title = f"✅ 【{strategy_name}】今日无变动"
            detail = (
                f"**状态**: {status_text}\n"
                f"**建议**: {hold_info}\n"
            )

            if last is not None:
                last_time = last.get('timestamp', '未知')
                detail += f"**上次变动**: {last_time}\n"

            message = f"{title}\n\n{detail}\n> 💤 推荐未变化，无需操作\n\n⏰ {now}"

        # 发送通知
        success = self._send_markdown(message)

        # 更新记录（无论是否变动都更新时间戳，有变动时更新推荐内容）
        if success:
            self._save_last_recommendation(strategy, current_etf_code, defense_mode)

        return {
            'changed': changed,
            'notified': success,
            'message': f"{'通知已发送' if success else '通知发送失败'}: {title}",
        }

    def _send_markdown(self, content):
        """发送 Markdown 格式消息到企业微信群"""
        if not self.webhook_url:
            print("[通知] Webhook URL 未配置")
            return False

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content,
            }
        }

        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            data = resp.json()
            if data.get('errcode') == 0:
                print(f"[通知] 发送成功")
                return True
            else:
                print(f"[通知] 发送失败: {data}")
                return False
        except Exception as e:
            print(f"[通知] 请求异常: {e}")
            return False

    def send_test(self):
        """发送测试通知"""
        if not self.webhook_url:
            return {'success': False, 'message': 'Webhook URL 未配置'}

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        content = (
            f"✅ **ETF动量轮动 - 通知测试**\n\n"
            f"恭喜！通知配置成功 🎉\n\n"
            f"当策略推荐的ETF发生买卖变动时，\n"
            f"你会在这里收到提醒。\n\n"
            f"⏰ {now}"
        )

        success = self._send_markdown(content)
        return {
            'success': success,
            'message': '测试通知已发送，请查看企业微信' if success else '发送失败，请检查 Webhook URL',
        }
