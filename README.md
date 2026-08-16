# Token Station

一个私有、可部署的 OpenAI Chat Completions 中转站。管理员在服务端配置真实上游 API Key，用户只拿到独立的中转 Key；系统提供模型权限、RPM/TPM、月 Token 额度、元数据日志和中文控制台。

## 安全边界

- 上游 Key 使用 AES-256-GCM 加密后存入 PostgreSQL，主密钥只从服务器环境变量读取。
- 管理 API 和页面不会返回已保存的上游 Key；只能看到末四位并替换。
- 用户 Key 使用 256 位安全随机数，明文仅在创建时返回一次，数据库只存 SHA-256 摘要和指纹。
- Web 登录使用服务端 Session、HttpOnly/Secure/SameSite Cookie 和 CSRF 校验。
- 上游 URL 只允许 HTTPS，并拒绝解析到回环、私网和链路本地地址。
- 调用日志不保存提示词、回答、Authorization 或完整请求头。

## 功能

- `GET /v1/models`
- `POST /v1/chat/completions`，支持 JSON 和 SSE 流式响应
- 管理员：上游、公开模型映射、用户、额度、调用日志、审计日志
- 用户：本月用量、模型权限、创建和撤销最多 5 把访问 Key、接入示例
- Redis 原子 RPM/TPM/月额度预留，PostgreSQL 最终用量账本
- Alembic、Docker Compose、Nginx、Let's Encrypt、备份恢复和服务器预检

## 本地开发

后端默认使用 SQLite 和进程内限流，仅供开发与测试。

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

另一个终端启动前端：

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`，开发管理员默认为：

- 邮箱：`admin@example.com`
- 临时密码：`DevelopmentOnly!123`

首次登录必须修改密码。不要在生产环境使用这些默认值。

运行检查：

```bash
.venv/bin/ruff check app tests alembic
.venv/bin/pytest -q
cd frontend && npm run build
```

## 阿里云轻量服务器部署

针对当前美国弗吉尼亚 `Docker-mfic` 轻量服务器的完整上线、验收、备份和回滚步骤，请先阅读 [`docs/阿里云轻量服务器部署指南.md`](docs/阿里云轻量服务器部署指南.md)。

首发服务器控制台链接中的 `us-east-1` 是美国弗吉尼亚地域。部署前先登录服务器并运行：

```bash
chmod +x scripts/*.sh
./scripts/preflight.sh
```

建议最低配置为 2 vCPU、4 GB 内存、30 GB 可用磁盘。系统支持 Ubuntu 22.04/24.04、Alibaba Cloud Linux 3 等可运行 Docker Compose 的 x86_64/arm64 Linux。

### 1. 配置域名和安全组

1. 给域名添加 A 记录，指向服务器公网 IP。
2. 安全组只向公网开放 TCP 80、443。
3. SSH 端口只允许管理员固定 IP。
4. 不要开放 5432、6379 或 8000。

### 2. 创建生产配置

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
python3 -m app.cli generate-encryption-key
```

编辑 `.env`，替换所有 `CHANGE_ME`，填写域名、证书邮箱和管理员初始密码。`TOKEN_ENCRYPTION_KEY` 一旦用于保存上游 Key，就必须安全备份；丢失后数据库中的上游 Key 无法恢复。

### 3. 启动并签发 HTTPS

```bash
chmod +x scripts/*.sh deploy/nginx/entrypoint.sh
./scripts/enable-tls.sh
docker compose ps
curl -fsS "https://你的域名/health/ready"
```

证书签发前，Nginx 的 HTTP 配置只允许 ACME 验证和存活检查，不允许登录或模型调用。签发完成后脚本会把 `.env` 中的 `TLS_ENABLED` 改为 `true` 并重建 Nginx。

建议在 root crontab 中每天执行证书续期检查：

```cron
17 3 * * * cd /opt/token-station && ./scripts/renew-tls.sh >> /var/log/token-station-certbot.log 2>&1
```

### 4. 首次配置

1. 使用 `.env` 中的管理员账号登录，立即修改初始密码。
2. 在“上游”中填写国内 OpenAI 兼容端点和真实 API Key，并执行连接测试。
3. 创建公开模型映射。
4. 创建用户，设置有限的月 Token、RPM、TPM 和模型权限。
5. 用户首次登录改密、创建 Key，再用控制台中的 curl 或 Python 示例调用。

## 备份和恢复

每日备份并保留 7 天：

```bash
./scripts/backup.sh
```

生产机建议同时配置每日备份与日志归档任务；归档任务把超过 90 天的请求元数据汇总为按月记录，并只保留最近 13 个月：

```cron
12 2 * * * cd /opt/token-station && ./scripts/backup.sh >> /var/log/token-station-backup.log 2>&1
42 2 * * * cd /opt/token-station && ./scripts/retention.sh >> /var/log/token-station-retention.log 2>&1
```

建议再把 `backups/` 同步到使用独立凭证保护的 OSS Bucket。恢复会替换当前数据库，必须显式确认：

```bash
CONFIRM_RESTORE=yes ./scripts/restore.sh backups/token-station-YYYYMMDDTHHMMSSZ.sql.gz
```

## 运维

```bash
docker compose ps
docker compose logs -f --tail=200 api nginx
docker compose pull
docker compose up -d --build
curl -fsS https://你的域名/health/live
curl -fsS https://你的域名/health/ready
```

`/health/live` 只表示进程存活；`/health/ready` 同时检查 PostgreSQL、Redis 和 Alembic 迁移版本。生产环境不会暴露 FastAPI `/docs`。

## OpenAI SDK 示例

```python
from openai import OpenAI

client = OpenAI(
    api_key="ts_sk_...",
    base_url="https://token.example.com/v1",
)

response = client.chat.completions.create(
    model="管理员配置的公开模型名",
    messages=[{"role": "user", "content": "你好"}],
)
print(response.choices[0].message.content)
```

管理员必须自行确认所配置上游的服务条款允许代理或向其他用户提供调用能力。
