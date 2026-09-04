#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行者工作台 · 进化存储层（SQLite）

定位：与浏览器 localStorage **共存**的结构化分析库。
- localStorage 仍是主存储，前端行为完全不变（本模块只读不写前端数据）
- 本库只做一件事：把行为事件结构化落盘，供进化模块 / 复盘分析做聚合查询
- Python 标准库 sqlite3，零外部依赖

设计原则：事件溯源（event sourcing）
  events        事实表：只追加，永不修改。任何新指标都可从它重算。
  daily_metrics 物化视图：按天聚合的缓存，供快速查询。

用法：
  python3 evolution_store.py init      初始化表结构
  python3 evolution_store.py backfill  从 review.json 回填历史数据（幂等）
  python3 evolution_store.py stats     查看数据概况
  python3 evolution_store.py query <sql>   执行自定义查询
"""

import json
import os
import sqlite3
import sys
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DIR, 'workbench.db')
REVIEW_PATH = os.path.join(DIR, 'review.json')

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    date       TEXT NOT NULL,
    type       TEXT NOT NULL,
    payload    TEXT,
    source     TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type, date);

CREATE TABLE IF NOT EXISTS daily_metrics (
    date             TEXT PRIMARY KEY,
    reading_done     INTEGER DEFAULT 0,
    reading_pct      REAL,
    reading_book     TEXT,
    agent_done       INTEGER DEFAULT 0,
    study_done       INTEGER DEFAULT 0,
    plan_done        INTEGER DEFAULT 0,
    exercise_done    INTEGER DEFAULT 0,
    exercise_minutes INTEGER DEFAULT 0,
    exercise_types   TEXT,
    skill_count      INTEGER DEFAULT 0,
    task_total       INTEGER,
    task_done        INTEGER,
    task_overdue     INTEGER,
    review_written   INTEGER DEFAULT 0,
    energy           INTEGER,
    prev_suggestion_done INTEGER,
    review_chars     INTEGER
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化表结构（幂等，可重复执行）"""
    conn = connect()
    conn.executescript(SCHEMA)
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
                 ('schema_version', str(SCHEMA_VERSION)))
    conn.commit()
    conn.close()
    print(f'[init] 数据库就绪：{DB_PATH}')


def record_event(date, type_, payload=None, source='agent', ts=None):
    """记录一条事件。date='YYYY-MM-DD'，payload 为可序列化 dict"""
    conn = connect()
    now = datetime.now().isoformat(timespec='seconds')
    conn.execute(
        "INSERT INTO events(ts,date,type,payload,source,created_at) VALUES(?,?,?,?,?,?)",
        (ts or now, date, type_, json.dumps(payload or {}, ensure_ascii=False), source, now)
    )
    conn.commit()
    conn.close()


def apply_event(date, type_, payload=None, source='pwa', ts=None):
    """
    双写通道的落库入口：追加一条事件，并增量更新当天 daily_metrics。

    与 record_event 的区别：本函数会同步维护聚合视图，供 06:30 建议生成直接查询。
    字段名全部来自本函数内部的固定映射，不接受外部传入，无注入风险。

    异常一律内部消化并返回 False —— 分析库故障绝不影响打卡主流程。
    """
    payload = payload or {}
    conn = connect()
    now = datetime.now().isoformat(timespec='seconds')
    try:
        # 当天行不存在则先占位（兼容未开启 UPSERT 的旧 SQLite）
        conn.execute("INSERT OR IGNORE INTO daily_metrics(date) VALUES(?)", (date,))

        updates = {}   # 直接赋值
        bumps = {}     # 累加

        if type_ == 'checkin.reading':
            updates['reading_done'] = 1
            if payload.get('pct') is not None:
                updates['reading_pct'] = payload['pct']
            if payload.get('book'):
                updates['reading_book'] = payload['book']
        elif type_ == 'checkin.agent':
            updates['agent_done'] = 1
        elif type_ == 'checkin.study':
            updates['study_done'] = 1
        elif type_ == 'checkin.plan':
            updates['plan_done'] = 1
        elif type_ == 'exercise':
            updates['exercise_done'] = 1
            bumps['exercise_minutes'] = payload.get('minutes') or 0
            if payload.get('types'):
                updates['exercise_types'] = json.dumps(payload['types'], ensure_ascii=False)
        elif type_ == 'skill.practice':
            bumps['skill_count'] = payload.get('count') or 1
        elif type_ == 'review.saved':
            updates['review_written'] = 1
            if payload.get('energy') is not None:
                updates['energy'] = payload['energy']
            if payload.get('chars') is not None:
                updates['review_chars'] = payload['chars']
            if payload.get('prevSuggestionDone') is not None:
                updates['prev_suggestion_done'] = 1 if payload['prevSuggestionDone'] else 0
        elif type_ == 'task.done':
            bumps['task_done'] = 1
        elif type_ == 'task.overdue':
            updates['task_overdue'] = payload.get('count')

        conn.execute(
            "INSERT INTO events(ts,date,type,payload,source,created_at) VALUES(?,?,?,?,?,?)",
            (ts or now, date, type_, json.dumps(payload, ensure_ascii=False), source, now)
        )
        if updates:
            sets = ','.join(f'{k}=?' for k in updates)
            conn.execute(f"UPDATE daily_metrics SET {sets} WHERE date=?",
                         (*updates.values(), date))
        if bumps:
            sets = ','.join(f'{k}=COALESCE({k},0)+?' for k in bumps)
            conn.execute(f"UPDATE daily_metrics SET {sets} WHERE date=?",
                         (*bumps.values(), date))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f'[apply_event] 落库失败（已忽略，不影响打卡）: {e}')
        return False
    finally:
        conn.close()


def backfill_from_review():
    """
    从 review.json 回填历史数据（幂等，重复执行不会产生重复行）。

    数据源：每条复盘里的 checkSnapshot（打卡快照）+ energy + prevSuggestionDone。
    这是目前唯一能拿到的历史行为数据——localStorage 里的细粒度打卡记录读不到。
    """
    if not os.path.exists(REVIEW_PATH):
        print('[backfill] review.json 不存在，跳过')
        return 0

    with open(REVIEW_PATH, encoding='utf-8') as f:
        data = json.load(f)
    entries = data.get('entries', {})

    conn = connect()
    n_new = 0
    for date in sorted(entries):
        e = entries[date]
        cs = e.get('checkSnapshot') or {}
        reading = cs.get('reading') or {}
        exercises = cs.get('exercise') or []

        # 已有则跳过（幂等）
        exist = conn.execute("SELECT 1 FROM daily_metrics WHERE date=?", (date,)).fetchone()
        if exist:
            continue

        saved_at = e.get('savedAt') or (date + 'T23:59:00')
        text = e.get('text') or ''

        conn.execute("""
            INSERT OR REPLACE INTO daily_metrics
            (date, reading_done, reading_pct, reading_book, agent_done, study_done, plan_done,
             exercise_done, exercise_minutes, exercise_types,
             review_written, energy, prev_suggestion_done, review_chars)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            date,
            1 if cs.get('plan') else 0,
            reading.get('pct'),
            reading.get('book'),
            1 if cs.get('agent') else 0,
            1 if cs.get('study') else 0,
            1 if cs.get('plan') else 0,
            1 if len(exercises) > 0 else 0,
            0,
            json.dumps(exercises, ensure_ascii=False) if exercises else None,
            1 if text.strip() else 0,
            e.get('energy'),
            (1 if e.get('prevSuggestionDone') is True else
             0 if e.get('prevSuggestionDone') is False else None),
            len(text),
        ))

        # 同步写入事件流，保留溯源能力
        conn.execute(
            "INSERT INTO events(ts,date,type,payload,source,created_at) VALUES(?,?,?,?,?,?)",
            (saved_at, date, 'review.saved',
             json.dumps({'energy': e.get('energy'), 'hasText': bool(text.strip())},
                        ensure_ascii=False),
             'backfill', datetime.now().isoformat(timespec='seconds'))
        )
        if exercises:
            conn.execute(
                "INSERT INTO events(ts,date,type,payload,source,created_at) VALUES(?,?,?,?,?,?)",
                (saved_at, date, 'exercise',
                 json.dumps({'types': exercises}, ensure_ascii=False),
                 'backfill', datetime.now().isoformat(timespec='seconds'))
            )
        n_new += 1

    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
                 ('backfilled_at', datetime.now().isoformat(timespec='seconds')))
    conn.commit()
    conn.close()
    print(f'[backfill] 新增 {n_new} 天记录（已有记录自动跳过）')
    return n_new


def stats():
    conn = connect()
    rows = conn.execute("SELECT * FROM daily_metrics ORDER BY date").fetchall()
    total = len(rows)
    if not total:
        print('[stats] 暂无数据，先跑 backfill')
        return
    print(f'\n共 {total} 天记录：{rows[0]["date"]} → {rows[-1]["date"]}\n')
    print(f'{"日期":<12}{"能量":<5}{"阅读%":<7}{"agent":<7}{"运动":<6}{"复盘":<6}')
    print('-' * 46)
    for r in rows:
        pct = r['reading_pct'] if r['reading_pct'] is not None else '-'
        print(f'{r["date"]:<12}{str(r["energy"] or "-"):<5}{str(pct):<7}'
              f'{"是" if r["agent_done"] else "·":<7}'
              f'{"是" if r["exercise_done"] else "·":<6}'
              f'{"是" if r["review_written"] else "·":<6}')
    conn.close()


def query(sql):
    conn = connect()
    try:
        rows = conn.execute(sql).fetchall()
        if not rows:
            print('(无结果)')
            return
        cols = rows[0].keys()
        widths = [max(len(str(c)), max((len(str(r[c])) for r in rows), default=0)) + 2
                  for c in cols]
        print(''.join(str(c).ljust(w) for c, w in zip(cols, widths)))
        print('-' * sum(widths))
        for r in rows:
            print(''.join(str(r[c]).ljust(w) for c, w in zip(cols, widths)))
    except sqlite3.Error as e:
        print(f'[SQL 错误] {e}')
    finally:
        conn.close()


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'stats'
    if cmd == 'init':
        init_db()
    elif cmd == 'backfill':
        init_db()
        backfill_from_review()
    elif cmd == 'stats':
        stats()
    elif cmd == 'query':
        if len(sys.argv) < 3:
            print('用法: python3 evolution_store.py query "<SQL>"')
        else:
            query(sys.argv[2])
    else:
        print(__doc__)
