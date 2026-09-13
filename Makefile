.PHONY: run install clean test help

# ─── AI Job Auto-Applier Dashboard ───────────────────────────────────
# Usage:  make run     → install deps, free port, start server & browser
#         make install → install Python dependencies & browser binaries
#         make clean   → stop any running dashboard processes
#         make test    → run test suite
#
# Note for Windows users:
# If you do not have 'make' installed, Windows Command Prompt natively runs:
#   make.bat run   (or just 'make run' from CMD)
#   .\make.ps1 run (PowerShell)
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
	@echo "  make test     - Run automated test suite"
	@echo ""
	@echo "Windows Alternatives (no GNU make required):"
	@echo "  make.bat      - Native Windows CMD make shim (type 'make run')"
	@printf "  .\\\\make.ps1   - Native Windows PowerShell make shim\n"
	@echo "  run.bat       - Double-click or run from CMD"
	@printf "  .\\\\run.ps1    - Run in Windows PowerShell\n"
	@echo "  python run.py - Universal cross-platform launcher"
	@echo ""

install: ## Install Python dependencies
	@$(PYTHON) run.py --install

run: ## Kill previous run, install deps, and start dashboard & browser
	@$(PYTHON) run.py

clean: ## Stop any running dashboard processes
	@$(PYTHON) run.py --clean-only

test: ## Run automated test suite
	@$(PYTHON) run.py --test

