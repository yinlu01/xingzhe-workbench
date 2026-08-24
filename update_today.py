#!/usr/bin/env python3
"""
Auto-update reading_plan.json's todaySchedule based on the actual current date.

- Calculates which week we're in (Week 1 starts Monday Aug 10, 2026)
- Looks up the current phase's weeks_detail for the matching week
- Updates todaySchedule + weeklyProgress to match the real day
- Handles week rollover (when Monday of next week arrives, advance)
- Handles phase rollover (when all weeks in a phase are done, advance to next)
"""
import json
import os
import sys
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PLAN_PATH = os.path.join(SCRIPT_DIR, 'reading_plan.json')

# Week 1 started on Monday, August 10, 2026
WEEK1_START = date(2026, 8, 10)

DAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def get_current_week_number():
    """Calculate current week number (1-based) from start date."""
    today = date.today()
    days_since_start = (today - WEEK1_START).days
    if days_since_start < 0:
        return 1  # Before start, show week 1
    return (days_since_start // 7) + 1


def get_day_of_week():
    """Return Chinese day name for today."""
    today = date.today()
    return DAY_NAMES[today.weekday()]


def update_plan():
    with open(PLAN_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    today = date.today()
    day_of_week = get_day_of_week()
    current_week = get_current_week_number()

    # Find current phase
    current_phase_id = data.get('currentPhase', 1)
    current_phase = None
    for phase in data.get('phases', []):
        if phase['id'] == current_phase_id:
            current_phase = phase
            break

    if not current_phase or not current_phase.get('weeks_detail'):
        print(f"[SKIP] Phase {current_phase_id} has no weeks_detail yet.")
        return False

    weeks_detail = current_phase['weeks_detail']

    # Clamp week to available range
    week_index = min(current_week - 1, len(weeks_detail) - 1)
    if week_index < 0:
        week_index = 0

    week_data = weeks_detail[week_index]
    week_schedule = week_data.get('schedule', {})

    # Get today's schedule
    today_info = week_schedule.get(day_of_week, {})
    if not today_info:
        print(f"[SKIP] No schedule for {day_of_week} in week {week_data.get('week', week_index+1)}")
        return False

    # --- Update todaySchedule ---
    book = today_info.get('book', '')
    chapter = today_info.get('chapter', '')
    point = today_info.get('point', '')

    notes = {
        "休息": "今天是休息日，可以浏览之前笔记或轻松阅读",
        "复习+笔记整理": "复习本周内容，用费曼学习法整理笔记到 Obsidian",
    }
    note = notes.get(book, "阅读20-30页，用费曼学习法复述核心内容")

    data['todaySchedule'] = {
        "week": week_data.get('week', current_week),
        "dayOfWeek": day_of_week,
        "book": book,
        "chapter": chapter,
        "point": point,
        "note": note,
    }

    # Update currentWeek in root
    data['currentWeek'] = week_data.get('week', current_week)

    # --- Update weeklyProgress ---
    weekly_progress = []
    for day_name in DAY_NAMES:
        day_info = week_schedule.get(day_name, {})
        prog_book = day_info.get('book', '')
        if day_info.get('chapter'):
            prog_book += ' ' + day_info['chapter']
        weekly_progress.append({
            "day": day_name,
            "book": prog_book,
            "done": False,
        })
    data['weeklyProgress'] = weekly_progress

    # --- Write back ---
    with open(PLAN_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, ensure_ascii=False, indent=2, fp=f)

    print(f"[OK] Updated reading_plan.json:")
    print(f"  Week:     {data['currentWeek']}")
    print(f"  Day:      {day_of_week}")
    print(f"  Book:     {book}")
    print(f"  Chapter:  {chapter}")
    print(f"  Point:    {point}")
    return True


if __name__ == '__main__':
    ok = update_plan()
    sys.exit(0 if ok else 1)
