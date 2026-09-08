#!/bin/bash
# ==============================================================================
# AI Job Search - 1-Command Turnkey Quickstart for Antigravity
# ==============================================================================

set -e

echo ""
echo "================================================================="
echo "   AI JOB SEARCH - AUTONOMOUS FRAMEWORK SETUP FOR ANTIGRAVITY    "
echo "================================================================="
echo "Setting up your automated job search, CV generator, and tracker..."
echo ""

# 1. Check & Install Bun
if ! command -v bun &> /dev/null; then
  echo "[+] Installing Bun runtime..."
  if command -v brew &> /dev/null; then
    brew install bun
  elif command -v npm &> /dev/null; then
    npm install -g bun
  else
    curl -fsSL https://bun.sh/install | bash
    export PATH="$HOME/.bun/bin:$PATH"
  fi
else
  echo "[OK] Bun runtime found: $(bun --version)"
fi

# 2. Check & Install Python Dependencies
echo "[+] Checking Python dependencies..."
PYTHON_BIN=$(command -v python3 || command -v python)
if [ -n "$PYTHON_BIN" ]; then
  $PYTHON_BIN -m pip install --quiet pypdf pyyaml
  echo "[OK] Python dependencies installed (pypdf, pyyaml)."
else
  echo "[!] Python 3 not found. Please install Python 3.10+."
fi

# 3. Check & Install TinyTeX (User space - no sudo needed)
if ! command -v lualatex &> /dev/null && [ ! -d "$HOME/Library/TinyTeX" ]; then
  echo "[+] Installing lightweight TinyTeX for compiling PDF resumes..."
  curl -fsSL https://yihui.org/tinytex/install-bin-unix.sh -o /tmp/tinytex-install.sh
  sh /tmp/tinytex-install.sh /tmp --no-path || true
  rm -f /tmp/tinytex-install.sh
  
  if [ -d "$HOME/Library/TinyTeX/bin/universal-darwin" ]; then
    export PATH="$HOME/Library/TinyTeX/bin/universal-darwin:$PATH"
    tlmgr install moderncv fontawesome5 fontawesome6 academicons import luatexbase pgf titlesec textpos xltxtra xunicode cite realscripts needspace || true
  fi
  echo "[OK] TinyTeX ready."
else
  echo "[OK] LaTeX compilation engine ready."
fi

# 4. Register Antigravity Global Skill
echo "[+] Registering Antigravity global skill..."
GLOBAL_SKILL_DIR="$HOME/.gemini/config/skills/ai-job-search"
mkdir -p "$GLOBAL_SKILL_DIR"
cp -f .agents/skills/ai-job-search/SKILL.md "$GLOBAL_SKILL_DIR/SKILL.md"
echo "[OK] Registered in $GLOBAL_SKILL_DIR."

# 5. Quick Configuration Check
if grep -q "\[YOUR_NAME\]" CLAUDE.md 2>/dev/null; then
  echo ""
  echo "-----------------------------------------------------------------"
  echo "Let's personalize your job search assistant. Only 3 quick questions:"
  echo "-----------------------------------------------------------------"
  
  read -p "1. What is your full name? " USER_NAME
  read -p "2. What is your target role (e.g. AI Automation, Fullstack)? " USER_ROLE
  read -p "3. Preferred work mode (e.g. Remote Worldwide, India, US)? " USER_LOC
  read -p "4. (Optional) Google Sheet Webhook URL (press Enter to skip): " SHEET_URL
  
  if [ -n "$USER_NAME" ]; then
    sed -i '' "s/\[YOUR_NAME\]/$USER_NAME/g" CLAUDE.md 2>/dev/null || sed -i "s/\[YOUR_NAME\]/$USER_NAME/g" CLAUDE.md
    sed -i '' "s/\[YOUR_PRIMARY_ROLE_TYPE\]/$USER_ROLE/g" CLAUDE.md 2>/dev/null || sed -i "s/\[YOUR_PRIMARY_ROLE_TYPE\]/$USER_ROLE/g" CLAUDE.md
  fi
  
  if [ -n "$SHEET_URL" ]; then
    $PYTHON_BIN tools/google_sheets_sync.py --set-webhook "$SHEET_URL"
  fi
fi

echo ""
echo "================================================================="
echo "   🎉 SETUP COMPLETE!                                           "
echo "================================================================="
echo "Open this folder in Google Antigravity and you can immediately run:"
echo "  /run-jobs-search     -> Starts autonomous continuous job search"
echo "  /scrape              -> Scrape matching jobs on demand"
echo "  /apply <job_url>     -> Generate tailored CV & cover letter PDF"
echo "================================================================="
echo ""
