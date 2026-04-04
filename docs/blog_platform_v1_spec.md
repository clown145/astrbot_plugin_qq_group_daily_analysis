# Group Blog Platform V1 Spec

## 1. 目标

本规格定义一个新的“群聊博客平台”V1。

它不是现有 HTML 导出功能的简单放大版，而是一个独立的、可长期演进的 Web 产品：

- 每个群对应一个博客
- 首页展示群聊长期趋势与画像
- 支持账号绑定、登录、多个群切换
- 支持 Worker 端持久化与二次聚合
- 支持插件或后续专用分析端向 Worker 发布数据

本规格同时回答两个核心问题：

1. 现有插件是否适合作为博客分析端
2. 如果不完全适合，应该复用哪些代码、重建哪些部分

---

## 2. 结论摘要

### 2.1 总结论

现有插件**不适合直接作为博客的“权威分析端”**，但**非常适合复用其中一部分基础能力**。

原因不是代码质量，而是产品语义不一致：

- 现插件允许“分析最近 N 天”
- 现插件有 `max_messages` 上限
- 现插件支持手动分析、自动分析、增量滑窗分析
- 现插件当前产物偏“单次报告”，不是“稳定日快照库”

而博客首页需要的是：

- 固定时区下的自然日快照
- 可长期累计的趋势数据
- 可去重、可覆盖、可追溯的数据模型
- 明确区分“正式日报”和“临时分享报告”

### 2.2 推荐策略

推荐采用“两阶段策略”：

#### 阶段 A

先让现插件成为一个**发布者**，直接支撑第一版博客。

但发布的数据要分层，而不是只发一种 JSON。

此阶段允许：

- 插件发布 `daily_snapshot`
- 插件发布 `range_report`
- 插件发布 `preview_report`
- 插件发布 `report_render_bundle`
- Worker 在接收后生成并归档日报 HTML

#### 阶段 B

逐步抽取现插件中真正稳定、适合长期复用的能力，形成一个更适合博客的数据采集/分析流水线。

长期建议仍然是：

- 插件继续做群内交互、即时报告、手动分析
- 博客分析端单独做“标准化日快照采集与发布”

### 2.3 V1 落地决策

V1 明确采用：

- **先基于现插件做博客**
- **不等待独立分析端完成**
- **首页趋势数据与日报归档数据分开存**

也就是说，第一版博客不是“彻底脱离插件”，而是：

- 插件负责生成分析结果
- 插件负责把结构化数据发给 Worker
- Worker 负责存储、归档、渲染和展示

---

## 3. 不应继续直接沿用的现有流程

以下流程不应直接作为博客**主趋势库**的数据来源：

- `execute_daily_analysis(days=N)` 的任意天数分析
- 手动触发的多天分析
- 增量滑窗最终报告
- 任何命中 `max_messages` 上限但未标记完整度的数据

原因：

- 多天分析会与已有日报重叠
- 滑窗报告不是自然日桶
- 手动分析通常是“查看”，不是“沉淀正式历史”
- 消息上限会导致样本不完整

结论：

- 博客首页趋势库只接收 `daily_snapshot`
- 多天分析和手动分析可以生成独立日报页，但不写入主趋势库

---

## 4. 建议复用的现有代码

适合复用：

- 统一消息模型 `UnifiedMessage`
- 平台适配器中的消息拉取能力
- 消息清洗能力
- 基础统计计算
- 用户活跃度分析
- 可选的 LLM 语义分析能力

不建议原样复用：

- 现有 HTML 报告生成流程
- 现有“保存 HTML + JSON”的自托管输出流程
- 现有历史摘要持久化流程
- 现有“最近 N 天”作为主分析入口的语义

说明：

- 第一版博客仍然会复用插件的模板与渲染输入
- 但这些能力会通过新的发布协议进入 Worker，而不是继续沿用旧自托管 HTML 方案

### 4.1 现阶段最值得抽取的模块

建议未来抽成独立可复用模块：

- `message fetch`
- `message normalize`
- `message clean`
- `group statistics`
- `user activity statistics`
- `semantic enrichment`
- `publish payload builder`

---

## 5. 新仓库与职责边界

旧的 Worker 仓库不再作为目标实现继续演进。

建议新建仓库：

- `astrbot-group-daily-analysis-blog`

职责如下：

- 提供博客页面
- 提供数据接收 API
- 提供绑定/登录/会话 API
- 持久化站点所需结构化数据
- 缓存站点读取模型

现有插件仓库职责：

- 群内命令
- 群聊即时分析
- 第一版博客的数据发布者

### 5.1 第一版边界

V1 先明确采用“插件作为生产者，Worker 作为博客后端”的模式。

这意味着：

- 现插件继续负责分析
- Worker 不负责直接抓群消息
- Worker 不负责调用 LLM 做语义分析
- Worker 只负责接收、归档、渲染、展示

只有到后续版本，才考虑把“标准化日报采集”从插件里逐步独立出去

---

## 6. 技术选型

### 6.1 Web 框架

主框架选择：

- `Astro`

原因：

- 博客首页本质是内容页 + 少量图表交互
- Astro 适合静态内容占大头、交互区块较少的站点
- 可以在 Cloudflare Workers 上部署
- 页面性能和长期维护成本都优于上来就做重型 SPA

### 6.2 运行时

- `Cloudflare Workers`
- `@astrojs/cloudflare`

### 6.3 图表

- `Apache ECharts`

用于：

- 30 天趋势图
- 24 小时活跃分布
- 每日 x 小时热力图
- 用户排行相关图表

### 6.4 存储

- `D1`：主数据源
- `KV`：缓存读取模型
- `R2`：原始快照与大对象归档

### 6.5 认证与会话

- 账户密码登录
- `HttpOnly` Cookie Session
- 绑定流程通过 bot 群内消息确认

### 6.6 不推荐的方向

当前不推荐：

- `Next.js` 作为主框架
- 直接把 KV 当主数据库
- 直接把 localStorage 当登录态存储
- 直接公开原始群号做 URL

### 6.7 插件侧配置约定

插件侧 V1 需要新增一组独立配置：

- `basic.output_format = web`
- `web_blog.enable_web_blog`
- `web_blog.worker_base_url`
- `web_blog.worker_ingest_path`
- `web_blog.worker_bind_verify_path`
- `web_blog.worker_upload_token`
- `web_blog.worker_bind_callback_token`
- `web_blog.worker_request_timeout_seconds`

约定如下：

- 只有当 `output_format = web` 时，插件才会走 Worker 上传流程
- `enable_web_blog` 是总开关，关闭时即使格式设为 `web` 也应回退文本
- `worker_upload_token` 仅用于插件 -> Worker 的服务端上传鉴权，不暴露给前端用户
- `worker_bind_callback_token` 用于 bot 在群里收到 `/绑定博客 <绑定码>` 后回调 Worker；建议和上传密钥分开配置，留空时可回退复用上传密钥

---

## 7. 数据分层

### 7.1 公开站点趋势数据

只允许进入站点的数据：

- 聚合统计
- 趋势桶
- 筛选后的榜单
- 筛选后的金句/话题
- 聊天质量总结

### 7.2 日报归档渲染数据

用于生成和保存“某一天具体日报 HTML”的数据：

- 模板名
- 模板版本
- 组件渲染所需字段
- 话题、金句、用户称号
- 头像资源引用

这类数据不一定全部直接暴露到首页接口，但需要被 Worker 保存，以便：

- 重新打开历史日报
- 按模板生成具体 HTML
- 支持未来模板切换策略

### 7.3 非公开内部数据

不应直接进入公开站点：

- 原始消息全文
- 内部 prompt
- 原始完整 LLM 输入
- 平台私密 ID 映射
- 内部调试字段

### 7.4 原始快照归档

可选归档到 R2：

- 发布时的完整 `publish payload v1`
- 供回放、补算、重建页面使用

---

## 8. 报告类型定义

Worker 侧必须把不同类型的报告明确区分。

### 8.1 `daily_snapshot`

语义：

- 固定时区下某自然日的正式快照
- 唯一允许进入首页趋势库的数据类型

特征：

- 有 `snapshot_date`
- 去重、覆盖规则明确
- 可以重发覆盖

### 8.2 `range_report`

语义：

- 一次性的时间范围分析
- 例如最近 3 天、最近 7 天

特征：

- 不进入主页趋势库
- 只作为单独页面保存

### 8.3 `preview_report`

语义：

- 临时页面
- 用于分享、测试、预览

特征：

- 可设置 TTL
- 不进入趋势库

### 8.4 `report_render_bundle`

语义：

- 用于生成某次日报 HTML 的完整渲染包
- 服务于“查看之前生成的日报”

特征：

- 可以来自 `daily_snapshot`
- 也可以来自 `range_report`
- 包含模板渲染所需的大部分字段
- 可比首页趋势 payload 大很多

---

## 8.5 为什么需要“趋势快照”和“日报渲染包”分离

博客系统里实际上有两类数据：

### A. 首页趋势数据

特点：

- 小
- 稳定
- 结构化
- 适合 D1 查询

典型内容：

- 每日消息数
- 活跃人数
- 小时分布
- Top 用户统计

### B. 历史日报渲染数据

特点：

- 大
- 模板相关
- 可能包含头像、组件片段、语义内容
- 适合归档，不适合频繁 SQL 查询

典型内容：

- 话题详情
- 金句详情
- 用户称号详情
- 模板上下文
- 头像资源引用

因此 V1 不应该只发一种 JSON，而应该至少有两类载荷：

- `daily_snapshot`
- `report_render_bundle`

---

## 9. 时间与完整度规则

### 9.1 时区

每个博客必须绑定一个固定时区，例如：

- `Asia/Shanghai`

后续所有日报快照都按这个时区切自然日。

### 9.2 时间边界

每个 payload 必须明确：

- `window_start`
- `window_end`
- `snapshot_date`
- `timezone`

### 9.3 完整度

每个 payload 必须带：

- `coverage_status`
- `message_limit_hit`
- `fetched_message_count`
- `analyzed_message_count`

`coverage_status` 建议枚举：

- `full`
- `partial`
- `truncated`
- `unknown`

如果因为 `max_messages` 命中上限，只能标为 `partial` 或 `truncated`，不能伪装成完整日报。

---

## 10. 去重与覆盖规则

### 10.1 博客主趋势库

唯一键：

- `(platform, group_id, snapshot_date, report_kind='daily_snapshot')`

行为：

- 同一自然日重复上传时允许覆盖
- 只保留最新正式快照

### 10.2 多天报告

唯一键：

- `report_id`

行为：

- 不写入主趋势表
- 独立归档

### 10.3 手动分析

默认规则：

- 手动分析不进入主趋势库

只有明确满足以下条件时，才允许当作正式日报：

- `report_kind = daily_snapshot`
- `snapshot_date` 为单一天
- `coverage_status` 合格
- 平台侧明确标记 `publish_as_official_snapshot = true`

---

## 11. 绑定与登录流程

### 11.1 总体原则

不要把长期有效的服务端秘钥交给用户。

用户只拿到：

- 一次性绑定码

服务端长期秘钥只用于：

- 插件 -> Worker 发布数据
- bot -> Worker 回调确认绑定
- Session 签名

### 11.2 首次绑定流程

1. 用户进入站点，填写 `群号 + QQ号`
2. Worker 生成短时效 `bind_code`
3. 用户在目标群中，用对应 QQ 对 bot 发送 `/绑定博客 <bind_code>`
4. bot 根据群上下文与发送者身份校验请求
5. bot 使用服务端秘钥回调 Worker
6. Worker 标记该 QQ 已绑定该群
7. 用户设置账户密码
8. Worker 创建账户或把该群挂到已有账户下

### 11.3 登录流程

1. 用户输入 `QQ号 + 密码`
2. Worker 校验账户
3. 下发 `HttpOnly` Session Cookie
4. 首页展示可访问的博客列表
5. 用户切换不同群博客

### 11.4 浏览器本地存储

浏览器本地只允许保存：

- 最近访问的博客 slug
- 非敏感 UI 偏好

不允许保存：

- session token
- 长期登录凭证
- 服务端签名数据

---

## 12. Worker 端安全规范

### 12.1 Secret 分离

至少分为：

- `INGEST_SECRET`
- `BOT_CALLBACK_SECRET`
- `SESSION_SECRET`
- `PASSWORD_PEPPER`

不要一个 secret 混用所有场景。

### 12.2 限流

以下接口必须限流：

- 绑定申请
- 绑定确认
- 登录
- 密码设置/重置
- 内部 ingest

### 12.3 密码存储

只存 `password_hash`，不存明文。

推荐：

- `Argon2id`

### 12.4 访问控制

V1 权限模型先做简单版：

- 已绑定成员可访问已绑定群博客

暂不做复杂 RBAC。

---

## 13. 存储职责划分

### 13.1 D1

用于结构化数据：

- 账户
- 博客
- 绑定关系
- 会话
- 每日快照
- 用户日统计
- 话题归档
- 金句归档
- 范围报告索引

不建议放入 D1 的内容：

- 大段模板渲染上下文
- base64 头像
- 整份 HTML

### 13.2 KV

只用于缓存：

- 首页读取模型
- 最近 30 天聚合结果
- 档案页缓存

KV 不做主真相源。

### 13.3 R2

用于：

- 原始发布 payload 归档
- 较大的 JSON 快照
- 未来可能的导出资产
- 历史日报 HTML
- 头像二进制对象
- `report_render_bundle` 归档

### 13.4 为什么头像不应直接长期放在 JSON 里

当前插件为了生成日报，会使用 base64 头像。

这对单次本地渲染是可以接受的，但对博客系统长期存储并不理想：

- base64 会增大体积
- 同一用户头像会在多份报告中重复
- D1/KV 都不适合长期保存这类大字段

V1 建议这样处理：

1. 插件仍可把头像作为 base64 放入 `report_render_bundle`
2. Worker ingest 时把头像拆出来
3. 头像按内容哈希存入 R2
4. 渲染包内部改写为头像对象引用

这样既兼容现插件，又避免长期重复存储

### 13.5 头像变化策略

必须区分两种展示：

#### 历史日报页

建议“冻结当时快照”。

也就是说：

- 某天的日报应该看到那天归档时使用的头像
- 不应因为用户后来换头像而改变历史日报外观

#### 博客首页和用户榜

可以使用较新的缓存头像，允许更新。

结论：

- 历史日报页使用归档头像引用
- 首页可使用“最近已知头像”

---

## 14. D1 表设计（V1）

### 14.1 `accounts`

- `id`
- `qq_number`
- `password_hash`
- `created_at`
- `updated_at`

### 14.2 `blogs`

- `id`
- `platform`
- `group_id`
- `group_name`
- `public_slug`
- `timezone`
- `visibility`
- `created_at`
- `updated_at`

唯一约束建议：

- `(platform, group_id)`
- `public_slug`

### 14.3 `memberships`

- `account_id`
- `blog_id`
- `role`
- `bound_at`

唯一约束建议：

- `(account_id, blog_id)`

### 14.4 `bind_challenges`

- `id`
- `platform`
- `group_id`
- `qq_number`
- `code_hash`
- `expires_at`
- `used_at`
- `created_at`

### 14.5 `sessions`

- `id`
- `account_id`
- `expires_at`
- `created_at`
- `revoked_at`

### 14.6 `daily_snapshots`

- `id`
- `blog_id`
- `snapshot_date`
- `timezone`
- `window_start`
- `window_end`
- `coverage_status`
- `message_limit_hit`
- `fetched_message_count`
- `analyzed_message_count`
- `message_count`
- `participant_count`
- `active_user_count`
- `total_characters`
- `emoji_count`
- `most_active_period`
- `chat_quality_title`
- `chat_quality_summary`
- `raw_payload_r2_key`
- `published_at`

唯一约束建议：

- `(blog_id, snapshot_date)`

### 14.7 `daily_hourly_buckets`

- `snapshot_id`
- `hour`
- `message_count`

唯一约束建议：

- `(snapshot_id, hour)`

### 14.8 `daily_user_stats`

- `snapshot_id`
- `user_hash`
- `display_name`
- `message_count`
- `char_count`
- `emoji_count`
- `reply_count`
- `night_ratio`
- `most_active_hour`

### 14.9 `range_reports`

- `id`
- `blog_id`
- `report_kind`
- `window_start`
- `window_end`
- `coverage_status`
- `title`
- `payload_json`
- `expires_at`
- `created_at`

---

## 15. `publish payload v1` 定义

以下是插件或未来专用分析端发布到 Worker 的标准 JSON。

```json
{
  "schema_version": "publish_payload_v1",
  "producer": {
    "name": "astrbot_plugin_qq_group_daily_analysis",
    "version": "0.0.0",
    "instance_id": "optional-instance-id"
  },
  "target": {
    "platform": "onebot",
    "group_id": "123456789",
    "group_name": "示例群",
    "timezone": "Asia/Shanghai"
  },
  "report": {
    "report_kind": "daily_snapshot",
    "source_mode": "scheduled",
    "snapshot_date": "2026-04-03",
    "window_start": "2026-04-03T00:00:00+08:00",
    "window_end": "2026-04-04T00:00:00+08:00",
    "generated_at": "2026-04-04T00:05:00+08:00",
    "publish_as_official_snapshot": true
  },
  "coverage": {
    "coverage_status": "full",
    "message_limit_hit": false,
    "fetched_message_count": 1387,
    "analyzed_message_count": 1362,
    "dropped_message_count": 25,
    "notes": []
  },
  "stats": {
    "message_count": 1362,
    "participant_count": 84,
    "active_user_count": 84,
    "total_characters": 28731,
    "emoji_count": 316,
    "most_active_period": "晚间 (18:00-24:00)"
  },
  "activity": {
    "hourly_buckets": [
      { "hour": 0, "message_count": 3 },
      { "hour": 1, "message_count": 1 },
      { "hour": 2, "message_count": 0 }
    ],
    "daily_buckets": [
      { "date": "2026-04-03", "message_count": 1362 }
    ]
  },
  "users": {
    "top_users": [
      {
        "user_hash": "u_8b5c...",
        "display_name": "Alice",
        "message_count": 138,
        "char_count": 4021,
        "emoji_count": 26,
        "reply_count": 15,
        "most_active_hour": 22,
        "night_ratio": 0.19
      }
    ]
  },
  "topics": [
    {
      "name": "新番讨论",
      "contributors": ["Alice", "Bob"],
      "detail": "围绕本周更新展开讨论"
    }
  ],
  "quotes": [
    {
      "content": "今天就到这里，明天继续。",
      "sender": "Bob",
      "reason": "收尾效果很好"
    }
  ],
  "chat_quality_review": {
    "title": "高参与高互动",
    "subtitle": "节奏稳定，夜间显著升温",
    "summary": "成员互动积极，回复链较多。"
  },
  "raw_flags": {
    "contains_llm_output": true,
    "contains_raw_messages": false
  }
}
```

---

## 15.1 `report_render_bundle_v1` 定义

用于 Worker 生成和归档日报 HTML。

该载荷允许比 `publish payload v1` 大很多。

```json
{
  "schema_version": "report_render_bundle_v1",
  "report_meta": {
    "report_id": "01J....",
    "platform": "onebot",
    "group_id": "123456789",
    "group_name": "示例群",
    "report_kind": "daily_snapshot",
    "snapshot_date": "2026-04-03",
    "template_name": "scrapbook",
    "template_version": "git:abcdef1",
    "timezone": "Asia/Shanghai",
    "generated_at": "2026-04-04T00:05:00+08:00"
  },
  "render_context": {
    "message_count": 1362,
    "participant_count": 84,
    "total_characters": 28731,
    "emoji_count": 316,
    "most_active_period": "晚间 (18:00-24:00)",
    "topics": [],
    "user_titles": [],
    "quotes": [],
    "chat_quality_review": {},
    "hourly_chart_data": []
  },
  "assets": {
    "avatars": [
      {
        "asset_id": "avatar_user_10001",
        "content_type": "image/png",
        "base64_data": "iVBORw0KGgoAAA..."
      }
    ]
  }
}
```

说明：

- `publish payload v1` 服务于趋势库
- `report_render_bundle_v1` 服务于日报页归档和 HTML 生成

---

## 15.2 Worker ingest 后的行为

Worker 接收到 `report_render_bundle_v1` 后应执行：

1. 拆分并保存头像资产到 R2
2. 把渲染包正文保存到 R2
3. 记录 `template_name + template_version`
4. 生成最终 HTML
5. 把最终 HTML 归档到 R2
6. 在 D1 中写入归档索引

这样历史日报页可以直接读取归档 HTML，而不必每次重新渲染

---

## 15.3 为什么历史日报应保存最终 HTML

如果只保存渲染数据，不保存最终 HTML，会有三个问题：

- 模板更新后旧日报可能显示变化
- 运行时重新渲染成本更高
- 历史回放依赖模板版本可用性

因此 V1 建议：

- **日报生成时就把最终 HTML 归档**

这样模板更新只影响未来报告，不影响过去报告

---

## 16. `publish payload v1` 设计原则

### 16.1 必须版本化

必须包含：

- `schema_version`

### 16.2 不直接暴露内部对象

不应直接传：

- Python dataclass 的原始序列化结构
- 插件内部 `analysis_result` 全量对象

### 16.3 用户标识应可脱敏

公开站点使用的用户 ID 建议使用：

- `user_hash`

不强制公开真实平台用户 ID。

### 16.4 支持未来扩展

后续可新增：

- `relations`
- `message_type_breakdown`
- `daily_newcomers`
- `retention`

### 16.5 允许第一版直接复用现插件模板输入

V1 为了快速落地，允许：

- 直接基于现插件已有渲染字段构造 `report_render_bundle_v1`

但要求：

- 通过新 schema 封装
- 不直接把插件内部对象原样透传为长期协议

---

## 17. 为博客补充的数据字段

为了让博客真正有“长期分析价值”，建议补充以下数据：

### 17.1 必补

- `active_user_count`
- 每用户日统计
- 24 小时完整桶
- 是否命中抓取上限
- 精确时区边界

### 17.2 推荐补

- 消息类型分布
- 回复链计数
- 提及计数
- 链接/图片发送量
- 新活跃用户数

### 17.3 暂缓

- 用户关系图
- 会话线程图
- 留存/回流高级指标

### 17.4 与历史日报查看直接相关的补充字段

为了支持“博客查看之前生成的日报”，建议记录：

- `template_name`
- `template_version`
- `report_id`
- `html_archive_key`
- `render_bundle_key`
- `avatar_asset_keys`

这些需要更完整、更稳定的明细采样后再做。

---

## 18. 博客可支持的分析内容

基于 V1 数据，首页与子页可做：

- 近 30 天消息趋势
- 近 30 天活跃人数趋势
- 24 小时活跃分布
- 近 30 天日 x 小时热力图
- Top 用户榜
- 夜猫子榜
- 长文王榜
- 表情王榜
- 回复王榜
- 热门话题归档
- 金句归档
- 聊天质量摘要

V1 不建议承诺：

- 精确关系网络图
- 真实群成员身份校验后的细粒度权限
- 高精度响应时延

---

## 19. 现插件与未来专用分析端的关系

### 19.1 现阶段判断

现插件更像：

- 即时报告生成器
- 群内交互入口
- 语义分析工具

它不像：

- 长期趋势数据库生产器

### 19.2 最合理路线

短期：

- 继续复用插件部分统计逻辑
- 增加标准化 payload 导出

中期：

- 抽取公共分析内核

长期：

- 独立出博客专用分析流水线

### 19.3 为什么需要独立分析流水线

因为博客想要的是：

- 固定时间切片
- 高一致性
- 可追溯
- 可补算
- 不受聊天命令和即时展示语义影响

---

## 20. 开发顺序

### 20.1 第一阶段

1. 定规格文档
2. 定 `publish payload v1`
3. 定 `report_render_bundle_v1`
3. 定 D1 schema
4. 新建 Worker 仓库骨架

### 20.2 第二阶段

1. 实现绑定与登录基础能力
2. 实现 `ingest` API
3. 实现博客首页最小页面
4. 实现日报 HTML 归档流程
5. 实现日快照读取模型

### 20.3 第三阶段

1. 在插件中增加 payload builder
2. 增加 Worker 发布接口
3. 明确 `daily_snapshot` 与 `range_report` 分流
4. 增加完整度标记
5. 增加 `report_render_bundle_v1` 导出
6. 增加头像资产拆分逻辑

### 20.4 第四阶段

1. 评估是否从插件抽出公共分析内核
2. 评估是否构建独立日快照采集器

---

## 21. 环境与实施注意事项

### 21.1 本地开发限制

当前 Android Termux 环境下，`wrangler/workerd` 不能直接运行。

因此：

- 文档、代码、数据模型可以在当前环境编写
- Worker 本地运行与部署验证需要在支持的平台完成

### 21.2 当前建议

在正式开始实现前，应先完成：

- 新 Worker 仓库初始化
- D1 migration 目录
- `publish payload v1` Python 数据模型
- 插件侧“官方日报 / 范围报告 / 预览报告”的类型分流

---

## 22. 最终执行建议

正式开工时，建议按以下决策执行：

### 决策 A

**旧 Worker 仓库不继续沿用。**

### 决策 B

**先写规格、协议、表结构，再写代码。**

### 决策 C

**博客首页主趋势库只接受 `daily_snapshot`。**

### 决策 D

**现插件在 V1 中直接作为博客分析与发布入口。**

但同时保留长期判断：

- 它不是最终最理想的唯一分析端
- 后续仍可能抽取更适合博客的独立分析流水线

### 决策 E

**V1 采用“双载荷”策略：趋势快照 + 日报渲染包。**

### 决策 F

**历史日报页归档最终 HTML，首页趋势读取结构化快照。**

### 决策 G

**模板更新通过仓库同步与重新部署完成，不依赖运行时 `git pull`。**
