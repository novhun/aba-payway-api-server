#!/usr/bin/env bash
# ==============================================================================
# ABA PayWay Web-Automation Engine - All-In-One VPS Deployment & Manager
# ==============================================================================

set -e

# Prevent interactive prompts from apt / needrestart
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
export NEEDRESTART_SUSPEND=1

# Colors for UI
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_REPO_URL="https://github.com/novhun/aba-payway-api-server.git"
DEFAULT_GIT_USER="novhun"

# Silent APT installer helper
apt_install() {
    export DEBIAN_FRONTEND=noninteractive
    export NEEDRESTART_MODE=a
    apt-get update -y -q >/dev/null 2>&1 || apt-get update -y
    apt-get install -y -q -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" "$@" >/dev/null 2>&1 || apt-get install -y "$@"
}

# Auto-Locate or Clone Project Repository (Fixes missing requirements.txt error)
ensure_project_files() {
    # If requirements.txt is already in current APP_DIR, we are good
    if [ -f "$APP_DIR/requirements.txt" ] && [ -f "$APP_DIR/main.py" ]; then
        cd "$APP_DIR"
        return 0
    fi

    # Check if /opt/aba-payway exists and has files
    if [ -f "/opt/aba-payway/requirements.txt" ]; then
        APP_DIR="/opt/aba-payway"
        cd "$APP_DIR"
        return 0
    fi

    # Check if subfolder exists
    if [ -f "$APP_DIR/aba-payway-api-server/requirements.txt" ]; then
        APP_DIR="$APP_DIR/aba-payway-api-server"
        cd "$APP_DIR"
        return 0
    fi

    # If missing, automatically clone the repo
    echo -e "\n${YELLOW}⚠️ Project files not found in: $APP_DIR${NC}"
    echo -e "${BLUE}📥 Automatically cloning repository into /opt/aba-payway...${NC}"
    
    check_install_git
    mkdir -p /opt/aba-payway
    
    if [ -d "/opt/aba-payway/.git" ]; then
        cd /opt/aba-payway
        git pull || true
    else
        git clone "$DEFAULT_REPO_URL" /opt/aba-payway || {
            echo -e "${RED}❌ Failed to clone repository. Please check your internet connection.${NC}"
            exit 1
        }
    fi
    
    APP_DIR="/opt/aba-payway"
    cd "$APP_DIR"
    echo -e "${GREEN}✅ Repository ready at $APP_DIR${NC}"
}

# Print Header Banner
print_banner() {
    clear
    echo -e "${CYAN}==============================================================================${NC}"
    echo -e "${GREEN}${BOLD}       ABA PayWay Web-Automation Engine - VPS All-In-One Manager       ${NC}"
    echo -e "${CYAN}==============================================================================${NC}"
    echo -e " Directory:  ${PURPLE}$APP_DIR${NC}"
    echo -e " Repository: ${BLUE}$DEFAULT_REPO_URL${NC}"
    echo -e "${CYAN}------------------------------------------------------------------------------${NC}"
}

# Check Root / Sudo
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}❌ Please run this script with sudo or as root.${NC}"
        echo -e "   Example: ${YELLOW}sudo bash host.sh${NC}"
        exit 1
    fi
}

# Auto-Check & Install Git (Skips if already present)
check_install_git() {
    if command -v git &> /dev/null; then
        echo -e "${GREEN}✅ Git is already installed: $(git --version)${NC}"
        return 0
    fi

    echo -e "\n${BLUE}🐙 Installing Git...${NC}"
    apt_install git
    echo -e "${GREEN}✅ Git installed successfully: $(git --version)${NC}"
}

# Auto-Check & Install Python 3, Pip & Venv (Skips if already present)
check_install_python() {
    if command -v python3 &> /dev/null && command -v pip3 &> /dev/null && python3 -m venv --help &> /dev/null; then
        echo -e "${GREEN}✅ Python 3 & Venv already installed: $(python3 --version)${NC}"
        return 0
    fi

    echo -e "\n${BLUE}🐍 Installing Python 3, Pip, and Venv...${NC}"
    apt_install python3 python3-pip python3-venv python3-dev build-essential
    echo -e "${GREEN}✅ Python 3 environment installed successfully!${NC}"
}

# Login to Git with Personal Access Token (PAT)
login_git_token() {
    check_install_git

    local passed_token="$1"
    local passed_user="$2"

    echo -e "\n${CYAN}==============================================================================${NC}"
    echo -e "${PURPLE}${BOLD}                   🐙 GitHub / Git Token Authentication                       ${NC}"
    echo -e "${CYAN}==============================================================================${NC}"
    echo -e " This will configure Git with your GitHub Personal Access Token (PAT) so you"
    echo -e " can pull private repos, push code, and update without password prompts."
    echo ""
    echo -e " 💡 Create a token at: ${CYAN}https://github.com/settings/tokens${NC}"
    echo -e "    (Recommended scopes: ${YELLOW}repo${NC} or ${YELLOW}workflow${NC})"
    echo -e "${CYAN}------------------------------------------------------------------------------${NC}"

    local git_user="${passed_user}"
    if [ -z "$git_user" ]; then
        read -p "Enter GitHub Username [default: ${DEFAULT_GIT_USER}]: " input_user
        git_user=${input_user:-$DEFAULT_GIT_USER}
    fi

    local git_token="${passed_token}"
    if [ -z "$git_token" ]; then
        echo ""
        echo -e "${YELLOW}Paste or type your GitHub Personal Access Token (PAT) below:${NC}"
        read -p "Git Token (e.g. ghp_xxxxxxxxxxxx): " git_token
    fi

    # Sanitize token
    git_token=$(echo "$git_token" | tr -d '\r\n[:space:]')

    if [ -z "$git_token" ]; then
        echo -e "${RED}❌ Token cannot be empty. Authentication aborted.${NC}"
        return 1
    fi

    # Enable credential helper store
    git config --global credential.helper store
    git config --global user.name "$git_user"
    if [ -z "$(git config --global user.email 2>/dev/null)" ]; then
        git config --global user.email "${git_user}@users.noreply.github.com"
    fi

    # Save to ~/.git-credentials
    local cred_file="$HOME/.git-credentials"
    touch "$cred_file"
    chmod 600 "$cred_file"

    sed -i "\|@github.com|d" "$cred_file" 2>/dev/null || true
    echo "https://${git_user}:${git_token}@github.com" >> "$cred_file"

    # Update git remote URL
    if [ -d "$APP_DIR/.git" ]; then
        cd "$APP_DIR"
        git remote set-url origin "https://${git_user}:${git_token}@github.com/novhun/aba-payway-api-server.git" 2>/dev/null || true
    fi

    echo -e "\n${GREEN}✅ Git credentials successfully saved to $cred_file!${NC}"
    echo -e "${BLUE}📡 Testing GitHub connection against repository...${NC}"

    if git ls-remote "https://${git_user}:${git_token}@github.com/novhun/aba-payway-api-server.git" HEAD &>/dev/null; then
        echo -e "${GREEN}${BOLD}🎉 SUCCESS: GitHub authentication verified for user: ${git_user}!${NC}"
    else
        echo -e "${YELLOW}⚠️ Notice: Unable to verify token online. Please check that the token has 'repo' permissions.${NC}"
    fi
}

# Git Configuration & Login Assistant Menu
setup_git_auth() {
    check_install_git
    while true; do
        print_banner
        echo -e "${PURPLE}${BOLD}--- 🐙 Git Configuration & Authentication Manager ---${NC}"
        
        local current_name=$(git config --global user.name 2>/dev/null || echo "Not set")
        local current_email=$(git config --global user.email 2>/dev/null || echo "Not set")
        local cred_helper=$(git config --global credential.helper 2>/dev/null || echo "Not set")
        
        echo -e " Current User Name:  ${YELLOW}$current_name${NC}"
        echo -e " Current User Email: ${YELLOW}$current_email${NC}"
        echo -e " Credential Helper:  ${YELLOW}$cred_helper${NC}"
        echo -e "${CYAN}------------------------------------------------------------------------------${NC}"
        echo -e " ${GREEN}1)${NC} 🔑 Login with Git Personal Access Token (PAT) (Input on Terminal)"
        echo -e " ${GREEN}2)${NC} 👤 Configure Git User Name & Email"
        echo -e " ${GREEN}3)${NC} 🛡️  Generate & View SSH Key (for GitHub / GitLab SSH Access)"
        echo -e " ${GREEN}4)${NC} 🧪 Test Git Connection & View Remotes"
        echo -e " ${RED}0)${NC} 🔙 Back to Main Menu"
        echo -e "${CYAN}------------------------------------------------------------------------------${NC}"
        read -p "Select an option [0-4]: " git_choice

        case $git_choice in
            1)
                login_git_token
                read -p "Press Enter to continue..."
                ;;
            2)
                echo -e "\n${BLUE}👤 Setting Global Git User Details...${NC}"
                read -p "Enter your Git Name [default: $DEFAULT_GIT_USER]: " new_name
                new_name=${new_name:-$DEFAULT_GIT_USER}
                read -p "Enter your Git Email: " new_email
                if [ -n "$new_name" ]; then
                    git config --global user.name "$new_name"
                fi
                if [ -n "$new_email" ]; then
                    git config --global user.email "$new_email"
                fi
                echo -e "${GREEN}✅ Git user information updated!${NC}"
                sleep 1.5
                ;;
            3)
                echo -e "\n${BLUE}🛡️  SSH Key Setup for GitHub / GitLab...${NC}"
                SSH_KEY="$HOME/.ssh/id_ed25519"
                if [ ! -f "$SSH_KEY" ]; then
                    SSH_KEY="$HOME/.ssh/id_rsa"
                fi

                if [ ! -f "${SSH_KEY}.pub" ]; then
                    echo -e "${YELLOW}No SSH key found. Generating new ED25519 SSH Key...${NC}"
                    mkdir -p "$HOME/.ssh"
                    chmod 700 "$HOME/.ssh"
                    SSH_KEY="$HOME/.ssh/id_ed25519"
                    ssh-keygen -t ed25519 -C "vps-deploy@aba-payway" -N "" -f "$SSH_KEY"
                    echo -e "${GREEN}✅ SSH Key generated at $SSH_KEY${NC}"
                fi

                echo -e "\n${CYAN}======================== YOUR PUBLIC SSH KEY ========================${NC}"
                echo -e "${YELLOW}$(cat "${SSH_KEY}.pub")${NC}"
                echo -e "${CYAN}=====================================================================${NC}"
                echo -e "\n${BOLD}Instructions to add to GitHub / GitLab:${NC}"
                echo -e " 1. Copy the public key above."
                echo -e " 2. Go to: ${CYAN}https://github.com/settings/keys${NC} (or GitLab Profile -> SSH Keys)"
                echo -e " 3. Click ${GREEN}'New SSH Key'${NC}, give it a title (e.g. 'Production VPS'), and paste the key."
                echo ""
                read -p "Would you like to test SSH connection to GitHub now? [y/N]: " test_ssh
                if [[ "$test_ssh" =~ ^[Yy]$ ]]; then
                    echo -e "${BLUE}Connecting to git@github.com...${NC}"
                    ssh -o StrictHostKeyChecking=accept-new -T git@github.com 2>&1 | grep -i "successfully authenticated" && echo -e "${GREEN}✅ GitHub SSH Authentication successful!${NC}" || echo -e "${YELLOW}Response from server above.${NC}"
                fi
                read -p "Press Enter to continue..."
                ;;
            4)
                echo -e "\n${BLUE}🧪 Current Git Status & Remotes:${NC}"
                if [ -d "$APP_DIR/.git" ]; then
                    cd "$APP_DIR"
                    echo -e "${CYAN}--- Remote URLs ---${NC}"
                    git remote -v
                    echo -e "\n${CYAN}--- Branch & Status ---${NC}"
                    git status -s || git status
                    echo -e "\n${CYAN}--- Testing Fetch ---${NC}"
                    git fetch --dry-run && echo -e "${GREEN}✅ Remote is reachable.${NC}" || echo -e "${RED}❌ Fetch failed. Check authentication.${NC}"
                else
                    echo -e "${YELLOW}This directory is not a Git repository.${NC}"
                fi
                read -p "Press Enter to continue..."
                ;;
            0)
                break
                ;;
            *)
                echo -e "${RED}❌ Invalid option.${NC}"
                sleep 1
                ;;
        esac
    done
}

# Check & Setup Swap Memory (Skips automatically if >=1GB swap exists)
setup_swap() {
    local existing_swap=$(free -m | awk '/^Swap:/{print $2}')
    if [ "$existing_swap" -ge 1024 ]; then
        echo -e "${GREEN}✅ Swap memory is sufficient (${existing_swap} MB). Skipping swap creation.${NC}"
        return 0
    fi

    echo -e "\n${BLUE}🔍 Creating 2GB Swap Memory (for Playwright Chromium)...${NC}"
    fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null 2>&1
    swapon /swapfile 2>/dev/null || true
    if ! grep -q '/swapfile' /etc/fstab; then
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi
    echo -e "${GREEN}✅ 2GB Swapfile activated successfully.${NC}"
}

# Install Docker & Compose (Skips if already running)
install_docker() {
    if command -v docker &> /dev/null && docker info &> /dev/null; then
        echo -e "${GREEN}✅ Docker is already installed and running: $(docker --version)${NC}"
        return 0
    fi

    echo -e "\n${BLUE}🐳 Installing Docker & Docker Compose plugin...${NC}"
    apt_install ca-certificates curl gnupg lsb-release
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker >/dev/null 2>&1
    echo -e "${GREEN}✅ Docker installed successfully.${NC}"
}

# Safe .env variable writer
set_env_var() {
    local key="$1"
    local val="$2"
    local env_file="$APP_DIR/.env"

    if [ ! -f "$env_file" ]; then
        touch "$env_file"
    fi

    if grep -q "^${key}=" "$env_file"; then
        sed -i "s|^${key}=.*|${key}=${val}|" "$env_file" 2>/dev/null || true
    else
        echo "${key}=${val}" >> "$env_file"
    fi
}

# Configure Environment Variables (.env)
configure_env() {
    ensure_project_files

    local env_file="$APP_DIR/.env"
    local env_example="$APP_DIR/.env.example"

    # If .env already exists with non-default values, skip prompt
    if [ -f "$env_file" ]; then
        local cur_pass=$(grep "^ADMIN_PASSWORD=" "$env_file" 2>/dev/null | cut -d '=' -f2- || true)
        local cur_user=$(grep "^ADMIN_USERNAME=" "$env_file" 2>/dev/null | cut -d '=' -f2- || true)
        if [ -n "$cur_pass" ] && [ "$cur_pass" != "admin" ] && [ -n "$cur_user" ]; then
            echo -e "${GREEN}✅ Environment (.env) already configured (Admin: ${cur_user}). Skipping.${NC}"
            set_env_var "PORT" "8000"
            touch "$APP_DIR/aba_automation.db"
            chmod 666 "$APP_DIR/aba_automation.db"
            return 0
        fi
    fi

    echo -e "\n${BLUE}⚙️  Configuring Environment (.env)...${NC}"
    if [ ! -f "$env_file" ]; then
        if [ -f "$env_example" ]; then
            cp "$env_example" "$env_file"
        else
            touch "$env_file"
        fi
    fi

    set_env_var "PORT" "8000"

    read -p "Enter Admin Username [default: admin]: " input_user
    ADMIN_USER=${input_user:-admin}
    set_env_var "ADMIN_USERNAME" "$ADMIN_USER"

    read -p "Enter Admin Password [default: Admin@12345]: " input_pass
    ADMIN_PASS=${input_pass:-Admin@12345}
    set_env_var "ADMIN_PASSWORD" "$ADMIN_PASS"

    touch "$APP_DIR/aba_automation.db"
    chmod 666 "$APP_DIR/aba_automation.db"

    echo -e "${GREEN}✅ Environment configured successfully.${NC}"
}

# Configure Firewall (Skips if rules already active)
configure_firewall() {
    if ! command -v ufw &> /dev/null; then
        echo -e "${YELLOW}UFW not installed, skipping firewall setup.${NC}"
        return 0
    fi

    if ufw status | grep -q "8000/tcp.*ALLOW"; then
        echo -e "${GREEN}✅ Firewall rules already configured. Skipping.${NC}"
        return 0
    fi

    echo -e "\n${BLUE}🛡️  Configuring UFW Firewall...${NC}"
    ufw allow 22/tcp comment 'SSH' >/dev/null 2>&1 || true
    ufw allow 80/tcp comment 'HTTP' >/dev/null 2>&1 || true
    ufw allow 443/tcp comment 'HTTPS' >/dev/null 2>&1 || true
    ufw allow 8000/tcp comment 'ABA PayWay API' >/dev/null 2>&1 || true
    ufw --force enable >/dev/null 2>&1 || true
    echo -e "${GREEN}✅ Firewall rules updated (Ports 22, 80, 443, 8000 allowed).${NC}"
}

# Print Deployment Complete Info
print_deployment_info() {
    local deploy_type="$1"
    local ip=$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_VPS_IP')
    echo -e "\n${CYAN}==============================================================================${NC}"
    echo -e "${GREEN}${BOLD}🎉 Deployment Complete! Mode: ${YELLOW}[$deploy_type]${NC}"
    echo -e "${CYAN}------------------------------------------------------------------------------${NC}"
    echo -e " 🌐 API Base URL:  ${YELLOW}http://$ip:8000${NC}"
    echo -e " 📚 Swagger Docs:  ${YELLOW}http://$ip:8000/docs${NC}"
    echo -e " 👑 Admin Panel:   ${YELLOW}http://$ip:8000/admin${NC}"
    echo -e " 🩺 Health Check:  ${YELLOW}http://$ip:8000/api/system/info${NC}"
    echo -e "${CYAN}==============================================================================${NC}"
}

# ==============================================================================
# DEPLOYMENT OPTION 1: DOCKER & DOCKER COMPOSE
# ==============================================================================
deploy_docker_mode() {
    echo -e "\n${PURPLE}${BOLD}==============================================================================${NC}"
    echo -e "${GREEN}${BOLD}     🐳 STARTING DEPLOYMENT: DOCKER & DOCKER COMPOSE MODE                     ${NC}"
    echo -e "${PURPLE}${BOLD}==============================================================================${NC}"

    check_root
    ensure_project_files
    check_install_git
    setup_swap
    install_docker
    configure_env
    configure_firewall

    # Stop native systemd service if running to prevent port 8000 conflict
    if systemctl is-active --quiet aba-payway 2>/dev/null; then
        echo -e "${YELLOW}Stopping conflicting Systemd service (aba-payway)...${NC}"
        systemctl stop aba-payway || true
        systemctl disable aba-payway || true
    fi

    echo -e "\n${BLUE}🚀 Building and Starting Docker Container...${NC}"
    cd "$APP_DIR"
    docker compose down --remove-orphans >/dev/null 2>&1 || true
    docker compose up -d --build

    echo -e "\n${GREEN}Checking Docker container status...${NC}"
    sleep 3
    docker compose ps

    print_deployment_info "Docker Container"
}

# ==============================================================================
# DEPLOYMENT OPTION 2: REAL / NATIVE ON VPS (SYSTEMD + PYTHON VENV)
# ==============================================================================
deploy_native_mode() {
    echo -e "\n${PURPLE}${BOLD}==============================================================================${NC}"
    echo -e "${GREEN}${BOLD}     🖥️  STARTING DEPLOYMENT: REAL ON VPS (NATIVE HOST + SYSTEMD)             ${NC}"
    echo -e "${PURPLE}${BOLD}==============================================================================${NC}"

    check_root
    ensure_project_files
    check_install_git
    setup_swap
    check_install_python
    configure_env
    configure_firewall

    # Stop docker container if running to prevent port 8000 conflict
    if command -v docker &>/dev/null; then
        cd "$APP_DIR"
        docker compose down >/dev/null 2>&1 || true
    fi

    cd "$APP_DIR"
    echo -e "\n${BLUE}📦 Setting up Python Virtual Environment (venv)...${NC}"
    if [ ! -d "$APP_DIR/venv" ]; then
        python3 -m venv "$APP_DIR/venv"
    fi

    source "$APP_DIR/venv/bin/activate"
    echo -e "${BLUE}📥 Installing Python requirements from $APP_DIR/requirements.txt...${NC}"
    pip install --upgrade pip >/dev/null 2>&1 || true
    pip install -r "$APP_DIR/requirements.txt"

    # Install system libraries for Chromium in Linux (compatible with Ubuntu 20/22/24/26)
    echo -e "${BLUE}📦 Ensuring Chromium system libraries and browser are installed...${NC}"
    apt_install curl ca-certificates fonts-liberation fonts-noto-color-emoji \
        libnss3 libnspr4 libcups2t64 libdrm2 libxkbcommon0 \
        libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
        libasound2t64 libxshmfence1 libfontconfig1 libx11-xcb1 libxcb-dri3-0 2>/dev/null || true

    # Install Google Chrome or Chromium directly if missing
    if ! command -v google-chrome &>/dev/null && ! command -v chromium &>/dev/null && ! command -v chromium-browser &>/dev/null; then
        echo -e "${BLUE}🌐 Installing Chrome/Chromium browser package...${NC}"
        apt_install wget ca-certificates gnupg 2>/dev/null || true
        wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/trusted.gpg.d/google-chrome.gpg 2>/dev/null || true
        echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list 2>/dev/null || true
        apt-get update -y -q >/dev/null 2>&1 || true
        apt_install google-chrome-stable 2>/dev/null || apt_install chromium-browser 2>/dev/null || apt_install chromium 2>/dev/null || true
    fi

    # Install Playwright Chromium browser
    echo -e "${BLUE}🎭 Installing Playwright Chromium...${NC}"
    playwright install chromium 2>/dev/null || {
        python3 -m playwright install chromium 2>/dev/null || true
    }
    echo -e "${GREEN}✅ Browser engine configured successfully!${NC}"

    echo -e "\n${BLUE}⚙️  Configuring Systemd Service (/etc/systemd/system/aba-payway.service)...${NC}"
    SERVICE_FILE="/etc/systemd/system/aba-payway.service"
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=ABA PayWay Web-Automation Engine
After=network.target

[Service]
User=root
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=$APP_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable --now aba-payway >/dev/null 2>&1
    echo -e "${GREEN}✅ Systemd service installed and started!${NC}"
    sleep 2
    systemctl status aba-payway --no-pager

    print_deployment_info "Native Host (Systemd)"
}

# Setup Nginx Reverse Proxy with SSL (Certbot)
setup_nginx_ssl() {
    echo -e "\n${BLUE}🌐 Setup Nginx Reverse Proxy + Free SSL (Let's Encrypt)...${NC}"
    read -p "Enter your domain name (e.g., api.yourdomain.com): " DOMAIN_NAME
    if [ -z "$DOMAIN_NAME" ]; then
        echo -e "${RED}❌ Domain name cannot be empty.${NC}"
        return
    fi

    echo -e "${BLUE}📦 Installing Nginx and Certbot...${NC}"
    apt_install nginx certbot python3-certbot-nginx

    NGINX_CONF="/etc/nginx/sites-available/aba-payway.conf"
    cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name $DOMAIN_NAME;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 180s;
    }
}
EOF

    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/aba-payway.conf
    nginx -t
    systemctl reload nginx

    echo -e "\n${BLUE}🔒 Obtaining Let's Encrypt SSL Certificate...${NC}"
    certbot --nginx -d "$DOMAIN_NAME" --non-interactive --agree-tos --register-unsafely-without-email || certbot --nginx -d "$DOMAIN_NAME"

    echo -e "\n${GREEN}✅ HTTPS configured successfully!${NC}"
    echo -e " Your API is now live at: ${YELLOW}https://$DOMAIN_NAME/docs${NC}"
}

# Update Source Code from Git & Reload Service
update_source_code() {
    check_root
    ensure_project_files
    check_install_git
    cd "$APP_DIR"

    echo -e "\n${PURPLE}${BOLD}==============================================================================${NC}"
    echo -e "${GREEN}${BOLD}     📥 UPDATING SOURCE CODE FROM GIT REPOSITORY                              ${NC}"
    echo -e "${PURPLE}${BOLD}==============================================================================${NC}"
    echo -e "${BLUE}📡 Pulling latest changes from Git...${NC}"

    if ! git pull; then
        echo -e "\n${RED}❌ Git pull failed.${NC}"
        echo -e "   If you need authentication, please run: ${YELLOW}sudo bash host.sh --token <YOUR_TOKEN>${NC}"
        return 1
    fi

    echo -e "${GREEN}✅ Latest code pulled successfully.${NC}"

    # Auto-detect whether to rebuild Docker or reload Systemd
    if command -v docker &>/dev/null && [ "$(docker compose ps -q payway-api 2>/dev/null)" ]; then
        echo -e "${BLUE}🐳 Rebuilding Docker container with latest changes...${NC}"
        docker compose down --remove-orphans >/dev/null 2>&1 || true
        docker compose up -d --build
        echo -e "${GREEN}✅ Docker container updated and restarted!${NC}"
        docker compose ps
    elif systemctl is-active --quiet aba-payway 2>/dev/null; then
        echo -e "${BLUE}🐍 Updating Python dependencies and restarting Systemd service...${NC}"
        source "$APP_DIR/venv/bin/activate"
        pip install -r "$APP_DIR/requirements.txt"
        playwright install chromium 2>/dev/null || true
        systemctl restart aba-payway
        echo -e "${GREEN}✅ Systemd service updated and restarted!${NC}"
        sleep 2
        systemctl status aba-payway --no-pager
    else
        echo -e "${YELLOW}ℹ️ Code updated. Start your service with Option 1 (Docker) or Option 2 (Real on VPS).${NC}"
    fi

    print_deployment_info "Updated & Running"
}

# Database Configuration Assistant
configure_database() {
    check_root
    ensure_project_files
    while true; do
        print_banner
        echo -e "${PURPLE}${BOLD}--- 🗄️  Database Configuration Manager ---${NC}"
        local current_db=$(grep "^DATABASE_URL=" "$APP_DIR/.env" 2>/dev/null | cut -d '=' -f2- || true)
        if [ -z "$current_db" ]; then
            current_db="SQLite (Default: aba_automation.db)"
        fi
        echo -e " Current Database: ${YELLOW}$current_db${NC}"
        echo -e "${CYAN}------------------------------------------------------------------------------${NC}"
        echo -e " ${GREEN}1)${NC} 📄 SQLite (Default local file: aba_automation.db)"
        echo -e " ${GREEN}2)${NC} 🐘 PostgreSQL / Supabase / Neon (postgresql+asyncpg://...)"
        echo -e " ${GREEN}3)${NC} 🐬 MySQL / MariaDB (mysql+aiomysql://...)"
        echo -e " ${GREEN}4)${NC} ✏️  Custom Connection String"
        echo -e " ${RED}0)${NC} 🔙 Back to Main Menu"
        echo -e "${CYAN}------------------------------------------------------------------------------${NC}"
        read -p "Select database type [0-4]: " db_choice

        case $db_choice in
            1)
                set_env_var "DATABASE_URL" ""
                touch "$APP_DIR/aba_automation.db"
                chmod 666 "$APP_DIR/aba_automation.db"
                echo -e "${GREEN}✅ Database set to default SQLite.${NC}"
                ;;
            2)
                echo -e "\n${BLUE}🐘 Configure PostgreSQL Connection:${NC}"
                echo -e " Format: ${CYAN}postgresql+asyncpg://user:password@host:port/dbname${NC}"
                echo -e " Example: ${YELLOW}postgresql+asyncpg://postgres:pass@db.xxxx.supabase.co:5432/postgres${NC}"
                read -p "Enter PostgreSQL DATABASE_URL: " pg_url
                if [ -n "$pg_url" ]; then
                    set_env_var "DATABASE_URL" "$pg_url"
                    echo -e "${GREEN}✅ PostgreSQL configured in .env!${NC}"
                fi
                ;;
            3)
                echo -e "\n${BLUE}🐬 Configure MySQL Connection:${NC}"
                echo -e " Format: ${CYAN}mysql+aiomysql://user:password@host:port/dbname${NC}"
                echo -e " Example: ${YELLOW}mysql+aiomysql://user:pass@localhost:3306/aba_payway${NC}"
                read -p "Enter MySQL DATABASE_URL: " mysql_url
                if [ -n "$mysql_url" ]; then
                    set_env_var "DATABASE_URL" "$mysql_url"
                    echo -e "${GREEN}✅ MySQL configured in .env!${NC}"
                fi
                ;;
            4)
                read -p "Enter full SQLAlchemy async DATABASE_URL: " custom_url
                if [ -n "$custom_url" ]; then
                    set_env_var "DATABASE_URL" "$custom_url"
                    echo -e "${GREEN}✅ DATABASE_URL updated!${NC}"
                fi
                ;;
            0)
                break
                ;;
            *)
                echo -e "${RED}❌ Invalid option.${NC}"
                sleep 1
                continue
                ;;
        esac

        read -p "Restart service now to connect to new database? [Y/n]: " restart_now
        restart_now=${restart_now:-Y}
        if [[ "$restart_now" =~ ^[Yy]$ ]]; then
            if command -v docker &>/dev/null && [ "$(docker compose ps -q payway-api 2>/dev/null)" ]; then
                docker compose restart
            elif systemctl is-active --quiet aba-payway 2>/dev/null; then
                systemctl restart aba-payway
            fi
            echo -e "${GREEN}✅ Service restarted with new database connection!${NC}"
        fi
        read -p "Press Enter to continue..."
        break
    done
}

# Main Interactive Menu
main_menu() {
    ensure_project_files
    while true; do
        print_banner
        echo -e " ${PURPLE}${BOLD}=== 🚀 CHOOSE HOSTING METHOD ===${NC}"
        echo -e " ${GREEN}1)${NC} 🐳 ${BOLD}Host with Docker & Docker Compose${NC} (Containers + Playwright)"
        echo -e " ${GREEN}2)${NC} 🖥️  ${BOLD}Host Real on VPS (Native Host)${NC} (Python venv + Systemd)"
        echo -e ""
        echo -e " ${PURPLE}${BOLD}=== ⚙️ CONFIGURATION & TOOLS ===${NC}"
        echo -e " ${GREEN}3)${NC} 🐙 Git Login & Token Setup (Input PAT Token on Terminal)"
        echo -e " ${GREEN}4)${NC} 🗄️  Change Database (SQLite / PostgreSQL / MySQL)"
        echo -e " ${GREEN}5)${NC} 🔒 Setup Domain + Nginx + Free SSL (HTTPS)"
        echo -e " ${GREEN}6)${NC} 🔄 Restart Service (Auto-detects Docker or Systemd)"
        echo -e " ${GREEN}7)${NC} ⏹️  Stop Service (Auto-detects Docker or Systemd)"
        echo -e " ${GREEN}8)${NC} 📜 View Live Logs (Auto-detects Docker or Systemd)"
        echo -e " ${GREEN}9)${NC} 📥 Update Code & Rebuild (Git Pull + Auto-reload)"
        echo -e " ${GREEN}10)${NC} 🩺 Check Health & Status (System, Ports, API)"
        echo -e " ${RED}0)${NC} 🚪 Exit"
        echo -e "${CYAN}------------------------------------------------------------------------------${NC}"
        read -p "Select an option [0-10]: " choice

        case $choice in
            1)
                deploy_docker_mode
                read -p "Press Enter to return to menu..."
                ;;
            2)
                deploy_native_mode
                read -p "Press Enter to return to menu..."
                ;;
            3)
                check_root
                setup_git_auth
                ;;
            4)
                configure_database
                ;;
            5)
                check_root
                setup_nginx_ssl
                read -p "Press Enter to return to menu..."
                ;;
            6)
                check_root
                cd "$APP_DIR"
                if command -v docker &>/dev/null && [ "$(docker compose ps -q payway-api 2>/dev/null)" ]; then
                    echo -e "${BLUE}Restarting Docker container...${NC}"
                    docker compose restart
                    echo -e "${GREEN}✅ Docker container restarted.${NC}"
                elif systemctl is-active --quiet aba-payway 2>/dev/null; then
                    echo -e "${BLUE}Restarting Systemd service...${NC}"
                    systemctl restart aba-payway
                    echo -e "${GREEN}✅ Systemd service restarted.${NC}"
                else
                    echo -e "${YELLOW}No active service found to restart.${NC}"
                fi
                read -p "Press Enter to return to menu..."
                ;;
            7)
                check_root
                cd "$APP_DIR"
                if command -v docker &>/dev/null; then
                    docker compose down 2>/dev/null || true
                fi
                if systemctl is-active --quiet aba-payway 2>/dev/null; then
                    systemctl stop aba-payway 2>/dev/null || true
                fi
                echo -e "${YELLOW}⏹️ All services stopped.${NC}"
                read -p "Press Enter to return to menu..."
                ;;
            8)
                cd "$APP_DIR"
                if command -v docker &>/dev/null && [ "$(docker compose ps -q payway-api 2>/dev/null)" ]; then
                    echo -e "${BLUE}Viewing Docker logs (Press Ctrl+C to exit)...${NC}"
                    docker compose logs -f --tail=100
                elif systemctl is-active --quiet aba-payway 2>/dev/null; then
                    echo -e "${BLUE}Viewing Systemd logs (Press Ctrl+C to exit)...${NC}"
                    journalctl -u aba-payway -f
                else
                    echo -e "${RED}❌ No active service found.${NC}"
                fi
                read -p "Press Enter to return to menu..."
                ;;
            9)
                update_source_code
                read -p "Press Enter to return to menu..."
                ;;
            10)
                echo -e "\n${BLUE}🩺 System Health & Status Check:${NC}"
                echo -e "${CYAN}--- Installed Packages ---${NC}"
                command -v git &>/dev/null && echo -e " Git:    ${GREEN}$(git --version)${NC}" || echo -e " Git:    ${RED}Not installed${NC}"
                command -v python3 &>/dev/null && echo -e " Python: ${GREEN}$(python3 --version)${NC}" || echo -e " Python: ${RED}Not installed${NC}"
                command -v docker &>/dev/null && echo -e " Docker: ${GREEN}$(docker --version)${NC}" || echo -e " Docker: ${RED}Not installed${NC}"
                
                echo -e "\n${CYAN}--- Service Status ---${NC}"
                cd "$APP_DIR"
                if command -v docker &>/dev/null && [ "$(docker compose ps -q payway-api 2>/dev/null)" ]; then
                    echo -e " Docker Mode:  ${GREEN}Active / Running${NC}"
                    docker compose ps
                else
                    echo -e " Docker Mode:  ${YELLOW}Not running${NC}"
                fi
                
                if systemctl is-active --quiet aba-payway 2>/dev/null; then
                    echo -e " Systemd Mode: ${GREEN}Active / Running${NC}"
                    systemctl status aba-payway --no-pager
                else
                    echo -e " Systemd Mode: ${YELLOW}Not active${NC}"
                fi
                
                echo -e "\n${CYAN}--- Memory & Swap ---${NC}"
                free -h
                
                echo -e "\n${CYAN}--- API Port 8000 Response ---${NC}"
                curl -s http://127.0.0.1:8000/api/system/info || echo -e "${RED}API not responding on http://127.0.0.1:8000${NC}"
                echo ""
                read -p "Press Enter to return to menu..."
                ;;
            0)
                echo -e "${GREEN}👋 Exiting... Have a great day!${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}❌ Invalid option. Please select 0-10.${NC}"
                sleep 1
                ;;
        esac
    done
}

# CLI Argument handling
ensure_project_files

if [ "$1" = "--docker" ] || [ "$1" = "-d" ]; then
    deploy_docker_mode
    exit 0
elif [ "$1" = "--native" ] || [ "$1" = "--vps" ] || [ "$1" = "-n" ]; then
    deploy_native_mode
    exit 0
elif [ "$1" = "--update" ] || [ "$1" = "-u" ] || [ "$1" = "--pull" ]; then
    update_source_code
    exit 0
elif [ "$1" = "--db" ] || [ "$1" = "--database" ]; then
    configure_database
    exit 0
elif [ "$1" = "--token" ] || [ "$1" = "-t" ]; then
    check_root
    login_git_token "$2" "$3"
    exit 0
elif [ "$1" = "--login" ]; then
    check_root
    login_git_token
    exit 0
fi

# Run interactive script
main_menu
