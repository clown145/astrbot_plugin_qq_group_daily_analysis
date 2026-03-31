[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/SXP-Simon/astrbot_plugin_qq_group_daily_analysis/tree/main/worker)

部署时填好 `UPLOAD_TOKEN`，完成后把同一个值填进插件配置页的“网页日报设置”。

构建时会优先尝试当前 GitHub 账号下的插件仓库 `astrbot_plugin_qq_group_daily_analysis@main`，找不到再回退到上游；部署页里如果填写了 `WORKER_SOURCE_REPO`、`WORKER_SOURCE_REF`，则优先按你填写的来源拉取。需要更细控制时，再填写 `WORKER_SOURCE_PATH`、`TEMPLATE_SOURCE_PATH`。
