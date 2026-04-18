# Neural Cloud

基于 **Flask + D3.js** 的本地 Markdown 知识图谱可视化工具。扫描本地笔记文件，解析 `[[wiki-link]]` 双向链接，以力导向图（Force-Directed Graph）呈现知识网络。

## 功能特性

- **知识图谱可视化** — D3.js 力导向图，节点大小随文件体积动态缩放
- **Markdown 流式预览** — 点击节点即时预览，大文件分块传输、边加载边渲染，支持代码高亮（highlight.js）和数学公式（MathJax）
- **智能搜索** — 实时搜索下拉列表，不区分大小写，按匹配度排序，支持键盘导航，点击结果自动定位并高亮节点
- **动态分组筛选** — 根据扫描路径自动生成 Filter 分组，按文件夹名称显示
- **节点交互** — 点击高亮脉冲动画，可为节点自定义颜色标记
- **Scan Path 管理面板** — 右下角齿轮按钮打开设置弹窗，在线增删扫描路径，保存后自动刷新图谱
- **配置热重载** — 修改 `config.json` 后无需重启，下次请求自动生效
- **文件代理** — 内置图片和 PDF 代理，浏览器内直接查看
- **响应式设计** — 桌面端侧边面板 + 移动端底部抽屉，适配 safe-area

## 项目结构

```
Neural-Cloud/
├── app.py                  # Flask 主应用，API 路由
├── main.py                 # 入口文件
├── config.json             # 扫描路径配置（启动时自动创建）
├── backend/
│   └── memo_utils.py       # 文件扫描、图数据构建、配置热重载
├── frontend/
│   ├── index.html          # 单页前端（D3.js + marked.js）
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

> 首次启动时，若不存在 `config.json` 会自动创建默认配置文件。

### 配置

在项目根目录的 `config.json`（或通过网页右下角齿轮按钮在线编辑）：

```json
{
    "scan_paths": [
        "~/your/notes/folder",
        "D:\\another\\notes\\folder"
    ],
    "core_memory_file": "~/path/to/MEMORY.md"
}
```

| 字段 | 说明 |
|------|------|
| `scan_paths` | 要扫描的 Markdown 文件夹路径列表，支持 `~` |
| `core_memory_file` | 核心记忆文件路径，作为图谱中心节点 |

> `config.json` 已加入 `.gitignore`，不会被提交到仓库。

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端页面 |
| `/api/graph` | GET | 获取图谱节点和连接数据 |
| `/api/content?id=` | GET | 获取节点对应的 Markdown 内容 |
| `/api/content/stream?id=` | GET | 流式分块获取内容（NDJSON） |
| `/api/image?path=` | GET | 本地图片代理 |
| `/api/pdf?path=` | GET | 本地 PDF 代理 |
| `/api/config` | GET | 读取配置 |
| `/api/config` | POST | 保存配置 |

## 技术栈

- **后端**: Flask
- **前端**: D3.js v7 · marked.js · highlight.js · MathJax
- **包管理**: uv