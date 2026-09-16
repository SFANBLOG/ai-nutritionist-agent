# AI 营养师 Agent V2：日常干预闭环设计

## 1. 产品方向与安全边界

从当前的「体检报告 → 多日食谱」升级为「记录 → 分析 → 微调 → 复盘 → 必要时转人工」的营养调理闭环。

系统提供健康教育、饮食建议和风险提示，**不做疾病诊断、药物剂量调整或急救处置**。用户出现胸痛、晕厥、严重低血糖症状、呼吸困难等红旗症状时，停止普通建议，展示紧急就医提示；孕哺期、未成年人、进食障碍史、肾病透析和使用胰岛素/华法林等用户进入「需专业人员复核」路径。

## 2. V2 功能包（按交付优先级）

### P0：提升留存和建议可信度

1. **饮食日志**：文字、语音转写、照片识别结果和手工录入；每项食物都可编辑重量、烹饪方式与份数。
2. **营养预算**：按日展示能量、蛋白质、纤维、钠、添加糖及用户病情相关指标；不把照片识别结果当作最终值。
3. **即时餐后反馈**：仅指出 1–2 个最重要、可执行的调整，例如“晚餐钠偏高，下一餐优先选择原型食物”。
4. **替换建议**：按忌口、过敏、预算、烹饪时间、地域食材和目标营养素生成等价替换。
5. **每周复盘**：依从性、体重/腰围趋势、目标完成率和下周一个行为实验；所有结论附数据时间范围和证据来源。
6. **人工复核队列**：沿用现有 HITL 闸门，将高风险用户、矛盾数据、模型低置信度和生成失败的个案转至营养师。

### P1：降低记录摩擦

1. 条码/包装营养成分表录入与本地食物库优先匹配。
2. 购物清单、家庭份量换算、剩菜复用和一键换餐。
3. 可选接入 Apple Health / Health Connect / 可穿戴设备，只读取用户明确授权的数据。
4. 提醒策略：基于用户习惯窗口触发，用户可一键暂停，避免高频打扰。

### P2：专业服务与长期调理

1. 营养师工作台：备注、模板、调整前后对比、审阅签名。
2. 检验指标时间序列及报告导入的差异比对。
3. 远程咨询后的结构化总结（必须由专业人员确认后写入病历）。
4. 面向机构的脱敏群体洞察；不使用个人健康信息训练或外发模型。

## 3. 多智能体拓扑

```text
输入（报告/日志/偏好/体征）
            │
            ▼
      调度与安全 Agent ──红旗/高风险──> 人工复核队列
            │
   ┌────────┼─────────┬─────────┐
   ▼        ▼         ▼         ▼
解析 Agent  食物识别 Agent  营养计算 Agent  证据检索 Agent
   └────────┴─────────┴─────────┘
            │ （结构化、带来源和置信度）
            ▼
       调理计划 Agent
            │
   ┌────────┴────────┐
   ▼                 ▼
菜单/替换 Agent     行为教练 Agent
   └────────┬────────┘
            ▼
       安全审计 Agent ──未通过──> 修订 / 人工复核
            │
            ▼
       用户可读答案 + 可追溯行动卡
```

### Agent 契约

| Agent | 只负责 | 输入 / 输出 | 禁止事项 |
| --- | --- | --- | --- |
| 调度与安全 | 分类、风险分流、工具授权 | `NutritionCase` → `RouteDecision` | 生成治疗建议 |
| 解析 | 报告和日志结构化 | 原文 → 指标/食物候选+置信度 | 推断未出现的诊断 |
| 食物识别 | 照片候选识别 | 图片 → `FoodCandidate[]` | 直接记账，必须等待用户确认 |
| 营养计算 | 基于食物库确定性加总 | 确认食物 → `NutrientTotals` | 用 LLM 估算数值作为事实 |
| 证据检索 | 召回已审核知识和版本 | 查询 → `EvidenceSnippet[]` | 使用未分级网络内容作医疗依据 |
| 调理计划 | 目标、预算与约束 | 用户画像+指标+证据 → `PlanDraft` | 覆盖过敏、禁忌、风险标记 |
| 菜单/替换 | 生成可执行菜单 | 预算+库存/偏好 → `MealOptions` | 绕过营养计算和审核 |
| 行为教练 | 一次一个可验证行为目标 | 周期数据 → `ActionCard` | 羞辱式、绝对化表达 |
| 安全审计 | 规则、完整性、冲突检测 | 所有产物 → `AuditResult` | 自动放行严重风险 |

现有 `NutritionAgentWorkflow` 可保留为“调理计划 + 菜单/替换 + 安全审计”的核心子图；报告解析和知识库分别迁移为独立子图。跨 Agent 只传 Pydantic 结构，不传无限增长的自然语言上下文。

## 4. Function calling：应用内确定性工具

模型只负责选择工具和解释结果；所有营养数值、数据库写入与风险判断由后端函数完成。工具均采用严格 JSON Schema、显式 `user_id` 作用域、`request_id` 幂等键与审计日志。

### 只读工具（默认可自动调用）

```json
[
  {
    "name": "get_user_nutrition_context",
    "description": "读取当前用户已授权的画像、目标、过敏、偏好和最近 14 天汇总；不返回密码或原始文件。",
    "parameters": {"type":"object","properties":{"user_id":{"type":"integer"},"days":{"type":"integer","minimum":1,"maximum":30}},"required":["user_id"],"additionalProperties":false}
  },
  {
    "name": "search_verified_nutrition_evidence",
    "description": "从内部、版本化且人工审核的营养知识库检索证据。",
    "parameters": {"type":"object","properties":{"query":{"type":"string","maxLength":500},"condition_tags":{"type":"array","items":{"type":"string"},"maxItems":8}},"required":["query"],"additionalProperties":false}
  },
  {
    "name": "calculate_nutrients",
    "description": "用食物库和份量计算宏量、微量营养素及钠、添加糖；返回食物库版本与不确定性。",
    "parameters": {"type":"object","properties":{"items":{"type":"array","minItems":1,"items":{"type":"object","properties":{"food_id":{"type":"string"},"grams":{"type":"number","exclusiveMinimum":0}},"required":["food_id","grams"],"additionalProperties":false}}},"required":["items"],"additionalProperties":false}
  }
]
```

### 写入工具（必须用户确认）

| 工具 | 动作 | 确认条件 |
| --- | --- | --- |
| `create_food_log_draft` | 保存候选饮食日志草稿 | 不确认；仅草稿 |
| `commit_food_log` | 写入正式日志和营养账本 | 展示食物、份量与数值后确认 |
| `propose_meal_swap` | 创建换餐方案草稿 | 不确认 |
| `apply_meal_swap` | 修改已生效菜单 | 用户确认；高风险用户需人工复核 |
| `create_human_review_case` | 提交最小必要信息到复核队列 | 系统红旗自动提交，或用户同意 |
| `schedule_check_in` | 创建提醒 | 用户明确选择时间和频率 |

模型不得拥有通用 SQL、任意 HTTP、文件系统或跨用户检索工具。对写入工具，前端呈现 `tool_call_id`、变更预览和确认 token；服务端二次校验用户身份、资源归属、版本号和确认 token。

## 5. MCP 设计：可插拔边界，而非把内部数据库暴露给模型

### `nutrition-core-mcp`（内部，首期实现）

| 类型 | 名称 | 作用 |
| --- | --- | --- |
| Tool | `search_food_catalog` | 用中文别名/条码查食物库，返回候选和来源 |
| Tool | `calculate_nutrients` | 确定性营养计算 |
| Tool | `get_daily_budget` | 读取个人当日预算和已摄入汇总 |
| Tool | `search_verified_evidence` | 按证据等级、版本、疾病标签检索 |
| Tool | `draft_meal_swap` | 生成但不应用等价替换 |
| Resource | `nutrition://guidelines/{version}` | 已审核指南的只读快照 |
| Resource | `nutrition://foods/{catalog_version}` | 食物库元数据、许可和更新时间 |
| Prompt | `weekly-review` | 固定输出周复盘行动卡和限制声明 |

MCP 服务只经后端网关访问，使用短期用户委托令牌，工具注解中明确 `readOnlyHint`、`destructiveHint`、`idempotentHint`。工具输出必须包含 `source`, `catalog_version`, `confidence`, `warnings`；任何 PII/PHI 都不写进工具描述、日志或模型长期记忆。

### 外部 MCP（后续，按需授权）

| MCP | 可开放能力 | 风险控制 |
| --- | --- | --- |
| 可穿戴/健康平台 | 每日步数、睡眠、活动消耗的只读汇总 | OAuth、粒度授权、可随时撤销；不读取原始定位数据 |
| 生鲜/外卖 | 搜索商品、生成购物清单 | 默认草稿；下单、支付永远不由 Agent 执行 |
| 日历 | 创建复诊/称重提醒 | 每次写入需用户确认 |
| 专业文献 | 只读检索和引用 | 仅白名单提供商；证据 Agent 进行等级过滤 |

远程 MCP 的风险与数据保留策略独立于本应用，故只传最小必要、去标识化字段，并在连接页展示用途、字段和撤销入口。

## 6. 数据模型与事件

新增实体：`FoodCatalogItem`、`FoodLog`、`FoodLogItem`、`DailyNutritionSummary`、`BodyMetric`、`Goal`、`ActionCard`、`AgentRun`、`ToolAuditLog`、`HumanReviewCase`、`ConsentGrant`。

关键事件：

```text
food_log.drafted → food_log.confirmed → nutrients.recalculated
→ budget.updated → coach.action_card_created
→ review.required | review.passed

body_metric.logged → trend.calculated → weekly_review.generated
```

每次 `AgentRun` 保存输入快照哈希、知识库/食物库版本、调用的工具、审核结果、模型和提示词版本。原始报告与图片采用分离对象存储、最小权限访问和生命周期策略。

## 7. 服务端 API（V2 草案）

```text
POST   /api/food-logs/drafts             # 解析文本/图片，返回待确认候选
POST   /api/food-logs/{id}/confirm       # 确认份量后入账
GET    /api/nutrition/daily?date=...     # 当日预算与摄入
POST   /api/meal-swaps/draft             # 生成等价替换
POST   /api/meal-swaps/{id}/apply        # 带确认 token 应用替换
POST   /api/body-metrics                 # 体重/腰围/血压等用户输入
GET    /api/insights/weekly              # 带证据和数据范围的周复盘
GET    /api/agent-runs/{id}              # 用户可见的执行轨迹摘要
```

## 8. 实施顺序与验收

1. **第 1 迭代**：食物库适配层、饮食日志、确定性营养计算、每日预算、审计表；不接照片识别。
2. **第 2 迭代**：把现有 LangGraph 拆为上述子图，增加工具注册表、风险路由、AgentRun 和人工复核队列。
3. **第 3 迭代**：替换建议、周复盘、前端行动卡与确认 UI。
4. **第 4 迭代**：照片/条码、外部 MCP 和专业人员工作台；各连接器单独安全评审。

验收用例至少覆盖：过敏食材强制拦截、照片低置信度必须确认、跨用户资源拒绝、写操作重放幂等、红旗症状升级、不含证据来源的计划拒绝放行、离线/LLM 失败时确定性计算仍可用。

## 9. 外部参考

- Nutrium：饮食日记、目标依从性、个性化餐单与营养素分析。
- ZOE：个性化食物洞察和 AI 食物记录。
- OpenAI Responses API：自定义函数工具与远程 MCP 工具均可受 allow-list、tool choice 与审批机制约束。
