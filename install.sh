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

# 自動偵測當前用戶和 PROJECT_DIR
# 不再強制把目錄 chown 給 llamapanel 用戶，而是用實際安裝用戶
SUDO_USER_REAL=$(logname 2>/dev/null || echo "$SUDO_USER" || whoami)
if [ -z "$SUDO_USER_REAL" ] || [ "$SUDO_USER_REAL" = "root" ]; then
    SUDO_USER_REAL=$(whoami)
fi

# 如果 PROJECT_DIR 在當前用戶的 home 目錄下，就不該被 root 強佔
# 例如：用戶 chenbin 把 ll clone 到 /home/chenbin/ll，則 PROJECT_DIR = /home/chenbin/ll
USER_HOME=$(eval echo "~$SUDO_USER_REAL")
if [[ "$PROJECT_DIR" == "$USER_HOME"* ]] && [ "$SUDO_USER_REAL" != "root" ]; then
    echo "📁 檢測到用戶模式安裝（$SUDO_USER_REAL → $PROJECT_DIR）"
    RUN_USER="$SUDO_USER_REAL"
else
    echo "📁 檢測到 root 模式安裝（$SUDO_USER_REAL → $PROJECT_DIR）"
    RUN_USER="llamapanel"
fi

# 設置目錄權限
if [ "$RUN_USER" = "llamapanel" ]; then
    sudo chown -R llamapanel:llamapanel "$PROJECT_DIR" 2>/dev/null || true
else
    # 用戶模式：不 chown，但確保當前用戶有讀寫權限
    sudo chown -R "$RUN_USER:$RUN_USER" "$PROJECT_DIR" 2>/dev/null || true
fi
sudo chown -R "$RUN_USER:$RUN_USER" "$DATA_DIR" 2>/dev/null || true
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
User=$RUN_USER
Group=$RUN_USER
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

# 配置 sudoers 权限（允许服務運行用戶重启自身服务 + 修复 .git 权限）
echo "🔐 配置 sudoers 权限..."
sudo tee /etc/sudoers.d/llamapanel > /dev/null << SUDOERS
# LlamaPanel 服务运行用户重启自身服务的权限
$RUN_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart llamapanel
# 允许更新时自动修复 .git 目录权限（无需用户手动操作）
$RUN_USER ALL=(ALL) NOPASSWD: /bin/chmod -R 777 $PROJECT_DIR/.git
# 允许更新时自动修复 .git 目录归属（一劳永逸解决权限问题）
$RUN_USER ALL=(ALL) NOPASSWD: /bin/chown -R $RUN_USER $PROJECT_DIR/.git
SUDOERS
sudo chmod 440 /etc/sudoers.d/llamapanel

# 将 .git 目录归属改为运行用戶（避免 git pull 权限问题）
sudo chown -R "$RUN_USER:$RUN_USER" "$PROJECT_DIR/.git" 2>/dev/null || true

# 将 .git 目录权限设为 777（避免 git pull/fetch 权限问题）
sudo chmod -R 777 "$PROJECT_DIR/.git" 2>/dev/null || true

# 忽略 git 的檔案權限變化（避免 chown 造成 git pull 衝突）
if [ -d "$PROJECT_DIR/.git" ]; then
    cd "$PROJECT_DIR" && git config core.fileMode false
fi

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
