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

按钮指向的是仓库里的 `worker/` 子目录，这个子目录本身就是一个独立 Worker 项目。
项目配置文件是 `wrangler.jsonc`，不使用 `wrangler.toml`。

1. 创建 KV Namespace，并把 `worker/wrangler.jsonc` 里的 `id` 改成真实值。
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

在 AstrBot 的插件配置 WebUI 里设置：

- `基础设置 -> 输出格式` 设为 `web`
- `网页报告设置 -> 启用网页报告发送` 打开
- `网页报告设置 -> Worker API 地址` 填 Worker 域名
- `网页报告设置 -> Worker 上传令牌` 填和 `UPLOAD_TOKEN` 一致的值
- `网页报告设置 -> 公开链接基础地址` 按需填写自定义域名
- `网页报告设置 -> 报告保留天数`、`上传超时时间（秒）` 按需调整
