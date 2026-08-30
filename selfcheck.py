#!/usr/bin/env python3
"""行者工作台每日轻量自测 —— 检查计划是否正确/完整、复盘是否已分析。只读，不修改任何数据。"""
import json, os, sqlite3
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))
TODAY = datetime.now(TZ).strftime('%Y-%m-%d')
YESTERDAY = (datetime.now(TZ) - timedelta(days=1)).strftime('%Y-%m-%d')
DIR = os.path.dirname(os.path.abspath(__file__))
LS_DB = os.path.expanduser(
    '~/Library/WebKit/com.xingzhe.dashboard/WebsiteData/Default/'
    '3seobT5AUYd7dAcPCK_0MeLaOvXbQfHIs-MvWXuYyus/3seobT5AUYd7dAcPCK_0MeLaOvXbQfHIs-MvWXuYyus/LocalStorage/localstorage.sqlite3')

CAT_LABEL = {'reading': '读书', 'study': '学习', 'exercise': '运动', 'express': '表达', 'review': '复盘'}


def ls_get(key):
    try:
        con = sqlite3.connect('file:' + LS_DB + '?mode=ro', uri=True)
        cur = con.cursor()
        cur.execute('SELECT value FROM ItemTable WHERE key=?', (key,))
        r = cur.fetchone()
        con.close()
        return json.loads(r[0].decode('utf-16-le')) if r else None
    except Exception:
        return None


def main():
    problems = []
    oks = []

    # 1) 进度游标
    rd_cursor = ls_get('wb_life_reading_cursor')
    ag_cursor = ls_get('wb_life_agent_cursor')
    oks.append('读书游标: %s' % (rd_cursor if rd_cursor is not None else '未初始化(首次打开自动迁移)'))
    oks.append('学习游标: %s' % (ag_cursor if ag_cursor is not None else '未初始化(首次打开自动迁移)'))

    # 2) 今日计划完整性
    plan_daily = ls_get('wb_life_plan_daily') or {}
    today_plan = plan_daily.get(TODAY)
    if not today_plan:
        problems.append('今日(%s)计划未生成 —— 可能 App 还没打开过' % TODAY)
    else:
        evening = today_plan.get('evening', [])
        cats = set(t.get('cat') for t in evening)
        missing = [CAT_LABEL[c] for c in CAT_LABEL if c not in cats]
        if missing:
            problems.append('今日计划缺任务: %s' % '、'.join(missing))
        else:
            oks.append('今日计划五类任务(读书/学习/运动/表达/复盘)完整')

    # 3) 昨天复盘 AI 分析
    try:
        rv = json.load(open(os.path.join(DIR, 'review.json'), encoding='utf-8'))
        ye = rv.get('entries', {}).get(YESTERDAY)
        if ye and ye.get('text'):
            if ye.get('aiSummary') and ye['aiSummary'].get('summary'):
                oks.append('昨天(%s)复盘 AI 分析已生成' % YESTERDAY)
            else:
                problems.append('昨天(%s)复盘写了但 AI 分析未生成，需补跑' % YESTERDAY)
        elif ye:
            oks.append('昨天(%s)复盘未写文字(正常)' % YESTERDAY)
        else:
            oks.append('昨天(%s)无复盘记录' % YESTERDAY)
    except Exception as e:
        problems.append('无法读取 review.json: %s' % e)

    print('=== 行者工作台自测 %s ===' % TODAY)
    for o in oks:
        print('✓ ' + o)
    if problems:
        print('')
        for p in problems:
            print('⚠️ ' + p)
    else:
        print('')
        print('✓ 全部正常')
    return 0 if not problems else 1


if __name__ == '__main__':
    raise SystemExit(main())
