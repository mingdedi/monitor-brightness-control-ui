"""
亮度预测模块
基于 history.log 中的历史记录，按时间段加权预测用户期望的亮度值
"""

import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Tuple, Optional

HISTORY_LOG_FILE = "history.log"

# 去重时间窗口（秒）：同一时间戳内间隔 <= 此值的记录视为同一次操作
DEDUP_WINDOW = 10

# 加权半衰期（天）：30天前的记录权重为现在的一半
HALF_LIFE_DAYS = 30

# 最少记录数：低于此值时回退到默认亮度
MIN_RECORDS = 10


def parse_history(filepath: str = HISTORY_LOG_FILE) -> List[Tuple[datetime, int]]:
    """
    解析 history.log，返回 (时间戳, 亮度) 列表

    日志格式：
        [2026-04-02 18:48:47] 显示器：Generic PnP Monitor | 亮度设置为：53%
    """
    pattern = re.compile(
        r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+显示器：.+?\s*\|\s*亮度设置为：(\d+)%'
    )
    records = []
    if not os.path.exists(filepath):
        return records
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            m = pattern.match(line.strip())
            if m:
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
                brightness = int(m.group(2))
                records.append((ts, brightness))
    return records


def dedup_records(records: List[Tuple[datetime, int]]) -> List[Tuple[datetime, int]]:
    """
    去重：同一时间戳内（间隔 <= DEDUP_WINDOW 秒）的多条记录只取最后一条
    消除用户拖动滑条时产生的中间值
    """
    if not records:
        return []
    deduped = []
    i = 0
    while i < len(records):
        group = [records[i]]
        j = i + 1
        while j < len(records) and (records[j][0] - records[i][0]).total_seconds() <= DEDUP_WINDOW:
            group.append(records[j])
            j += 1
        deduped.append(group[-1])
        i = j
    return deduped


def compute_hourly_brightness(records: List[Tuple[datetime, int]],
                              now: Optional[datetime] = None) -> dict:
    """
    按小时(0-23)分桶，计算每个小时的加权平均亮度

    权重按时间远近指数衰减，半衰期 HALF_LIFE_DAYS 天
    """
    if now is None:
        now = datetime.now()

    buckets = defaultdict(list)  # hour -> [(weight, brightness), ...]

    for ts, brightness in records:
        days_ago = (now - ts).total_seconds() / 86400.0
        if days_ago < 0:
            days_ago = 0
        weight = 0.5 ** (days_ago / HALF_LIFE_DAYS)
        buckets[ts.hour].append((weight, brightness))

    hourly = {}
    for hour in range(24):
        entries = buckets.get(hour, [])
        if not entries:
            continue
        total_weight = sum(w for w, _ in entries)
        weighted_sum = sum(b * w for w, b in entries)
        hourly[hour] = weighted_sum / total_weight

    return hourly


def predict_brightness(now: Optional[datetime] = None,
                       filepath: str = HISTORY_LOG_FILE,
                       fallback: int = 50) -> Tuple[int, str]:
    """
    预测当前时间应有的亮度

    返回 (亮度值, 说明文字)

    算法：
    1. 解析历史记录并去重
    2. 按小时分桶计算加权平均
    3. 在当前时间所在的前后两个有数据的小时桶之间线性插值
    4. 数据不足时回退到 fallback
    """
    if now is None:
        now = datetime.now()

    records = parse_history(filepath)
    if len(records) < MIN_RECORDS:
        return fallback, f"历史记录不足({len(records)}条)，使用默认亮度"

    records = dedup_records(records)
    hourly = compute_hourly_brightness(records, now)

    if not hourly:
        return fallback, "无有效历史数据，使用默认亮度"

    current_hour_decimal = now.hour + now.minute / 60.0

    # 找到 <= 当前时间 的最近有数据的小时桶
    before_hour = None
    for h in range(int(current_hour_decimal), -1, -1):
        if h in hourly:
            before_hour = h
            break
    # 如果当前小时之前没有数据，从一天末尾找（环形）
    if before_hour is None:
        for h in range(23, int(current_hour_decimal), -1):
            if h in hourly:
                before_hour = h
                break

    # 找到 > 当前时间 的最近有数据的小时桶
    after_hour = None
    for h in range(int(current_hour_decimal) + 1, 24):
        if h in hourly:
            after_hour = h
            break
    # 如果当前小时之后没有数据，从一天开头找（环形）
    if after_hour is None:
        for h in range(0, int(current_hour_decimal) + 1):
            if h in hourly:
                after_hour = h
                break

    if before_hour is None and after_hour is None:
        return fallback, "无有效历史数据，使用默认亮度"

    if before_hour is None:
        predicted = hourly[after_hour]
    elif after_hour is None:
        predicted = hourly[before_hour]
    elif before_hour == after_hour:
        predicted = hourly[before_hour]
    else:
        # 线性插值
        h1, h2 = before_hour, after_hour
        # 处理环形跨午夜情况
        if h2 < h1:
            h2 += 24
        t = current_hour_decimal
        if t < h1:
            t += 24
        ratio = (t - h1) / (h2 - h1) if h2 != h1 else 0
        predicted = hourly[h1] + ratio * (hourly[h2 % 24] - hourly[h1])

    predicted = max(0, min(100, round(predicted)))
    return predicted, f"根据{len(records)}条历史记录预测"


if __name__ == "__main__":
    brightness, reason = predict_brightness()
    now = datetime.now()
    print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"预测亮度: {brightness}%")
    print(f"说明: {reason}")
