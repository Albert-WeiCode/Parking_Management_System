import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import is_authenticated
from app.config import OLLAMA_BASE_URL, OLLAMA_MODEL


router = APIRouter(prefix="/api/chat", tags=["智能问答"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.post("")
def chat(request: Request, body: ChatRequest):
    if not is_authenticated(request):
        return JSONResponse(status_code=401, content={"message": "请先登录"})

    prompt = (
        "你是停车场管理系统中的中文智能助手。回答应简洁、准确。"
        "系统只管理已有车牌记录的存储、查询和展示，不包含进出场、计费或停车时长业务。"
        f"\n用户问题：{body.message.strip()}"
    )
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()
        return {"success": True, "answer": answer, "model": OLLAMA_MODEL}
    except requests.RequestException as exc:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "无法连接本地 Ollama，请确认服务已启动且模型可用。",
                "detail": str(exc),
            },
        )
