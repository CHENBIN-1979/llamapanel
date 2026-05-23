@echo off
cd /d D:\llamapanel
git add install.sh
git commit -m "fix: install.sh 部署时保留 .git 目录，支持后续 git pull 更新"
git push
echo ✅ 推送完成
pause
