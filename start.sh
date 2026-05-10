#!/bin/bash
set -e

echo "🚀 Patent Diff Analyzer — Quick Start"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start PostgreSQL + pgvector
echo "📦 Starting PostgreSQL + pgvector..."
cd infra
docker-compose up -d
cd ..

# Wait for database
sleep 3

# Check if Python virtual environment exists
if [ ! -d "venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing Python dependencies..."
pip install -q -r api/requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Copying from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env and add your OPENAI_API_KEY"
fi

# Start backend
echo "🌐 Starting FastAPI backend on http://localhost:8000"
echo ""
uvicorn api.main:app --reload --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "🎨 Starting Next.js frontend on http://localhost:3000"
cd web
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Patent Diff Analyzer is running!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap "echo ''; echo '🛑 Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker-compose -f infra/docker-compose.yml down; exit 0" INT
wait
