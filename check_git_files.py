#!/usr/bin/env python3
"""检查 git 提交是否包含 system.html"""
import zlib, os, subprocess

# 使用 git 命令检查
result = subprocess.run(
    ["git", "show", "--stat", "--name-only", "e5bbd32"],
    cwd="D:\\llamapanel",
    capture_output=True, text=True
)
print("=== Commit e5bbd32 文件变更 ===")
print(result.stdout)
print(result.stderr)

result2 = subprocess.run(
    ["git", "show", "--stat", "--name-only", "5577271"],
    cwd="D:\\llamapanel",
    capture_output=True, text=True
)
print("=== Commit 5577271 文件变更 ===")
print(result2.stdout)
print(result2.stderr)

# 检查 system.html 是否被跟踪
result3 = subprocess.run(
    ["git", "ls-files", "backend/templates/system.html"],
    cwd="D:\\llamapanel",
    capture_output=True, text=True
)
print("=== system.html 在 git 中追踪状态 ===")
print(f"输出: '{result3.stdout.strip()}'")
print(f"已追踪: {bool(result3.stdout.strip())}")

# 检查工作区与暂存区的差异
result4 = subprocess.run(
    ["git", "diff", "--stat", "backend/templates/system.html"],
    cwd="D:\\llamapanel",
    capture_output=True, text=True
)
print("=== system.html 工作区 vs 暂存区差异 ===")
print(result4.stdout or "无差异")
print(result4.stderr)
