# RoundLens

RoundLens 是面向 Windows 10/11 的本地 CS2 个人对局分析器。它以问题、证据和可执行训练规则为主线，而不是把 K/D 或精彩击杀当作结论。Demo 解析、指标计算和历史记录默认只在本机完成；只有用户主动生成 AI 报告时才会向所配置的 OpenAI-compatible 服务发送经过裁剪的结构化摘要。

> 当前状态：MVP 开发中。真实 `.dem` 解析由 Awpy 主解析器与 demoparser2 补充查询接入；仓库不附带任何真实 Demo 或受版权保护的地图资源。规则影响分不是精确胜率，也不替代专业教练判断。

> 本机验证状态（2026-07-25）：Python、React 与 Rust 的静态检查、测试和构建均通过，PyInstaller sidecar 的健康检查和 JSONL 烟雾测试通过。NSIS 安装包与干净 Windows 虚拟机验收仍未完成。详见 [实施计划](docs/IMPLEMENTATION_PLAN.md)。

## 当前功能

- Tauri 2 + React + TypeScript 桌面骨架，默认深色、中英文切换、键盘可操作。
- Python JSONL Sidecar：健康检查、应用初始化、导入/扫描、解析、历史、分析与报告 RPC。
- `.dem` 流式 SHA-256、哈希去重、原文件状态与重新定位验证。
- SQLite WAL 持久化；高频数据预留 Parquet 分层目录。
- Awpy 主解析、demoparser2 补充、能力探测与缺失数据降级。
- 核心回合/交火指标、规则影响、问题合并、优势与复盘候选。
- 可分别生成确定性本地报告或完整 AI 报告；报告中心支持手动重新打开历史报告，OpenAI-compatible 输出带结构校验与安全降级。
- Windows Credential Manager 凭据桥接；API Key 不进入 SQLite、前端持久化或日志。

完整进度与未完成项见 [实施计划](docs/IMPLEMENTATION_PLAN.md)。

## 非目标

MVP 不实现完整 3D/POV/Tick 动画回放、实时比赛监控、自动下载 Demo、语音分析、云账户、多玩家档案、精确输入还原或机器学习胜率预测。

## 系统要求

最终安装目标为 Windows 10/11 x64。开发需要：

- Node.js 22+ 与 pnpm 10+
- Python 3.11 与 uv
- Rust stable、MSVC Build Tools、Windows 10/11 SDK 与 WebView2（仅桌面层）

## 开发

```powershell
corepack enable
pnpm install
uv sync --all-groups
pnpm dev
```

只运行 Sidecar：

```powershell
uv run roundlens-analyzer --data-dir "$env:LOCALAPPDATA\RoundLens"
```

标准输入每行发送一个 JSONL RPC 请求；普通日志只写 stderr。

## 检查与测试

```powershell
pnpm lint
pnpm typecheck
pnpm test
pnpm build
uv run ruff check .
uv run mypy services/analyzer/src
uv run pytest
cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml
```

也可运行 `scripts/test.ps1`。本地 Demo 回归说明见 [fixtures 说明](tests/fixtures/README.md)。默认测试不会访问真实大模型 API。

## 打包

```powershell
./scripts/build-sidecar.ps1
./scripts/build-desktop.ps1
./scripts/package-windows.ps1
```

Sidecar 使用 PyInstaller one-dir：Awpy、Polars、PyArrow 等依赖较大且包含动态库，one-dir 启动更快、漏包更容易诊断。Tauri 将其作为 external binary 打入 NSIS 安装包。目标机无需安装 Python、Node、Rust 或解析依赖。

## 数据与安全

默认数据目录是 `%LOCALAPPDATA%\RoundLens\`，包含 `database`、`parsed`、`reports`、`cache`、`logs`、`map-cache` 和 `backups`。应用只保存原 Demo 的路径与哈希，不复制或删除源 `.dem`。

API Key 只保存在 Windows Credential Manager。React 无读取 Key 的命令；只可设置、替换、清除并查询“是否已配置”。日志和导出内容会再次脱敏。完整威胁模型见 [安全说明](docs/SECURITY.md)。

## 解析能力与限制

- 解析器版本和 Demo 格式变化可能造成部分字段不可用。
- 缺失能力返回 `unavailable`/`partial`，不会伪装成数值 0，也不会进入 AI 候选问题。
- User Command 缺失时，急停等数据只能根据速度与开火事件估算，并明确标记为 `estimated`。
- 地图资源缺失时降级为事件时间线；不打包 Valve、CS2 或 FACEIT 的 Logo、雷达图和其他未授权资产。
- 内置基准是版本化的临时参考区间，不代表职业或同段位玩家真实平均值。

## 常见问题

- **找不到玩家**：填写 Demo 记分板中的玩家名称或 SteamID64。名称匹配不区分大小写，但必须在该 Demo 中唯一。
- **没有 2D 地图**：地图分析仍可完成，复盘自动显示文本时间线。
- **AI 失败**：已解析指标不会丢失，可重试或生成无 AI 报告。
- **源 Demo 被移动**：历史仍可查看；用“重新定位”选择同一文件并通过 SHA-256 校验。
- **Windows 打包失败**：确认安装 Rust `stable-msvc`、Desktop development with C++、Windows SDK 和 WebView2。

## 许可与第三方依赖

项目代码许可将在首次发布前确定。第三方依赖遵循各自许可证；Awpy、demoparser2、Tauri、React、Polars 与 PyArrow 不代表 Valve 或其关联方背书。Counter-Strike 与相关名称归其权利人所有。
