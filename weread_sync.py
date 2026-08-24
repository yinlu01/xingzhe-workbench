#!/usr/bin/env python3
"""微信读书数据同步脚本
通过微信读书 Agent API 拉取阅读数据，输出可用于生活台导入的 JSON。
使用方法:
  python3 weread_sync.py          # 输出 JSON 到 stdout
  python3 weread_sync.py --save   # 保存到 weread_data.json
"""
import json, urllib.request, os, sys
from datetime import datetime, timezone, timedelta

API_KEY = os.environ.get("WEREAD_API_KEY", "")
GATEWAY = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.4"
TZ = timezone(timedelta(hours=8))

if not API_KEY:
    # Try to read from shell config
    for path in [os.path.expanduser("~/.zshrc"), os.path.expanduser("~/.bashrc")]:
        try:
            with open(path) as f:
                for line in f:
                    if "WEREAD_API_KEY" in line:
                        # Extract value from export/quotes
                        API_KEY = line.split("=", 1)[-1].strip().strip('"').strip("'")
                        break
        except FileNotFoundError:
            pass
    if not API_KEY:
        print("❌ 未找到 WEREAD_API_KEY，请设置环境变量", file=sys.stderr)
        print("   export WEREAD_API_KEY=wrk-xxxx", file=sys.stderr)
        sys.exit(1)


def call_api(api_name, **params):
    """调用微信读书 Agent API"""
    body = {"api_name": api_name, "skill_version": SKILL_VERSION, **params}
    req = urllib.request.Request(
        GATEWAY,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ⚠️ API 调用失败 [{api_name}]: {e}", file=sys.stderr)
        return {}


def fmt_seconds(s):
    if s < 60:
        return f"{s}秒"
    h = s // 3600
    m = (s % 3600) // 60
    if h > 0:
        return f"{h}小时{m}分钟"
    return f"{m}分钟"


def ts_to_date(ts):
    if not ts or ts == 0:
        return ""
    return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d")


def main():
    print("🔄 正在同步微信读书数据...", file=sys.stderr)

    # 1. 书架
    shelf = call_api("/shelf/sync")
    books = shelf.get("books", [])
    albums = shelf.get("albums", [])
    mp = shelf.get("mp")

    # 2. 阅读统计
    overall = call_api("/readdata/detail", mode="overall")
    monthly = call_api("/readdata/detail", mode="monthly")
    weekly = call_api("/readdata/detail", mode="weekly")

    # 3. 笔记本（取第一页）
    notebooks = call_api("/user/notebooks", count=50)

    # --- 构建结果 ---
    result = {"syncedAt": datetime.now(TZ).isoformat()}

    # 书架概览
    result["shelf"] = {
        "totalItems": len(books) + len(albums) + (1 if mp else 0),
        "bookCount": len(books),
        "albumCount": len(albums),
    }

    # 累计统计
    result["overall"] = {
        "totalReadTime": overall.get("totalReadTime", 0),
        "totalReadTimeFmt": fmt_seconds(overall.get("totalReadTime", 0)),
        "readDays": overall.get("readDays", 0),
        "readStat": overall.get("readStat", []),
    }
    # Top 5 书
    result["overall"]["topBooks"] = []
    for item in overall.get("readLongest", [])[:5]:
        bk = item.get("book", {})
        alb = item.get("albumInfo", {})
        result["overall"]["topBooks"].append(
            {
                "title": bk.get("title") if bk else alb.get("name", ""),
                "author": bk.get("author") if bk else alb.get("authorName", ""),
                "readTimeFmt": fmt_seconds(item.get("readTime", 0)),
            }
        )
    # 偏好
    result["overall"]["preferCategory"] = [
        {"title": c["categoryTitle"], "readingCount": c["readingCount"], "readingTimeFmt": fmt_seconds(c["readingTime"])}
        for c in overall.get("preferCategory", [])[:5]
    ]
    result["overall"]["preferTimeWord"] = overall.get("preferTimeWord", "")
    result["overall"]["preferAuthor"] = overall.get("preferAuthor", [])[:3]

    # 本月
    result["monthly"] = {
        "totalReadTime": monthly.get("totalReadTime", 0),
        "totalReadTimeFmt": fmt_seconds(monthly.get("totalReadTime", 0)),
        "readDays": monthly.get("readDays", 0),
        "compare": monthly.get("compare"),
        "readStat": monthly.get("readStat", []),
    }

    # 本周
    result["weekly"] = {
        "totalReadTime": weekly.get("totalReadTime", 0),
        "totalReadTimeFmt": fmt_seconds(weekly.get("totalReadTime", 0)),
        "readDays": weekly.get("readDays", 0),
    }

    # 在读书目：按最近阅读时间取书架前 10 本未读完的书，逐本查真实阅读进度
    notes_by_title = {}
    for bk in notebooks.get("books", []):
        t = bk.get("book", {}).get("title", "")
        notes_by_title[t] = bk.get("reviewCount", 0) + bk.get("noteCount", 0) + bk.get("bookmarkCount", 0)
    nb_progress_by_title = {}
    for bk in notebooks.get("books", []):
        nb_progress_by_title[bk.get("book", {}).get("title", "")] = bk.get("readingProgress", 0)

    candidates = [b for b in books if b.get("finishReading") != 1 and b.get("readUpdateTime")]
    candidates.sort(key=lambda x: x.get("readUpdateTime", 0) or 0, reverse=True)
    # 并发查询真实阅读进度
    from concurrent.futures import ThreadPoolExecutor
    top = candidates[:10]
    with ThreadPoolExecutor(max_workers=10) as pool:
        prog_results = list(pool.map(
            lambda b: call_api("/book/getprogress", bookId=b.get("bookId", "")).get("book", {}).get("progress"),
            top,
        ))
    progress_map = {}
    for b, prog in zip(top, prog_results):
        progress_map[b.get("title", "")] = prog if isinstance(prog, int) else None
    in_progress = []
    for b in top:
        prog = progress_map.get(b.get("title", ""))
        if prog is None:
            prog = nb_progress_by_title.get(b["title"], 0)
        if isinstance(prog, int) and 0 < prog < 100:
            in_progress.append(
                {
                    "title": b.get("title", ""),
                    "author": b.get("author", ""),
                    "readingProgress": prog,
                    "lastRead": ts_to_date(b.get("readUpdateTime")),
                    "deepLink": b.get("deepLink", ""),
                    "totalNotes": notes_by_title.get(b.get("title", ""), 0),
                }
            )
        if len(in_progress) >= 8:
            break
    result["inProgressBooks"] = in_progress

    # Top 笔记书
    nb_list = []
    for bk in notebooks.get("books", []):
        nb_list.append(
            {
                "title": bk.get("book", {}).get("title", ""),
                "author": bk.get("book", {}).get("author", ""),
                "readingProgress": bk.get("readingProgress", 0),
                "noteCount": bk.get("noteCount", 0),
                "reviewCount": bk.get("reviewCount", 0),
                "totalNotes": bk.get("reviewCount", 0) + bk.get("noteCount", 0) + bk.get("bookmarkCount", 0),
            }
        )
    nb_list.sort(key=lambda x: x["totalNotes"], reverse=True)
    result["topNoteBooks"] = nb_list[:8]
    result["totalNotes"] = notebooks.get("totalNoteCount", 0)

    # 最近阅读
    recent = [b for b in books if b.get("finishReading") != 1 and b.get("readUpdateTime")]
    recent.sort(key=lambda x: x.get("readUpdateTime", 0) or 0, reverse=True)
    result["recentBooks"] = [
        {
            "title": b["title"],
            "author": b["author"],
            "lastRead": ts_to_date(b.get("readUpdateTime")),
            "readingProgress": progress_map.get(b["title"]) or 0,
            "deepLink": b.get("deepLink", ""),
        }
        for b in recent[:6]
    ]

    # 输出
    output = json.dumps(result, ensure_ascii=False, indent=2)

    if "--save" in sys.argv or "-s" in sys.argv:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(script_dir, "weread_data.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"✅ 已保存到 {path}", file=sys.stderr)
    else:
        print(output)
        print(
            f"\n✅ 同步完成 | 总计 {result['overall']['totalReadTimeFmt']} | 本月 {result['monthly']['totalReadTimeFmt']}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
