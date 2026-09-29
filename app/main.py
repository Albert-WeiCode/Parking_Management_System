from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.detect import router as detect_router
from app.api.detect import RESULT_DIR
from app.api.records import router as records_router
from app.auth import current_username, is_authenticated
from app.config import APP_NAME, OLLAMA_MODEL, SECRET_KEY
from app.database import get_db, init_database
from app.models import ParkingRecord


PROVINCE_NAMES = {
    "京": "北京", "津": "天津", "沪": "上海", "渝": "重庆",
    "冀": "河北", "豫": "河南", "云": "云南", "辽": "辽宁",
    "黑": "黑龙江", "湘": "湖南", "皖": "安徽", "鲁": "山东",
    "新": "新疆", "苏": "江苏", "浙": "浙江", "赣": "江西",
    "鄂": "湖北", "桂": "广西", "甘": "甘肃", "晋": "山西",
    "蒙": "内蒙古", "陕": "陕西", "吉": "吉林", "闽": "福建",
    "贵": "贵州", "粤": "广东", "青": "青海", "藏": "西藏",
    "川": "四川", "宁": "宁夏", "琼": "海南",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_database()
        app.state.database_error = None
    except Exception as exc:
        app.state.database_error = str(exc)
        print(f"MySQL 初始化失败: {exc}")
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/results", StaticFiles(directory=RESULT_DIR), name="results")
templates = Jinja2Templates(directory="app/templates")

app.include_router(auth_router)
app.include_router(detect_router)
app.include_router(records_router)
app.include_router(chat_router)


def page_context(request: Request, active: str, **extra):
    return {
        "request": request,
        "app_name": APP_NAME,
        "active": active,
        "username": current_username(request),
        **extra,
    }


def require_page_login(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return None


@app.get("/")
def index(request: Request):
    return RedirectResponse("/dashboard" if is_authenticated(request) else "/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse("/dashboard", status_code=303)
    error = request.session.pop("login_error", None)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context=page_context(
            request,
            "login",
            error=error,
            database_error=getattr(request.app.state, "database_error", None),
        ),
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    redirect = require_page_login(request)
    if redirect:
        return redirect

    today_start = datetime.combine(date.today(), datetime.min.time())
    total = db.query(func.count(ParkingRecord.id)).scalar() or 0
    today_total = (
        db.query(func.count(ParkingRecord.id))
        .filter(ParkingRecord.recorded_at >= today_start)
        .scalar()
        or 0
    )
    unique_plates = db.query(func.count(func.distinct(ParkingRecord.plate_number))).scalar() or 0
    province_rows = (
        db.query(ParkingRecord.province, func.count(ParkingRecord.id).label("count"))
        .group_by(ParkingRecord.province)
        .order_by(func.count(ParkingRecord.id).desc())
        .all()
    )
    province_stats = [
        {"code": code, "name": PROVINCE_NAMES.get(code, code), "count": count}
        for code, count in province_rows
    ]

    trend = []
    for offset in range(6, -1, -1):
        day = date.today() - timedelta(days=offset)
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        count = (
            db.query(func.count(ParkingRecord.id))
            .filter(ParkingRecord.recorded_at >= start, ParkingRecord.recorded_at < end)
            .scalar()
            or 0
        )
        trend.append({"label": day.strftime("%m-%d"), "count": count})

    latest = db.query(ParkingRecord).order_by(ParkingRecord.recorded_at.desc()).limit(6).all()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=page_context(
            request,
            "dashboard",
            total=total,
            today_total=today_total,
            unique_plates=unique_plates,
            province_stats=province_stats,
            trend=trend,
            latest=latest,
        ),
    )


@app.get("/detect/image", response_class=HTMLResponse)
def detect_image_page(request: Request):
    redirect = require_page_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request=request,
        name="detect_image.html",
        context=page_context(request, "detect-image"),
    )


@app.get("/detect/camera", response_class=HTMLResponse)
def detect_camera_page(request: Request):
    redirect = require_page_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request=request,
        name="detect_camera.html",
        context=page_context(request, "detect-camera"),
    )


@app.get("/records", response_class=HTMLResponse)
def records_page(
    request: Request,
    q: str = Query("", max_length=32),
    province: str = Query("", max_length=2),
    db: Session = Depends(get_db),
):
    redirect = require_page_login(request)
    if redirect:
        return redirect
    query = db.query(ParkingRecord)
    if q.strip():
        query = query.filter(ParkingRecord.plate_number.like(f"%{q.strip().upper()}%"))
    if province.strip():
        query = query.filter(ParkingRecord.province == province.strip())
    records = query.order_by(ParkingRecord.recorded_at.desc()).limit(200).all()
    return templates.TemplateResponse(
        request=request,
        name="records.html",
        context=page_context(
            request,
            "records",
            records=records,
            q=q,
            province=province,
            province_names=PROVINCE_NAMES,
            error=request.session.pop("record_error", None),
            success=request.session.pop("record_success", None),
        ),
    )


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    redirect = require_page_login(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context=page_context(request, "chat", ollama_model=OLLAMA_MODEL),
    )
