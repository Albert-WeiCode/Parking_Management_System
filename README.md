# 停车场管理系统

基于 **FastAPI + MySQL + YOLO11s + LPRNet + 本地 Ollama DeepSeek** 的停车场管理系统，提供登录、数据概览（Dashboard）、图片检测、摄像头检测、停车记录查询与智能问答功能。

> **说明**：停车记录仅保存手工录入的已有车牌记录，图片和摄像头识别结果不会自动写入数据库。

## 功能特性

- 🔐 **登录认证**：管理员账号登录，凭据可在 `.env` 中修改
- 📊 **数据概览（Dashboard）**：停车记录统计、省份车牌统计、最近停车记录展示
- 🖼️ **图片检测**：基于 YOLO11s + LPRNet 对车辆图片进行车牌检测与识别
- 📹 **摄像头检测**：基于 OpenCV Pipeline 的实时视频检测
- 📋 **停车记录**：手工录入的车牌记录查询与管理（MySQL 存储）
- 💬 **智能问答**：基于本地 Ollama DeepSeek 的停车管理助手

## 技术栈

| 模块 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| 数据库 | MySQL |
| 车牌检测 | YOLO11s |
| 车牌识别 | LPRNet |
| 智能问答 | Ollama + DeepSeek（本地部署） |
| 视频处理 | OpenCV |

## 系统截图

### 登录页面

![登录页面](images/停车场管理系统-登录页面.png)

### 图片检测

![图片检测](images/停车场管理系统-图片检测.png)

### 数据概览（Dashboard）

![数据概览](images/停车场管理系统-数据概览.png)

### 智能问答

![智能问答](images/停车场管理系统-智能问答.png)

## 快速开始

### 环境要求

- Python 3.8+
- MySQL
- Ollama（本地部署 DeepSeek 模型）

### 启动步骤

1. **启动本地 MySQL 和 Ollama 服务**

2. **配置数据库密码**（如 MySQL root 账号有密码）：

   将 `.env.example` 复制为 `.env` 并填写密码：

   ```bash
   cp .env.example .env
   ```

3. **安装依赖并启动应用**：

   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

4. **访问系统**：

   浏览器打开 `http://127.0.0.1:8000`

### 默认账号

| 项目 | 值 |
|------|------|
| 用户名 | `admin` |
| 密码 | `admin123` |

> 默认密码可以在 `.env` 文件中修改。

### 数据库初始化

首次启动时系统会自动创建数据库 `Paking_Car_Sysetem`、数据表及默认管理员账号，无需手动建库。

## 项目结构

```
Parking_Management_System/
├── app/
│   ├── templates/          # 前端页面（HTML 模板）
│   ├── __init__.py
│   ├── auth.py             # 登录认证
│   ├── config.py           # 配置
│   ├── database.py         # 数据库连接
│   ├── main.py             # 应用入口
│   └── models.py           # 数据模型
├── CLPD/                   # 车牌检测与识别模型相关
├── scripts/                # 数据准备与训练脚本
├── .env.example            # 环境变量示例
└── requirements.txt        # 依赖列表
```

## License

本项目仅供学习交流使用。
