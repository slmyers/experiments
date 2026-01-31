#!/bin/bash
# Quick start script for the PostgreSQL MVCC Visualizer

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "🚀 PostgreSQL MVCC Bloat Visualizer - Quick Start"
echo "=================================================="
echo ""

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is required but not installed."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js is required but not installed."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "❌ npm is required but not installed."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed."; exit 1; }

echo "✅ Prerequisites check passed"
echo ""

# Check if PostgreSQL is running (check for common container name patterns)
if docker ps | grep -qE "(postgres|pg-mvcc)"; then
    echo "✅ PostgreSQL container is running"
else
    echo "⚠️  PostgreSQL container is not running"
    echo "   Run 'make infra AUTOVACUUM=disabled' to start it"
    exit 1
fi

# Install dependencies if needed
if [ ! -d "webapp/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd "$SCRIPT_DIR/webapp" && npm install
fi

# Check and install Python dependencies
echo "📦 Checking Python dependencies..."
pip3 install -q flask flask-cors psycopg2-binary 2>/dev/null || python3 -m pip install -q flask flask-cors psycopg2-binary

echo ""
echo "✅ All dependencies installed"
echo ""

# Start the servers
echo "🌐 Starting web application..."
echo ""
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:5001"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Cleanup on exit
cleanup() {
    echo ""
    echo "Stopping servers..."
    kill $API_PID 2>/dev/null
    kill $VITE_PID 2>/dev/null
    exit
}
trap cleanup INT TERM

# Start backend - output to terminal
echo "--- Starting Flask API ---"
cd "$SCRIPT_DIR/api"
python3 server.py 2>&1 &
API_PID=$!

# Give backend time to start and show any errors
sleep 3

# Check if API is running
if ! kill -0 $API_PID 2>/dev/null; then
    echo "❌ Flask API failed to start. Check errors above."
    exit 1
fi

echo "✅ Flask API started (PID: $API_PID)"
echo ""

# Start frontend
echo "--- Starting Vite ---"
cd "$SCRIPT_DIR/webapp"
npm run dev &
VITE_PID=$!

# Wait for either process to exit
wait
