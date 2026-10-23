#公共登录辅助函数，用于判断用户是否登录、获取当前用户名
from fastapi import Request

def current_username(request: Request) -> str | None:
    return request.session.get("username")


def is_authenticated(request: Request) -> bool:
    return bool(current_username(request))
