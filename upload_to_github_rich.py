#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub 仓库维护工具 —— 企业级重构版 v2.1
==========================================
修复：操作后统一清屏重绘菜单，消除菜单漂移问题
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from rich.align import Align
    from rich.box import DOUBLE, HEAVY, ROUNDED, SIMPLE
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Confirm, Prompt
    from rich.style import Style
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text
    from rich.tree import Tree
except ImportError:
    print("[ERROR] 缺少依赖:  pip install rich")
    sys.exit(1)

console = Console()


# ────────────────────────────── 主题与设计系统 ──────────────────────────────
class Theme:
    PRIMARY = "bold cyan"
    SUCCESS = "bold green"
    ERROR = "bold red"
    WARN = "bold yellow"
    INFO = "dim white"
    HIGHLIGHT = "bold magenta"
    MUTED = "dim"
    BORDER_OK = "green"
    BORDER_WARN = "yellow"
    BORDER_ERR = "red"
    BORDER_INFO = "cyan"


# ────────────────────────────── 数据模型 ──────────────────────────────
class OpStatus(Enum):
    SUCCESS = auto()
    FAIL = auto()
    CANCEL = auto()
    SKIP = auto()


@dataclass
class OperationResult:
    status: OpStatus
    title: str
    message: str = ""
    details: List[str] = field(default_factory=list)
    suggestion: str = ""


@dataclass
class GitSummary:
    is_repo: bool = False
    current_branch: str = ""
    local_branches: List[str] = field(default_factory=list)
    remote_branches: List[str] = field(default_factory=list)
    ahead_behind: str = ""
    last_commit: str = ""
    dirty_files: int = 0
    untracked_files: int = 0


# ────────────────────────────── 异常体系 ──────────────────────────────
class ToolException(Exception):
    pass


class CancelOperation(ToolException):
    pass


class GitCommandError(ToolException):
    def __init__(self, message: str, stderr: str = ""):
        super().__init__(message)
        self.stderr = stderr


class ValidationError(ToolException):
    pass


# ────────────────────────────── 工具函数 ──────────────────────────────
def sanitize_input(value: str) -> str:
    value = value.strip()
    for a, b in [('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"), ("`", "`")]:
        if value.startswith(a) and value.endswith(b):
            value = value[1:-1].strip()
    return value


def is_quit_command(value: str) -> bool:
    return value.strip().lower() in ("q", "quit", "exit", "back", "cancel")


def ensure_path(path_str: str) -> Path:
    path_str = sanitize_input(path_str)
    if not path_str:
        return Path.cwd()
    if len(path_str) == 2 and path_str[1] == ":" and path_str[0].isalpha():
        path_str += "\\"
    p = Path(path_str)
    if not p.is_absolute():
        p = p.resolve()
    return p


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists() or (path / ".git").is_file()


# ────────────────────────────── 核心引擎：命令执行器 ──────────────────────────────
class CommandRunner:
    DEFAULT_TIMEOUT = 120

    @staticmethod
    def run(
        cmd: str,
        *,
        cwd: Optional[Path] = None,
        timeout: int = DEFAULT_TIMEOUT,
        capture: bool = False,
        show_cmd: bool = True,
        allow_fail: bool = False,
        env: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str, str]:
        if show_cmd:
            console.print(f"[{Theme.MUTED}]$ {cmd}[/{Theme.MUTED}]")

        try:
            proc = subprocess.Popen(
                cmd,
                shell=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, **(env or {})},
            )
            stdout_data, stderr_data = proc.communicate(timeout=timeout)
            success = proc.returncode == 0

            if not success and not allow_fail:
                raise GitCommandError(
                    f"命令退出码 {proc.returncode}", stderr=stderr_data.strip()
                )

            return success, stdout_data, stderr_data

        except subprocess.TimeoutExpired:
            proc.kill()
            raise GitCommandError(f"命令执行超时（>{timeout}s）")
        except Exception as e:
            if not allow_fail:
                raise GitCommandError(f"执行异常: {e}")
            return False, "", str(e)

    @classmethod
    def run_with_spinner(
        cls,
        cmd: str,
        description: str = "执行中...",
        **kwargs,
    ) -> Tuple[bool, str, str]:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"[cyan]{description}", total=None)
            success, out, err = cls.run(cmd, capture=True, show_cmd=False, **kwargs)
            progress.update(task, completed=1)
            if out.strip():
                console.print(out.strip(), style=Theme.MUTED)
            if err.strip() and not success:
                console.print(err.strip(), style=Theme.ERROR)
            return success, out, err


# ────────────────────────────── 核心服务：Git 封装 ──────────────────────────────
class GitService:
    """Git 操作服务层 —— 所有内部查询默认静默（show_cmd=False），避免刷屏"""

    def __init__(self, cwd: Path):
        self.cwd = cwd

    def _git(self, args: str, **kwargs) -> Tuple[bool, str, str]:
        # [FIX v2.1] 内部 Git 查询默认静默，防止仪表盘等操作刷屏顶走菜单
        kwargs.setdefault("show_cmd", False)
        return CommandRunner.run(f"git {args}", cwd=self.cwd, **kwargs)

    def summary(self) -> GitSummary:
        s = GitSummary()
        if not is_git_repo(self.cwd):
            return s

        s.is_repo = True

        ok, out, _ = self._git("branch --show-current", allow_fail=True, capture=True)
        s.current_branch = out.strip() if ok else "unknown"

        ok, out, _ = self._git("branch --format=%(refname:short)", allow_fail=True, capture=True)
        if ok:
            s.local_branches = [b for b in out.strip().splitlines() if b]

        ok, out, _ = self._git("branch -r --format=%(refname:short)", allow_fail=True, capture=True)
        if ok:
            s.remote_branches = [
                b.replace("origin/", "") for b in out.strip().splitlines()
                if b and not b.startswith("HEAD")
            ]

        ok, out, _ = self._git(
            f"rev-list --left-right --count origin/{s.current_branch}...HEAD",
            allow_fail=True,
            capture=True,
        )
        if ok:
            parts = out.strip().split()
            if len(parts) == 2:
                behind, ahead = parts
                s.ahead_behind = f"↑{ahead} ↓{behind}"

        ok, out, _ = self._git(
            "log -1 --format=%h %s (%cr)", allow_fail=True, capture=True
        )
        s.last_commit = out.strip() if ok else "无提交记录"

        ok, out, _ = self._git("status --short", allow_fail=True, capture=True)
        if ok and out.strip():
            for line in out.strip().splitlines():
                if line.startswith("??"):
                    s.untracked_files += 1
                else:
                    s.dirty_files += 1

        return s

    def status_tree(self) -> Optional[Tree]:
        ok, out, _ = self._git("status -s", allow_fail=True, capture=True)
        if not ok or not out.strip():
            return None

        root = Tree("📁 工作区变更")
        staged = Tree("[green]已暂存 (Staged)[/green]")
        unstaged = Tree("[yellow]未暂存 (Unstaged)[/yellow]")
        untracked = Tree("[cyan]未跟踪 (Untracked)[/cyan]")

        for line in out.strip().splitlines():
            if len(line) < 3:
                continue
            x, y, filepath = line[0], line[1], line[3:].strip()
            if x == "?" and y == "?":
                untracked.add(filepath)
            elif x in "MADRC":
                staged.add(f"[{x}] {filepath}")
            else:
                unstaged.add(f"[{y}] {filepath}")

        if staged.children:
            root.add(staged)
        if unstaged.children:
            root.add(unstaged)
        if untracked.children:
            root.add(untracked)
        return root

    def diff_stat(self) -> Optional[Table]:
        ok, out, _ = self._git("diff --stat", allow_fail=True, capture=True)
        if not ok or not out.strip():
            return None
        table = Table(show_header=False, box=SIMPLE, padding=(0, 1))
        table.add_column("文件", style="white")
        table.add_column("变更", style="dim", justify="right")
        for line in out.strip().splitlines():
            if "|" in line:
                file_part, change_part = line.rsplit("|", 1)
                table.add_row(file_part.strip(), change_part.strip())
        return table

    def get_branches(self) -> Tuple[List[str], List[str], str]:
        local, remote, current = [], [], "main"

        ok, out, _ = self._git("branch", allow_fail=True, capture=True)
        if ok:
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("*"):
                    current = line[1:].strip()
                    local.append(current)
                elif line:
                    local.append(line)

        ok, out, _ = self._git("branch -r", allow_fail=True, capture=True)
        if ok:
            for line in out.splitlines():
                line = line.strip()
                if line and not line.startswith("HEAD"):
                    remote.append(line.replace("origin/", ""))

        return local, remote, current

    def checkout_branch(self, branch: str, local_branches: List[str], remote_branches: List[str]) -> bool:
        if branch in local_branches:
            ok, _, err = self._git(f"checkout {branch}", allow_fail=True, capture=True)
            if not ok:
                console.print(f"[{Theme.ERROR}]切换分支失败: {err}[/{Theme.ERROR}]")
            return ok

        if branch in remote_branches:
            ok, _, err = self._git(
                f"checkout -b {branch} origin/{branch}",
                allow_fail=True,
                capture=True,
            )
            if ok:
                console.print(f"[{Theme.SUCCESS}]已创建并追踪远程分支: {branch}[/{Theme.SUCCESS}]")
            else:
                console.print(f"[{Theme.ERROR}]检出远程分支失败: {err}[/{Theme.ERROR}]")
            return ok

        ok, _, err = self._git(f"checkout -b {branch}", allow_fail=True, capture=True)
        if not ok:
            console.print(f"[{Theme.ERROR}]创建分支失败: {err}[/{Theme.ERROR}]")
        return ok

    def safe_remote_set(self, url: str) -> bool:
        ok, out, _ = self._git("remote get-url origin", allow_fail=True, capture=True)
        if ok and out.strip():
            existing = out.strip()
            console.print(f"[{Theme.WARN}]⚠️  已存在远程 origin: {existing}[/{Theme.WARN}]")
            if not Confirm.ask("是否覆盖为新的仓库地址？", default=False):
                console.print(f"[{Theme.INFO}]保留原有远程配置[/{Theme.INFO}]")
                return True
            self._git("remote remove origin", allow_fail=True, capture=True)
        return self._git(f"remote add origin {url}", capture=True)[0]

    def user_info(self) -> Tuple[str, str]:
        ok_u, u, _ = self._git("config --global user.name", allow_fail=True, capture=True)
        ok_e, e, _ = self._git("config --global user.email", allow_fail=True, capture=True)
        return (u.strip() if ok_u else ""), (e.strip() if ok_e else "")

    def set_user_info(self, name: str, email: str) -> bool:
        ok1, _, _ = self._git(f'config --global user.name "{name}"', capture=True)
        ok2, _, _ = self._git(f'config --global user.email "{email}"', capture=True)
        return ok1 and ok2


# ────────────────────────────── UI 渲染层 ──────────────────────────────
class UIRenderer:
    @staticmethod
    def header(title: str = "GitHub 仓库维护工具"):
        console.print(Panel(
            Align.center(f"[{Theme.PRIMARY}]🚀 {title}[/]  [{Theme.MUTED}]v2.1 企业级重构版[/]"),
            border_style=Theme.BORDER_INFO,
            box=ROUNDED,
            padding=(0, 2),
        ))

    @staticmethod
    def section(title: str, emoji: str = "▶"):
        console.print(f"\n[{Theme.HIGHLIGHT}]{emoji} {title}[/{Theme.HIGHLIGHT}]")
        console.print("─" * 50, style="dim")

    @staticmethod
    def result_card(result: OperationResult):
        color = {
            OpStatus.SUCCESS: Theme.BORDER_OK,
            OpStatus.FAIL: Theme.BORDER_ERR,
            OpStatus.CANCEL: Theme.BORDER_WARN,
            OpStatus.SKIP: Theme.BORDER_INFO,
        }[result.status]

        emoji = {
            OpStatus.SUCCESS: "✅",
            OpStatus.FAIL: "❌",
            OpStatus.CANCEL: "⏹️",
            OpStatus.SKIP: "⏭️",
        }[result.status]

        content = [f"[bold]{result.message}[/bold]"]
        if result.details:
            content.append("")
            for d in result.details:
                content.append(f"  • {d}")
        if result.suggestion:
            content.append(f"\n[{Theme.INFO}]💡 {result.suggestion}[/{Theme.INFO}]")

        console.print(Panel(
            "\n".join(content),
            title=f"{emoji} {result.title}",
            border_style=color,
            box=ROUNDED,
            padding=(1, 2),
        ))

    @staticmethod
    def dashboard(summary: GitSummary, cwd: Path):
        if not summary.is_repo:
            console.print(Panel(
                "[dim]当前目录未检测到 Git 仓库[/dim]",
                title="📊 仓库状态",
                border_style=Theme.BORDER_WARN,
            ))
            return

        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)

        left = Table(show_header=False, box=SIMPLE, padding=(0, 1))
        left.add_column(style="cyan")
        left.add_column(style="white")
        left.add_row("当前分支", f"[bold]{summary.current_branch}[/bold]")
        left.add_row("本地分支", str(len(summary.local_branches)))
        left.add_row("远程分支", str(len(summary.remote_branches)))
        left.add_row("同步状态", summary.ahead_behind or "已同步")
        left.add_row("最后提交", summary.last_commit[:60] if summary.last_commit else "-")

        right = Table(show_header=False, box=SIMPLE, padding=(0, 1))
        right.add_column(style="cyan")
        right.add_column(style="white")
        right.add_row("已修改", str(summary.dirty_files))
        right.add_row("未跟踪", str(summary.untracked_files))
        right.add_row("路径", str(cwd))

        grid.add_row(
            Panel(left, title="🌿 分支信息", border_style=Theme.BORDER_INFO),
            Panel(right, title="📁 工作区", border_style=Theme.BORDER_INFO),
        )
        console.print(Panel(grid, title="📊 仓库仪表盘", border_style=Theme.PRIMARY, box=HEAVY))

    @staticmethod
    def menu():
        table = Table(
            title=f"[{Theme.PRIMARY}]功能菜单[/]",
            box=ROUNDED,
            border_style=Theme.BORDER_INFO,
            show_header=True,
            header_style="bold cyan",
            padding=(0, 1),
        )
        table.add_column("编号", justify="center", width=4, style="bold green")
        table.add_column("功能", style="bold white", width=22)
        table.add_column("说明", style="dim")

        items = [
            ("1", "📤  上传本地项目", "初始化仓库 → 首次推送"),
            ("2", "🔄  同步本地更改", "add → commit → pull → push"),
            ("3", "🗑️  清空远程仓库", "⚠️  危险操作，需二次确认"),
            ("4", "👤  Git 用户信息", "检查 / 修改 user.name & email"),
            ("5", "🛡️  生成 .gitignore", "智能检测技术栈并生成模板"),
            ("6", "🌿  分支管理", "切换 / 新建 / 查看分支"),
            ("7", "⬇️  拉取远程更新", "git pull --rebase 指定分支"),
            ("8", "📊  仓库仪表盘", "查看当前仓库全景状态"),
            ("0", "❌  退出程序", ""),
        ]
        for num, func, desc in items:
            table.add_row(num, func, desc)
        console.print(table)

    @staticmethod
    def danger_banner(title: str, subtitle: str):
        console.print(Panel(
            f"[{Theme.ERROR}]{title}[/{Theme.ERROR}]\n[{Theme.WARN}]{subtitle}[/{Theme.WARN}]",
            border_style=Theme.BORDER_ERR,
            box=DOUBLE,
        ))


# ────────────────────────────── 交互向导 ──────────────────────────────
class InteractiveWizard:
    @staticmethod
    def ask_path(prompt: str, default: Optional[str] = None) -> Path:
        while True:
            raw = Prompt.ask(
                f"[bold]{prompt}[/bold] [{Theme.MUTED}][q=返回菜单][/]",
                default=default or str(Path.cwd()),
                show_default=True,
            )
            if is_quit_command(raw):
                raise CancelOperation()
            path = ensure_path(raw)
            if path.is_dir():
                return path
            console.print(f"[{Theme.ERROR}]❌ 路径不存在: {path}[/{Theme.ERROR}]")

    @staticmethod
    def ask_nonempty(prompt: str, default: str = "") -> str:
        while True:
            val = Prompt.ask(
                f"[bold]{prompt}[/bold] [{Theme.MUTED}][q=返回菜单][/]",
                default=default,
            ).strip()
            if is_quit_command(val):
                raise CancelOperation()
            if val:
                return val
            console.print(f"[{Theme.ERROR}]输入不能为空[/{Theme.ERROR}]")

    @staticmethod
    def ask_confirm(prompt: str, default: bool = False) -> bool:
        return Confirm.ask(f"[bold]{prompt}[/bold]", default=default)

    @staticmethod
    def ask_verification_code(expected: str, prompt: str) -> bool:
        val = Prompt.ask(
            f"[bold red]{prompt}[/bold red] [{Theme.MUTED}][q=取消][/]"
        ).strip()
        if is_quit_command(val):
            raise CancelOperation()
        return val == expected

    @staticmethod
    def choose_branch(git: GitService, prompt: str = "选择分支", allow_new: bool = True) -> str:
        local, remote, current = git.get_branches()

        if not local and not remote:
            console.print(f"[{Theme.WARN}]未检测到分支，默认使用 main[/{Theme.WARN}]")
            return "main"

        table = Table(
            title=f"📋 {prompt}",
            box=ROUNDED,
            header_style="bold cyan",
            border_style=Theme.BORDER_INFO,
        )
        table.add_column("序号", style="dim", width=4, justify="center")
        table.add_column("分支名", style="bold white")
        table.add_column("类型", style="green")
        table.add_column("状态", style="yellow")

        choices: List[str] = []
        seen = set()

        for b in local:
            if b in seen:
                continue
            seen.add(b)
            choices.append(b)
            status = "👈 当前" if b == current else ""
            table.add_row(str(len(choices)), b, "[cyan]本地[/cyan]", status)

        for b in remote:
            if b in seen:
                continue
            seen.add(b)
            choices.append(b)
            table.add_row(str(len(choices)), b, "[magenta]远程[/magenta]", "")

        if allow_new:
            table.add_row("N", "[dim]输入新分支名...[/dim]", "[dim]新建[/dim]", "")
        table.add_row("Q", "[dim]返回主菜单[/dim]", "[dim]取消[/dim]", "")

        console.print(table)

        while True:
            choice = Prompt.ask(
                "[bold]请输入序号[/bold] [dim][q=返回菜单][/]",
                default="1",
            ).strip().upper()
            if is_quit_command(choice):
                raise CancelOperation()

            if choice == "N" and allow_new:
                new_branch = InteractiveWizard.ask_nonempty("新分支名称")
                git._git(f"checkout -b {new_branch}", capture=True)
                return new_branch

            try:
                idx = int(choice)
                if 1 <= idx <= len(choices):
                    selected = choices[idx - 1]
                    git.checkout_branch(selected, local, remote)
                    return selected
                console.print(f"[{Theme.ERROR}]序号超出范围[/{Theme.ERROR}]")
            except ValueError:
                console.print(f"[{Theme.ERROR}]请输入有效序号、N 或 Q[/{Theme.ERROR}]")


# ────────────────────────────── 业务工作流 ──────────────────────────────
class Workflow:
    def __init__(self, renderer: UIRenderer, wizard: InteractiveWizard):
        self.r = renderer
        self.w = wizard

    def _enter_project(self, must_be_git: bool = False) -> Tuple[Path, GitService]:
        self.r.section("项目目录选择", "📂")
        path = self.w.ask_path("请输入本地项目路径")
        os.chdir(path)
        git = GitService(path)

        if must_be_git and not git.summary().is_repo:
            raise ValidationError("当前目录不是 Git 仓库，请先初始化")
        return path, git


class UploadWorkflow(Workflow):
    def execute(self) -> OperationResult:
        self.r.section("上传本地项目到 GitHub", "📤")
        path, git = self._enter_project()

        self.r.section("Git 用户信息检查", "👤")
        name, email = git.user_info()
        info_table = Table(show_header=False, box=SIMPLE)
        info_table.add_column(style="cyan")
        info_table.add_column()
        info_table.add_row("user.name", name or "[red]未设置[/red]")
        info_table.add_row("user.email", email or "[red]未设置[/red]")
        console.print(info_table)

        if (not name or not email) or self.w.ask_confirm("是否需要修改？", default=False):
            new_name = self.w.ask_nonempty("新的 Git 用户名") if not name else Prompt.ask(
                "新的 Git 用户名（留空保持当前）", default=name
            ).strip()
            if is_quit_command(new_name):
                raise CancelOperation()
            new_email = self.w.ask_nonempty("新的 Git 邮箱") if not email else Prompt.ask(
                "新的 Git 邮箱（留空保持当前）", default=email
            ).strip()
            if is_quit_command(new_email):
                raise CancelOperation()
            if new_name:
                name = new_name
            if new_email:
                email = new_email
            git.set_user_info(name, email)
            console.print(f"[{Theme.SUCCESS}]✅ 用户信息已更新[/{Theme.SUCCESS}]")

        self._generate_gitignore(path)

        if not git.summary().is_repo:
            CommandRunner.run_with_spinner("git init", "初始化 Git 仓库")
            console.print(f"[{Theme.SUCCESS}]✅ 已初始化本地仓库[/{Theme.SUCCESS}]")
        else:
            console.print(f"[{Theme.INFO}]已检测到本地 Git 仓库[/{Theme.INFO}]")

        tree = git.status_tree()
        if tree:
            console.print(Panel(tree, title="变更预览", border_style=Theme.BORDER_WARN))

        CommandRunner.run_with_spinner("git add .", "暂存变更")
        msg = self.w.ask_nonempty("本次提交说明", default="feat: 首次提交")
        ok, _, err = CommandRunner.run_with_spinner(
            f'git commit -m "{msg}"', "提交变更", allow_fail=True
        )
        if not ok:
            console.print(f"[{Theme.WARN}]⚠️  提交失败或没有新变动: {err}[/{Theme.WARN}]")

        self.r.section("远程仓库配置", "🔗")
        default_url = "https://github.com/username/repo.git"
        url = self.w.ask_nonempty("GitHub 仓库地址", default=default_url)
        if not git.safe_remote_set(url):
            return OperationResult(
                OpStatus.FAIL, "远程配置", "添加远程仓库失败",
                suggestion="请检查仓库地址格式及网络连通性",
            )

        branch = self.w.choose_branch(git, "选择要推送的分支", allow_new=True)
        CommandRunner.run_with_spinner(
            f"git pull --rebase origin {branch}", "预同步远程", allow_fail=True
        )
        ok, _, err = CommandRunner.run_with_spinner(
            f"git push -u origin {branch}", "推送到远程"
        )
        if not ok:
            return OperationResult(
                OpStatus.FAIL, "推送失败", err,
                suggestion="请检查 GitHub Token / SSH 密钥 / 网络代理设置",
            )

        return OperationResult(
            OpStatus.SUCCESS, "上传完成",
            f"仓库: {url}\n分支: {branch}",
            suggestion="后续可使用「同步本地更改」功能进行日常推送",
        )

    def _generate_gitignore(self, path: Path):
        self.r.section(".gitignore 生成", "🛡️")
        gi_path = path / ".gitignore"
        if gi_path.exists():
            console.print(f"[{Theme.WARN}]⚠️  .gitignore 已存在，跳过生成[/{Theme.WARN}]")
            with open(gi_path, "r", encoding="utf-8") as f:
                content = f.read()
            console.print(Panel(
                Syntax(content, "gitignore", theme="monokai", line_numbers=True),
                title="当前内容", border_style=Theme.BORDER_WARN,
            ))
            return

        content = "# Generated by GitHub Tool v2.1\n"
        files = [f.name for f in path.iterdir()]
        detected = []

        patterns = {
            "Python": ([".py", ".pyw"], "__pycache__/\n*.py[cod]\n*.so\n.env\n.venv\nvenv/\n"),
            "Jupyter": ([".ipynb"], ".ipynb_checkpoints/\n"),
            "Node.js": ([".js", ".ts", ".jsx", ".tsx"], "node_modules/\ndist/\nbuild/\n*.log\n"),
            "Java": ([".java", ".class"], "*.class\ntarget/\n*.jar\n"),
            "Go": ([".go"], "bin/\n*.exe\nvendor/\n"),
            "Rust": ([".rs"], "target/\nCargo.lock\n"),
            "C/C++": ([".c", ".cpp", ".h"], "*.o\n*.exe\n*.dll\n*.so\nbuild/\n"),
            "PHP": ([".php"], "vendor/\ncomposer.lock\n.env\n"),
        }

        for lang, (exts, pat) in patterns.items():
            if any(any(f.endswith(e) for e in exts) for f in files) or (lang == "Node.js" and "node_modules" in files):
                content += f"\n# {lang}\n{pat}"
                detected.append(lang)

        content += "\n# IDE & OS\n*.log\n.DS_Store\nThumbs.db\n.idea/\n.vscode/\n*.swp\n"
        content += "\n# Secrets\n*.pem\n*.key\n.env.local\n.env.*.local\n"

        console.print(f"[{Theme.MUTED}]检测到技术栈: {', '.join(detected) if detected else '未知'}[/{Theme.MUTED}]")
        console.print(Panel(
            Syntax(content, "gitignore", theme="monokai", line_numbers=True),
            title="即将生成的 .gitignore", border_style=Theme.BORDER_OK,
        ))

        if self.w.ask_confirm("确认生成？", default=True):
            gi_path.write_text(content, encoding="utf-8")
            console.print(f"[{Theme.SUCCESS}]✅ 已生成 .gitignore[/{Theme.SUCCESS}]")
        else:
            console.print(f"[{Theme.INFO}]已取消生成[/{Theme.INFO}]")


class SyncWorkflow(Workflow):
    def execute(self) -> OperationResult:
        self.r.section("同步本地更改到远程", "🔄")
        path, git = self._enter_project(must_be_git=True)

        summary = git.summary()
        self.r.dashboard(summary, path)

        tree = git.status_tree()
        if not tree:
            return OperationResult(
                OpStatus.SKIP, "无变更", "工作区干净，没有需要同步的更改",
                suggestion="修改文件后再试，或使用「拉取远程更新」获取最新代码",
            )

        console.print(Panel(tree, title="待提交变更", border_style=Theme.BORDER_WARN))
        diff = git.diff_stat()
        if diff:
            console.print(Panel(diff, title="Diff 统计", border_style=Theme.MUTED))

        if not self.w.ask_confirm("确认暂存以上所有变更？", default=True):
            return OperationResult(OpStatus.CANCEL, "已取消", "用户取消了暂存操作")

        CommandRunner.run_with_spinner("git add .", "暂存变更")

        default_msg = "update: 日常更新"
        msg = Prompt.ask(
            "[bold]提交说明[/bold] [dim][q=取消][/dim]",
            default=default_msg,
        ).strip()
        if is_quit_command(msg):
            raise CancelOperation()

        ok, _, err = CommandRunner.run_with_spinner(
            f'git commit -m "{msg}"', "提交变更", allow_fail=True
        )
        if not ok:
            return OperationResult(
                OpStatus.FAIL, "提交失败", err,
                suggestion="检查是否有变更被暂存，或手动执行 git status 查看",
            )

        branch = self.w.choose_branch(git, "选择要推送的分支", allow_new=True)
        CommandRunner.run_with_spinner(
            f"git pull --rebase origin {branch}", "同步远程", allow_fail=True
        )
        ok, _, err = CommandRunner.run_with_spinner(
            f"git push origin {branch}", "推送到远程"
        )
        if not ok:
            return OperationResult(OpStatus.FAIL, "推送失败", err)

        return OperationResult(
            OpStatus.SUCCESS, "同步完毕",
            f"分支: {branch}\n提交: {msg}",
            suggestion="可在 GitHub 上查看本次提交的 Actions / PR 状态",
        )


class ClearWorkflow(Workflow):
    def execute(self) -> OperationResult:
        self.r.danger_banner(
            "⚠️  危险操作：即将清空远程仓库所有文件",
            "此操作不可恢复！所有提交历史将被清空！"
        )

        if not self.w.ask_confirm("我已了解风险，确认继续？", default=False):
            return OperationResult(OpStatus.CANCEL, "已取消", "用户在风险确认阶段取消")

        if not self.w.ask_verification_code(
            "DELETE", "请输入 'DELETE' 以确认清空操作"
        ):
            return OperationResult(OpStatus.CANCEL, "已取消", "验证码不匹配")

        self.r.section("执行清空操作", "🗑️")

        url = self.w.ask_nonempty("GitHub 仓库地址")
        tmp = Path("__temp_empty_repo__")
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)

        try:
            CommandRunner.run_with_spinner(
                f"git clone --depth 1 {url} {tmp}", "克隆仓库"
            )
        except GitCommandError as e:
            return OperationResult(
                OpStatus.FAIL, "克隆失败", str(e),
                suggestion="检查仓库地址、Token 权限、网络连接",
            )

        git = GitService(tmp)
        branch = self.w.choose_branch(git, "选择要清空的分支", allow_new=False)

        for item in tmp.iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)

        CommandRunner.run_with_spinner("git add -A", "暂存删除", cwd=tmp)
        CommandRunner.run_with_spinner(
            'git commit -m "chore: remove all files"', "提交清空", cwd=tmp, allow_fail=True
        )

        if not self.w.ask_confirm("最终确认：立即推送到远程？", default=False):
            os.chdir(tmp.parent)
            shutil.rmtree(tmp, ignore_errors=True)
            return OperationResult(OpStatus.CANCEL, "已取消", "用户在最终确认阶段取消")

        ok, _, err = CommandRunner.run_with_spinner(
            f"git push origin {branch}", "强制清空推送", cwd=tmp
        )
        os.chdir(tmp.parent)
        shutil.rmtree(tmp, ignore_errors=True)

        if not ok:
            return OperationResult(OpStatus.FAIL, "推送失败", err)

        return OperationResult(
            OpStatus.SUCCESS, "清空完成",
            f"远程分支 {branch} 已清空",
            suggestion="如需保留历史，请在 GitHub 网页端立即新建文件以阻止意外拉取",
        )


class BranchWorkflow(Workflow):
    def execute(self) -> OperationResult:
        self.r.section("分支管理", "🌿")
        path, git = self._enter_project(must_be_git=True)

        summary = git.summary()
        self.r.dashboard(summary, path)

        branch = self.w.choose_branch(git, "切换或新建分支", allow_new=True)
        return OperationResult(
            OpStatus.SUCCESS, "分支就绪",
            f"当前工作分支: {branch}",
            suggestion="使用「同步本地更改」将当前分支推送到远程",
        )


class PullWorkflow(Workflow):
    def execute(self) -> OperationResult:
        self.r.section("拉取远程最新内容", "⬇️")
        path, git = self._enter_project(must_be_git=True)

        summary = git.summary()
        self.r.dashboard(summary, path)

        branch = self.w.choose_branch(git, "选择要拉取的分支", allow_new=False)
        ok, out, err = CommandRunner.run_with_spinner(
            f"git pull --rebase origin {branch}", "拉取中"
        )
        if not ok:
            return OperationResult(
                OpStatus.FAIL, "拉取失败", err,
                suggestion="可能存在冲突，请手动解决后执行 git rebase --continue",
            )

        return OperationResult(OpStatus.SUCCESS, "拉取完成", out.strip())


class DashboardWorkflow(Workflow):
    def execute(self) -> OperationResult:
        self.r.section("仓库仪表盘", "📊")
        path, git = self._enter_project()
        summary = git.summary()
        self.r.dashboard(summary, path)

        tree = git.status_tree()
        if tree:
            console.print(Panel(tree, title="变更详情", border_style=Theme.BORDER_WARN))
        else:
            console.print(Panel("[dim]工作区干净，无变更[/dim]", border_style=Theme.BORDER_OK))

        diff = git.diff_stat()
        if diff:
            console.print(Panel(diff, title="Diff 统计", border_style=Theme.MUTED))

        return OperationResult(OpStatus.SUCCESS, "仪表盘刷新完成")


# ────────────────────────────── 应用程序壳 ──────────────────────────────
class GitHubToolApp:
    def __init__(self):
        self.renderer = UIRenderer()
        self.wizard = InteractiveWizard()
        self.workflows = {
            "1": UploadWorkflow(self.renderer, self.wizard),
            "2": SyncWorkflow(self.renderer, self.wizard),
            "3": ClearWorkflow(self.renderer, self.wizard),
            "4": self._user_info_workflow,
            "5": self._gitignore_only_workflow,
            "6": BranchWorkflow(self.renderer, self.wizard),
            "7": PullWorkflow(self.renderer, self.wizard),
            "8": DashboardWorkflow(self.renderer, self.wizard),
        }

    def _user_info_workflow(self) -> OperationResult:
        self.renderer.section("Git 用户信息", "👤")
        git = GitService(Path.cwd())
        name, email = git.user_info()
        table = Table(show_header=False, box=SIMPLE)
        table.add_column(style="cyan")
        table.add_column()
        table.add_row("user.name", name or "[red]未设置[/red]")
        table.add_row("user.email", email or "[red]未设置[/red]")
        console.print(table)

        if not self.wizard.ask_confirm("是否需要修改？", default=False):
            return OperationResult(OpStatus.SKIP, "保留配置", "用户选择不修改")

        new_name = Prompt.ask("新用户名（留空保持）", default=name).strip()
        if is_quit_command(new_name):
            raise CancelOperation()
        new_email = Prompt.ask("新邮箱（留空保持）", default=email).strip()
        if is_quit_command(new_email):
            raise CancelOperation()

        if new_name or (not name and not new_name):
            if not new_name and not name:
                console.print(f"[{Theme.ERROR}]必须设置用户名！[/{Theme.ERROR}]")
                return OperationResult(OpStatus.FAIL, "校验失败", "用户名为空")
        if new_email or (not email and not new_email):
            if not new_email and not email:
                console.print(f"[{Theme.ERROR}]必须设置邮箱！[/{Theme.ERROR}]")
                return OperationResult(OpStatus.FAIL, "校验失败", "邮箱为空")

        final_name = new_name or name
        final_email = new_email or email
        git.set_user_info(final_name, final_email)
        return OperationResult(OpStatus.SUCCESS, "更新完成", f"{final_name} <{final_email}>")

    def _gitignore_only_workflow(self) -> OperationResult:
        path = self.wizard.ask_path("请输入项目路径")
        os.chdir(path)
        wf = UploadWorkflow(self.renderer, self.wizard)
        wf._generate_gitignore(path)
        return OperationResult(OpStatus.SUCCESS, "生成完成")

    def run(self):
        need_menu = True

        while True:
            # [FIX v2.1] 统一清屏重绘：header + menu 始终一起出现在屏幕顶部
            if need_menu:
                console.clear()
                self.renderer.header()
                self.renderer.menu()
                need_menu = False

            try:
                choice = Prompt.ask(
                    f"[{Theme.PRIMARY}]请输入操作编号[/] [{Theme.MUTED}][q=退出, m=刷新菜单][/]"
                ).strip()

                if is_quit_command(choice) or choice == "0":
                    console.print(Panel(
                        f"[{Theme.SUCCESS}]👋 感谢使用，再见！[/]",
                        border_style=Theme.BORDER_OK,
                        box=ROUNDED,
                    ))
                    break

                # [FIX v2.1] 增加 m 快捷键，随时强制刷新菜单
                if choice == "m":
                    need_menu = True
                    continue

                wf = self.workflows.get(choice)
                if not wf:
                    console.print(f"[{Theme.ERROR}]❌ 无效输入，请重新选择[/{Theme.ERROR}]")
                    continue

                if isinstance(wf, Workflow):
                    result = wf.execute()
                else:
                    result = wf()

                if result:
                    self.renderer.result_card(result)

            except CancelOperation:
                need_menu = True
                continue
            except ValidationError as e:
                console.print(f"[{Theme.ERROR}]❌ {e}[/{Theme.ERROR}]")
                need_menu = True
            except GitCommandError as e:
                console.print(f"[{Theme.ERROR}]❌ Git 错误: {e}[/{Theme.ERROR}]")
                if e.stderr:
                    console.print(Panel(
                        Syntax(e.stderr, "bash", theme="monokai", line_numbers=False),
                        title="错误输出", border_style=Theme.BORDER_ERR,
                    ))
                need_menu = True
            except KeyboardInterrupt:
                console.print(f"\n[{Theme.WARN}]⚠️  操作被中断[/{Theme.WARN}]")
                need_menu = True

            # [FIX v2.1] 统一后处理：所有操作（除退出/刷新外）完成后暂停，按 Enter 清屏重绘菜单
            # 彻底消除"操作多了看不到菜单"的问题
            if choice not in ("0", "m"):
                Prompt.ask(f"\n[{Theme.MUTED}]按 Enter 返回主菜单...[/]", default="")
                need_menu = True


if __name__ == "__main__":
    try:
        GitHubToolApp().run()
    except Exception as e:
        console.print(f"[{Theme.ERROR}]💥 程序异常退出: {e}[/{Theme.ERROR}]")
        sys.exit(1)