# 🍎 AI 营养师 Agent

基于 **LangGraph 多 Agent 协作** 的智能个性化营养饮食管理系统。

上传体检报告 → 四个 AI Agent 依次协作(健康分析 → 营养规划 → 食谱生成 → 质量审核)→ 输出可直接执行的多日三餐方案,并经**人工确认闸门(HITL)**放行。

---

## 1. 核心功能

| 功能模块 | 说明 |
| --- | --- |
| 📊 健康报告解析 | 上传体检报告文本,自动抽取血糖/血压/尿酸/胆固醇/甘油三酯并分级评估 |
| 🧠 多 Agent 协作 | LangGraph 编排 4 个 Agent;开启 HITL 闸门时审核不通过交由人工决策,关闭时自动回边重做(最多 3 轮) |
| 📚 向量知识库 | **BGE 中文向量模型** + **Milvus** 向量库,存储 **28 条**营养学知识(覆盖血糖/血压/尿酸/血脂/膳食指南/慢性肾病/老年/孕期/肿瘤/地中海饮食等 20+ 主题),每条标注**证据等级(A/B/C)**,语义检索增强生成(RAG) |
| 📎 对象存储 | **MinIO** 存储上传的体检报告文件(PDF/文本),支持预览与文本抽取 |
| 🍎 多日个性化食谱 | 结合体检指标 + 口味偏好 + 目标热量,生成 **一周 / 一个月 / 自定义(最长 90 天)** 菜单;周/月方案按 **7 天轮换**主菜避免重复,并在方案中**标注知识库依据与证据等级**;结构化落库 `recipes / daily_menus / meals / dishes` |
| ⛨ 人工确认闸门(HITL) | 食谱生成后进入「待人工确认」状态,用户可**确认采用**或**请求修订**(后端据意见重做),杜绝无监督自动放行 |
| 👤 用户偏好管理 | 喜爱食材、忌口食材、偏好菜系、过敏食材、健康目标,生成时自动规避 |
| 🔐 JWT 认证 | OAuth2 密码模式 + bcrypt 密码哈希 |
| 🖥 Vue3 前端 | Element Plus + TailwindCSS + Pinia,含控制台/报告/食谱/偏好/个人中心 |

## 2. 技术栈

**后端**:Python 3.10+ · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · LangChain · LangGraph · **BGE(sentence-transformers)** · **Milvus** · **MinIO** · python-jose · bcrypt
**数据库**:MySQL 8.0(默认,开箱即用)/ SQLite(自动回退兜底)
**向量化**:BGE 本地模型(BAAI/bge-small-zh-v1.5,512 维,默认)· 可选 OpenAI 兼容 embedding
**向量库**:Milvus 2.4(默认)· 进程内检索(兜底)
**对象存储**:MinIO(默认)· 本地磁盘(兜底)
**部署**:Docker Compose(etcd + MinIO + Milvus + MySQL + 后端 + 前端)
**前端**:Vue 3.4 · Vite 5 · Element Plus · TailwindCSS 3.4 · Pinia · Vue Router · Axios

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────┐
│  前端层  Vue3 + Vite + Element Plus + Pinia             │
│          (Nginx / Vite Dev Server 反向代理 /api)         │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP (REST + JWT)
┌──────────────────────────▼──────────────────────────────┐
│  API 网关层  FastAPI  /api/*                            │
│  认证 · 用户 · 健康报告 · 食谱 · 口味偏好                │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  AI Agent 层  LangGraph 状态图                           │
│  健康分析 → 营养规划 → 食谱生成 → 质量审核               │
│                              └─不通过─→ 回到食谱生成      │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  数据层  关系库(SQLite/MySQL)  ·  Milvus 向量库          │
│          · MinIO 对象存储  ·  BGE 本地向量化            │
│          + LLM(OpenAI 兼容协议:DeepSeek/OpenAI/Qwen)     │
└─────────────────────────────────────────────────────────┘
```

### 数据与向量链路

```
体检报告 ──► MinIO 对象存储(文件) ──► 文本抽取 ──► 规则解析引擎
                                                    │
营养学知识 ──► BGE 向量化(512维) ──► Milvus 向量库 ──┤
                                                    ▼
                           LangGraph 多 Agent 工作流(RAG 检索增强生成)
```

### Agent 工作流

```
        指标分析完成        营养方案确定       食谱初稿生成
健康分析 ────────► 营养规划 ────────► 食谱生成 ────────► 质量审核
                      ▲                                    │
                      │         审核不通过(最多重做3轮)      │
                      └────────────────────────────────────┘
                                                           │
                                              审核通过 ─────► 完成
```

| Agent | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| 健康分析 Agent | 解析体检指标、评估健康状况、定位饮食关注点 | 体检报告 + 指标 | 健康分析报告 |
| 营养规划 Agent | 结合知识库制定营养方案、供能比、三餐分配 | 健康分析 + 知识库 | 营养需求方案 |
| 食谱生成 Agent | 输出结构化三餐食谱(规避忌口/过敏) | 营养方案 + 偏好 | 食谱 JSON |
| 质量审核 Agent | 四个维度审核,不通过则给出修改意见并触发返工 | 食谱 + 健康分析 | 审核结论 |

### 多日菜单(HITL 闸门)

```
生成请求(health_report_id, period=week|month|custom, days=1~90, start_date?)
        │
        ▼
LangGraph 工作流(第 1 天跑完整四 Agent;后续天复用指标、仅做按天轮换生成)
        │  产出:每日 meals/dishes + 当日审核结果 + 知识库依据(来源/证据等级)
        ▼
落库  recipes(计划) ─ 1:N ─ daily_menus(天) ─ 1:N ─ meals(餐次) ─ 1:N ─ dishes(菜品)
        │  recipes 额外记录 cycle_type(week/month/custom) 与 cycle_label
        ▼
HUMAN_REVIEW_GATE=true ──► 状态 = pending_review(待人工确认)
        │                         ├─ 确认采用   ──► status=active(生效)
        │                         └─ 请求修订   ──► 据意见重做 ──► 回到 pending_review
        ▼
HUMAN_REVIEW_GATE=false ─► 沿用旧自动回边(审核不通过自动重做,最多 3 轮)后直接生效
```

- **方案周期(新增)**:前端生成对话框提供 **一周(7 天) / 一个月(30 天) / 自定义(1~90 天)** 三种周期;`period=week|month` 由后端换算天数,`custom` 沿用 `days`(上限 `MENU_MAX_DAYS=90`)。食谱计划落库 `cycle_type` 与可读 `cycle_label`,卡片与详情页均展示周期标签,**请求修订时自动沿用原周期**。
- **结构化多日数据**:`recipes`(一份多日计划,含 `days`/`start_date`/`cycle_type`/`cycle_label`/`review_status`)、`daily_menus`(一天一条,含当日三大营养素汇总)、`meals`、`dishes` 全部真实落库,前端按天切换渲染。
- **按天多样性(新增)**:规则引擎模板内置 **7 天轮换菜品池**,周/月方案每日主菜不重复(月方案即周模式循环);自动净化任何健康状况禁忌食材(如高尿酸剔除海鲜变体,改非海鲜晚餐);LLM 模式额外注入「与相邻天轮换」指令。
- **知识库依据标注(新增)**:营养方案与食谱 tips 均引用召回知识的**来源文献 + 证据等级(A/B/C)**,详情页「知识库依据」标签页逐条展示 `来源 · 证据等级 · 内容`,便于溯源。
- **人工确认闸门**:食谱默认进入 `pending_review`,必须人工**确认采用**才生效;用户也可**请求修订**,后端将意见作为重做指令重新生成(记录 `revision_count`),防止无监督自动放行。关闭 `HUMAN_REVIEW_GATE` 时回退为旧版自动重做。
- 相关接口:`POST /api/recipes/generate`、`GET /api/recipes/{id}/menus`、`POST /api/recipes/{id}/review/approve`、`POST /api/recipes/{id}/review/request-revision`。

## 4. 目录结构

```
ai-nutritionist-agent/
├── backend/                        # 后端项目
│   ├── app/
│   │   ├── main.py                 # FastAPI 主应用(含启动初始化)
│   │   ├── core/                   # 核心配置
│   │   │   ├── config.py           # 应用配置(读取 .env)
│   │   │   ├── database.py         # 数据库连接(SQLite/MySQL 自适应)
│   │   │   └── security.py         # JWT 认证 + bcrypt 密码哈希
│   │   ├── models/                 # SQLAlchemy 数据模型
│   │   │   ├── user.py             # 用户(含身高体重年龄)
│   │   │   ├── health_report.py    # 健康报告
│   │   │   └── recipe.py           # 偏好/食谱/每日菜单/餐次/菜品
│   │   ├── schemas/                # Pydantic 校验模式
│   │   ├── api/                    # REST 路由
│   │   │   ├── auth.py             # 注册/登录
│   │   │   ├── users.py            # 用户资料(含 BMI)
│   │   │   ├── health_reports.py   # 报告上传/解析/CRUD(兼容文件)
│   │   │   ├── recipes.py          # AI 生成食谱/多日菜单/HITL 审核闸门
│   │   │   ├── preferences.py      # 口味偏好 CRUD
│   │   │   └── files.py            # 文件上传/下载(MinIO / 本地)
│   │   ├── services/               # 业务服务
│   │   │   ├── health_report_parser.py  # 体检报告规则解析引擎
│   │   │   ├── document_text.py        # 文件文本抽取(txt/md/pdf)
│   │   │   ├── menu_service.py         # 多日菜单编排 + 落库 + 序列化
│   │   │   ├── knowledge_base.py        # 知识库(Milvus + 内存兜底)
│   │   │   ├── embeddings.py            # 向量化(BGE / OpenAI / 哈希兜底)
│   │   │   ├── minio_storage.py         # 对象存储(MinIO + 本地磁盘兜底)
│   │   │   └── recipe_generator.py      # 食谱规整/模板兜底/规则审核
│   │   └── agents/
│   │       └── workflow.py         # LangGraph 四 Agent 工作流
│   ├── knowledge_base/
│   │   └── default_data.py         # 13 类营养学知识种子数据
│   ├── scripts/
│   │   └── reset_admin.py          # 默认管理员密码重置/自检工具
│   ├── requirements.txt            # 完整依赖(含 BGE / Milvus / MinIO)
│   ├── requirements-lite.txt       # 轻量依赖(不含 BGE/Milvus/MinIO)
│   ├── Dockerfile                  # 后端镜像(BGE 预载 + HFT 镜像)
│   ├── .env.example                # 环境变量模板
│   └── data/ · uploads/            # 运行时生成(SQLite / 本地文件兜底)
├── frontend/                       # 前端项目
│   ├── src/
│   │   ├── main.js · App.vue
│   │   ├── assets/main.css         # Tailwind + 全局样式
│   │   ├── router/index.js         # 路由 + 登录守卫
│   │   ├── stores/user.js          # Pinia 用户状态
│   │   ├── api/index.js            # Axios 封装(拦截器)
│   │   ├── utils/index.js          # 格式化 / 指标配色
│   │   └── views/                  # 11 个页面
│   │       ├── Layout.vue          # 侧边栏布局 + Agent 状态
│   │       ├── Dashboard.vue       # 控制台
│   │       ├── Login.vue / Register.vue
│   │       ├── HealthReports.vue / HealthReportDetail.vue
│   │       ├── Recipes.vue / RecipeDetail.vue
│   │       ├── Preferences.vue / Profile.vue / NotFound.vue
│   ├── package.json · vite.config.js
│   ├── tailwind.config.js · postcss.config.js · index.html
├── sample_reports/                 # 10 份三甲医院格式体检报告样本(含生成器与解析校验)
│   ├── report_01~10_*.txt          # 可直接上传的报告
│   ├── _generate_reports.py        # 报告生成器(结构化数据 + 版式模板)
│   ├── verify_reports.py           # 用后端解析器校验 6 项指标抽取正确性
│   └── README.md                   # 报告一览 + 版式与解析器约束说明
├── sql/init.sql                    # MySQL 初始化脚本
├── docker-compose.yml              # 全套容器编排(etcd/MinIO/Milvus/MySQL/backend/frontend)
├── start.py                        # 一键启动(本地后端 + 前端)
└── README.md
```

## 5. 快速开始

### 5.1 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

# 安装依赖(轻量环境可改用 requirements-lite.txt:BGE/Milvus/MinIO 将自动降级)
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env     # Windows: copy .env.example .env
# 编辑 .env,填入 OPENAI_API_KEY(支持 DeepSeek / OpenAI / 通义千问)

# 启动
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后自动完成:建表 → 创建默认管理员 → 写入营养知识库。

- 后端 API:<http://localhost:8000>
- 交互式文档:<http://localhost:8000/docs>

### 5.2 前端

```bash
cd frontend
npm install
npm run dev
```

- 前端地址:<http://localhost:5173>
- 已在 `vite.config.js` 中配置 `/api` 代理到 `http://localhost:8000`,无需处理跨域

### 5.3 一键启动(本地)

```bash
python start.py
```

### 5.4 Docker 一键部署(推荐)

无需本地安装 Python/Node,使用 Docker Compose 启动完整链路(BGE 向量化 + Milvus + MinIO + MySQL + 后端 + 前端):

```bash
# 在项目根目录执行
docker compose up -d --build
```

构建完成后访问:

- 前端(nginx,已内置 `/api` 反代):<http://localhost:18080>
- 后端 API 文档:<http://localhost:8000/docs>
- MinIO 控制台:<http://localhost:19001>(账号 `minioadmin` / `minioadmin`)
- MySQL:`localhost:13306`(账号 `ai_user` / `ai_password`,库 `ai_nutritionist`)

> **端口说明**:为避免与宿主既有服务冲突,本编排把 MySQL 宿主端口映射为 `13306`、MinIO 映射为
> `19000/19001`(宿主 3306 常被本机 MySQL 服务占用,9000/9001 常被其它 MinIO 占用)。
> 容器内部仍是标准端口,`backend` 通过 `mysql:3306` / `minio:9000` 访问,无需任何改动;
> 若你的机器上述端口空闲,可按需改回 `3306:3306` / `9000:9000` / `9001:9001`。

常用命令:

```bash
docker compose ps                 # 查看服务状态
docker compose logs -f backend    # 查看后端日志(启动时会自动建表 + 连接 Milvus + 写入知识库)
docker compose down               # 停止并移除容器(数据保留在 named volumes)
docker compose down -v            # 连同数据卷一并清除
```

> 说明:首次构建后端镜像会下载 BGE 模型(经 `HF_ENDPOINT=https://hf-mirror.com` 镜像加速)并安装 PyTorch,
> 镜像较大、耗时较长,属正常现象。若构建机无法访问 HuggingFace,模型会在容器内首次调用时尝试下载,
> 否则自动降级为哈希向量化(RAG 召回精度下降但不影响功能)。

### 5.5 测试账号

| 用户名 | 密码 |
| --- | --- |
| `admin` | `admin123` |

### 5.6 部署到 PocketBay(公网托管)

线上地址:<https://ai-nutritionist-agent.pocketbay.app>(首次访问会显示「应用正在休眠」,点「唤醒并继续」即可)

平台会自动识别本仓库为**一个 Python 应用**(`frontend/` + `backend/` 同一主机),无需拆项目、无需自写 Dockerfile。
托管环境下本项目会自动做两处适配(本地与 Docker 行为**不变**):

| 平台注入 | 本项目的自适应行为 |
| --- | --- |
| `POCKETBAY_DATA_DIR`(持久卷 `/data`) | `DATA_DIR` 与 `DATABASE_URL` 均指向该卷,数据库自动切为**持久卷上的 SQLite**(不依赖外部 MySQL) |
| `PORT` | `python -m app.main` 入口读取 `PORT` 并绑定 `0.0.0.0`;`EMBEDDING_BACKEND=auto` 在平台降级为 `hash` 向量化,保证秒级启动 |

> 说明:平台托管库仅支持 PostgreSQL,本项目源库为 MySQL,**无法直接迁移**,故托管实例使用持久卷 SQLite。
> 如需恢复 BGE 语义检索,在平台可承受内存的前提下把 `EMBEDDING_BACKEND` 显式设为 `bge` 后重新部署。

## 6. 环境变量(.env)

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `mysql+pymysql://ai_user:ai_password@localhost:3306/ai_nutritionist?charset=utf8mb4` | 默认 MySQL(与 docker-compose 凭据一致);裸机无 MySQL 时 `start.py` 自动回退 SQLite;也可显式覆盖为 SQLite 或自定义 MySQL |
| `SECRET_KEY` | dev 占位 | JWT 签名密钥,**生产环境必须更换** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 1440 | Token 有效期(分钟) |
| `OPENAI_API_KEY` | 空 | LLM 密钥。**留空时系统自动进入规则引擎模式,功能完整可用** |
| `OPENAI_BASE_URL` | `https://api.deepseek.com/v1` | 兼容 OpenAI 协议的服务地址 |
| `LLM_MODEL` | `deepseek-chat` | 模型名 |
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | BGE 本地向量模型;可选 `bge-base-zh-v1.5`(768) / `bge-large-zh-v1.5`(1024) |
| `EMBEDDING_DIM` | `512` | 须与所选 BGE 模型维度一致 |
| `OPENAI_EMBEDDING_MODEL` | 空 | 可选;填写后优先级高于 BGE,调用 OpenAI 兼容 embedding |
| `EMBEDDING_BACKEND` | `auto` | 向量化后端:`auto` / `bge` / `openai` / `hash`。`auto` 在本地与 Docker 走 BGE;在托管平台(注入 `POCKETBAY_DATA_DIR`)自动降级为 `hash`,避免启动加载 torch/BGE 造成启动超时或 OOM |
| `VECTOR_DB_TYPE` | `milvus` | 向量库:`milvus`(需 Milvus 服务)/ `memory`(进程内,无需外部服务) |
| `MILVUS_HOST` / `MILVUS_PORT` | `localhost` / `19530` | Milvus 连接地址(Docker 内为 `milvus:19530`) |
| `MINIO_ENDPOINT` | 空 | 对象存储地址;留空则使用本地磁盘 `data/uploads` 兜底;Docker 内为 `minio:9000` |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_BUCKET` | `minioadmin` / `minioadmin` / `ai-nutritionist-uploads` | MinIO 凭证与桶名 |
| `MAX_REVIEW_ITERATIONS` | 3 | 质量审核最大返工轮次 |
| `CORS_ORIGINS` | localhost:5173/18080 等 | 允许的前端来源 |

### 数据库说明(默认 MySQL)

默认使用 **MySQL 8.0**(与 `docker-compose.yml` 中 `mysql` 服务的库名/账号一致):

```bash
# 方式一(推荐):Docker 一键起 MySQL + 后端,后端自动连 mysql:3306
docker compose up -d --build

# 方式二:裸机已有 MySQL,先初始化库与账号(与默认凭据一致)
mysql -u root -p < sql/init.sql
# 或自行建库建号后,在 backend/.env 覆盖 DATABASE_URL

# 方式三:不想装 MySQL —— 直接用 SQLite(显式覆盖)
# DATABASE_URL=sqlite:///./data/ai_nutritionist.db
```

> 裸机执行 `python start.py` 时,程序会**自动探测本地 MySQL**:可达则用 MySQL(默认),
> 不可达则自动回退 SQLite 并打印提示,保证「开箱即用」。

## 7. API 一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 登录,返回 JWT |
| GET/PUT | `/api/users/me` | 获取 / 更新当前用户资料(含 BMI) |
| POST | `/api/health-reports/` | 上传体检报告并自动解析 |
| GET | `/api/health-reports/` | 报告列表 |
| GET | `/api/health-reports/{id}` | 报告详情(含指标明细与评估) |
| DELETE | `/api/health-reports/{id}` | 删除报告 |
| POST | `/api/recipes/generate` | **运行多 Agent 工作流生成食谱** |
| GET | `/api/recipes/` `/{id}` | 食谱列表 / 详情(含三餐、审核、Agent 日志) |
| DELETE | `/api/recipes/{id}` | 删除食谱 |
| GET/POST | `/api/preferences/` | 口味偏好列表 / 新增 |
| DELETE | `/api/preferences/{id}` | 删除偏好 |
| GET | `/health` | 健康检查(含 LLM 与知识库状态) |

## 8. 设计说明与工程取舍

原始项目文档基于 MySQL + OpenAI 编写,本实现为保证「**开箱即用、无外部依赖也能跑通全链路**」做了以下工程化处理,功能对齐文档:

| 项 | 文档方案 | 本实现 | 原因 |
| --- | --- | --- | --- |
| 数据库 | MySQL 8.0 | **默认 MySQL 8.0(与文档一致),无 MySQL 时自动回退 SQLite** | Docker 一键起 MySQL;裸机 `start.py` 探测不可达时自动回退,兼顾「与文档一致」和「开箱即用」;`sql/init.sql` 与 ORM 完全兼容 MySQL(枚举用 VARCHAR+CHECK 而非原生 ENUM) |
| LLM | 必须 OpenAI Key | **可选**。未配置时自动进入规则引擎模式 | 无 Key 时依然能完整演示「解析→规划→生成→审核→返工」全流程 |
| Embedding | OpenAI Embeddings | **BGE 本地向量模型**(默认,零 Key、可离线),可选 OpenAI | 本地推理、无外部依赖,适合中文营养学语料;可用 `EMBEDDING_MODEL` 切换 bge-base/large |
| 向量库 | ChromaDB | **Milvus 2.4**(默认),**不可用时自动降级进程内向量检索** | 生产级向量库,支持 IVL_FLAT 索引;降级后检索接口不变 |
| 对象存储 | 无 | **MinIO**(默认),**不可用时自动降级本地磁盘** | 上传的体检报告(txt/md/pdf)统一经对象存储保存与预览;降级后接口不变 |
| 部署 | 手动起服务 | **Docker Compose 一键编排**(etcd/MinIO/Milvus/MySQL/backend/frontend) | 一条命令拉起完整生产级链路 |
| 密码哈希 | passlib[bcrypt] | 直接使用 `bcrypt` 库 | passlib 1.7.4 与 bcrypt 4.1+/5.x 存在兼容问题 |
| 审核规则 | 仅 LLM 判断 | 规则引擎 + LLM 双重校验 | 规则模式无需 Key 也能保证审核环节真实生效 |
| 前端响应解包 | 组件内 `res.data.data` | 拦截器统一解包 | 修正原文档示例中数据层级不一致的问题 |

### 审核假阳性修复

初版规则审核对整个食谱 JSON 做关键词匹配,会把「避免含糖饮料」这类**建议文本**误判为实际违规食材,导致所有食谱都被退回重做。现已修正为**仅检查真实菜品名 / 食材 / 菜品描述**,审核结果与实际情况一致。

## 9. 完整验证流程

```
注册/登录 → 上传体检报告 → 自动解析指标 → 新增口味偏好 →
点击「AI 生成食谱」→ 四 Agent 依次执行 → 审核通过 → 查看食谱详情
```

实测(无 LLM Key 的规则引擎模式)输入指标 `血糖 7.4 / 血压 148/95 / 尿酸 486 / 总胆固醇 6.3 / 甘油三酯 2.6`:

- 解析出 5 项指标,5 项异常,自动生成风险标签
- 目标热量按 Mifflin-St Jeor 公式估算为 2300 kcal
- 知识库召回 4 条营养学知识作为 RAG 依据(每条带来源与证据等级 A/B/C),并在方案与食谱中标注
- 生成 4 餐次、总热量 2018 kcal 的食谱,审核**第 1 轮即通过**
- Agent 日志完整记录每一步执行情况

## 10. 常见问题

**Q: 如何更换 LLM?**
A: 修改 `backend/.env` 中的 `OPENAI_BASE_URL` 与 `LLM_MODEL`。DeepSeek、OpenAI、通义千问(兼容模式)均已验证可用。

**Q: 一定要配置 API Key 吗?**
A: 不需要。未配置时自动使用内置规则引擎,完整走通四 Agent 工作流,只是食谱内容来自营养学模板库而非大模型生成。

**Q: 知识库显示 `memory` 后端?**
A: 说明 Milvus 未能连接,已自动降级为进程内向量检索,功能不受影响。请确认 `VECTOR_DB_TYPE=milvus` 且 Milvus 服务可访问(`MILVUS_HOST`/`MILVUS_PORT` 正确)。

**Q: 健康检查里 `embedding_provider` 显示 `hash`?**
A: 说明 BGE 模型未能加载(sentence-transformers 未安装或模型下载失败),已降级为哈希向量化。Docker 镜像已预载 BGE;本地环境请 `pip install sentence-transformers` 并确保能下载 `BAAI/bge-small-zh-v1.5`(国内可设 `HF_ENDPOINT=https://hf-mirror.com`)。

**Q: 上传的文件存在哪里?**
A: 配置了 `MINIO_ENDPOINT` 时存入 MinIO 桶 `ai-nutritionist-uploads`;未配置时存入本地 `backend/data/uploads`,两者均可通过 `/api/files/{key}` 访问,接口一致。

**Q: 用 admin / admin123 登录却提示「用户名或密码错误」?**
A: 后端与默认账号本身没有问题,绝大多数情况是**浏览器自动填充了旧的凭据**——同一台机器上 `localhost:8080`(或 `localhost:5173`)曾跑过别的项目,浏览器按域名保存并自动填入了那个项目的密码,于是用户名看着是 `admin`、实际提交的密码不是 `admin123`。
排查步骤:
1. 在密码框里**手动全选删除后重新输入** `admin123`(不要依赖自动填充),再登录。登录页已加 `autocomplete` 防护,且登录失败会自动清空密码框,避免旧密码被反复提交。
2. 仍不行时,命令行直连后端自证账号是否正常:
   ```bash
   curl -X POST http://localhost:8000/api/auth/login \
     -d "username=admin&password=admin123"
   # 返回 {"access_token":"..."} 说明账号与密码完全正常,问题在浏览器端
   ```
3. 确实忘记/改乱过密码时,用内置脚本重置:
   ```bash
   docker exec ain-backend python scripts/reset_admin.py            # 重置为 admin123
   docker exec ain-backend python scripts/reset_admin.py --check    # 只看状态不改动
   docker exec ain-backend python scripts/reset_admin.py --password 新密码
   ```
4. 可用带时间戳的后端日志确认请求到底来自哪里(`172.21.0.7` 是 nginx/浏览器,`172.21.0.1` 是宿主机命令行):
   ```bash
   docker logs -t ain-backend | grep auth/login
   ```

**Q: Docker 部署时后端一直重启?**
A: 后端以 `restart: on-failure` 运行,且 `depends_on` 等待 MySQL/Milvus/MinIO 健康。Milvus 首次启动较慢(约 1~2 分钟),属正常;若仍异常请用 `docker compose logs backend` 排查(常见为 Milvus 未就绪或环境变量缺失)。

**Q: 前端提示「无法连接后端服务」?**
A: 本地开发:确认后端已在 8000 端口启动,Vite 已配置 `/api` 代理(前端 5173)。Docker:前端经 nginx 反代 `backend:8000`,确认 `docker compose ps` 中 backend 状态为 healthy/running。

**Q: 数据库连接失败?**
A: 若使用 MySQL/Docker,请确认 `DATABASE_URL` 正确且 MySQL 已就绪;或直接删除该配置项回退 SQLite。
