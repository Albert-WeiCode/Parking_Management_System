from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.models import User, verify_password


router = APIRouter(tags=["用户认证"])


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        user = db.query(User).filter(User.username == username.strip()).first()
    except SQLAlchemyError:
        request.session["login_error"] = "无法连接数据库，请检查数据库服务和连接配置"
        return RedirectResponse("/login", status_code=303)
    if not user or not verify_password(password, user.password_hash):
        request.session["login_error"] = "用户名或密码错误"
        return RedirectResponse("/login", status_code=303)
    request.session.clear()
    request.session["username"] = user.username
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
