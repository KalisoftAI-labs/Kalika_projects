## QUICK START GUIDE

### Prerequisites

- Python 3.9+
- PostgreSQL 12+
- pip (Python package manager)

### Local Development Setup

#### 1. Clone & Setup Project

```bash
cd /path/to/rca_dashboard

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. PostgreSQL Setup

```bash
# Start PostgreSQL (if not running)
# macOS:
brew services start postgresql

# Linux:
sudo systemctl start postgresql

# Create database and user
psql -U postgres << EOF
CREATE USER rca_user WITH PASSWORD 'rca_password';
CREATE DATABASE rca_dashboard OWNER rca_user;
GRANT ALL PRIVILEGES ON DATABASE rca_dashboard TO rca_user;
EOF
```

#### 3. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your database credentials
nano .env
```

Edit `.env`:
```
DATABASE_URL=postgresql+psycopg2://rca_user:rca_password@localhost:5432/rca_dashboard
LOG_LEVEL=INFO
```

#### 4. Initialize Database

```bash
# The database will automatically initialize on first API startup
# Or manually initialize tables:
python -c "from app.storage.database import init_db; init_db()"
```

#### 5. Run the Application

```bash
# Start development server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Server will be available at:
# - API: http://localhost:8000/api/health
# - Dashboard: http://localhost:8000/
# - Docs: http://localhost:8000/docs
```

---

### Testing the API

#### 1. Check System Health

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "operational",
  "timestamp": "2024-10-10T14:00:00Z",
  "component_status": {"database": "healthy", "api": "healthy"},
  "system_health": {"response_time_ms": 10.5, "uptime_seconds": 3600}
}
```

#### 2. Ingest Sample Logs

```bash
# Sample Nginx logs
curl -X POST http://localhost:8000/api/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source": "nginx",
    "logs": [
      "127.0.0.1 - - [10/Oct/2024:14:00:00 +0000] \"GET /api/users HTTP/1.1\" 200 1234 \"-\" \"curl/7.64.1\"",
      "127.0.0.1 - - [10/Oct/2024:14:00:01 +0000] \"POST /api/users HTTP/1.1\" 201 567 \"-\" \"curl/7.64.1\"",
      "127.0.0.1 - - [10/Oct/2024:14:00:02 +0000] \"GET /api/users HTTP/1.1\" 500 123 \"-\" \"curl/7.64.1\""
    ]
  }'

# Sample Application logs (JSON format)
curl -X POST http://localhost:8000/api/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source": "application",
    "logs": [
      "{\"timestamp\": \"2024-10-10T14:00:00Z\", \"level\": \"INFO\", \"message\": \"Request received\", \"request_id\": \"req_123\"}",
      "{\"timestamp\": \"2024-10-10T14:00:01Z\", \"level\": \"ERROR\", \"message\": \"Database error\", \"request_id\": \"req_123\", \"exception_type\": \"ConnectionTimeoutError\"}"
    ]
  }'
```

#### 3. Query Logs

```bash
# Get recent logs
curl "http://localhost:8000/api/logs/recent?limit=10&source=nginx"

# Get logs for specific request (trace through layers)
curl http://localhost:8000/api/logs/by-request-id/req_123

# Get error logs
curl "http://localhost:8000/api/logs/errors?limit=20"
```

#### 4. Get Metrics

```bash
# Get request metrics for a component
curl "http://localhost:8000/api/metrics/request-metrics?component=nginx&start_time=2024-10-10T13:00:00Z&end_time=2024-10-10T15:00:00Z"

# Get error distribution
curl "http://localhost:8000/api/metrics/error-distribution?component=application&start_time=2024-10-10T13:00:00Z&end_time=2024-10-10T15:00:00Z"

# Get latency by endpoint
curl "http://localhost:8000/api/metrics/latency-by-endpoint?component=nginx&start_time=2024-10-10T13:00:00Z&end_time=2024-10-10T15:00:00Z"
```

#### 5. Analyze RCA

```bash
# Analyze error spike
curl -X POST "http://localhost:8000/api/rca/analyze-error-spike?start_time=2024-10-10T13:55:00Z&end_time=2024-10-10T14:05:00Z"

# Analyze latency spike
curl -X POST "http://localhost:8000/api/rca/analyze-latency-spike?start_time=2024-10-10T13:55:00Z&end_time=2024-10-10T14:05:00Z"

# Get incident details
curl "http://localhost:8000/api/rca/incident/inc_20241010_a1b2c3"
```

#### 6. Get Dashboard Data

```bash
# Get metrics snapshot
curl http://localhost:8000/api/dashboard/metrics-snapshot

# Get component health
curl http://localhost:8000/api/dashboard/component-health

# Get recent incidents
curl http://localhost:8000/api/dashboard/recent-incidents?limit=10
```

#### 7. Generate Charts

```bash
# Get error trend chart (base64 encoded PNG)
curl "http://localhost:8000/api/charts/error-trend?component=nginx&start_time=2024-10-10T13:00:00Z&end_time=2024-10-10T15:00:00Z" | jq '.image'

# Get latency distribution
curl "http://localhost:8000/api/charts/latency-distribution?component=application&start_time=2024-10-10T13:00:00Z&end_time=2024-10-10T15:00:00Z"
```

---

### Using the Dashboard

1. Open browser to `http://localhost:8000/`
2. Dashboard shows:
   - Real-time metrics from all components
   - Component health status
   - Recent RCA incidents with root causes
   - Visualization placeholders (fetch charts via API)

Dashboard auto-refreshes every 30 seconds.

---

### Project Structure

```
rca_dashboard/
├── app/
│   ├── core/                    # Configuration and utilities
│   │   ├── config.py           # Settings, constants
│   │   ├── utils.py            # Helper functions
│   │   └── __init__.py
│   ├── parsers/                # Log parsing
│   │   ├── log_parsers.py      # Parser implementations
│   │   └── __init__.py
│   ├── models/                 # Data models
│   │   ├── orm.py              # SQLAlchemy ORM models
│   │   ├── schemas.py          # Pydantic schemas
│   │   └── __init__.py
│   ├── storage/                # Database and storage
│   │   ├── database.py         # PostgreSQL connection
│   │   ├── object_storage.py   # Local file storage (S3-like)
│   │   └── __init__.py
│   ├── processors/             # Business logic
│   │   ├── metrics.py          # Metrics aggregation
│   │   └── __init__.py
│   ├── rca_engine/             # RCA analysis
│   │   ├── analyzer.py         # RCA logic
│   │   └── __init__.py
│   ├── visualization/          # Chart generation
│   │   ├── charts.py           # Seaborn visualizations
│   │   └── __init__.py
│   ├── api/                    # FastAPI routes
│   │   ├── routes/
│   │   │   ├── health.py       # Health endpoints
│   │   │   ├── logs.py         # Log endpoints
│   │   │   ├── metrics.py      # Metrics endpoints
│   │   │   ├── rca.py          # RCA endpoints
│   │   │   ├── dashboard.py    # Dashboard endpoints
│   │   │   ├── charts.py       # Chart endpoints
│   │   │   └── __init__.py
│   │   └── __init__.py
│   ├── collectors/             # Log collectors (extensible)
│   ├── migrations/             # Database migrations
│   ├── main.py                 # FastAPI application entry
│   └── __init__.py
├── frontend/
│   └── index.html             # Dashboard UI
├── tests/                      # Unit and integration tests
├── docs/
│   ├── ARCHITECTURE.md        # System architecture
│   ├── API_DESIGN.md          # API specification
│   └── DATABASE_SCHEMA.md     # Database design
├── requirements.txt           # Python dependencies
├── .env.example              # Example environment
├── README.md                 # Project README
└── .gitignore
```

---

### Development Workflow

#### Adding a New Log Parsers

```python
# In app/parsers/log_parsers.py

class CustomServiceLogParser(BaseLogParser):
    """Parse logs from custom service"""
    
    def __init__(self):
        super().__init__("custom_service")
    
    def parse(self, line: str) -> Optional[ParsedLogLine]:
        # Implement parsing logic
        # Return ParsedLogLine or None
        pass

# Register in factory
LogParserFactory._parsers['custom_service'] = CustomServiceLogParser
```

#### Adding a New Analytics

```python
# In app/processors/metrics.py

class CustomMetricsProcessor(MetricsProcessor):
    def calculate_custom_metric(self, ...):
        """Calculate custom metric"""
        pass
```

#### Adding New API Endpoints

```python
# In app/api/routes/

from fastapi import APIRouter

router = APIRouter()

@router.get("/endpoint-name")
async def endpoint_function():
    """Endpoint documentation"""
    pass

# In app/main.py, add to include_router:
app.include_router(your_router, prefix="/api/custom", tags=["custom"])
```

---

### Debugging

#### Enable Debug Logging

Edit `.env`:
```
LOG_LEVEL=DEBUG
```

#### Check PostgreSQL Connection

```bash
# Test connection
python -c "from app.storage.database import get_engine; print(get_engine().connect())"

# Check active queries
psql rca_dashboard -U rca_user -c "SELECT * FROM pg_stat_activity;"
```

#### Monitor API Logs

```bash
# Run with verbose output
python -m uvicorn app.main:app --reload --log-level debug
```

#### Check Database State

```bash
# Count rows in each table
psql rca_dashboard -U rca_user -c "
SELECT 'log_entries' as table_name, COUNT(*) FROM log_entries
UNION ALL
SELECT 'metrics', COUNT(*) FROM metrics
UNION ALL
SELECT 'rca_analyses', COUNT(*) FROM rca_analyses
UNION ALL
SELECT 'system_metrics', COUNT(*) FROM system_metrics
UNION ALL
SELECT 'request_traces', COUNT(*) FROM request_traces;
"
```

---

### Production Deployment

#### Docker Deployment (Optional)

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY frontend/ ./frontend/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Docker Compose with PostgreSQL

```yaml
version: '3.8'

services:
  db:
    image: postgres:14
    environment:
      POSTGRES_USER: rca_user
      POSTGRES_PASSWORD: rca_password
      POSTGRES_DB: rca_dashboard
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  api:
    build: .
    environment:
      DATABASE_URL: postgresql+psycopg2://rca_user:rca_password@db:5432/rca_dashboard
      LOG_LEVEL: INFO
    ports:
      - "8000:8000"
    depends_on:
      - db

volumes:
  postgres_data:
```

Run with:
```bash
docker-compose up -d
```

---

### Performance Tuning

#### Optimize Database Queries

```python
# Use .yield_per() for large result sets
for log in db.query(LogEntry).yield_per(5000):
    process(log)

# Use select only needed columns
db.query(LogEntry.source, LogEntry.timestamp).filter(...)

# Add query filters as early as possible
db.query(LogEntry).filter(
    LogEntry.source == 'nginx',
    LogEntry.timestamp >= start_time
)
```

#### Enable Query Caching

```python
# Cache common queries for 5 minutes
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=100)
def get_cached_metrics(component: str, hour: str):
    # Cache results
    pass
```

#### Scale API Horizontally

```bash
# Run multiple Uvicorn workers
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

---

### Troubleshooting

#### "database connection failed"
```
Check:
1. PostgreSQL is running
2. Database name, user, password in .env
3. Network connectivity
```

#### "table already exists"
```
Tables are auto-created. If conflicting:
DROP DATABASE rca_dashboard;
CREATE DATABASE rca_dashboard OWNER rca_user;
```

#### "slow queries"
```
Check:
1. Database indexes are created
2. Use EXPLAIN ANALYZE to identify bottlenecks
3. Increase DATABASE_POOL_SIZE in .env
```

#### "high memory usage"
```
Check:
1. Are logs streamed or loaded entirely?
2. Is pagination enabled in API responses?
3. Monitor with: watch 'free -h'
```

---

### Next Steps

1. **Ingest Real Logs**: Connect actual Nginx/Gunicorn log sources
2. **Extend Parsers**: Add custom parsers for your services
3. **Add Rules**: Extend RCA engine with domain-specific rules
4. **Production Setup**: Deploy with load balancing, monitoring
5. **Dashboard Enhancement**: Add more visualizations, filters
6. **Alerting**: Integrate with PagerDuty/Slack for incident notifications

See [ARCHITECTURE.md](ARCHITECTURE.md) and [API_DESIGN.md](API_DESIGN.md) for detailed documentation.
