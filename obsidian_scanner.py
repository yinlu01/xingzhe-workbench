#!/usr/bin/env python3
"""
Obsidian 知识库扫描器
扫描 Obsidian vault，检测内容更新、读书计划执行情况、日记一致性
输出结构化报告供自动化使用
"""
import os, re, json, time, sys
from datetime import datetime, timedelta

VAULT = '/Users/yinlu01/Obsidian/'
STATE_FILE = '/Users/yinlu01/WorkBuddy/2026-08-06-13-47-58/.workbuddy/memory/obsidian_scan_state.json'
REPORT_FILE = '/Users/yinlu01/WorkBuddy/2026-08-06-13-47-58/obsidian_report.json'

def scan_vault():
    """Scan all markdown files in the vault"""
    md_files = []
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith('.md'):
                fp = os.path.join(root, f)
                try:
                    mtime = os.path.getmtime(fp)
                    size = os.path.getsize(fp)
                    rel = fp.replace(VAULT, '')
                    md_files.append({
                        'path': rel,
                        'mtime': mtime,
                        'size': size,
                        'date': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d'),
                        'time': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                    })
                except:
                    pass
    md_files.sort(key=lambda x: -x['mtime'])
    return md_files

def scan_reading_plan():
    """Parse reading plan progress from the plan file"""
    plan_path = VAULT + '职业规划/行者创业系统读书计划-每日1小时版.md'
    if not os.path.exists(plan_path):
        return None
    with open(plan_path, 'r') as f:
        content = f.read()
    
    total = len(re.findall(r'\| \d+ \|', content))
    done = len(re.findall(r'✅', content))
    undone = len(re.findall(r'⬜', content))
    
    done_books = re.findall(r'\| (\d+) \| (.*?) \| (.*?) \| ✅', content)
    done_list = [{'seq': s, 'title': t.strip(), 'author': a.strip()} for s, t, a in done_books]
    
    # Parse phases
    phases = re.findall(r'### 第([一二三四五六七八])阶段：(.*?)（', content)
    phase_info = {}
    for num, name in phases:
        phase_info[f'第{num}阶段'] = name.strip()
    
    return {
        'total_books': total,
        'done_books': done,
        'undone_books': undone,
        'completion_rate': round(done / total * 100, 1) if total > 0 else 0,
        'done_list': done_list,
        'phases': phase_info
    }

def scan_daily_notes():
    """Check daily note consistency"""
    daily_dir = VAULT + '日程管理/2026/'
    daily_notes = set()
    if os.path.exists(daily_dir):
        for root, dirs, files in os.walk(daily_dir):
            for f in files:
                if f.endswith('.md') and '模板' not in f:
                    daily_notes.add(f.replace('.md', ''))
    
    today = datetime.now()
    streak = 0
    missing_recent = []
    for i in range(1, 15):
        d = today - timedelta(days=i)
        dstr = d.strftime('%Y-%m-%d')
        if dstr in daily_notes:
            streak += 1
        else:
            missing_recent.append(dstr)
    
    has_today = today.strftime('%Y-%m-%d') in daily_notes
    
    return {
        'total_notes': len(daily_notes),
        'recent_14d_count': streak,
        'missing_recent': missing_recent[:5],
        'has_today': has_today,
        'latest': sorted(daily_notes, reverse=True)[:5] if daily_notes else []
    }

def scan_content_distribution(md_files):
    """Count files per top-level folder"""
    counts = {}
    for f in md_files:
        top = f['path'].split('/')[0] if '/' in f['path'] else '(root)'
        counts[top] = counts.get(top, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: -x[1])[:10])

def scan_activity(md_files, days=30):
    """Daily activity for the last N days"""
    now = time.time()
    activity = []
    for d in range(days, 0, -1):
        start = now - d * 86400
        end = now - (d - 1) * 86400
        count = sum(1 for f in md_files if start <= f['mtime'] < end)
        dt = datetime.fromtimestamp(start).strftime('%Y-%m-%d')
        activity.append({'date': dt, 'count': count})
    return activity

def scan_special_dirs():
    """Scan special directories for recent updates"""
    dirs = {
        'input_reports': VAULT + '输入沉淀/_待review/',
        'ai_hotspots': VAULT + 'AI技术/每日热点追踪/',
        'clippings': VAULT + 'Clippings/',
        'mba': VAULT + '清华MBA学习/',
    }
    result = {}
    for name, path in dirs.items():
        files = []
        if os.path.exists(path):
            for f in os.listdir(path):
                if f.endswith('.md'):
                    fp = os.path.join(path, f)
                    mt = os.path.getmtime(fp)
                    files.append({
                        'name': f,
                        'time': datetime.fromtimestamp(mt).strftime('%Y-%m-%d %H:%M'),
                        'mtime': mt
                    })
            files.sort(key=lambda x: -x['mtime'])
        result[name] = {
            'count': len(files),
            'latest': files[:3]
        }
    return result

def detect_new_files(md_files, prev_state):
    """Detect files added since last scan"""
    prev_paths = set()
    if prev_state and 'file_paths' in prev_state:
        prev_paths = set(prev_state['file_paths'])
    
    current_paths = {f['path'] for f in md_files}
    new_files = current_paths - prev_paths
    removed = prev_paths - current_paths
    
    new_file_details = [f for f in md_files if f['path'] in new_files]
    return list(new_files), list(removed), new_file_details[:10]

def load_state():
    """Load previous scan state"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return None

def save_state(md_files):
    """Save current scan state"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    state = {
        'last_scan': datetime.now().isoformat(),
        'file_count': len(md_files),
        'file_paths': [f['path'] for f in md_files]
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False)

def generate_report():
    """Generate comprehensive report"""
    prev_state = load_state()
    md_files = scan_vault()
    
    new_files, removed_files, new_details = detect_new_files(md_files, prev_state)
    
    report = {
        'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'vault_path': VAULT,
        'total_files': len(md_files),
        'new_since_last': len(new_files),
        'removed_since_last': len(removed_files),
        'new_files': new_details,
        'reading_plan': scan_reading_plan(),
        'daily_notes': scan_daily_notes(),
        'content_distribution': scan_content_distribution(md_files),
        'activity_30d': scan_activity(md_files),
        'special_dirs': scan_special_dirs(),
        'recent_modified': [{
            'path': f['path'],
            'time': f['time'],
            'date': f['date']
        } for f in md_files[:15]]
    }
    
    save_state(md_files)
    
    # Save report to file
    with open(REPORT_FILE, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    return report

def format_report_text(report):
    """Format report as readable text for automation output"""
    lines = []
    lines.append(f"=== Obsidian 知识库扫描报告 ===")
    lines.append(f"扫描时间: {report['scan_time']}")
    lines.append(f"总笔记数: {report['total_files']}")
    
    if report['new_since_last'] > 0:
        lines.append(f"\n[新增] 自上次扫描以来新增 {report['new_since_last']} 个文件:")
        for f in report['new_files'][:5]:
            lines.append(f"  + {f['time']} {f['path']}")
    else:
        lines.append("\n[新增] 无新文件")
    
    rp = report['reading_plan']
    if rp:
        lines.append(f"\n[读书计划] {rp['done_books']}/{rp['total_books']} 已完成 ({rp['completion_rate']}%)")
        if rp['done_list']:
            lines.append("  已完成书目:")
            for b in rp['done_list']:
                lines.append(f"    ✅ 《{b['title']}》- {b['author']}")
    
    dn = report['daily_notes']
    lines.append(f"\n[日记一致性] 最近14天: {dn['recent_14d_count']}/14 天有记录")
    if dn['missing_recent']:
        lines.append(f"  缺失日期: {', '.join(dn['missing_recent'][:3])}")
    if not dn['has_today']:
        lines.append("  ⚠️ 今天还没写日记")
    
    # Activity summary
    active_days = sum(1 for a in report['activity_30d'] if a['count'] > 0)
    total_activity = sum(a['count'] for a in report['activity_30d'])
    lines.append(f"\n[活跃度] 最近30天: {active_days}/30 天有更新, 共 {total_activity} 次修改")
    
    # Recent modifications
    lines.append(f"\n[最近修改] Top 5:")
    for f in report['recent_modified'][:5]:
        lines.append(f"  {f['time']} {f['path']}")
    
    # Alerts
    alerts = []
    if rp and rp['completion_rate'] < 5:
        alerts.append(f"读书计划执行率仅 {rp['completion_rate']}%，远低于目标")
    if dn['recent_14d_count'] < 7:
        alerts.append(f"日记一致性偏低，14天仅 {dn['recent_14d_count']} 天有记录")
    if not dn['has_today']:
        alerts.append("今天还没有写日记")
    
    if alerts:
        lines.append(f"\n[提醒] {len(alerts)} 项需要关注:")
        for a in alerts:
            lines.append(f"  ⚠️ {a}")
    
    return '\n'.join(lines)

if __name__ == '__main__':
    report = generate_report()
    print(format_report_text(report))
