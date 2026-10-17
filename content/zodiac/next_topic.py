#!/usr/bin/env python3
"""
选题轮换系统，分两条独立的线：

1. 常年型内容（性格解析、爱情配对、事业财运、健康、天文科普、上升/月亮星座、同星座名人）
   —— 写过一次就能长期用，逻辑是"挑一个还没写过 / 写过最久的组合"。
2. 时效型内容（今日运势、本周运势、本月运势）
   —— 每天/每周/每月都要重新写，逻辑是"挑一个这个周期内还没更新过的星座"，
      写过一次之后，在同一个周期内不会重复被建议。

topics.csv      主题池：星座 x 维度 的所有组合，记录每个组合被使用过几次、最近一次使用日期（真实日期，不是周期标签）。
content_calendar.csv  实际发布记录：每次生成一篇文章就追加一行。

用法：
    python3 next_topic.py                # 常年型选题：选出下一个该写的主题
    python3 next_topic.py --list N       # 预览接下来 N 个常年型选题（不标记使用）
    python3 next_topic.py daily          # 时效型：今日运势，挑一个今天还没更新的星座
    python3 next_topic.py weekly         # 时效型：本周运势，挑一个本周还没更新的星座
    python3 next_topic.py monthly        # 时效型：本月运势，挑一个本月还没更新的星座
"""
import csv
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).parent
TOPICS_CSV = ROOT / "topics.csv"
CALENDAR_CSV = ROOT / "content_calendar.csv"

SIGNS = ["白羊座", "金牛座", "双子座", "巨蟹座", "狮子座", "处女座",
         "天秤座", "天蝎座", "射手座", "摩羯座", "水瓶座", "双鱼座"]

EVERGREEN_DIMENSIONS = [
    "性格深度解析", "爱情配对", "事业财运", "健康与生活方式",
    "天文科普(神话与观星)", "上升/月亮星座", "同星座名人",
]

# 维度名 -> 更新周期
RECURRING_DIMENSIONS = {
    "今日运势": "daily",
    "本周运势": "weekly",
    "本月运势": "monthly",
}

ALL_DIMENSIONS = EVERGREEN_DIMENSIONS + list(RECURRING_DIMENSIONS)


def ensure_topics_csv():
    if TOPICS_CSV.exists():
        return
    with TOPICS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sign", "dimension", "times_used", "last_used"])
        for dim in ALL_DIMENSIONS:
            for sign in SIGNS:
                w.writerow([sign, dim, 0, ""])


def ensure_calendar_csv():
    if CALENDAR_CSV.exists():
        return
    with CALENDAR_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "sign", "dimension", "title", "filename", "status"])


def load_topics():
    with TOPICS_CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_topics(rows):
    with TOPICS_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sign", "dimension", "times_used", "last_used"])
        w.writeheader()
        w.writerows(rows)


def append_calendar(row):
    with CALENDAR_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(row)


def period_key(d, cadence):
    if cadence == "daily":
        return d.isoformat()
    if cadence == "weekly":
        y, w, _ = d.isocalendar()
        return f"{y}-W{w:02d}"
    if cadence == "monthly":
        return d.strftime("%Y-%m")
    raise ValueError(cadence)


def mark_used(rows, sign, dimension, today):
    for r in rows:
        if r["sign"] == sign and r["dimension"] == dimension:
            r["times_used"] = str(int(r["times_used"]) + 1)
            r["last_used"] = today.isoformat()
            break


# ---- 常年型：挑还没写过 / 写过最久的组合 ----

def pick_evergreen(rows, exclude_keys=set()):
    candidates = [
        r for r in rows
        if r["dimension"] in EVERGREEN_DIMENSIONS and (r["sign"], r["dimension"]) not in exclude_keys
    ]
    candidates.sort(key=lambda r: (int(r["times_used"]), r["last_used"] or ""))
    return candidates[0]


def cmd_evergreen_list(rows, n):
    exclude = set()
    for i in range(n):
        pick = pick_evergreen(rows, exclude)
        exclude.add((pick["sign"], pick["dimension"]))
        print(f"{i + 1}. {pick['sign']} - {pick['dimension']}  (历史使用 {pick['times_used']} 次)")


def cmd_evergreen(rows, today):
    pick = pick_evergreen(rows)
    mark_used(rows, pick["sign"], pick["dimension"], today)
    save_topics(rows)
    append_calendar([today.isoformat(), pick["sign"], pick["dimension"], "", "", "planned"])
    print(f"常年型选题，今天建议写：【{pick['sign']} · {pick['dimension']}】")
    print(f"已记录到 {CALENDAR_CSV.name}（状态: planned），文章写好后把 title/filename 填上、status 改成 published 即可。")


# ---- 时效型：挑这个周期内还没更新过的星座 ----

def cmd_recurring(rows, today, dimension):
    cadence = RECURRING_DIMENSIONS[dimension]
    current_period = period_key(today, cadence)

    due = []
    for r in rows:
        if r["dimension"] != dimension:
            continue
        last_used = r["last_used"]
        if not last_used:
            due.append(r)
            continue
        last_date = datetime.strptime(last_used, "%Y-%m-%d").date()
        if period_key(last_date, cadence) != current_period:
            due.append(r)

    if not due:
        cadence_label = {"daily": "今天", "weekly": "本周", "monthly": "本月"}[cadence]
        print(f"{cadence_label}的【{dimension}】十二星座都已经更新过了，不用再选了。")
        return

    due.sort(key=lambda r: r["last_used"] or "")
    pick = due[0]
    mark_used(rows, pick["sign"], pick["dimension"], today)
    save_topics(rows)
    append_calendar([today.isoformat(), pick["sign"], pick["dimension"], "", "", "planned"])
    print(f"时效型选题，建议写：【{pick['sign']} · {dimension}】")
    print(f"已记录到 {CALENDAR_CSV.name}（状态: planned），文章写好后把 title/filename 填上、status 改成 published 即可。")


def main():
    ensure_topics_csv()
    ensure_calendar_csv()
    rows = load_topics()
    today = date.today()

    args = sys.argv[1:]

    if args and args[0] == "--list":
        n = int(args[1]) if len(args) > 1 else 7
        cmd_evergreen_list(rows, n)
        return

    if args and args[0] in RECURRING_DIMENSIONS.values():
        # args[0] is a cadence name ("daily"/"weekly"/"monthly") -> map back to dimension
        dimension = next(dim for dim, cad in RECURRING_DIMENSIONS.items() if cad == args[0])
        cmd_recurring(rows, today, dimension)
        return

    if args:
        print(f"未知参数：{args[0]}")
        print("用法：python3 next_topic.py [--list N | daily | weekly | monthly]")
        sys.exit(1)

    cmd_evergreen(rows, today)


if __name__ == "__main__":
    main()
