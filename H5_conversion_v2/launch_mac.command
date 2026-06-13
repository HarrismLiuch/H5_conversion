#!/usr/bin/env zsh
# macOS auto-runs .command files in Terminal on double-click — no "Open With"
# prompt, and the Terminal window stays open so error messages are visible.
#
# This is the recommended double-click entry point on macOS.

set -e
cd "$(dirname "$0")"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${TMPDIR:-/tmp}/h5conv-matplotlib}"

# 1. Make sure `uv` is on PATH. The installer appends to ~/.zshrc / fish,
#    but those files may be root-owned and unwritable. We instead source
#    the env drop-in that the installer always writes successfully to
#    ~/.local/bin/env.
if ! command -v uv >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/uv" ]; then
        export PATH="$HOME/.local/bin:$PATH"
    elif [ -x "$HOME/.cargo/bin/uv" ]; then
        export PATH="$HOME/.cargo/bin:$PATH"
    else
        echo "uv not found anywhere; trying the installer once…"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        # shellcheck disable=SC1091
        [ -f "$HOME/.local/bin/env" ] && source "$HOME/.local/bin/env"
    fi
fi

if ! command -v uv >/dev/null 2>&1; then
    echo
    echo "ERROR: uv is still not on PATH after the install attempt."
    echo "Try installing it manually:"
    echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Then add this to your shell rc (or open a new Terminal):"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo
    read -r "?Press Enter to close…"
    exit 1
fi

# 2. Create / update the venv and install deps.
echo "Syncing dependencies (this may take a minute on first run)…"
uv sync

# 3. Run the GUI.
uv run python run.py
status=$?

# 4. If the GUI exited non-zero, keep the window open.
if [ $status -ne 0 ]; then
    echo
    echo "The GUI exited with status $status."
    read -r "?Press Enter to close…"
fi
exit $status
