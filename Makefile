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
	@$(PYTHON) -m pip install --quiet fastapi "uvicorn[standard]" websockets psutil python-dotenv 2>/dev/null || \
		$(PYTHON) -m pip install fastapi "uvicorn[standard]" websockets psutil python-dotenv
	@echo "✅ Dependencies installed"

run: install ## Start the dashboard and open browser
	@echo ""
	@echo "🚀 Starting AI Job Auto-Applier Dashboard..."
	@echo "   URL: $(URL)"
	@echo "   Press Ctrl+C to stop"
	@echo ""
	@( sleep 2 && $(PYTHON) -c "import webbrowser; webbrowser.open('$(URL)')" ) &
	@$(PYTHON) -m uvicorn dashboard.server:app --host 0.0.0.0 --port $(PORT) --reload

clean: ## Stop any running dashboard processes
	@echo "🧹 Stopping dashboard..."
	@-pkill -f "uvicorn dashboard.server" 2>/dev/null || true
	@echo "✅ Cleaned up"
