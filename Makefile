.PHONY: run install clean help

# ─── AI Job Auto-Applier Dashboard ───────────────────────────────────
# Usage:  make run     → install deps, start server, open browser
#         make install → install Python dependencies only
#         make clean   → stop any running dashboard processes

PYTHON := python3
PORT   := 8420
URL    := http://localhost:$(PORT)

help: ## Show this help
	@echo ""
	@echo "🚀 AI Job Auto-Applier Dashboard"
	@echo "─────────────────────────────────"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-12s %s\n", $$1, $$2}'
	@echo ""

install: ## Install Python dependencies
	@echo "📦 Installing dependencies..."
	@$(PYTHON) -m pip install --quiet fastapi "uvicorn[standard]" websockets psutil python-dotenv playwright 2>/dev/null || \
		$(PYTHON) -m pip install fastapi "uvicorn[standard]" websockets psutil python-dotenv playwright
	@echo "✅ Dependencies installed"

run: clean install ## Kill previous run, install deps, and start a fresh dashboard
	@echo ""
	@echo "🚀 Starting AI Job Auto-Applier Dashboard..."
	@echo "   URL: $(URL)"
	@echo "   Press Ctrl+C to stop"
	@echo ""
	@( sleep 2 && $(PYTHON) -c "import webbrowser; webbrowser.open('$(URL)')" ) &
	@$(PYTHON) -m uvicorn dashboard.server:app --host 0.0.0.0 --port $(PORT) --reload

clean: ## Stop any running dashboard processes
	@echo "🧹 Stopping any previous dashboard run..."
	@-PIDS=$$(lsof -t -i :$(PORT) 2>/dev/null); if [ -n "$$PIDS" ]; then echo "$$PIDS" | xargs kill -9 2>/dev/null || true; fi
	@-pkill -f "uvicorn dashboard.server" 2>/dev/null || true
	@-pkill -f "dashboard/server.py" 2>/dev/null || true
	@sleep 0.5
	@echo "✅ Cleaned up"
