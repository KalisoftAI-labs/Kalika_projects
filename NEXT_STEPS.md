# 🚀 RCA Dashboard - Next Steps

## Step 1: Verify Python Environment
```powershell
python --version
pip --version
```

If Python is not found, add it to your system PATH or use the full path to the Python executable.

---

## Step 2: Install Dependencies

Run the following command to install the required Python packages:

```powershell
cd "c:\Users\user\New folder\rca_dashboard"
pip install -r requirements-minimal.txt
```

**What gets installed:**
- `fastapi` - Web framework for the API
- `uvicorn` - ASGI server to run the app
- `sqlalchemy` - ORM for database operations
- `pandas` - Data processing and analysis
- Other utilities for logging and utilities

---

## Step 3: Run Log Analysis (Demo Mode)

Analyze the Nginx logs without a database:

```powershell
cd "c:\Users\user\New folder\rca_dashboard"
python analyze_logs.py
```

**Output includes:**
- Request metrics (total, success rate, error rate)
- HTTP status code breakdown (200, 404, etc.)
- Top endpoints and IP addresses
- Error analysis with root cause insights
- Time-based request rate analysis

---

## Step 4: Start the Dashboard Server

Launch the FastAPI web server:

```powershell
cd "c:\Users\user\New folder\rca_dashboard"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**What this command does:**
- Starts a web server on `http://localhost:8000`
- `--reload` enables auto-reload when you modify code
- `--host 0.0.0.0` makes it accessible from other machines

---

## Step 5: Access the Dashboard

Open your browser and visit:

### Main Dashboard
**http://localhost:8000**
- Displays real-time metrics and charts
- Shows request trends and error patterns
- Provides RCA insights

### Health Check
**http://localhost:8000/health**
- Verifies the server is running

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main dashboard UI |
| `GET /health` | Server health check |
| `GET /api/metrics/summary` | Overall metrics |
| `GET /api/metrics/timeseries` | Time-series data |
| `GET /api/logs` | Retrieve parsed logs |
| `GET /api/rca/analyze` | Root cause analysis |
| `POST /api/logs/ingest` | Upload new logs |

---

## Step 6: Database Setup (Optional but Recommended)

For persistent data storage, set up PostgreSQL:

### Option A: Using Docker
```powershell
docker run --name rca-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:15
```

### Option B: Manual PostgreSQL Installation
1. Download PostgreSQL from [postgresql.org](https://www.postgresql.org/download/)
2. Install with default settings
3. Note the password you set for the `postgres` user
4. Update `app/core/config.py` with your database credentials:

```python
DATABASE_URL = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/rca_dashboard"
```

---

## Step 7: Run Database Migrations

After setting up PostgreSQL:

```powershell
cd "c:\Users\user\New folder\rca_dashboard"
python -m alembic upgrade head
```

This creates all necessary database tables.

---

## Step 8: Ingest Logs into Database

Upload the Nginx logs to the database:

```powershell
python ingest_logs.py
```

Check `app/access_nginx_log` is in the correct location before running.

---

## Troubleshooting

### Python Not Found
- You may need to restart your PowerShell terminal after updating PATH
- Try using the full path: `C:\Python\Python312\python.exe analyze_logs.py`
- Or use: `py analyze_logs.py` (if Python Launcher is installed)

### Port 8000 Already in Use
```powershell
# Find what's using port 8000
netstat -ano | findstr :8000

# Kill the process (replace PID with actual process ID)
taskkill /PID PID /F

# Or use a different port
python -m uvicorn app.main:app --port 8001
```

### Database Connection Error
- Ensure PostgreSQL is running
- Check database credentials in `app/core/config.py`
- Verify firewall allows port 5432

### Missing Dependencies
```powershell
# Install all dependencies
pip install -r requirements.txt

# Or the minimal set
pip install -r requirements-minimal.txt
```

---

## Architecture Overview

```
RCA Dashboard
├── Frontend (index.html)
│   └── Displays real-time metrics & charts
├── API Layer (FastAPI)
│   ├── /api/metrics/* - Request metrics
│   ├── /api/logs/* - Log management
│   ├── /api/rca/* - Root cause analysis
│   └── /health - Health checks
├── Core Engine
│   ├── Log Parsers - Parse Nginx logs
│   ├── Processors - Calculate metrics
│   ├── RCA Analyzer - Identify issues
│   └── Storage - PostgreSQL database
└── Utilities
    ├── Configuration
    ├── Database ORM
    └── Logging
```

---

## API Examples

### Get Metrics Summary
```bash
curl http://localhost:8000/api/metrics/summary
```

### Get Logs
```bash
curl "http://localhost:8000/api/logs?limit=10&status_code=404"
```

### Trigger RCA Analysis
```bash
curl -X POST http://localhost:8000/api/rca/analyze \
  -H "Content-Type: application/json" \
  -d '{"time_window": "1h"}'
```

---

## Performance Tips

1. **Use index.html** for a fast web-based UI
2. **API responses** are cached automatically for 5 minutes
3. **Database queries** use connection pooling for efficiency
4. **Log parsing** processes 1000+ entries per second

---

## Support

For errors or issues:
1. Check application logs in the terminal
2. Review `app/core/config.py` for settings
3. Verify all dependencies are installed
4. Check database connectivity
5. Review API documentation at `/docs` (Swagger UI)

---

**Ready to get started?** Follow Steps 1-5 for a demo dashboard, or continue to Step 6 for full functionality with database persistence.
