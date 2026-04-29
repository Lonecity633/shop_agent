# Repository Guidelines

## 项目结构与模块组织
- `app/` 是 FastAPI 后端，按分层组织：`api/routers`（接口）、`crud/`（数据访问）、`models/`（SQLAlchemy 模型）、`schemas/`（Pydantic 数据结构）、`core/`（配置与安全）、`db/`（会话与初始化）。
- `frontend/` 是 Vue 3 + Vite 前端，核心目录包括 `src/views`、`src/components`、`src/stores`、`src/api`。
- `sql/` 存放手工迁移脚本（按版本追加 `.sql` 文件）。
- 根目录运维文件：`docker-compose.yml`、`requirements.txt`、`.env.example`、`README.md`。

## 构建、测试与开发命令
- `docker compose up -d`：启动本地 MySQL 和 Redis 依赖。
- `conda activate env && pip install -r requirements.txt`：初始化后端环境。
- `uvicorn app.main:app --reload`：本地启动后端 API（`http://127.0.0.1:8000`）。
- `cd frontend && npm install && npm run dev`：启动前端开发服务。
- `cd frontend && npm run build`：构建前端生产包。
- `cd frontend && npm run preview`：本地预览构建结果。

## 代码风格与命名规范
- Python 遵循 PEP 8，使用 4 空格缩进；模块/函数用 `snake_case`，类名用 `PascalCase`。
- 同一业务在后端多层文件尽量保持同名（例如 `product.py` 在 router/crud/schema/model 中对应）。
- Vue 单文件组件使用 `PascalCase` 文件名（如 `ProductList.vue`），工具模块使用 `camelCase` 或简洁小写（如 `request.js`）。
- 保持统一接口返回结构：`{ "message": "...", "data": ... }`。

## 测试指南
- 当前仓库未提交自动化测试套件。每次改动都应在 PR 中提供可复现的验证步骤。
- 提交前最低检查：后端可通过 `uvicorn app.main:app --reload` 正常启动，前端可通过 `npm run build` 构建成功。
- 新增后端测试时，建议命名为 `tests/test_<feature>.py`，优先覆盖 API 和 CRUD 行为。

## 提交与 Pull Request 规范
- 当前历史提交较少（仅 `first commit`），建议使用清晰的 Conventional Commits，例如 `feat(order): add refund status filter`。
- 每个 commit 聚焦单一变更点，并在描述中标明影响范围（如 `app/api/routers`、`frontend/src/views`、`sql/`）。
- PR 需包含：变更目的、关键改动、本地验证命令与结果、关联 issue；前端改动需附截图。

## 安全与配置提示
- 本地开发先将 `.env.example` 复制为 `.env`，不要提交真实密钥、密码或令牌。
- `sql/` 中迁移脚本应追加新文件，不要重写历史脚本，确保可审计与可回滚。
