#!/bin/bash

VENV_DIR="venv"
REQ_FILE="requirements.txt"
RUN_CMD="uvicorn main:app --host 0.0.0.0 --port 8001 --reload"

# Helper function to activate the virtual environment
activate_venv() {
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
        echo "✅ Activated virtual environment ($VENV_DIR)."
    else
        echo "❌ Error: '$VENV_DIR' does not exist. Please run option 1 first."
    fi
}

# Helper function to install requirements
install_reqs() {
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
    fi
    if [ -f "$REQ_FILE" ]; then
        echo "📦 Installing dependencies from $REQ_FILE..."
        if command -v pip &>/dev/null; then
            pip install -r "$REQ_FILE"
        else
            python3 -m pip install -r "$REQ_FILE"
        fi
        echo "🌐 Ensuring Playwright Chromium is installed..."
        if command -v playwright &>/dev/null; then
            playwright install chromium
        elif [ -f "$VENV_DIR/bin/playwright" ]; then
            "$VENV_DIR/bin/playwright" install chromium
        fi
    else
        echo "⚠️ Warning: $REQ_FILE not found!"
    fi
}

while true; do
    echo "=========================================================================="
    echo "  Python VENV & FastAPI/Uvicorn Manager"
    echo "=========================================================================="
    echo "1. Create venv -> use venv"
    echo "2. Use venv -> install pip from requirements.txt"
    echo "3. Use venv -> install pip from requirements.txt > run: uvicorn main:app"
    echo "4. Run only: uvicorn main:app --host 0.0.0.0 --port 8001"
    echo "5. Install pip from requirements.txt > run: uvicorn main:app"
    echo "0. Exit"
    echo "=========================================================================="
    read -p "Enter your choice [0-5]: " choice

    case $choice in
        1)
            echo "Creating virtual environment..."
            python3 -m venv "$VENV_DIR"
            source "$VENV_DIR/bin/activate"
            echo "✅ Virtual environment created and activated."
            ;;
        2)
            activate_venv
            install_reqs
            ;;
        3)
            activate_venv
            install_reqs
            echo "🚀 Starting server..."
            $RUN_CMD
            ;;
        4)
            # Activates venv if it exists so Uvicorn can be found, then runs
            if [ -d "$VENV_DIR" ]; then
                source "$VENV_DIR/bin/activate"
            fi
            echo "🚀 Starting server..."
            if command -v uvicorn &>/dev/null; then
                $RUN_CMD
            elif [ -f "$VENV_DIR/bin/uvicorn" ]; then
                "$VENV_DIR/bin/uvicorn" main:app --host 0.0.0.0 --port 8001 --reload
            else
                echo "❌ Uvicorn not found. Please run option 2 or 3 first."
            fi
            ;;
        5)
            if [ -d "$VENV_DIR" ]; then
                source "$VENV_DIR/bin/activate"
            fi
            install_reqs
            echo "🚀 Starting server..."
            if command -v uvicorn &>/dev/null; then
                $RUN_CMD
            elif [ -f "$VENV_DIR/bin/uvicorn" ]; then
                "$VENV_DIR/bin/uvicorn" main:app --host 0.0.0.0 --port 8001 --reload
            else
                echo "❌ Uvicorn not found. Please run option 1 or 2 first."
            fi
            ;;
        0)
            echo "👋 Exiting..."
            exit 0
            ;;
        *)
            echo "❌ Invalid choice. Please enter a number between 0 and 5."
            ;;
    esac
    echo ""
done