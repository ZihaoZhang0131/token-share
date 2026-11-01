# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- 管理员：在浏览器控制台中配置上游模型服务、公开模型映射、聊天/编码接入模式、固定推理强度、用户账号、模型权限、月度额度、RPM/TPM 限制，并检查调用与审计元数据。
- 普通用户：查看自身月度用量与可用模型，创建或撤销中转 Key，按聊天或编码模式选择已授权的公开模型，并复制 OpenAI SDK、curl 或 Codex 配置示例。
- 待确认假设：管理员的配置与运行监控是最高频核心任务，普通用户自助接入是次要任务。

## Product Purpose

Token Station 是一个私有、可部署的 OpenAI Chat Completions / Responses 中转站，提供聊天与无状态编码工具调用接入。它在用户与上游模型服务之间提供安全的凭证隔离、模型权限、速率限制、月度 Token 配额、用量记账和审计能力。成功意味着管理员能清楚地完成配置与治理，普通用户能在不知道真实上游 Key 的情况下，按支持的接口边界接入模型。

## Positioning

产品不托管模型，也不保存聊天正文；它把真实上游 API Key 留在服务端，以每个用户独立、可撤销的中转 Key 和公开模型别名建立访问边界。编码模式是 API 中转能力，不是网站内 IDE，也不在服务端执行用户工具或模型生成的命令。

## Operating Context

- 管理员通过中文 Web 控制台完成首次配置、日常治理和问题排查。
- 普通用户在控制台获取中转 Key、可用模型和可复制的接入代码，然后通过 SDK、curl 或按兼容边界配置的 Codex 客户端调用 `/v1/*`。控制台中的聊天示例与编码示例分开呈现。
- 产品采用单机 Docker Compose 私有部署，由 Nginx 提供 HTTPS 与静态前端，FastAPI 提供控制面和调用面。
- 待确认假设：目标部署场景是内部团队或小规模受控用户群，而非公开售卖的多租户 SaaS。

## Capabilities and Constraints

- 必须保留现有 React SPA 的角色分流、首次登录改密、所有管理员/用户功能、API 合同、字段、权限和安全边界。
- 公开模型可设置聊天（`chat`）、编码（`responses`）或双模式（`both`），并可固定推理强度；固定档位不可被客户端覆盖，不同固定档位使用不同公开别名。模型表与编辑表单需同时说明模式和推理设置。
- 调用面提供 `POST /v1/chat/completions` 与 `POST /v1/responses`。Responses 仅支持无状态 HTTP / SSE，使用 `store=false`；客户端每轮传回完整历史与工具结果，不使用 `previous_response_id`。
- 编码工具仅支持客户端执行的 `function`、`custom` 及其 `namespace`；不开放托管工具、上游文件 ID 等私有资源引用、后台任务、WebSocket 或 `/responses/compact`。Codex 配置片段不等于所有客户端版本或工作流均已兼容。
- 接入指南按模式筛选已授权模型，给出 Python 聊天、curl 聊天、Python 编码工具循环、SSE 和 Codex 配置示例；无可用模型时明确提示授权前置条件，不伪造可用模型。
- 上游 Key 保存后只能查看末四位并替换；用户中转 Key 明文仅在创建时展示一次，最多保留 5 把有效 Key。
- 调用日志只展示元数据，不保存提示词、回答、Authorization 或完整请求头。
- 前端技术栈为 React 19、TypeScript、Vite、lucide-react 和原生 CSS，不依赖路由器或组件库。
- 页面需要支持桌面与移动 Web，保持中文界面。
- 待确认假设：允许重新组织导航、视觉层级和微文案，但不删除、弱化或改变任何现有功能与安全提示。

## Brand Commitments

- 当前产品名为 “Token Station”；在用户未批准更名之前保留。
- 语气应专业、直接、可信，安全事实必须准确，不夸大保障。

## Evidence on Hand

- 产品、安全边界、部署方式与功能说明：`README.md`。
- 控制面、调用面、技术栈与密钥生命周期：`docs/项目架构与技术栈详解.md`。
- 实际界面、角色流程与文案：`frontend/src/App.tsx`、`frontend/src/Login.tsx`、`frontend/src/AdminConsole.tsx`、`frontend/src/UserConsole.tsx`。
- 双模式接入与客户端示例：`frontend/src/IntegrationGuide.tsx`；接口与固定推理策略：`app/gateway.py`、`app/model_policy.py`。
- 上述能力记录的是当前代码边界，不代表生产部署验收或所有上游、客户端组合均已实测通过。
- 当前没有品牌 Logo、摄影素材、客户证言、性能基准或商业证明；未来设计不得虚构这些内容。

## Product Principles

1. 安全边界应在关键决策点被清楚解释，而不是只作为装饰性口号出现。
2. 高频治理任务必须易扫描、易比较、易操作，并明确显示状态和下一步。
3. 普通用户应从用量状态快速抵达“创建 Key 并完成第一次调用”。
4. 一次性秘密、危险操作、错误和空状态必须明确告知后果与恢复路径。
5. 视觉表达服务于可信与可操作性，不能牺牲密度、响应式、无障碍或性能。

