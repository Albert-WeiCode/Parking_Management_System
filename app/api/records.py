from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import is_authenticated
from app.database import get_db
from app.models import ParkingRecord


router = APIRouter(prefix="/api/records", tags=["停车记录"])

PROVINCES = set("京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼")


@router.post("")
def create_record(
    request: Request,
    plate_number: str = Form(...),
    note: str = Form(""),
    recorded_at: str = Form(""),
    db: Session = Depends(get_db),
):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)

    plate = plate_number.strip().upper().replace(" ", "")
    if len(plate) < 2 or plate[0] not in PROVINCES:
        request.session["record_error"] = "请输入以省份简称开头的有效车牌号"
        return RedirectResponse("/records", status_code=303)

    try:
        timestamp = datetime.fromisoformat(recorded_at) if recorded_at else datetime.now()
    except ValueError:
        request.session["record_error"] = "记录时间格式不正确"
        return RedirectResponse("/records", status_code=303)

    db.add(
        ParkingRecord(
            plate_number=plate,
            province=plate[0],
            source="手工录入",
            note=note.strip(),
            recorded_at=timestamp,
        )
    )
    db.commit()
    request.session["record_success"] = "停车记录已保存"
    return RedirectResponse("/records", status_code=303)
