#!/bin/bash

# Test script for dual-agent system
cd /Users/hari/Documents/haricode/CXBuddy

echo "🧹 Cleaning up existing processes..."
lsof -ti:8003 | xargs kill -9 2>/dev/null
lsof -ti:8004 | xargs kill -9 2>/dev/null
lsof -ti:8005 | xargs kill -9 2>/dev/null
sleep 1

echo ""
echo "🚀 Starting Mock GXS API (port 8004)..."
python3 mock_gxs_api.py > mock_api.log 2>&1 &
sleep 2

echo "🚀 Starting Riley/Hari Server (port 8003)..."
python3 server.py > server.log 2>&1 &
sleep 2

echo "🚀 Starting HTTP Server for login (port 8005)..."
python3 -m http.server 8005 > http_server.log 2>&1 &
sleep 2

echo ""
echo "✅ All services started!"
echo ""
echo "📊 Service Status:"
echo "  Mock API (8004): $(curl -s http://localhost:8004/health 2>/dev/null || echo 'Not responding')"
echo "  Riley/Hari (8003): $(curl -s http://localhost:8003/health 2>/dev/null || echo 'Not responding')"
echo "  HTTP Server (8005): $(curl -s http://localhost:8005 2>/dev/null | head -1 || echo 'Not responding')"
echo ""
echo "🧪 Test URLs:"
echo "  Without login: http://localhost:8003"
echo "  With login: http://localhost:8005/mock_gxs_app.html"
echo ""
echo "📋 View logs:"
echo "  tail -f server.log"
echo "  tail -f mock_api.log"
