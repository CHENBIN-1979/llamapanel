@echo off
cd /d D:\llamapanel
echo.
echo === 正在提交修复 ===
git add backend/app.py
git commit -m "fix: 修复语法错误导致服务无法启动

- 修复第982行多余的 else: 语法错误（if pull_ok 有两个 else 分支）
- 将 actually_updated = not already_up_to_date 移入 if pull_ok 块内
- 该语法错误导致 Python 解析失败，服务完全无法启动

这是唯一的崩溃原因，修复后服务即可恢复正常运行"
echo.
echo === 正在推送到 GitHub ===
git push
echo.
echo === 完成 ===
pause
