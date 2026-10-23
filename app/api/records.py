import csv
from io import StringIO
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import is_authenticated
from app.database import get_db
from app.models import ParkingRecord, ParkingSetting
from app.parking import duration, filtered_records, normalize_plate, now, status_label

router = APIRouter(prefix="/api/records", tags=["停车管理"])


def feedback(request, message, success=False, status=400):
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"success": success, "message": message}, status_code=200 if success else status)
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    request.session["record_success" if success else "record_error"] = message
    target = "/parking" if request.headers.get("referer", "").split("?")[0].endswith("/parking") else "/records"
    return RedirectResponse(target, status_code=303)


def locked_setting(db):
    setting = db.query(ParkingSetting).filter(ParkingSetting.id == 1).with_for_update().one_or_none()
    if setting is None:
        raise ValueError("停车场设置尚未初始化，请重新启动服务")
    return setting


@router.post("")
@router.post("/entry")
def enter(request: Request, plate_number: str = Form(...), note: str = Form(""),
          source: str = Form("手工录入"), db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return feedback(request, "请先登录", status=401)
    try:
        plate = normalize_plate(plate_number)
        if len(note) > 500:
            raise ValueError("备注不能超过 500 字")
        if source not in {"手工录入", "图片识别", "摄像头识别"}:
            raise ValueError("无效的登记来源")
        setting = locked_setting(db)
        if db.query(ParkingRecord).filter(ParkingRecord.active_plate == plate).first():
            raise ValueError(f"{plate} 已在场，请勿重复入场")
        if db.query(ParkingRecord).filter(ParkingRecord.active_plate.is_not(None)).count() >= setting.capacity:
            raise ValueError("停车场已满，无法登记入场")
        timestamp = now()
        db.add(ParkingRecord(plate_number=plate, province=plate[0], source=source,
                             note=note.strip(), entered_at=timestamp, recorded_at=timestamp, active_plate=plate))
        db.commit()
        return feedback(request, f"{plate} 入场成功", True)
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        return feedback(request, str(exc) if isinstance(exc, ValueError) else "该车辆已在场，请勿重复登记", status=409)


@router.post("/exit")
def exit_vehicle(request: Request, plate_number: str = Form(...), db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return feedback(request, "请先登录", status=401)
    try:
        plate = normalize_plate(plate_number)
        locked_setting(db)
        record = db.query(ParkingRecord).filter(ParkingRecord.active_plate == plate).with_for_update().first()
        if record is None:
            raise ValueError(f"未找到 {plate} 的在场记录，请核对车牌或人工处理")
        record.exited_at = now()
        record.active_plate = None
        parked = duration(record)
        db.commit()
        return feedback(request, f"{plate} 出场成功，停车 {parked}", True)
    except ValueError as exc:
        db.rollback()
        return feedback(request, str(exc), status=409)


@router.post("/capacity")
def set_capacity(request: Request, capacity: int = Form(...), db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return feedback(request, "请先登录", status=401)
    try:
        setting = locked_setting(db)
        occupied = db.query(ParkingRecord).filter(ParkingRecord.active_plate.is_not(None)).count()
        if not 1 <= capacity <= 100000:
            raise ValueError("总车位数应在 1 到 100000 之间")
        if capacity < occupied:
            raise ValueError(f"总车位数不能小于当前在场车辆数 {occupied}")
        setting.capacity = capacity
        db.commit()
        return feedback(request, "车位总数已更新", True)
    except ValueError as exc:
        db.rollback()
        return feedback(request, str(exc))


def safe_cell(value):
    value = str(value or "")
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


@router.get("/export")
def export_records(request: Request, q: str = Query("", max_length=32), status: str = "", start: str = "", end: str = "", db: Session = Depends(get_db)):
    if not is_authenticated(request):
        return JSONResponse({"message": "请先登录"}, status_code=401)
    try:
        records = filtered_records(db, q, status, start, end).order_by(ParkingRecord.recorded_at.desc())
    except ValueError as exc:
        return JSONResponse({"message": str(exc)}, status_code=400)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["车牌号码", "状态", "入场时间", "出场时间", "停车时长", "来源", "备注", "原记录时间"])
    current = now()
    for record in records.yield_per(500):
        writer.writerow([safe_cell(record.plate_number), status_label(record),
                         record.entered_at, record.exited_at, duration(record, current),
                         safe_cell(record.source), safe_cell(record.note), record.recorded_at])
    return Response(content='\ufeff' + output.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="parking-records.csv"'})
