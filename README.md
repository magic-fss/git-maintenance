<div align="center">

# 🚀 GitHub 仓库维护工具 v2.1

**企业级 Git 仓库运维 CLI | 全流程可视化交互 | 智能 .gitignore 生成**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)](https://python.org)
[![Rich](https://img.shields.io/badge/Rich-13%2B-green?logo=python)](https://github.com/Textualize/rich)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/Code%20Style-Black-black)](https://github.com/psf/black)

</div>

---

## 📋 目录

- [功能概览](#-功能概览)
- [安装指南](#-安装指南)
- [快速开始](#-快速开始)
- [功能详解](#-功能详解)
- [项目架构](#-项目架构)
- [技术亮点](#-技术亮点)
- [常见问题](#-常见问题)
- [开源协议](#-开源协议)

---

## ✨ 功能概览

| 编号 | 功能模块 | 说明 |
|:---:|:---|:---|
| 1 | 📤 **上传本地项目** | 初始化仓库 → 配置用户信息 → 生成 .gitignore → 首次推送 |
| 2 | 🔄 **同步本地更改** | add → commit → pull --rebase → push 完整闭环 |
| 3 | 🗑️ **清空远程仓库** | 危险操作三级确认机制，彻底清空分支所有文件 |
| 4 | 👤 **Git 用户信息** | 全局 user.name / user.email 检查与修改 |
| 5 | 🛡️ **生成 .gitignore** | 智能检测技术栈（Python/Node/Java/Go 等 8 种）并生成模板 |
| 6 | 🌿 **分支管理** | 切换 / 新建 / 追踪远程分支，可视化分支列表 |
| 7 | ⬇️ **拉取远程更新** | git pull --rebase 指定分支，冲突预警 |
| 8 | 📊 **仓库仪表盘** | 实时展示分支信息、同步状态、工作区变更、Diff 统计 |

---

## 📦 安装指南

### 环境要求

- Python **3.9+**
- Git **2.30+**
- 终端支持 Unicode 和真彩色（推荐 Windows Terminal / iTerm2 / Kitty）

### 方式一：pip 安装（推荐）

```bash
# 克隆仓库
git clone https://github.com/magic-fss/git-maintenance.git
cd git-maintenance

# 创建虚拟环境（可选但推荐）
python -m venv venv
source venv/bin/activate      # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 运行
python upload_to_github_rich.py
```

### 方式二：pyproject.toml 现代构建

```bash
pip install -e .

# 安装后可直接使用命令
grt
# 或
github-tool
```

---

## 🚀 快速开始

```bash
$ python upload_to_github_rich.py
```

启动后将看到主菜单：

```
┌─────────────────────────────────────────────────────────┐
│              🚀 GitHub 仓库维护工具                      │
│                      v2.1 企业级重构版                   │
└─────────────────────────────────────────────────────────┘

▶ 功能菜单
──────────────────────────────────────────────────────────
┌────┬──────────────────────┬────────────────────────────┐
│ 编号│ 功能                 │ 说明                       │
├────┼──────────────────────┼────────────────────────────┤
│  1 │ 📤  上传本地项目      │ 初始化仓库 → 首次推送       │
│  2 │ 🔄  同步本地更改      │ add → commit → pull → push │
│ ...│ ...                  │ ...                        │
└────┴──────────────────────┴────────────────────────────┘
```

输入对应编号即可进入工作流，全程交互式引导，支持 `q` 随时返回菜单。

---

## 🔍 功能详解

### 1. 📤 上传本地项目到 GitHub

适合首次将本地项目推送到远程仓库：

1. **路径选择** — 输入本地项目目录（支持相对/绝对路径）
2. **用户信息检查** — 自动检测 Git 全局配置，未设置时强制引导填写
3. **智能 .gitignore** — 扫描目录文件后缀，自动匹配技术栈模板
4. **仓库初始化** — 自动 `git init`（已存在则跳过）
5. **远程配置** — 输入 GitHub HTTPS/SSH 地址，支持覆盖已有 origin
6. **分支选择与推送** — 选择或新建分支，自动预同步后推送

### 2. 🔄 同步本地更改

日常开发推送的标准工作流：

- 自动展示 **仓库仪表盘**（当前分支、ahead/behind、未跟踪文件数）
- **变更预览树** — 分类展示已暂存 / 未暂存 / 未跟踪文件
- **Diff 统计** — 文件级变更量可视化表格
- 自动 `git add .` → 自定义提交信息 → `pull --rebase` → `push`

### 3. 🗑️ 清空远程仓库（危险操作）

> ⚠️ **三级确认机制**：确认理解风险 → 输入验证码 `DELETE` → 最终推送确认

- 临时克隆仓库到本地空目录
- 删除所有非 `.git` 文件并提交
- 推送后自动清理临时目录
- 操作不可逆，请谨慎使用

### 4. 👤 Git 用户信息管理

- 读取全局 `user.name` 与 `user.email`
- 支持增量更新（留空保持原值）
- 空值强制校验，防止提交记录身份缺失

### 5. 🛡️ 智能 .gitignore 生成

支持自动检测的技术栈：

| 技术栈 | 检测依据 | 生成规则 |
|:---|:---|:---|
| Python | `.py` 文件 | `__pycache__`, `.env`, `venv/` |
| Node.js | `.js/.ts` 或 `node_modules` | `node_modules/`, `dist/`, `*.log` |
| Java | `.java/.class` | `target/`, `*.jar` |
| Go | `.go` | `bin/`, `vendor/` |
| Rust | `.rs` | `target/`, `Cargo.lock` |
| C/C++ | `.c/.cpp/.h` | `*.o`, `build/` |
| PHP | `.php` | `vendor/`, `composer.lock` |
| Jupyter | `.ipynb` | `.ipynb_checkpoints/` |

同时内置 IDE/OS 通用规则（`.idea/`, `.vscode/`, `.DS_Store`）及密钥保护规则（`*.pem`, `.env.local`）。

### 6. 🌿 分支管理

- 可视化展示本地 / 远程分支列表
- 自动标注当前分支
- 支持新建分支、切换已有分支、追踪远程分支

### 7. ⬇️ 拉取远程更新

- 选择目标分支后执行 `git pull --rebase origin <branch>`
- 失败时提供冲突解决指引

### 8. 📊 仓库仪表盘

实时展示：

```
┌─────────────────────────────────────────────────────────┐
│ 📊 仓库仪表盘                                            │
├──────────────────────────┬────────────────────────────────┤
│ 🌿 分支信息              │ 📁 工作区                      │
├──────────────────────────┼────────────────────────────────┤
│ 当前分支    main         │ 已修改     3                   │
│ 本地分支    4            │ 未跟踪     1                   │
│ 远程分支    2            │ 路径       /path/to/project    │
│ 同步状态    ↑2 ↓1        │                                │
│ 最后提交    a1b2c3d      │                                │
└──────────────────────────┴────────────────────────────────┘
```

---

## 🏗️ 项目架构

```
github-repo-toolkit/
├── upload_to_github_rich.py    # 主程序（单文件企业级重构版）
├── pyproject.toml               # 现代 Python 项目配置
├── requirements.txt             # 依赖清单
├── README.md                    # 项目说明（本文档）
├── LICENSE                      # MIT 开源协议
└── .gitignore                   # 项目自身忽略规则
```

### 代码分层设计

| 层级 | 职责 | 对应类/模块 |
|:---|:---|:---|
| **主题系统** | 统一配色与边框风格 | `Theme` |
| **数据模型** | 操作结果、Git 摘要、状态枚举 | `OperationResult`, `GitSummary`, `OpStatus` |
| **异常体系** | 业务异常隔离与友好提示 | `ToolException`, `GitCommandError`, `ValidationError` |
| **命令引擎** | 子进程封装、超时控制、Spinner 进度 | `CommandRunner` |
| **Git 服务层** | 所有 Git 操作封装，内部静默执行 | `GitService` |
| **UI 渲染层** | 仪表盘、菜单、结果卡片、危险横幅 | `UIRenderer` |
| **交互向导** | 路径/分支/确认/验证码等输入封装 | `InteractiveWizard` |
| **业务工作流** | 8 大功能的具体实现 | `UploadWorkflow`, `SyncWorkflow`, ... |
| **应用壳** | 路由分发、异常捕获、菜单生命周期 | `GitHubToolApp` |

---

## 💡 技术亮点

1. **企业级异常体系** — 区分 `CancelOperation`（用户取消）、`GitCommandError`（命令失败）、`ValidationError`（输入校验），异常不中断主循环
2. **统一清屏重绘机制** — 操作完成后按 Enter 自动清屏并刷新菜单，彻底解决 CLI 菜单漂移问题
3. **双模式命令执行** — 内部查询静默执行（`show_cmd=False`），用户操作展示 Spinner 进度与实时输出
4. **输入安全处理** — `sanitize_input` 自动去除中文引号、英文引号、反引号包裹，防止注入
5. **状态机式菜单生命周期** — `need_menu` 标志精确控制重绘时机，支持 `m` 快捷键强制刷新
6. **100% 类型注解** — 全项目使用 `typing` 模块，配合 `mypy` 可达严格模式零报错
7. **Rich 全组件覆盖** — Panel、Table、Tree、Syntax、Progress、Prompt、Align 等组件协同，终端体验媲美 GUI

---

## ❓ 常见问题

**Q: 为什么需要 Python 3.9+？**  
A: 项目使用了标准库 `typing` 的泛型内置类型（`list[str]` 等）以及 `pathlib` 的增强 API，3.9 以下需额外兼容处理。

**Q: Windows CMD 显示乱码？**  
A: 请使用 **Windows Terminal** 或 **PowerShell 7+**，旧版 CMD 不支持 Rich 的 Unicode 边框字符。

**Q: 推送时提示权限不足？**  
A: 请检查 GitHub Token / SSH 密钥配置。HTTPS 方式需使用 Personal Access Token 替代密码。

**Q: 能否支持 GitLab / Gitee？**  
A: 当前版本以 GitHub 为默认远程平台，但底层 Git 命令通用，只需在输入仓库地址时替换为对应平台 URL 即可。

---

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源，允许自由使用、修改及商业用途，保留原作者署名即可。

---

<div align="center">

**Made with ❤️ by [magic-fss](https://github.com/magic-fss)**

如果本项目对你有帮助，欢迎 ⭐ Star 支持！

</div>
