[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/SXP-Simon/astrbot_plugin_qq_group_daily_analysis/tree/main/worker)

部署时填好 `UPLOAD_TOKEN`，完成后把同一个值填进插件配置页的“网页日报设置”。

构建时默认会从当前部署仓库的 `origin` 和当前 `HEAD` commit 拉取 Worker 运行代码和模板；部署页里如果把 `WORKER_SOURCE_REPO`、`WORKER_SOURCE_REF` 留空，就会走这个自动检测。需要手动改来源时，再填写 `WORKER_SOURCE_REPO`、`WORKER_SOURCE_REF`、`WORKER_SOURCE_PATH`、`TEMPLATE_SOURCE_PATH`。
