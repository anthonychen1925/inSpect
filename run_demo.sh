#!/bin/bash
set -e

cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    wait 2>/dev/null
    echo "Done."
}
trap cleanup EXIT INT TERM

echo "Starting DiamondHacks demo..."
echo ""

if [ ! -d "data/fixtures" ] || [ -z "$(ls data/fixtures/*.json 2>/dev/null)" ]; then
    echo "ERROR: No fixture data found. Run these first:"
    echo "  python scripts/fetch_demo_data.py"
    echo "  python scripts/build_fixtures.py"
    exit 1
fi

echo "Step 1: Starting FastAPI backend on :8000"
DEMO_MODE=true uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"
echo ""

sleep 2

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "ERROR: Backend failed to start."
    exit 1
fi

echo "Step 2: Starting Next.js frontend on :3000"
cd frontend && npm run dev &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"
echo ""
cd ..

echo "Open: http://localhost:3000"
echo "API:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."
wait
