from fastapi import Request


def current_username(request: Request) -> str | None:
    return request.session.get("username")


def is_authenticated(request: Request) -> bool:
    return bool(current_username(request))
