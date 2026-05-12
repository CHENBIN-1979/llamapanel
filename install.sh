#!/bin/bash
# LlamaPanel 一键安装脚本 (Ubuntu/Debian)

set -e
echo "🦙 LlamaPanel 安装脚本启动..."
echo "================================"

# 安装系统依赖
echo "📦 安装系统依赖..."
sudo apt update
sudo apt install -y python3-pip python3-venv git cmake build-essential curl wget

# 创建项目目录
sudo mkdir -p /opt/llamapanel
sudo chown -R $USER:$USER /opt/llamapanel

# 复制项目文件
cp -r ./* /opt/llamapanel/

# 创建 Python 虚拟环境
echo "🐍 创建 Python 虚拟环境..."
cd /opt/llamapanel
python3 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
echo "📚 安装 Python 依赖..."
pip install --upgrade pip
pip install fastapi uvicorn psutil

# 创建必要目录
mkdir -p logs data

# 创建 systemd 服务文件
echo "🔧 创建系统服务..."
sudo tee /etc/systemd/system/llamapanel.service > /dev/null << 'SERVICE'
[Unit]
Description=LlamaPanel Web Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/llamapanel
Environment="PATH=/opt/llamapanel/venv/bin"
ExecStart=/opt/llamapanel/venv/bin/python /opt/llamapanel/backend/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

# 重新加载 systemd
sudo systemctl daemon-reload

echo ""
echo "✅ 安装完成！"
echo ""
echo "启动服务: sudo systemctl start llamapanel"
echo "开机自启: sudo systemctl enable llamapanel"
echo "查看状态: sudo systemctl status llamapanel"
echo "查看日志: sudo journalctl -u llamapanel -f"
