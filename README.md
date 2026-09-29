# 停车场管理系统

系统使用 FastAPI、MySQL、YOLO11s、LPRNet 和本地 Ollama DeepSeek，提供登录、Dashboard、图片检测、摄像头检测、停车记录查询与智能问答。

停车记录仅保存手工录入的已有车牌记录。图片和摄像头识别结果不会自动写入数据库。

## 启动

1. 启动本地 MySQL 和 Ollama 服务。
2. 如 MySQL root 账号有密码，将 `.env.example` 复制为 `.env` 并填写密码。
3. 安装依赖并启动应用：

```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000`。默认管理员账号为 `admin`，默认密码为 `admin123`，可以在 `.env` 中修改。

首次启动时会自动创建数据库 `Paking_Car_Sysetem`、数据表及默认管理员。
