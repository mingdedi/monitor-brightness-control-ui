"""
分析 history.log 中的亮度使用习惯
按时间段统计亮度分布
"""

import re
from datetime import datetime
from collections import defaultdict

LOG_FILE = "history.log"

# 正则匹配日志行
pattern = re.compile(
    r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+显示器：(.+?)\s*\|\s*亮度设置为：(\d+)%'
)

records = []
with open(LOG_FILE, "r", encoding="utf-8") as f:
    for line in f:
        m = pattern.match(line.strip())
        if m:
            ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
            monitor = m.group(2).strip()
            brightness = int(m.group(3))
            records.append((ts, monitor, brightness))

print(f"总记录数: {len(records)}")
print(f"时间跨度: {records[0][0]} ~ {records[-1][0]}")
print()

# 去重：同一时间戳内（间隔<=10秒的多条记录）只取最后一条
deduped = []
i = 0
while i < len(records):
    group = [records[i]]
    j = i + 1
    while j < len(records) and (records[j][0] - records[i][0]).total_seconds() <= 10:
        group.append(records[j])
        j += 1
    # 取组内最后一条
    deduped.append(group[-1])
    i = j

print(f"去重后记录数: {len(deduped)}")
print()

# 按2小时分桶
buckets = defaultdict(list)
for ts, monitor, brightness in deduped:
    hour_bucket = (ts.hour // 2) * 2
    buckets[hour_bucket].append(brightness)

# 输出统计表
print(f"{'时间段':<12} {'记录数':>6} {'平均':>6} {'最小':>6} {'最大':>6} {'中位数':>8}")
print("-" * 55)

for bucket_start in range(0, 24, 2):
    vals = buckets.get(bucket_start, [])
    if vals:
        avg = sum(vals) / len(vals)
        mn = min(vals)
        mx = max(vals)
        median = sorted(vals)[len(vals) // 2]
        label = f"{bucket_start:02d}-{bucket_start+2:02d}"
        print(f"{label:<12} {len(vals):>6} {avg:>6.1f} {mn:>6} {mx:>6} {median:>8}")
    else:
        label = f"{bucket_start:02d}-{bucket_start+2:02d}"
        print(f"{label:<12} {'(无数据)':>6}")

print()

# 额外：按小时细粒度统计
print("=== 按小时细粒度统计 ===")
hourly = defaultdict(list)
for ts, monitor, brightness in deduped:
    hourly[ts.hour].append(brightness)

print(f"{'小时':>4} {'记录数':>6} {'平均':>6} {'最小':>6} {'最大':>6} {'中位数':>8}")
print("-" * 50)
for h in range(24):
    vals = hourly.get(h, [])
    if vals:
        avg = sum(vals) / len(vals)
        mn = min(vals)
        mx = max(vals)
        median = sorted(vals)[len(vals) // 2]
        print(f"{h:>4} {len(vals):>6} {avg:>6.1f} {mn:>6} {mx:>6} {median:>8}")
