#!/usr/bin/bash

RUNTIME_FIFO_DIR="/var/tmp/speakpy"
if [ ! -d $RUNTIME_FIFO_DIR ]; then
    echo "Creating runtime directory: $RUNTIME_FIFO_DIR"
    sudo mkdir -p $RUNTIME_FIFO_DIR
    sudo chown -R $USER: $RUNTIME_FIFO_DIR
fi

SCRIPT_DIR=$(dirname "$(realpath "$0")")
TARGET_BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
mkdir -p "$TARGET_BIN_DIR"
NEW_SCRIPT_PATH="${TARGET_BIN_DIR}/speakpy"
echo "Creating launcher script at $NEW_SCRIPT_PATH"
cat > "$NEW_SCRIPT_PATH" << EOL
#!/usr/bin/bash
cd "${SCRIPT_DIR}"
uv run main.py
EOL

chmod +x "$NEW_SCRIPT_PATH"

echo "Launcher script created and made executable."
echo "You can now run 'run_main.sh' from your terminal."
echo "Please ensure '${TARGET_BIN_DIR}' is in your \$PATH."


