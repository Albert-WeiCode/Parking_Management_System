"""Shared parking rules and read-only statistics."""
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func

from app.models import ParkingRecord, ParkingSetting

PROVINCES = "京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼"
PLATE_PATTERN = rf"[{PROVINCES}][A-HJ-NP-Z][A-HJ-NP-Z0-9]{{4,5}}[A-HJ-NP-Z0-9学警港澳挂]"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)


def normalize_plate(value):
    plate = "".join(value.upper().split())
    if not re.fullmatch(PLATE_PATTERN, plate):
        raise ValueError("请输入有效的 7 位或 8 位车牌号码")
    return plate


def duration(record, current=None):
    if record.entered_at is None:
        return "—"
    minutes = max(0, int(((record.exited_at or current or now()) - record.entered_at).total_seconds() // 60))
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    return (f"{days}天 " if days else "") + (f"{hours}小时 " if hours else "") + f"{minutes}分钟"


def status_label(record):
    return "历史记录" if record.entered_at is None else ("已出场" if record.exited_at else "在场")


def filtered_records(db, q="", status="", start="", end=""):
    query = db.query(ParkingRecord)
    if q.strip():
        # Literal substring, not SQL wildcard syntax supplied by the user.
        query = query.filter(ParkingRecord.plate_number.contains(q.strip().upper(), autoescape=True))
    if status == "active":
        query = query.filter(ParkingRecord.active_plate.is_not(None))
    elif status == "exited":
        query = query.filter(ParkingRecord.exited_at.is_not(None))
    elif status == "history":
        query = query.filter(ParkingRecord.entered_at.is_(None))
    elif status:
        raise ValueError("无效的车辆状态")
    try:
        start_day = datetime.strptime(start, "%Y-%m-%d") if start else None
        end_day = datetime.strptime(end, "%Y-%m-%d") if end else None
    except ValueError:
        raise ValueError("日期格式不正确，请重新选择日期")
    if start_day and end_day and start_day > end_day:
        raise ValueError("开始日期不能晚于结束日期")
    timestamp = func.coalesce(ParkingRecord.entered_at, ParkingRecord.recorded_at)
    if start_day:
        query = query.filter(timestamp >= start_day)
    if end_day:
        try:
            exclusive_end = end_day + timedelta(days=1)
        except OverflowError:
            raise ValueError("结束日期超出支持范围")
        query = query.filter(timestamp < exclusive_end)
    return query


def parking_stats(db):
    current = now()
    start = datetime.combine(current.date(), time.min)
    end = start + timedelta(days=1)
    setting = db.get(ParkingSetting, 1)
    capacity = setting.capacity if setting else 100
    occupied = db.query(ParkingRecord).filter(ParkingRecord.active_plate.is_not(None)).count()
    return {
        "capacity": capacity, "occupied": occupied, "remaining": max(0, capacity - occupied),
        "today_entries": db.query(ParkingRecord).filter(ParkingRecord.entered_at >= start, ParkingRecord.entered_at < end).count(),
        "today_exits": db.query(ParkingRecord).filter(ParkingRecord.exited_at >= start, ParkingRecord.exited_at < end).count(),
        "occupancy": round(occupied / capacity * 100) if capacity else 0,
    }
