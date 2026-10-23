import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from math import ceil
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.detect import RESULT_DIR, router as detect_router
from app.api.records import router as records_router
from app.auth import current_username, is_authenticated
from app.config import APP_NAME, OLLAMA_MODEL, ROOT, SECRET_KEY
from app.database import get_db, init_database
from app.models import ParkingRecord
from app.parking import duration, filtered_records, now, parking_stats, status_label


@asynccontextmanager
async def lifespan(app):
    try:
        init_database()
        app.state.database_error = None
    except Exception:
        logging.getLogger(__name__).exception("数据库初始化或升级失败")
        app.state.database_error = "数据库连接或升级失败，请检查 MySQL 服务及配置。"
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="lax")
app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")
app.mount("/results", StaticFiles(directory=RESULT_DIR), name="results")
templates = Jinja2Templates(directory=ROOT / "app/templates")
templates.env.globals.update(duration=duration, status_label=status_label)
for router in (auth_router, detect_router, records_router, chat_router):
    app.include_router(router)


def page_context(request, active, **extra):
    return {"request": request, "app_name": APP_NAME, "active": active,
            "username": current_username(request), **extra}


def require_page_login(request):
    return None if is_authenticated(request) else RedirectResponse("/login", status_code=303)


@app.get("/")
def index(request: Request):
    return RedirectResponse("/dashboard" if is_authenticated(request) else "/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context=page_context(
        request, "login", error=request.session.pop("login_error", None),
        database_error=getattr(request.app.state, "database_error", None)))


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    if redirect := require_page_login(request):
        return redirect
    stats = parking_stats(db)
    trend = []
    for offset in range(6, -1, -1):
        day = now().date() - timedelta(days=offset)
        start = datetime.combine(day, datetime.min.time())
        count = db.query(ParkingRecord).filter(ParkingRecord.entered_at >= start, ParkingRecord.entered_at < start + timedelta(days=1)).count()
        trend.append({"label": day.strftime("%m-%d"), "count": count})
    latest = db.query(ParkingRecord).order_by(ParkingRecord.recorded_at.desc(), ParkingRecord.id.desc()).limit(8).all()
    return templates.TemplateResponse(request=request, name="dashboard.html", context=page_context(
        request, "dashboard", stats=stats, trend=trend, latest=latest))


@app.get("/detect/image", response_class=HTMLResponse)
def image_page(request: Request):
    if redirect := require_page_login(request):
        return redirect
    return templates.TemplateResponse(request=request, name="detect_image.html", context=page_context(request, "detect-image"))


@app.get("/detect/camera", response_class=HTMLResponse)
def camera_page(request: Request):
    if redirect := require_page_login(request):
        return redirect
    return templates.TemplateResponse(request=request, name="detect_camera.html", context=page_context(request, "detect-camera"))


@app.get("/parking", response_class=HTMLResponse)
@app.get("/records", response_class=HTMLResponse)
def records_page(request: Request, q: str = Query("", max_length=32), status: str = "", start: str = "", end: str = "",
                 page: int = Query(1, ge=1), db: Session = Depends(get_db)):
    if redirect := require_page_login(request):
        return redirect
    active_view = request.url.path == "/parking"
    status = "active" if active_view else status
    error = request.session.pop("record_error", None)
    try:
        query = filtered_records(db, q, status, start, end)
    except ValueError as exc:
        error = str(exc)
        query = db.query(ParkingRecord).filter(ParkingRecord.id < 0)
    total = query.count()
    pages = max(1, ceil(total / 30))
    page = min(page, pages)
    records = query.order_by(ParkingRecord.recorded_at.desc(), ParkingRecord.id.desc()).offset((page-1)*30).limit(30).all()
    params = {"q": q, "status": status, "start": start, "end": end}
    return templates.TemplateResponse(request=request, name="records.html", context=page_context(
        request, "parking" if active_view else "records", records=records, stats=parking_stats(db),
        active_view=active_view, q=q, status=status, start=start, end=end, page=page, pages=pages, total=total,
        export_url="/api/records/export?" + urlencode(params),
        previous_url=request.url.path + "?" + urlencode({**params, "page": max(1, page-1)}),
        next_url=request.url.path + "?" + urlencode({**params, "page": page+1}),
        error=error, success=request.session.pop("record_success", None)))


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    if redirect := require_page_login(request):
        return redirect
    return templates.TemplateResponse(request=request, name="chat.html", context=page_context(request, "chat", ollama_model=OLLAMA_MODEL))
