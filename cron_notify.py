#!/usr/bin/env python3
"""
GitHub Actions 定时推送脚本
不依赖 Flask，直接调用引擎计算策略并推送到企业微信。

环境变量:
    WECHAT_WORK_WEBHOOK  - 企业微信群机器人 Webhook URL（必填）
"""

import os, sys, json, requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import QuantEngine, TopScoreEngine, get_etf_name

WEBHOOK_URL = os.environ.get('WECHAT_WORK_WEBHOOK', '')
DATA_DIR = os.environ.get('DATA_DIR', '/tmp/quant_data')
RECORD_DIR = os.environ.get('RECORD_DIR', '/tmp/quant_records')


def send_markdown(content):
    if not WEBHOOK_URL:
        print("[错误] WECHAT_WORK_WEBHOOK 未设置")
        return False
    try:
        resp = requests.post(WEBHOOK_URL, json={"msgtype": "markdown", "markdown": {"content": content}}, timeout=15)
        data = resp.json()
        if data.get('errcode') == 0:
            print("[推送] 发送成功")
            return True
        print(f"[推送] 失败: {data}")
        return False
    except Exception as e:
        print(f"[推送] 异常: {e}")
        return False


def load_last(strategy):
    fp = os.path.join(RECORD_DIR, f'last_{strategy}.json')
    try:
        if os.path.exists(fp):
            with open(fp, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return None


def save_last(strategy, etf_code, defense_mode):
    os.makedirs(RECORD_DIR, exist_ok=True)
    fp = os.path.join(RECORD_DIR, f'last_{strategy}.json')
    with open(fp, 'w') as f:
        json.dump({'target_etf': etf_code, 'defense_mode': defense_mode,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False, indent=2)


def build_ranking_table(result, strategy):
    """构建 ETF 得分排名表"""
    ranked = result.get('ranked_etfs', [])
    filtered = result.get('filtered_etfs', [])

    lines = []
    # 排名内的 ETF
    for i, etf in enumerate(ranked):
        name = etf.get('etf_name', '')
        code = etf.get('etf', '').split('.')[0]
        score = etf.get('score', 0)
        marker = ' 👈' if i == 0 and not result.get('defense_mode', False) else ''
        lines.append(f"> {i+1}. {name}({code}) 得分:**{score:.4f}**{marker}")

    # 被过滤的 ETF
    for etf in filtered:
        name = etf.get('etf_name', '')
        code = etf.get('etf', '').split('.')[0]
        reason = etf.get('filter_reason', '已过滤')
        score = etf.get('score', 0)
        lines.append(f"> ❌ {name}({code}) {score:.4f} - {reason}")

    return '\n'.join(lines) if lines else '> 无排名数据'


def build_message(strategy, result, last):
    etfs = result.get('target_etfs', [])
    defense = result.get('defense_mode', False)
    code = etfs[0]['etf'] if etfs else ''
    name = etfs[0].get('etf_name', '') if etfs else ''
    score = etfs[0].get('score', 0) if etfs else 0
    sname = '动量轮动' if strategy == 'momentum' else '最高评分'
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    changed, ctype = False, ''
    if last:
        le, ld = last.get('target_etf', ''), last.get('defense_mode', False)
        if code != le:
            changed = True
            if ld and not defense: ctype = 'from_defense'
            elif not ld and defense: ctype = 'to_defense'
            else: ctype = 'switch'
    else:
        le = ''

    ln = get_etf_name(le) if le else '无'

    # 得分排名表
    ranking = build_ranking_table(result, strategy)

    if changed:
        if ctype == 'to_defense':
            title = f"🚨🛡️ 【{sname}】⚠️ 变动：切换至防御模式！"
            detail = f"**原持仓**: {ln}（{le}）\n**当前建议**: <font color=\"warning\">空仓 / 货币基金ETF</font>\n"
            if result.get('empty_signal'):
                detail += "**原因**: 上证180ETF评分最高，市场偏防御\n"
            else:
                detail += "**原因**: 所有ETF均不满足筛选条件\n"
        elif ctype == 'from_defense':
            title = f"🚨🚀 【{sname}】⚠️ 变动：发现买入信号！"
            detail = (
                f"**原状态**: 防御模式（空仓）\n"
                f"**建议买入**: <font color=\"info\">{name}（{code}）</font>\n"
                f"**综合得分**: {score:.4f}\n"
            )
        else:
            title = f"🚨🔄 【{sname}】⚠️ 变动：持仓需调整！"
            detail = (
                f"**卖出**: <font color=\"warning\">{ln}（{le}）</font>\n"
                f"**买入**: <font color=\"info\">{name}（{code}）</font>\n"
                f"**综合得分**: {score:.4f}\n"
            )
        msg = f"{title}\n\n{detail}\n📊 **今日排名**:\n{ranking}\n\n> 📌 请注意操作！推荐已发生变更\n\n⏰ {now}"
    else:
        if defense:
            status = '🛡️ 防御模式（空仓）'
            hold = '当前建议空仓 / 持有货币基金ETF'
        else:
            status = '📈 持有中'
            hold = f'继续持有 **{name}**（{code}）· 得分 {score:.4f}'
        title = f"✅ 【{sname}】今日无变动"
        detail = f"**状态**: {status}\n**建议**: {hold}\n"
        if last:
            detail += f"**上次变动**: {last.get('timestamp', '未知')}\n"
        msg = f"{title}\n\n{detail}\n📊 **今日排名**:\n{ranking}\n\n> 💤 推荐未变化，无需操作\n\n⏰ {now}"

    return msg, changed, code, defense


def main():
    if not WEBHOOK_URL:
        print("错误: 请设置环境变量 WECHAT_WORK_WEBHOOK")
        sys.exit(1)

    now = datetime.now()
    if now.weekday() >= 5:
        print(f"今天是周{'六' if now.weekday() == 5 else '日'}，跳过推送")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    engines = {
        'momentum': QuantEngine(data_dir=DATA_DIR),
        'topscore': TopScoreEngine(data_dir=DATA_DIR),
    }

    success_count = 0
    for strategy, eng in engines.items():
        print(f"\n{'='*40}\n正在计算 {strategy} 策略...")
        try:
            eng.clear_cache()
            if strategy == 'topscore':
                result = eng.get_today_recommendation()
            else:
                result = eng.get_today_recommendation(use_large_pool=False)

            last = load_last(strategy)
            msg, changed, code, defense = build_message(strategy, result, last)

            tag = "⚠️ 有变动" if changed else "✅ 无变动"
            print(f"[{strategy}] {tag}")

            if send_markdown(msg):
                save_last(strategy, code, defense)
                success_count += 1
        except Exception as e:
            print(f"[{strategy}] 计算出错: {e}")
            import traceback
            traceback.print_exc()
            # 发送错误通知
            sname = '动量轮动' if strategy == 'momentum' else '最高评分'
            err_msg = f"❌ 【{sname}】策略计算失败\n\n**错误**: {str(e)[:200]}\n\n⏰ {now.strftime('%Y-%m-%d %H:%M')}"
            send_markdown(err_msg)

    print(f"\n推送完成: {success_count}/{len(engines)} 个策略")


if __name__ == '__main__':
    main()
