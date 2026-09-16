# 企业级交付基线

本项目的目标架构是“模块化单体 + 异步任务 + 可插拔 MCP 网关”，而不是在用户量尚未验证前拆成大量微服务。它保留当前 FastAPI、MySQL、Milvus、MinIO 和 Vue 的运行路径，并为规模、安全和团队协作增加边界。

## 已落地的基础能力

| 范畴 | 当前实现 |
| --- | --- |
| 运行环境 | `ENVIRONMENT`、`DEBUG`、日志级别和 `.env.example`；生产环境拒绝弱 JWT 密钥、调试模式、通配 CORS 与 SQLite |
| 可观测性 | `X-Request-ID`、请求耗时/状态日志、`/health` 存活检查、`/ready` 数据库就绪检查 |
| API 安全 | JWT、资源归属校验、管理员依赖、安全响应头、无缓存的 API 响应 |
| 审计 | `audit_events` 记录注册、成功登录及后续可扩展的高风险写操作；不存令牌、密码或原始健康数据 |
| 交付 | GitHub Actions 编译后端、验证生产配置守卫、构建前端 |

## 推荐部署拓扑

```text
Internet → WAF / API Gateway → Frontend CDN
                           └→ FastAPI replicas → MySQL (HA / backup)
                                                → Redis / task workers
                                                → MinIO (encrypted object storage)
                                                → Milvus
                                                → MCP Gateway → allow-listed providers
```

生产环境中 MySQL、Milvus、etcd 和 MinIO 不公开宿主机端口；仅网关暴露 TLS。密钥交由云密钥管理系统或 Vault 注入，镜像仓库、对象存储和数据库均采用独立服务账户与最小权限。

## 下一阶段必须完成的事项

1. **身份与组织**：组织/租户、成员、角色（平台管理员、机构管理员、营养师、用户、审计员）、OIDC/SAML SSO、MFA 和会话撤销。
2. **数据治理**：用户同意书版本、数据导出/删除工作流、保留期限、字段分级、加密密钥轮换和跨租户自动化测试。
3. **可靠性**：Alembic 取代轻量 DDL 迁移；Redis 队列承载模型生成和文件解析；任务幂等、重试、死信队列和限流。
4. **可观测性**：OpenTelemetry traces、Prometheus 指标、集中日志、告警和 SLO；指标避免包含用户名、报告正文和令牌。
5. **AI 治理**：提示词和知识库版本、离线评测集、工具调用审计、模型回退策略、敏感请求升级和人工抽检。
6. **发布治理**：镜像漏洞扫描、SBOM、依赖锁定、密钥扫描、数据库备份演练、蓝绿/金丝雀发布与回滚演练。

## SLO 建议

| 用户路径 | 目标 |
| --- | --- |
| 登录、读取菜单、记录饮食 | 月可用性 ≥ 99.9%，P95 < 500 ms（不含外部调用） |
| 报告解析、Agent 生成 | 接收成功率 ≥ 99.5%，异步任务可追踪、可重试、可人工接管 |
| 数据恢复 | 每日备份、恢复点目标 RPO ≤ 24 小时；恢复时间目标应在演练后确定 |

## 上线闸门

- `ENVIRONMENT=production`、`DEBUG=false`，使用长度不少于 32 的随机 `SECRET_KEY` 和精确的 HTTPS CORS 域名。
- 迁移已在预生产环境执行并通过备份恢复演练。
- 所有 MCP 外部连接完成供应商、数据最小化和人工审批策略评审。
- 红旗症状、过敏冲突、权限越界、审计完整性和故障降级均有自动化回归测试。
