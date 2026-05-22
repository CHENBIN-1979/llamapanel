#!/bin/bash
# LlamaPanel 一键安装脚本 (Ubuntu/Debian)

set -e
echo "🦙 LlamaPanel 安装脚本启动..."
echo "================================"

# 安装系统依赖
echo "📦 安装系统依赖..."
sudo apt update
sudo apt install -y python3-pip python3-venv git cmake build-essential curl wget rsync

# 创建专用用户（如果不存在）
if ! id -u llamapanel &>/dev/null; then
    echo "👤 创建 llamapanel 用户..."
    sudo useradd -r -s /bin/false -d /opt/llamapanel llamapanel
fi

# 创建项目目录
sudo mkdir -p /opt/llamapanel

# 复制项目文件（跳过 rsync 如果已经在目标目录中）
CURRENT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$CURRENT_DIR" = "/opt/llamapanel" ]; then
    echo "📁 已在 /opt/llamapanel 目录，跳过复制"
else
    echo "📁 复制项目文件..."
    rsync -av --exclude='venv' --exclude='logs' --exclude='data' --exclude='__pycache__' --exclude='*.py[cod]' --exclude='.git' "$CURRENT_DIR/" /opt/llamapanel/
fi

# 设置目录权限（llamapanel 用户拥有）
sudo chown -R llamapanel:llamapanel /opt/llamapanel
sudo chmod 755 /opt/llamapanel

# 创建 Python 虚拟环境
echo "🐍 创建 Python 虚拟环境..."
cd /opt/llamapanel
python3 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
echo "📚 安装 Python 依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 创建必要目录
mkdir -p logs data

# 确保 llamapanel 用户可写
sudo chown -R llamapanel:llamapanel /opt/llamapanel/logs /opt/llamapanel/data

# 创建 systemd 服务文件
echo "🔧 创建系统服务..."
sudo tee /etc/systemd/system/llamapanel.service > /dev/null << 'SERVICE'
[Unit]
Description=LlamaPanel Web Service
After=network.target

[Service]
Type=simple
User=llamapanel
Group=llamapanel
WorkingDirectory=/opt/llamapanel
Environment="PATH=/opt/llamapanel/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/opt/llamapanel/venv/bin/python /opt/llamapanel/backend/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE

# 重新加载 systemd
sudo systemctl daemon-reload

# 配置 sudoers 权限（允许 llamapanel 用户重启自身服务，用于面板更新功能）
echo "🔐 配置 sudoers 权限..."
sudo tee /etc/sudoers.d/llamapanel > /dev/null << 'SUDOERS'
# LlamaPanel 用户重启自身服务的权限
llamapanel ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart llamapanel
SUDOERS
sudo chmod 440 /etc/sudoers.d/llamapanel

echo ""
echo "✅ 安装完成！"
echo ""
echo "启动服务: sudo systemctl start llamapanel"
echo "开机自启: sudo systemctl enable llamapanel"
echo "查看状态: sudo systemctl status llamapanel"
echo "查看日志: sudo journalctl -u llamapanel -f"