# 停车场管理系统

基于 FastAPI、MySQL、YOLO11s 和本地字符/颜色识别模型，提供车辆出入场、在场管理、停车记录、车位统计和停车助手。

## 功能

- 图片、摄像头识别车牌及颜色；支持修改识别结果，再确认入场或出场。
- 手工登记入场与出场；同车在场禁止重复入场，满位禁止入场，没有在场记录时提示人工处理。
- 在场车辆列表、入场时间与已停时长；一次停车对应一条记录，出场时更新该记录。
- 按车牌、状态、入场日期查询，分页展示，按当前筛选条件导出全部 CSV 记录。
- 设置停车场总车位，首页展示今日入场、今日出场、当前在场、剩余车位及近七日趋势。
- 停车助手直接读取数据库回答车位、进出场数量和完整车牌状态；其他问题使用带实时停车快照的本地 Ollama。
- 助手不修改停车数据，识别结果也不会未经确认自动登记；暂不包含计费、支付或道闸控制。

## 启动

使用 Python 3.10+，先启动 MySQL。Ollama 为可选服务：未启动时，基础停车数据问答仍可使用。

```bash
cp .env.example .env
# 编辑 .env，填写 MySQL 连接、管理员账号及 SECRET_KEY
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

访问 http://127.0.0.1:8000 。默认管理员为 `admin` / `admin123`，请按实际需要在 `.env` 设置。
默认数据库名称为 `Paking_Car_Sysetem`，启动时自动创建数据库、表和初始管理员。

## 使用流程

1. 在“出入场登记”上传图片，或在“摄像头识别”截帧。
2. 核对、修改车牌，点击“确认入场”或“确认出场”。无法识别时，可在“在场车辆”页手工登记。
3. 在“在场车辆”查看当前车辆并确认出场，在“停车记录”查询历史或导出 CSV。
4. 在在场车辆或停车记录页面设置总车位数（初始 100）；不可小于当前在场车辆数。
5. 问停车助手“现在还剩多少车位？”“今天进出了多少辆车？”或“粤B12345 在场吗？”。

日期、进出场时间按 Asia/Shanghai 记录。日期筛选按入场日期，已停时长在页面刷新时更新。
CSV 使用 UTF-8 BOM 编码，适合 Excel 打开；导出遵循筛选条件，包含全部匹配记录，而不只当前页。

## 旧数据兼容

首次升级启动时，在旧停车记录表增加可空的入场时间、出场时间和在场唯一标记，并创建车位设置表。
不会删除或覆盖原车牌、来源、备注和记录时间。旧数据没有入场状态，因此显示为“历史记录”，不计入在场或今日进出场统计。
可使用“历史记录”筛选查看；日期筛选对旧数据使用原记录时间。请在升级前按日常维护习惯备份数据库，并确保数据库账号有建表、增加字段和索引权限。

## 项目结构

```text
app/
  main.py                 应用入口、页面、统计和查询
  config.py               环境配置
  database.py             连接、初始化与兼容升级
  models.py               用户、停车记录、车位设置数据表
  parking.py              时间、车牌校验、停车统计和查询公共规则
  auth.py                 登录状态辅助函数
  api/                    登录、检测、出入场、导出与停车助手接口
  templates/              页面与公共记录表格
  static/                 页面样式及交互脚本
recognize/
  model.py                字符/颜色识别网络、预处理和解码
  service.py              模型加载、YOLO定位、裁剪与联合识别
  plate_rec_color.pth      字符及颜色识别权重
runs/license_plate/weights/best.pt  当前车牌检测权重
scripts/                  数据准备、训练、识别评估
CLPD/                     原始图片与标注
dataset/                  训练/验证/测试数据
```

## 模型及配置

当前检测模型是已训练的 YOLO11s `runs/license_plate/weights/best.pt`，识别模型是 `recognize/plate_rec_color.pth`，支持 78 类字符、5 类颜色。
网络和输入契约参考[上游识别实现](https://github.com/we0091234/yolov8-plate/tree/master/plate_recognition)，按 checkpoint cfg 构建并严格加载。
模型置信度不代表经校准的准确率。

`.env.example` 中可设置：

- `DETECTION_MODEL_PATH`、`RECOGNITION_MODEL_PATH`：模型路径，相对于项目根目录或使用绝对路径。
- `INFERENCE_DEVICE`：默认 `auto`，按 CUDA / MPS / CPU 自动选择，也可指定 `cpu`。
- `DETECTION_CONFIDENCE`、`DETECTION_IMAGE_SIZE`：默认 0.25、1024。
- `MAX_UPLOAD_MB`：默认 10，最大图片分辨率为 2000 万像素。
- `OLLAMA_BASE_URL`、`OLLAMA_MODEL`：本地问答服务与模型。
- `PARKING_RUNTIME_DIR`：默认系统临时目录下 `parking_management_system`，结果图保存在其中的 `results/`，可按部署需要定期清理。

摄像头需要 HTTPS 或 localhost，并由用户授权浏览器访问。连续识别每次请求完成后间隔一秒，编辑识别结果时停止连续模式。
模型首次识别时加载并在进程内复用。

## 数据准备与评估

```bash
python scripts/prepare_dataset.py --output /tmp/parking-dataset
python scripts/evaluate_recognition.py --limit 30 --output /tmp/recognition-evaluation.json
```

数据准备拒绝覆盖已有目录。训练脚本默认读取项目 `dataset/data.yaml`，使用根目录 `yolo11s.pt` 预训练权重；`last.pt` 保留用于继续训练。

本项目供学习交流使用。
