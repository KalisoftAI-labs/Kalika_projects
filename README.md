# RCA Dashboard System

A scalable Root Cause Analysis (RCA) Dashboard built with FastAPI for analyzing logs and metrics from multiple sources (Nginx, Gunicorn, Uvicorn, Application-level) with GB-scale log processing capabilities.

## Architecture Overview

- **Log Collection**: Nginx, Gunicorn, Uvicorn, Application logs + System metrics
- **Processing**: Streaming parser, metrics aggregation, correlation engine
- **Analysis**: Rule-based + heuristic RCA with cross-layer correlation
- **Storage**: PostgreSQL for metrics/RCA outputs, local S3-like storage for raw logs
- **Visualization**: Seaborn-based charts, Pandas data aggregation
- **API**: FastAPI with comprehensive endpoint design
- **Frontend**: HTML + CSS dashboard

## Project Structure

```
rca_dashboard/
├── app/
│   ├── core/                 # Configuration, constants, utilities
│   ├── collectors/           # Log collection adapters
│   ├── parsers/              # Log parsing logic (regex, structured)
│   ├── processors/           # Metrics aggregation and processing
│   ├── rca_engine/           # RCA rules and correlation logic
│   ├── storage/              # Database and object storage interfaces
│   ├── visualization/        # Chart generation (Seaborn)
│   ├── models/               # SQLAlchemy ORM models
│   ├── api/                  # FastAPI endpoints and schemas
│   └── migrations/           # Database migrations
├── frontend/                 # HTML/CSS dashboard
├── tests/                    # Unit and integration tests
├── docs/                     # Architecture documentation
└── requirements.txt          # Python dependencies
```

## Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL 12+

### Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your PostgreSQL credentials

# Initialize database
python -m app.migrations.init_db

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Key Features

1. **Multi-source Log Collection**: Ingest from Nginx, Gunicorn, Uvicorn, app logs
2. **Efficient Streaming Processing**: Handle GB-scale logs without full file loads
3. **Cross-layer Correlation**: Trace requests through the full stack
4. **RCA Engine**: Rule-based and heuristic-based root cause identification
5. **Real-time Metrics**: Request volume, error rates, latency distribution
6. **Rich Visualizations**: Error trends, traffic patterns, resource utilization
7. **Comprehensive APIs**: RESTful endpoints for dashboard consumption

## API Endpoints

See [API_DESIGN.md](docs/API_DESIGN.md) for complete endpoint documentation.

## Database Schema

See [DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md) for schema details and indexing strategies.

## Performance Considerations

- Streaming log parsing to avoid memory overhead
- Batch metrics aggregation with windowing
- Strategic database indexing on timestamp and component fields
- Efficient visualization with downsampling for large datasets

## Production Deployment

- Use production-grade ASGI server (Gunicorn + Uvicorn)
- Enable connection pooling for PostgreSQL
- Implement log rotation and archival strategies
- Monitor system resources and set up alerts
- Use transaction isolation levels appropriately

## License

MIT
