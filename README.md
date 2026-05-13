# LlamaPanel

llama.cpp 图形化管理面板 - 无需命令行
这只是为了方便操作llama.cpp并非llama.cpp分支，实际使用的还是llama.cpp

## 功能

- 🚀 一键安装 llama.cpp
- 🔄 自动检测硬件（CPU核心数、GPU）
- 📊 实时编译进度显示
- 📋 彩色日志输出
- 🧹 清理编译产物
- ⚙️ 智能使用一半CPU核心编译，不影响Web服务

## 系统要求

- Ubuntu 24.04
- 2GB+ 内存
- 2GB+ 磁盘空间

## 一键安装

```bash
git clone https://github.com/CHENBIN-1979/llamapanel.git
cd llamapanel
chmod +x install.sh
sudo ./install.sh
sudo systemctl start llamapanel
```
