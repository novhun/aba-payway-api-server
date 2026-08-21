# 🚀 DigitalKH PayWay Web-Automation Engine & Admin Control Center

[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-45ba4b.svg?style=flat&logo=playwright&logoColor=white)](https://playwright.dev/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-D71F00.svg?style=flat&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![Render](https://img.shields.io/badge/Render-Deployable-46E3B7.svg?style=flat&logo=render&logoColor=white)](https://render.com/)

An asynchronous, enterprise-grade API and Web-Automation Engine built with **FastAPI**, **Playwright (Headless Chromium)**, and **SQLAlchemy 2.0**. The engine bridges ABA PayWay payment links into automated API endpoints by generating standard **KHQR (EMVCo)** matrices, intercepting network status in real time, and presenting a rich, real-time **Admin Dashboard**.

---

## 🌟 Key Features & Highlights

### ⚡ 1. High-Performance Automation Engine

- **Singleton Browser Architecture**: Chromium is initialized once on startup (`lifespan`) and shared globally, drastically cutting memory overhead from ~300MB/task to just ~5MB - 10MB per isolated request context.
- **Route Asset Aborting**: Automatically aborts heavy images (`.png`, `.jpg`, `.webp`), fonts (`.woff2`, `.ttf`), and media streams during automation to maximize speed and minimize network bandwidth.
- **Real-Time Network Interception**: Listens to live status polling (`check-payment-status`) to instantly capture transaction approval, `tran_id`, and `download_receipt`.
- **Fast DOM Extraction**: Uses `domcontentloaded` for ultra-fast selector resolution (< 1.5s).

### 💳 2. KHQR Processing & Dynamic QR Generation

- **EMVCo Parser**: Extracts official merchant naming and transaction parameters directly from raw KHQR strings.
- **High-Resolution QR Generator**: Renders Base64 PNG QR code matrices with high ECC and centered branding logos.
- **Responsive Payment UI**: Public standalone checkout screen (`/api/v1/payment/qr-code/verify/{invoice_id}`) with live auto-refresh, countdown expiration, and verified success badges.

### 📊 3. Modern Real-Time Admin Dashboard

- **Live System Resource Usage**: Real-time gauges and progress bars for:
  - **CPU Load (%)** and Logical Core Count.
  - **Memory (RAM)**: Used vs. Total (GB) and utilization percentage.
  - **Disk Storage**: Used vs. Total (GB) and available space.
  - **Automation Engine Status**: Singleton Chromium health (Online/Standby), Active Task counter, and Engine RAM footprint (MB).
- **Real-Time Tasks Stream**: Auto-refreshing live table (polls every 2.5s) displaying active workers, task status (`PROCESSING`, `SUCCESS`, `EXPIRED`, `FAILED`), amounts, and instant receipt links.
- **Financial Analytics & 7-Day Trend**: Visual bar charts tracking daily volumes, success rates, USD revenue, and KHR revenue.
- **Multi-Merchant Management**: Register, edit, and manage multiple merchants with distinct USD/KHR payment links and custom logos.
- **Granular API Key Management**: Generate secure `sk_...` tokens with custom descriptions, activation toggles, and deletion.
- **Complete Transaction Ledger & Export**: Search, filter, and export transaction logs to **Excel (XLSX)**, **PDF**, or **CSV**.
- **Traffic Analytics & IP Ban Firewall**: Monitor IP addresses, geo-locations, HTTP methods, and ban malicious IPs with a single click.
- **Built-in API Tester**: Interactive UI simulator to create payments, test endpoints, and preview checkout iframes directly inside the dashboard.
- **UI Customization**: Multi-theme support (**Light**, **Dark**, **Glassmorphism**), dynamic color palette picker, and full **Bilingual Support (Khmer & English)**.

### 🗄️ 4. Multi-Database Support

- Supports **SQLite**, **PostgreSQL (Supabase)**, and **MySQL** via SQLAlchemy 2.0 asynchronous drivers (`aiosqlite`, `asyncpg`, `aiomysql`).

---

## 🏗️ Architecture & Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Client / Frontend
    participant API as FastAPI Backend
    participant Engine as Playwright Engine (Singleton)
    participant ABA as ABA PayWay Gateway
    participant DB as Database (Postgres/SQLite)

    Customer->>API: POST /api/v1/payment/create (Amount, Currency, Merchant)
    API->>DB: Create Order (Status: PENDING)
    API-->>Customer: Return Invoice ID & Processing Status
    API->>Engine: Spawn Background Worker (Isolated Context)
    Engine->>ABA: Navigate to Merchant Link & Fill Amount
    ABA-->>Engine: Generate KHQR Payload (000201...)
    Engine->>DB: Save KHQR String & Base64 QR Image
    Customer->>API: Scan KHQR & Pay via Mobile Banking App
    ABA->>Engine: Network Response: action: "approved", tran_id, receipt
    Engine->>DB: Update Order (Status: SUCCESS, tran_id, receipt_link)
    Engine->>Engine: Close Context & Free Memory
    Customer->>API: GET /api/v1/payment/verify/{invoice_id} -> SUCCESS
```

---

## 📁 Project Directory Structure

```text
aba-payway-api-single-store/
├── main.py                     # Application entry point, lifespan, CORS, and middleware
├── Dockerfile                  # Production-ready Docker container with Playwright & fonts
├── docker-compose.yml          # Container orchestration with shm_size and host volume
├── render.yaml                 # 1-Click deployment blueprint for Render.com
├── requirements.txt            # Python dependencies
├── .env.example                # Template for environment variables
├── model/                      # SQLAlchemy async database models
│   ├── database.py             # Engine initialization & session factory
│   ├── order.py                # OrderTracking schema
│   ├── merchant.py             # Merchant configuration schema
│   ├── api_key.py              # API key authorization schema
│   ├── api_log.py              # API request logging schema
│   ├── banned_ip.py            # Banned IP firewall schema
│   └── setting.py              # Persistent system settings
├── router/                     # FastAPI route handlers
│   ├── admin.py                # Admin dashboard data, live-status, ledger, metrics, CRUD
│   ├── payment.py              # Payment invoice creation, verification, and QR card HTML
│   ├── system.py               # Health check endpoints (/status, /health)
│   └── security.py             # X-API-Key validation dependency
├── schema/                     # Pydantic data validation schemas
│   └── payment.py              # Request and response models
├── service/                    # Core business logic
│   ├── playwright_worker.py    # Singleton browser lifecycle & automation worker
│   └── qr_generator.py         # EMVCo KHQR parser & Base64 QR generator
└── static/                     # Web dashboard assets
    ├── index.html              # React 18 + Ant Design Dashboard SPA
    └── assets/
        └── lang/               # Bilingual localization (en.json, km.json)
```

---

## 🚀 Quick Start (Local Setup)

### Prerequisites

- **Python 3.9+**
- Git

### 1. Clone & Setup Virtual Environment

```bash
git clone <repository_url>
cd aba-payway-api-single-store

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### 2. Install Dependencies & Playwright Chromium

```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Configure your credentials inside `.env`:

```ini
# Database Connection (SQLite or PostgreSQL)
DATABASE_URL=sqlite+aiosqlite:///aba_automation.db
# Or PostgreSQL / Supabase:
# DATABASE_URL=postgresql+asyncpg://user:password@host:port/database

# Admin Panel Credentials
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
```

### 4. Run the Application

```bash
python main.py
# Or via Uvicorn directly:
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

- **Admin Dashboard**: `http://localhost:8001/`
- **Swagger Interactive API Docs**: `http://localhost:8001/docs`

---

## 🐳 Docker Deployment

The application includes a fully optimized `Dockerfile` with system dependencies, CA certificates, Khmer/Unicode fonts, and Playwright Chromium pre-installed.

### Using Docker Compose (Recommended)

```bash
# Build and start container in detached mode
docker compose up -d --build

# View real-time logs
docker compose logs -f
```

### Using Standard Docker CLI

```bash
# Build image
docker build -t aba-payway-api .

# Run container with 2GB shared memory for Chromium stability
docker run -d \
  --name aba-payway-api \
  --shm-size=2gb \
  -p 8000:10000 \
  --env-file .env \
  aba-payway-api
```

---

## ☁️ Deploying to Cloud (Render.com / VPS)

### Option A: Deploy on Render.com

1. Push your repository to **GitHub**.
2. Go to **[Render Dashboard](https://dashboard.render.com/)** -> **New +** -> **Web Service**.
3. Select your repository and configure:
   - **Environment**: `Docker`
   - **Region**: `Singapore (Southeast Asia)` *(Lowest latency to Cambodia & Supabase)*
   - **Plan**: `Starter` ($7/mo) or `Standard` ($25/mo)
4. Add Environment Variables:
   - `DATABASE_URL`: `postgresql+asyncpg://...`
   - `ADMIN_USERNAME`: `admin`
   - `ADMIN_PASSWORD`: `your_secure_password`
5. Deploy! Render will build the container and provide your live HTTPS URL.

### Option B: Deploy on VPS (Hetzner / DigitalOcean / Vultr)

For high-traffic production at low cost ($4 - $6/month):

1. Install Docker & Docker Compose on your Ubuntu/Debian VPS.
2. Clone repository, configure `.env`, and run `docker compose up -d`.
3. Set up Nginx reverse proxy with Certbot for SSL (`https://pay.yourdomain.com`).

---

## 📖 API Documentation & Reference

All endpoints requiring authentication expect the API Key in the `X-API-Key` header.

### 1. Create Payment Invoice

Creates an order entry in the database and launches a background worker to extract the KHQR code.

- **Endpoint**: `POST /api/v1/payment/create`
- **Headers**:
  - `X-API-Key: sk_your_api_key`
  - `Content-Type: application/json`
- **Request Body**:

```json
{
  "code_merchant": "aba_payway001",
  "amount": "1.50",
  "currency": "USD"
}
```

*(Currency accepts `"USD"` or `"KHR"`)*

- **Response (200 OK)**:

```json
{
  "invoice_id": 66,
  "payment_status": "PROCESSING"
}
```

---

### 2. Verify Payment Status (JSON API)

Poll this endpoint to check the transaction status.

- **Endpoint**: `GET /api/v1/payment/verify/{invoice_id}`
- **Headers**: `X-API-Key: sk_your_api_key`
- **Response (200 OK)**:

```json
{
  "invoice_id": 66,
  "amount": "1.50",
  "currency": "USD",
  "status": "SUCCESS",
  "khqr": "00020101021229...6304A1B2",
  "receipt": "https://link.payway.com.kh/download-receipt/..."
}
```

#### Status Lifecycle:

| Status      | Description                                                             |
| ----------- | ----------------------------------------------------------------------- |
| `PENDING` | Order created; background worker is generating KHQR / awaiting payment. |
| `SUCCESS` | Payment verified and approved by ABA PayWay ledger.                     |
| `EXPIRED` | Customer did not pay within the timeout window (2 minutes).             |
| `FAILED`  | Worker encountered an automation error or invalid payment link.         |

---

### 3. Public Checkout Screen (HTML Card)

Embeddable QR checkout page for customers. Does not require an API key.

- **Endpoint**: `GET /api/v1/payment/qr-code/verify/{invoice_id}`
- **Format**: `text/html`
- **Features**:
  - Automatically renders the KHQR matrix.
  - Automatically polls and updates to **Payment Verified ✓** when paid.
  - Displays **Payment Expired ✗** if the countdown elapses.

---

### 4. System Health Check

- **Endpoint**: `GET /status` or `GET /health` (Also supports `HEAD`)
- **Response**:

```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## 🔒 Security Best Practices

1. **Protect Admin Credentials**: Always change `ADMIN_USERNAME` and `ADMIN_PASSWORD` from default values before deploying to production.
2. **Rotate API Keys**: Use the Admin Dashboard to generate distinct API keys for different client applications and revoke unused tokens.
3. **CORS Restrictions**: Navigate to **Settings** in the Admin Dashboard to replace `*` with your specific web domains (e.g. `https://myshop.com`).
4. **Firewall & Rate Limiting**: Monitor the **Traffic Logs** tab and use the **Ban IP** button to immediately blacklist malicious requests.

---

## 🛠️ Performance & Concurrency Tuning

| Server Tier              | CPU     | RAM  | Max Concurrent Workers | Recommended Scale      |
| ------------------------ | ------- | ---- | ---------------------- | ---------------------- |
| **Development**    | 1 Core  | 1 GB | 3 - 5 Tasks            | Testing & Dev          |
| **Standard Cloud** | 2 Cores | 2 GB | 15 - 25 Tasks          | Small / Medium Stores  |
| **Production VPS** | 4 Cores | 4 GB | 50+ Tasks              | High-Volume E-Commerce |

---

## 📄 License

This project is open-source and available under the **MIT License**.
