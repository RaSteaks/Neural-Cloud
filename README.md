# Neural Cloud

基于 **Flask + D3.js** 的本地 Markdown 知识图谱可视化工具。扫描本地笔记文件，解析 `[[wiki-link]]` 双向链接，以力导向图（Force-Directed Graph）呈现知识网络。

## 功能特性

- **知识图谱可视化** — D3.js 力导向图，节点大小随文件体积动态缩放
- **Markdown / PDF 预览** — 点击节点即时预览，大文件分块传输、边加载边渲染；支持同名 PDF 内嵌预览、代码高亮（highlight.js）和数学公式（MathJax）
- **智能搜索** — 实时搜索下拉列表，不区分大小写，支持忽略 `-`、空格、下划线等分隔符的模糊匹配，支持键盘导航，点击结果自动定位并高亮节点
- **动态分组筛选** — 根据扫描路径自动生成 Filter 分组，按文件夹名称显示
- **节点交互** — 点击高亮脉冲动画，可为节点自定义颜色标记
- **Scan Path 管理面板** — 右下角齿轮按钮打开设置弹窗，在线增删扫描路径，保存后自动刷新图谱
- **配置热重载** — 修改 `config.json` 后无需重启，下次请求自动生效
- **访客界面** — 提供 `/guest` 只读访客入口，界面布局与主页面一致，可按配置控制是否显示内部文件路径
- **文件代理** — 内置图片和 PDF 代理，仅允许访问配置声明目录中的资源
- **响应式设计** — 桌面端侧边面板 + 移动端底部抽屉，适配 safe-area

## 项目结构

```
Neural-Cloud/
├── app.py                  # Flask 主应用，API 路由
├── main.py                 # 占位入口文件
├── config.json             # 本地运行配置（首次启动自动创建）
├── config.template.json    # 新环境生成 config.json 时使用的模板
├── backend/
│   └── memo_utils.py       # 文件扫描、图数据构建、配置热重载与模板配置
├── frontend/
│   ├── index.html          # 单页前端（D3.js + marked.js + DOMPurify）
│   ├── favicon.ico         # 网站图标
│   └── apple-touch-icon.png
├── pyproject.toml          # 项目依赖
└── .gitignore
```

## 快速开始

### 环境要求

- Python >= 3.14
- [uv](https://github.com/astral-sh/uv) 包管理器（推荐）

### 安装与运行

```bash
# 安装依赖
uv sync

# 启动服务
uv run app.py
```

服务启动后访问 `http://localhost:19001`

### 公网部署

默认监听地址是 `127.0.0.1`。现在服务监听、端口、鉴权和重启开关统一在 `config.json` 中管理。

示例：

```json
{
    "scan_paths": [
        "G:\\Color-appearance-models\\docs"
    ],
    "core_memory_file": "G:\\Color-appearance-models\\README.md",
    "prefer_pdf": true,
    "ui": {
        "site_title": "Neural Cloud",
        "guest_enabled": true,
        "guest_title": "",
        "guest_subtitle": "Read-only access to the knowledge graph.",
        "show_file_paths_in_guest": false
    },
    "server": {
        "host": "0.0.0.0",
        "port": 19001
    },
    "auth": {
        "username": "admin",
        "password": "change-this-password"
    },
    "allow_restart": false
}
```

配置完成后直接启动：

```bash
uv run app.py
```

说明：

- 访客界面入口是 `/guest`
- `ui.guest_enabled` 控制是否启用访客界面
- 访客界面默认与主界面保持一致布局，但隐藏设置入口和节点颜色编辑，属于只读模式
- `ui.guest_title` 和 `ui.guest_subtitle` 作为保留配置字段，可用于后续扩展访客页文案
- `ui.show_file_paths_in_guest` 控制访客界面是否显示内部文件路径
- 当 `server.host` 是 `0.0.0.0` 时，必须同时设置 `auth.username` 和 `auth.password`
- `/api/image`、`/api/pdf`、`/api/browse` 只允许访问 `config.json` 中声明的扫描目录及核心记忆文件所在目录
- `/api/restart` 默认禁用；只有把 `allow_restart` 设为 `true` 才会启用
- `/api/config` 不会向前端返回认证密码明文
- 前端 Markdown 预览已增加 HTML 清洗，避免扫描到恶意笔记时直接执行脚本

> 首次启动时，若不存在 `config.json` 会自动创建默认配置文件。
> 自动生成时会优先使用项目根目录的 `config.template.json`，因此新电脑上的配置模板会保持一致。

### 配置

在项目根目录的 `config.json`（或通过网页右下角齿轮按钮在线编辑）：

```json
{
    "scan_paths": [
        "~/your/notes/folder",
        "D:\\another\\notes\\folder"
    ],
    "core_memory_file": "~/path/to/MEMORY.md",
    "prefer_pdf": false,
    "ui": {
        "site_title": "Neural Cloud",
        "guest_enabled": true,
        "guest_title": "",
        "guest_subtitle": "Read-only access to the knowledge graph.",
        "show_file_paths_in_guest": false
    },
    "server": {
        "host": "127.0.0.1",
        "port": 19001
    },
    "auth": {
        "username": "",
        "password": ""
    },
    "allow_restart": false
}
```

| 字段 | 说明 |
|------|------|
| `scan_paths` | 要扫描的 Markdown 文件夹路径列表，支持 `~` |
| `core_memory_file` | 核心记忆文件路径，作为图谱中心节点 |
| `prefer_pdf` | 若存在同名 PDF，优先在预览面板中显示 PDF |
| `ui` | 前端界面配置，包含访客界面开关与文案 |
| `server.host` / `server.port` | 服务监听地址和端口 |
| `auth.username` / `auth.password` | 站点 Basic Auth 账号密码 |
| `allow_restart` | 是否允许通过网页调用重启接口 |

> `config.json` 已加入 `.gitignore`，不会被提交到仓库。

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端页面 |
| `/guest` | GET | 访客只读页面 |
| `/api/graph` | GET | 获取图谱节点和连接数据 |
| `/api/content?id=` | GET | 获取节点对应的 Markdown 内容 |
| `/api/content/stream?id=` | GET | 流式分块获取内容（NDJSON） |
| `/api/image?path=` | GET | 本地图片代理 |
| `/api/pdf?path=` | GET | 本地 PDF 代理 |
| `/api/config` | GET | 读取配置 |
| `/api/config` | POST | 保存配置 |
| `/api/browse` | GET | 浏览允许目录，用于设置面板选择路径 |
| `/api/restart` | POST | 按配置允许时重启服务 |

## 技术栈

- **后端**: Flask
- **前端**: D3.js v7 · marked.js · DOMPurify · highlight.js · MathJax
- **包管理**: uv
