# DigitalKH PayWay Web-Automation Engine

An asynchronous API built with FastAPI that connects to ABA PayWay for web-automation payment processing. The engine generates KHQR codes, performs background status verification using headless browser automation via Playwright, and utilizes SQLAlchemy for flexible database support.

## Features

- **FastAPI Backend**: High-performance asynchronous API.
- **Playwright Automation**: Emulates mobile web sessions to verify payment transactions seamlessly in the background.
- **KHQR Parsing & Generation**: Parses EMVCo layout sequences to extract merchant information and generates QR codes with centered branding.
- **Multi-Database Support**: Uses SQLAlchemy v2, allowing you to seamlessly connect to SQLite, PostgreSQL, or MySQL via configuration.
- **Modular Architecture**: Clean, scalable folder structure separating concerns (routers, models, schemas, and services).

## Project Structure

```text
.
├── main.py                 # Application entry point and lifespan configuration
├── .env.example            # Example configuration file
├── requirements.txt        # Python dependencies
├── model/                  # Database configuration and SQLAlchemy declarative models
├── schema/                 # Pydantic validation schemas
├── router/                 # FastAPI endpoint definitions
└── service/                # Core business logic (QR generation & Playwright background workers)
```

## Prerequisites

- **Python 3.9+**
- Chromium browser binaries (installed via Playwright)

## Installation

1. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright Browsers**:
   ```bash
   playwright install chromium
   ```

## Configuration

Copy the example environment variables file and configure your values:

```bash
cp .env.example .env
```

Edit the `.env` file with your specific settings:

```env
# Database Configuration
# Supported drivers:
# SQLite: sqlite+aiosqlite:///aba_automation.db
# PostgreSQL: postgresql+asyncpg://user:password@localhost/dbname
# MySQL: mysql+asyncmy://user:password@localhost/dbname
DATABASE_URL=sqlite+aiosqlite:///aba_automation.db

# Payment Links Configuration
PAYMENT_LINK_KHR=https://link.payway.com.kh/ABAPAYm0459397n
PAYMENT_LINK_USD=https://link.payway.com.kh/ABAPAYp1459398p

# Security
API_KEY=your_super_secret_api_key_here
```

## Running the Application

Start the FastAPI server using Uvicorn:

```bash
python main.py
```
*(Alternatively, you can run it manually via `uvicorn main:app --host 0.0.0.0 --port 8000`)*

The API documentation will be available at `http://localhost:8000/docs`.

## System Requirements & Hosting Recommendations

Due to the use of headless browser automation (Playwright), this application requires more system resources than a typical API. Each background verification worker spawns a Chromium instance which consumes CPU and RAM.

### Hardware Specifications & Uvicorn Workers

A common formula for calculating the maximum number of Uvicorn workers is:
**`Workers = (2 * CPU Cores) + 1`**

| Setup | CPU | RAM | Max Uvicorn Workers | Expected Capacity |
|---|---|---|---|---|
| **Minimum** | 1 vCPU | 1 GB | 1 - 2 | Low traffic, testing, development |
| **Recommended** | 2 vCPU | 4 GB | 4 - 5 | Medium traffic, standard business |
| **Production** | 4 vCPU | 8 GB | 8 - 9 | High traffic, concurrent payments |
| **Enterprise** | 8 vCPU | 16+ GB| 16 - 17 | Heavy load, very high scale |

### Throughput & Capacity (Tasks Per Worker)

Because this engine relies on **Headless Chromium browsers** to intercept the live payment ledger, **RAM is your primary bottleneck**.

- **Memory Usage**: Every time a user creates a new payment, a new background task starts. This task opens a new Chromium browser that stays open for up to 2 minutes waiting for the customer to scan and pay. Each Chromium instance consumes approximately **150MB - 250MB of RAM**.
- **Concurrent Tasks**: A single Uvicorn worker can asynchronously handle multiple transactions, but you are strictly limited by your server's RAM. 
  - **1 GB RAM** can safely handle **~3 to 4 concurrent pending payments**.
  - **4 GB RAM** can safely handle **~15 to 20 concurrent pending payments**.

> [!WARNING]
> If you expect 50 customers to check out at the exact same minute, you will need a server with at least 10GB+ of RAM to keep 50 Chromium browsers open simultaneously without causing an Out-Of-Memory (OOM) crash.

### Running in Production (Gunicorn)

For production environments, it is highly recommended to run the app using `gunicorn` with the Uvicorn worker class to manage multiple processes efficiently:

```bash
# Example for a 2 vCPU server (5 workers)
gunicorn main:app --workers 5 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## API Endpoints

- `GET /status`: Health check endpoint.
- `POST /api/v1/payment/create`: Creates a new payment invoice and starts a background worker. 
  - **Headers**: `X-API-Key: <your_api_key>`
  - **Body**: `{ "amount": "1.00", "currency": "USD" }`
- `GET /api/v1/payment/verify/{invoice_id}`: Retrieves the JSON status of an invoice.
  - **Headers**: `X-API-Key: <your_api_key>`
- `GET /api/v1/payment/qr-code/verify/{invoice_id}`: Returns an HTML rendering of the KHQR code for scanning (Publicly accessible, no API key required).
