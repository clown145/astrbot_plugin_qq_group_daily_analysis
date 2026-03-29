# Cloudflare Worker

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/SXP-Simon/astrbot_plugin_qq_group_daily_analysis/tree/main/worker)

最小可用的网页报告 Worker：

- `UPLOAD_TOKEN`
- `REPORTS` KV Namespace

接口：

- `POST /api/internal/reports`
- `GET /r/<report_id>`
- `GET /healthz`

## 快速部署

1. 创建 KV Namespace，并把 `wrangler.jsonc` 里的 `id` 改成真实值。
2. 安装依赖并写入 Secret：

```bash
cd worker
npm install
npx wrangler secret put UPLOAD_TOKEN
```

3. 部署：

```bash
npm run deploy
```

## 插件配置

```bash
{
  "basic": {
    "output_format": "web"
  },
  "web_report": {
    "enabled": true,
    "worker_api_base": "https://your-worker.example.workers.dev",
    "upload_token": "与 Worker Secret 一致",
    "public_base_url": "https://your-report-domain.example.com",
    "report_ttl_days": 7,
    "request_timeout_seconds": 20
  }
}
```
