# 本地开发环境 — 接续指南

## 当前状态（✅ 全部就绪）

- ✅ Docker Desktop 运行中
- ✅ PostgreSQL + pgvector 容器运行中（端口 5432）
- ✅ DeepSeek API Key 已配置
- ✅ Python 3.14 + 虚拟环境创建完毕
- ✅ 所有 Python 依赖安装完成
- ✅ 数据库迁移执行完成（表已创建）
- ✅ 后端服务运行中（http://localhost:8000）
- ✅ `/health` 端点验证通过
- ✅ `/api/chat` 流式聊天 API 验证通过

## 已安装的依赖版本

| 包 | 版本 |
|---|---|
| fastapi | 0.137.1 |
| uvicorn | 0.49.0 |
| sqlalchemy | 2.0.51 |
| asyncpg | 0.31.0 |
| alembic | 1.18.4 |
| pydantic | 2.13.4 |
| httpx | 0.28.1 |
| sentence-transformers | 5.5.1 |
| torch | 2.12.0 |

## 常用命令

```bash
# 进入后端目录
cd "D:\Claude code\个人API应用\backend"

# 激活虚拟环境
.venv\Scripts\activate

# 启动后端（开发模式，支持热重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 验证后端
curl http://localhost:8000/health

# 测试聊天 API
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: local-dev-secret" \
  -d '{"message":"你好"}'

# 数据库管理
docker compose up -d db        # 启动数据库
docker compose down            # 停止数据库
alembic upgrade head           # 运行迁移
alembic revision --autogenerate -m "描述"  # 创建新迁移

# 查看数据库日志
docker logs backend-db-1
```

## 如何继续开发

直接说「继续本地开发环境搭建」,
Claude Code 会自动检查当前状态，知道还需要做什么。
