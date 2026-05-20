cd /d/llamapanel
git add backend/routers/download.py
git add backend/routers/local.py
git add backend/routers/progress.py
git add backend/routers/__init__.py
git commit -m "修复: 使用 jinja2.Environment 禁用模板缓存，解决 unhashable type dict 错误"
git push origin main