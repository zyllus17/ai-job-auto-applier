.PHONY: run install clean help

# ─── AI Job Auto-Applier Dashboard ───────────────────────────────────
# Usage:  make run     → install deps, free port, start server & browser
#         make install → install Python dependencies only
#         make clean   → stop any running dashboard processes
#
# Note for Windows users:
# If you do not have 'make' installed, you can simply run:
#   run.bat        (Command Prompt or double-click)
#   .\run.ps1      (PowerShell)
#   python run.py  (Universal)

ifeq ($(OS),Windows_NT)
    PYTHON ?= python
else
    PYTHON ?= python3
endif

PORT := 8420
URL  := http://localhost:$(PORT)

help: ## Show this help
	@echo ""
	@echo "🚀 AI Job Auto-Applier Dashboard"
	@echo "─────────────────────────────────"
	@echo "  make run      - Install deps, free port, start dashboard & open browser"
	@echo "  make install  - Install dashboard Python dependencies only"
	@echo "  make clean    - Terminate any running dashboard processes on port $(PORT)"
	@echo ""
	@echo "Windows Alternatives (no make required):"
	@echo "  run.bat       - Double-click or run from CMD"
	@echo "  .\\\\run.ps1     - Run in Windows PowerShell"
	@echo "  python run.py - Universal cross-platform launcher"
	@echo ""

install: ## Install Python dependencies
	@$(PYTHON) run.py --install

run: ## Kill previous run, install deps, and start dashboard & browser
	@$(PYTHON) run.py

clean: ## Stop any running dashboard processes
	@$(PYTHON) run.py --clean-only
