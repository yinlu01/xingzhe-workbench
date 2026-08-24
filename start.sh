#!/bin/bash
# 行者工作台 PWA 启动脚本
# 一键启动服务器并显示访问地址

DIR="$(cd "$(dirname "$0")" && pwd)"
PID=$(lsof -ti:8765 2>/dev/null)

if [ -n "$PID" ]; then
    echo "⚠️  服务器已在运行 (PID: $PID)"
    echo "   停止: kill $PID"
else
    cd "$DIR"
    /Users/yinlu01/.workbuddy/binaries/python/envs/default/bin/python -u server.py &
    sleep 2
    
    if lsof -ti:8765 > /dev/null 2>&1; then
        IP=$(ipconfig getifaddr en0 2>/dev/null || echo "127.0.0.1")
        echo ""
        echo "==========================================="
        echo "  行者 · 生活工作台 已启动"
        echo ""
        echo "  本机访问: http://localhost:8765"
        echo "  手机访问: http://${IP}:8765"
        echo "==========================================="
        echo ""
        echo "  📱 Android 手机安装步骤："
        echo "  1. 确保手机和电脑在同一 WiFi"
        echo "  2. Chrome 打开: http://${IP}:8765"
        echo "  3. 浏览器菜单 → 添加到主屏幕"
        echo ""
        echo "  📱 iOS 手机安装步骤："
        echo "  1. Safari 打开: http://${IP}:8765"
        echo "  2. 底部分享按钮 → 添加到主屏幕"
        echo ""
    else
        echo "❌ 服务器启动失败，请检查端口 8765 是否被占用"
    fi
fi
