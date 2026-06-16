# VPS 部署指南

## 前置条件

- 一台香港 VPS（推荐 Ubuntu 22.04+）
- 已购买的域名（可选，用于 HTTPS）
- DeepSeek API Key

## Step 1: 在 VPS 上安装 Docker

```bash
ssh root@<your-vps-ip>
curl -fsSL https://get.docker.com | sh
apt install docker-compose -y
```

## Step 2: 上传代码并配置

```bash
# 在本地
cd backend
scp -r . root@<your-vps-ip>:/opt/ai-assistant/

# 在 VPS 上
ssh root@<your-vps-ip>
cd /opt/ai-assistant
cp .env.example .env
nano .env  # 填入 DeepSeek API Key 和自定义 DEVICE_SECRET
```

## Step 3: 启动服务

```bash
cd /opt/ai-assistant
docker compose up -d --build
docker compose logs -f  # 查看日志确认启动成功
```

## Step 4: 配置 Nginx HTTPS 代理（可选，建议）

```bash
apt install nginx certbot python3-certbot-nginx -y

# 配置 Nginx 反向代理
cat > /etc/nginx/sites-available/ai-assistant << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
        proxy_buffering off;
    }
}
EOF

ln -s /etc/nginx/sites-available/ai-assistant /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 如果有域名，配置 HTTPS
certbot --nginx -d your-domain.com
```

## Step 5: 测试连接

```bash
# 健康检查
curl http://<your-vps-ip>:8000/health

# 测试聊天（替换 DEVICE_SECRET）
curl -X POST http://<your-vps-ip>:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: your-device-secret" \
  -d '{"message": "你好", "stream": false}'
```

## Flutter APP 配置

在 APP 设置页面填入：
- **服务器地址**: `http://<your-vps-ip>:8000` 或 `https://your-domain.com`
- **设备密钥**: 与 `.env` 中 `DEVICE_SECRET` 一致

## 常见问题

### 数据库连接失败
确保 `.env` 中 `DATABASE_URL` 使用 `db` 作为主机名（Docker Compose 内部网络）。

### Docker 启动失败
```bash
docker compose down -v  # 清除数据卷
docker compose up -d --build  # 重新构建
```
