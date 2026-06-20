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

# 小时桶最少记录数：低于此值的桶不参与插值，避免单条异常值主导
MIN_BUCKET_SIZE = 3


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


def weighted_median(values: List[float], weights: List[float]) -> float:
    """加权中位数：按值排序后，累积权重达到总权重50%处的值"""
    sorted_pairs = sorted(zip(values, weights))
    total = sum(w for _, w in sorted_pairs)
    cumulative = 0.0
    for v, w in sorted_pairs:
        cumulative += w
        if cumulative >= total / 2:
            return v
    return sorted_pairs[-1][0]


def remove_outliers_iqr(values: List[float], weights: List[float]) -> Tuple[List[float], List[float]]:
    """
    使用IQR方法剔除异常值

    仅对记录数 >= 5 的桶生效，避免小样本下IQR不稳定
    若剔除后为空则返回原始数据
    """
    if len(values) < 5:
        return values, weights
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[3 * n // 4]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    filtered = [(v, w) for v, w in zip(values, weights) if lower <= v <= upper]
    if not filtered:
        return values, weights
    return [v for v, _ in filtered], [w for _, w in filtered]


def compute_hourly_brightness(records: List[Tuple[datetime, int]],
                              now: Optional[datetime] = None) -> dict:
    """
    按小时(0-23)分桶，计算每个小时的加权中位数亮度

    权重按时间远近指数衰减，半衰期 HALF_LIFE_DAYS 天
    使用加权中位数而非加权均值，对个别极端异常值免疫
    记录数不足 MIN_BUCKET_SIZE 的桶被丢弃，不参与插值
    对足够数据的桶先做IQR异常值剔除，再计算加权中位数
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
        if len(entries) < MIN_BUCKET_SIZE:
            continue
        weights = [w for w, _ in entries]
        brightnesses = [float(b) for _, b in entries]
        brightnesses, weights = remove_outliers_iqr(brightnesses, weights)
        hourly[hour] = weighted_median(brightnesses, weights)

    return hourly


def interpolate_brightness(hour_decimal: float, hourly: dict) -> Optional[float]:
    """
    在给定小时（小数）处，根据小时桶数据线性插值预测亮度

    处理环形跨午夜情况
    """
    if not hourly:
        return None

    int_hour = int(hour_decimal)

    before_hour = None
    for h in range(int_hour, -1, -1):
        if h in hourly:
            before_hour = h
            break
    if before_hour is None:
        for h in range(23, int_hour, -1):
            if h in hourly:
                before_hour = h
                break

    after_hour = None
    for h in range(int_hour + 1, 24):
        if h in hourly:
            after_hour = h
            break
    if after_hour is None:
        for h in range(0, int_hour + 1):
            if h in hourly:
                after_hour = h
                break

    if before_hour is None and after_hour is None:
        return None
    if before_hour is None:
        return hourly[after_hour]
    if after_hour is None:
        return hourly[before_hour]
    if before_hour == after_hour:
        return hourly[before_hour]

    # 5:00前后不插值：夜间(5点前)与白天(5点后)之间为突变，保持前一个点的值
    if before_hour < 5 and after_hour >= 5:
        return hourly[before_hour]

    h1, h2 = before_hour, after_hour
    if h2 < h1:
        h2 += 24
    t = hour_decimal
    if t < h1:
        t += 24
    ratio = (t - h1) / (h2 - h1) if h2 != h1 else 0
    return hourly[h1] + ratio * (hourly[h2 % 24] - hourly[h1])


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
    predicted = interpolate_brightness(current_hour_decimal, hourly)

    if predicted is None:
        return fallback, "无有效历史数据，使用默认亮度"

    predicted = max(0, min(100, round(predicted)))
    return predicted, f"根据{len(records)}条历史记录预测"


def compute_24h_curve(filepath: str = HISTORY_LOG_FILE) -> Tuple[List[Tuple[float, float]], str]:
    """
    计算24小时预测亮度曲线

    返回 ([(小时, 亮度), ...], 说明文字)
    每半小时采样一次，共48个点
    """
    now = datetime.now()
    records = parse_history(filepath)
    if len(records) < MIN_RECORDS:
        return [], f"历史记录不足({len(records)}条)"

    records = dedup_records(records)
    hourly = compute_hourly_brightness(records, now)

    if not hourly:
        return [], "无有效历史数据"

    curve = []
    for h in range(48):
        hour_decimal = h * 0.5
        brightness = interpolate_brightness(hour_decimal, hourly)
        if brightness is not None:
            curve.append((hour_decimal, max(0, min(100, brightness))))

    return curve, f"基于{len(records)}条历史记录"


def plot_24h_curve(filepath: str = HISTORY_LOG_FILE):
    """用 matplotlib 绘制24小时预测亮度曲线图"""
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    from matplotlib import font_manager

    font_manager.fontManager.addfont("C:/Windows/Fonts/msyh.ttc")
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei"]
    plt.rcParams["axes.unicode_minus"] = False

    curve, reason = compute_24h_curve(filepath)

    now = datetime.now()
    records = parse_history(filepath)
    records = dedup_records(records)
    hourly = compute_hourly_brightness(records, now)

    fig, ax = plt.subplots(figsize=(10, 5))

    if not curve:
        ax.text(0.5, 0.5, "无足够数据生成曲线", ha="center", va="center",
                fontsize=14, color="red", transform=ax.transAxes)
        ax.set_title("24小时亮度预测曲线", fontsize=15, fontweight="bold")
        plt.show()
        return

    # 插值曲线
    hours = [h for h, _ in curve]
    values = [v for _, v in curve]
    ax.plot(hours, values, color="#4CAF50", linewidth=2, label="预测曲线")

    # 所有历史记录散点
    if records:
        raw_h = [ts.hour + ts.minute / 60.0 + ts.second / 3600.0 for ts, _ in records]
        raw_v = [b for _, b in records]
        ax.scatter(raw_h, raw_v, color="#FF9800", s=10, alpha=0.4, zorder=3,
                   label="历史记录")

    # 原始小时桶数据点
    if hourly:
        raw_hours = sorted(hourly.keys())
        raw_values = [hourly[h] for h in raw_hours]
        ax.scatter(raw_hours, raw_values, color="#2196F3", s=40, zorder=5,
                   label="历史加权中位数")

    # 当前时间标记
    current_hour = now.hour + now.minute / 60.0
    ax.axvline(x=current_hour, color="red", linestyle="--", linewidth=1, alpha=0.7)
    ax.annotate("现在", xy=(current_hour, 100), fontsize=9, color="red",
                ha="center", va="top")

    ax.set_title("24小时亮度预测曲线", fontsize=15, fontweight="bold", pad=12)
    ax.text(0.5, 1.02, reason, fontsize=9, color="gray", ha="center",
            transform=ax.transAxes)
    ax.set_xlabel("小时", fontsize=11)
    ax.set_ylabel("亮度 (%)", fontsize=11)
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 105)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(3))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(25))
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(loc="lower right", fontsize=9)

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    plot_24h_curve()
