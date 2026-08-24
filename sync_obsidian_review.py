#!/usr/bin/env python3
"""同步每日复盘到 Obsidian vault，按 年/月/日期 归档。

用法:
  python3 sync_obsidian_review.py [date]         # 同步指定日期(默认今天)到 每日复盘/YYYY/MM/YYYY-MM-DD.md
  python3 sync_obsidian_review.py --all          # 同步全部已有条目
  python3 sync_obsidian_review.py --week WEEK    # 同步周报到 每日复盘/周报/WEEK.md (如 2026-W35)

由 server.py 保存复盘时调用，也由「每日复盘分析·23:00」定时任务在生成 AI 分析后调用。
md 内容与 review.json 始终保持一致：有 AI 摘要则含 AI 分析，无则只含用户复盘。
"""

import json
import os
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
REVIEW_FILE = os.path.join(DIR, 'review.json')
OBSIDIAN_ROOT = '/Users/yinlu01/Obsidian'
FOLDER = '每日复盘'


def load_review():
    try:
        with open(REVIEW_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'entries': {}, 'weekly': {}, 'insights': []}


def md_path(date):
    y, m, _ = date.split('-')
    return os.path.join(OBSIDIAN_ROOT, FOLDER, y, m, date + '.md')


def snapshot_lines(snapshot):
    """把当日打卡快照渲染成 md 列表。"""
    s = snapshot or {}
    lines = []
    if s.get('study'):
        lines.append('- 学习打卡 ✅')
    if s.get('agent'):
        lines.append('- Agent 学习 ✅')
    if s.get('plan'):
        lines.append('- 计划待办 ✅')
    if s.get('planType'):
        pt = {'reading': '读书计划', 'review': '复盘', 'other': '其他'}.get(s['planType'], s['planType'])
        lines.append(f"- 今日计划类型：{pt}")
    ex = s.get('exercise') or []
    for e in ex:
        extra = f"，吊杠 {e['hang']} 秒" if e.get('hang') else ''
        lines.append(f"- 运动：{e.get('tp', '')}（{e.get('dr', '')} 分钟{extra}）")
    rd = s.get('reading')
    if rd:
        if rd.get('pct'):
            lines.append(f"- 读书：《{rd.get('book')}》已读 {rd['pct']}")
        elif rd.get('cur') is not None:
            lines.append(f"- 读书：《{rd.get('book')}》{rd.get('cur')}/{rd.get('total')} 页")
    done = s.get('prevSuggestionDone')
    if done == 'yes':
        lines.append('- 昨日建议 ✅ 已执行')
    elif done == 'no':
        lines.append('- 昨日建议 ❌ 未执行')
    return lines


def render_md(date, entry):
    text = (entry.get('text') or '').strip()
    energy = entry.get('energy')
    ai = entry.get('aiSummary')

    parts = []
    parts.append('---')
    parts.append(f"日期: {date}")
    if energy:
        parts.append(f"能量: {energy}/5")
    parts.append('标签: [复盘]')
    parts.append('---')
    parts.append('')
    parts.append(f"# {date} 复盘")
    parts.append('')

    parts.append('## ✍️ 今日复盘')
    parts.append('')
    if text:
        parts.append(text)
    else:
        parts.append('_（今天没有写复盘）_')
    parts.append('')

    slines = snapshot_lines(entry.get('checkSnapshot'))
    if slines:
        parts.append('## 📊 今日数据')
        parts.append('')
        parts.extend(slines)
        parts.append('')

    if ai:
        parts.append('## 🤖 AI 分析')
        parts.append('')
        if ai.get('summary'):
            parts.append(f"**总览**：{ai['summary']}")
            parts.append('')
        for h in ai.get('highlights') or []:
            parts.append(f"- ✨ {h}")
        parts.append('')
        parts.append(f"**卡点**：{ai.get('problem') or '无明显卡点'}")
        parts.append('')
        parts.append(f"**明日建议**：{ai.get('suggestion') or ''}")
        parts.append('')

    parts.append('---')
    parts.append('*由行者工作台自动生成*')
    parts.append('')
    return '\n'.join(parts)


def sync_day(date):
    rv = load_review()
    entry = rv.get('entries', {}).get(date)
    if not entry:
        print(f'  [OBS] {date} 无条目，跳过')
        return False
    path = md_path(date)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(render_md(date, entry))
    print(f'  [OBS] 已写入 {path}')
    return True


def sync_week(week):
    rv = load_review()
    w = rv.get('weekly', {}).get(week)
    if not w:
        print(f'  [OBS] 周报 {week} 不存在，跳过')
        return False
    path = os.path.join(OBSIDIAN_ROOT, FOLDER, '周报', week + '.md')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        '---',
        f"周次: {week}",
        '标签: [复盘, 周报]',
        '---',
        '',
        f"# {w.get('title', week)}",
        '',
    ]
    for k, v in [('目标', 'goal'), ('实际完成', 'result'), ('偏差分析', 'analysis'), ('规律提炼', 'insight')]:
        if w.get(v):
            lines += [f"## {k}", '', w[v], '']
    lines.append('---')
    lines.append('*由行者工作台自动生成*')
    lines.append('')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'  [OBS] 周报已写入 {path}')
    return True


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--all' in args:
        rv = load_review()
        dates = sorted(rv.get('entries', {}))
        for d in dates:
            sync_day(d)
        for wk in rv.get('weekly', {}):
            sync_week(wk)
    elif args and args[0].startswith('--week'):
        week = args[1] if len(args) > 1 else None
        if not week:
            week = subprocess.check_output(['date', '+%G-W%V']).decode().strip()
        sync_week(week)
    else:
        date = args[0] if args else subprocess.check_output(['date', '+%F']).decode().strip()
        sync_day(date)
