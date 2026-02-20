#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${STEALTH_BROWSER_MCP_PATH:-.stealth-browser-mcp}"

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "Clonando stealth-browser-mcp em $REPO_DIR..."
  git clone https://github.com/vibheksoni/stealth-browser-mcp.git "$REPO_DIR"
else
  echo "Repositorio ja existe em $REPO_DIR. Atualizando..."
  git -C "$REPO_DIR" pull --ff-only
fi

echo "Instalando dependencias do stealth-browser-mcp..."
python3 -m pip install -r "$REPO_DIR/requirements.txt"

echo "Instalacao concluida."
