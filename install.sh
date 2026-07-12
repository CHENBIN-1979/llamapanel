#!/bin/bash
# LlamaPanel 一键安装脚本 (Ubuntu/Debian)
# 数据与代码分离：代码在 /opt/llamapanel，数据在 /data/llamapanel

set -e
echo "🦙 LlamaPanel 安装脚本启动..."
echo "================================"

# 定义路径
PROJECT_DIR="/opt/llamapanel"
DATA_DIR="/data/llamapanel"

# 安装系统依赖
echo "📦 安装系统依赖..."
sudo apt update
sudo apt install -y python3-pip python3-venv git cmake build-essential curl wget rsync

# 创建专用用户（如果不存在）
if ! id -u llamapanel &>/dev/null; then
    echo "👤 创建 llamapanel 用户..."
    sudo useradd -r -s /bin/false -d "$PROJECT_DIR" llamapanel
fi

# 创建项目目录
sudo mkdir -p "$PROJECT_DIR"

# 复制项目文件：优先就地安裝（PROJECT_DIR = CURRENT_DIR），
# 避免「git clone 跟 install 跑在不同目錄」的目錄衝突問題。
CURRENT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$CURRENT_DIR/backend/app.py" ]; then
    # 偵測到 source code（backend/app.py 存在）→ 就地安裝
    PROJECT_DIR="$CURRENT_DIR"
    echo "✓ 偵測到 source code，將就地安裝在 $PROJECT_DIR"
elif [ "$CURRENT_DIR" = "$PROJECT_DIR" ]; then
    # 兼容舊邏輯：在 /opt/llamapanel 跑且沒 source code（極少見）
    echo "📁 已在 $PROJECT_DIR 目錄，跳過複製"
else
    echo "❌ install.sh 沒找到 source code（backend/app.py 不存在）"
    echo "   請在 git clone 出來的 llamapanel 目錄執行此腳本："
    echo "     cd /your/path/llamapanel"
    echo "     sudo ./install.sh"
    exit 1
fi

# 创建数据目录（与项目代码分离）
echo "📂 创建数据目录..."
sudo mkdir -p "$DATA_DIR"/{models,model_links,logs,llama.cpp/build}

# 设置目录权限（llamapanel 用户拥有）
sudo chown -R llamapanel:llamapanel "$PROJECT_DIR"
sudo chown -R llamapanel:llamapanel "$DATA_DIR"
sudo chmod 755 "$PROJECT_DIR"
sudo chmod 755 "$DATA_DIR"

# 创建 Python 虚拟环境
echo "🐍 创建 Python 虚拟环境..."
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
echo "📚 安装 Python 依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 创建 systemd 服务文件（设置环境变量指定数据目录）
echo "🔧 创建系统服务..."
sudo tee /etc/systemd/system/llamapanel.service > /dev/null << SERVICE
[Unit]
Description=LlamaPanel Web Service
After=network.target

[Service]
Type=simple
User=llamapanel
Group=llamapanel
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="LLAMAPANEL_DATA_DIR=$DATA_DIR"
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/backend/app.py
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
echo "📁 项目代码目录: $PROJECT_DIR"
echo "📂 数据存储目录: $DATA_DIR"
echo "   ├─ 模型文件:   $DATA_DIR/models/"
echo "   ├─ 软链接:     $DATA_DIR/model_links/"
echo "   ├─ 日志:       $DATA_DIR/logs/"
echo "   └─ llama.cpp:  $DATA_DIR/llama.cpp/"
echo ""
echo "启动服务: sudo systemctl start llamapanel"
echo "开机自启: sudo systemctl enable llamapanel"
echo "查看状态: sudo systemctl status llamapanel"
echo "查看日志: sudo journalctl -u llamapanel -f"
