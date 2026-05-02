## DATABASE SCHEMA DESIGN

### PostgreSQL Setup

#### Prerequisites
```bash
# Install PostgreSQL 12+
brew install postgresql  # macOS
# or
sudo apt-get install postgresql  # Linux
```

#### Create Database and User

```sql
-- Connect to PostgreSQL
psql -U postgres

-- Create RCA user
CREATE USER rca_user WITH PASSWORD 'rca_password';

-- Create database
CREATE DATABASE rca_dashboard OWNER rca_user;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE rca_dashboard TO rca_user;

-- Connect to database
\c rca_dashboard

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO rca_user;
```

---

### Schema Initialization

The application automatically creates all tables on startup via SQLAlchemy. This script documents the generated schema.

#### LogEntry Table

Stores raw log data from all sources.

```sql
CREATE TABLE log_entries (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,               -- nginx, gunicorn, uvicorn, application
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    level VARCHAR(20) NOT NULL,                -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    message TEXT NOT NULL,
    component VARCHAR(100),
    request_id VARCHAR(100),
    
    -- HTTP fields (primarily from Nginx)
    http_method VARCHAR(10),                   -- GET, POST, PUT, DELETE, etc
    http_status INTEGER,                       -- 200, 404, 500, etc
    remote_addr VARCHAR(50),                   -- Client IP
    request_uri VARCHAR(500),                  -- /api/users, /api/posts/{id}, etc
    response_time FLOAT,                       -- Milliseconds
    bytes_sent INTEGER,
    
    -- Application-specific fields
    user_id VARCHAR(100),
    service_name VARCHAR(100),
    exception_type VARCHAR(100),               -- OutOfMemoryError, NullPointerException, etc
    stack_trace TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT log_entries_pkey PRIMARY KEY (id)
);

-- Indexes for common query patterns
CREATE INDEX idx_source_timestamp 
ON log_entries(source, timestamp DESC);

CREATE INDEX idx_request_id 
ON log_entries(request_id) WHERE request_id IS NOT NULL;

CREATE INDEX idx_component_timestamp 
ON log_entries(component, timestamp DESC) WHERE component IS NOT NULL;

CREATE INDEX idx_http_status 
ON log_entries(http_status) WHERE http_status >= 400;

CREATE INDEX idx_timestamp 
ON log_entries(timestamp DESC);
```

**Retention Strategy**:
- Keep last 30 days in hot storage
- Archive older logs to compressed object storage
- Implement partition by month for easier pruning

---

#### Metric Table

Stores pre-aggregated metrics at various time granularities.

```sql
CREATE TABLE metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    window_size INTEGER NOT NULL,              -- 60, 300, 3600, 86400 (seconds)
    component VARCHAR(100) NOT NULL,           -- nginx, gunicorn, uvicorn, application
    metric_type VARCHAR(50) NOT NULL,          -- request_count, error_rate, p99_latency, etc
    value FLOAT NOT NULL,                      -- Numeric value of metric
    
    -- Dimensions for drill-down
    http_status INTEGER,
    endpoint VARCHAR(500),
    error_type VARCHAR(100),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT metrics_pkey PRIMARY KEY (id)
);

-- Primary query index
CREATE INDEX idx_component_metric_timestamp 
ON metrics(component, metric_type, timestamp DESC);

-- Optimization for aggregation queries
CREATE INDEX idx_window_component_timestamp 
ON metrics(window_size, component, timestamp DESC);

-- Dimension indexes for filtering
CREATE INDEX idx_endpoint 
ON metrics(endpoint) WHERE endpoint IS NOT NULL;

CREATE INDEX idx_http_status 
ON metrics(http_status) WHERE http_status IS NOT NULL;
```

**Aggregation Levels**:
- 1-minute: Real-time dashboard
- 5-minute: Hour-long trends
- 1-hour: Day-long trends
- 1-day: Monthly trends

---

#### RCAAnalysis Table

Stores root cause analysis findings and incident records.

```sql
CREATE TABLE rca_analyses (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) NOT NULL UNIQUE, -- UUID for external reference
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Incident classification
    incident_type VARCHAR(50) NOT NULL,        -- error_spike, latency_spike, timeout, crash, etc
    severity VARCHAR(20) NOT NULL,             -- critical, high, medium, low
    affected_component VARCHAR(100) NOT NULL,  -- nginx, gunicorn, uvicorn, application
    
    -- RCA findings
    root_cause VARCHAR(500) NOT NULL,          -- Hypothesis of root cause
    confidence_score FLOAT NOT NULL,           -- 0.0 to 1.0
    
    -- Evidence and supporting data
    evidence_log_ids VARCHAR(1000),            -- JSON-encoded array: ["log_1", "log_2"]
    related_metrics VARCHAR(1000),             -- JSON: {error_rate: 0.28, p99: 8234}
    
    -- Recommendations
    recommendations TEXT,                      -- Newline-separated recommendations
    
    -- Timeline
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,         -- NULL if ongoing
    duration_seconds INTEGER,
    
    -- Status
    status VARCHAR(20) DEFAULT 'ongoing',      -- ongoing, resolved, investigating
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT rca_analyses_pkey PRIMARY KEY (id),
    CONSTRAINT rca_analyses_incident_id_unique UNIQUE (incident_id)
);

-- Indexes for analysis queries
CREATE INDEX idx_incident_timestamp 
ON rca_analyses(timestamp DESC);

CREATE INDEX idx_incident_component 
ON rca_analyses(affected_component, timestamp DESC);

CREATE INDEX idx_incident_severity 
ON rca_analyses(severity);

CREATE INDEX idx_incident_status 
ON rca_analyses(status) WHERE status != 'resolved';
```

---

#### SystemMetric Table

Stores system-level metrics (CPU, memory, disk, load average).

```sql
CREATE TABLE system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    hostname VARCHAR(100) NOT NULL,
    cpu_percent FLOAT,                         -- 0-100
    memory_percent FLOAT,                      -- 0-100
    disk_percent FLOAT,                        -- 0-100
    load_average_1min FLOAT,
    load_average_5min FLOAT,
    load_average_15min FLOAT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT system_metrics_pkey PRIMARY KEY (id)
);

-- Index for time-series queries
CREATE INDEX idx_hostname_timestamp 
ON system_metrics(hostname, timestamp DESC);

CREATE INDEX idx_timestamp 
ON system_metrics(timestamp DESC);
```

---

#### RequestTrace Table

Maps individual requests through the system layers.

```sql
CREATE TABLE request_traces (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(100) NOT NULL UNIQUE,
    trace_id VARCHAR(100),                     -- Optional: distributed tracing ID
    
    -- Timing across layers
    nginx_received_at TIMESTAMP WITH TIME ZONE,
    nginx_response_time FLOAT,                 -- Time spend in Nginx (ms)
    
    gunicorn_worker_id VARCHAR(100),
    gunicorn_received_at TIMESTAMP WITH TIME ZONE,
    
    uvicorn_received_at TIMESTAMP WITH TIME ZONE,
    
    app_received_at TIMESTAMP WITH TIME ZONE,
    app_response_time FLOAT,                   -- Time spent in app (ms)
    
    -- Results
    final_status INTEGER,                      -- HTTP status of response
    total_latency FLOAT,                       -- Total request time (ms)
    error_occurred BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT request_traces_pkey PRIMARY KEY (id),
    CONSTRAINT request_traces_request_id_unique UNIQUE (request_id)
);

-- Indexes for tracing
CREATE INDEX idx_trace_id 
ON request_traces(trace_id) WHERE trace_id IS NOT NULL;

CREATE INDEX idx_total_latency 
ON request_traces(total_latency DESC);

CREATE INDEX idx_error_occurred 
ON request_traces(error_occurred) WHERE error_occurred = TRUE;
```

---

### Indexing Strategy

#### Query Pattern Analysis

```
High-Frequency Queries:
1. Time-range queries: 60% of queries
   → Index: (source, timestamp)
   → Index: (component, timestamp)

2. Request tracing: 20% of queries
   → Index: (request_id)
   → Index: (trace_id)

3. Metrics aggregation: 15% of queries
   → Index: (component, metric_type, timestamp)

4. Error analysis: 5% of queries
   → Index: (source, level, timestamp)
   → Index: (http_status)
```

#### Index Maintenance

```sql
-- Check index effectiveness
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Identify unused indexes (remove them)
SELECT schemaname, tablename, indexname
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY pg_relation_size(relid) DESC;

-- Analyze query plans
EXPLAIN ANALYZE
SELECT * FROM log_entries
WHERE source = 'nginx'
AND timestamp >= NOW() - INTERVAL '1 hour'
ORDER BY timestamp DESC
LIMIT 100;

-- Update statistics
ANALYZE log_entries;
ANALYZE metrics;
ANALYZE rca_analyses;
ANALYZE system_metrics;
ANALYZE request_traces;

-- Vacuum to reclaim space
VACUUM ANALYZE log_entries;
```

---

### Partitioning Strategy

For very large `log_entries` table (100M+ rows), implement partitioning:

```sql
-- Create partitioned table (PostgreSQL 11+)
CREATE TABLE log_entries_partitioned (
    id SERIAL,
    source VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    -- ... other columns ...
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Create monthly partitions
CREATE TABLE log_entries_2024_10
PARTITION OF log_entries_partitioned
FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');

CREATE TABLE log_entries_2024_11
PARTITION OF log_entries_partitioned
FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');

-- Queries automatically use correct partition
-- Easier to drop old partitions: DROP TABLE log_entries_2024_09;
```

---

### Connection Pooling

Configure in application:

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    'postgresql://rca_user:rca_password@localhost:5432/rca_dashboard',
    poolclass=QueuePool,
    pool_size=20,              # Number of persistent connections
    max_overflow=10,           # Additional connections when pool exhausted
    pool_recycle=3600,         # Recycle connections every hour
    pool_pre_ping=True,        # Verify connection before using
    echo=False,
)
```

---

### Performance Tuning

Edit `/etc/postgresql/14/main/postgresql.conf`:

```ini
# Memory
shared_buffers = 256MB          # 25% of RAM
effective_cache_size = 1GB      # 50-75% of RAM
work_mem = 16MB                 # shared_buffers / (max_connections * 2)

# Parallelization
max_parallel_workers_per_gather = 4
max_parallel_workers = 4
max_worker_processes = 4

# Logging
log_min_duration_statement = 1000  # Log queries slower than 1s
log_statement = 'all'
log_duration = on

# Synchronous replication (for HA)
synchronous_commit = remote_write
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
```

---

### Backup & Recovery

#### Backup Strategy

```bash
# Full backup
pg_dump rca_dashboard -U rca_user -F custom > rca_backup.sql

# Compressed backup
pg_dump rca_dashboard -U rca_user -F custom -Z 9 > rca_backup.sql.gz

# Backup with tables
pg_dump rca_dashboard -U rca_user -t log_entries -F custom > log_entries_backup.sql

# Schedule daily backups (cron)
0 2 * * * pg_dump rca_dashboard -U rca_user -F custom -Z 9 > /backups/rca_$(date +\%Y\%m\%d).sql.gz
```

#### Recovery

```bash
# Full restore
pg_restore -d rca_dashboard rca_backup.sql

# Restore to specific point in time (with WAL archiving)
pg_ctl recover -D /var/lib/postgresql/14/main -r '2024-10-10 14:00:00'
```

---

### Monitoring

```sql
-- Monitor table sizes
SELECT 
    schemaname, tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Monitor active queries
SELECT 
    pid, usename, application_name, query, query_start
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY query_start DESC;

-- Monitor connections
SELECT count(*) as active_connections FROM pg_stat_activity;

-- Monitor slow queries
SELECT 
    calls, mean_time, max_time, query
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 20;

-- Monitor table bloat
SELECT 
    schemaname, tablename,
    round(100.0 * pg_total_relation_size(schemaname||'.'||tablename) / 
    NULLIF(sum(pg_total_relation_size(schemaname||'.'||tablename)) 
    OVER (), 0), 1) as ratio
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY ratio DESC;
```

---

### Common Queries for Analysis

#### Get error spike details

```sql
SELECT 
    timestamp::date as date,
    EXTRACT(hour FROM timestamp) as hour,
    source,
    http_status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (
        PARTITION BY timestamp::date, EXTRACT(hour FROM timestamp)
    ), 2) as percentage
FROM log_entries
WHERE timestamp >= NOW() - INTERVAL '24 hours'
AND http_status >= 400
GROUP BY date, hour, source, http_status
ORDER BY date DESC, hour DESC, count DESC;
```

#### Get request latency distribution

```sql
SELECT 
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY response_time) as p50,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY response_time) as p75,
    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY response_time) as p90,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time) as p95,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time) as p99,
    MAX(response_time) as p100
FROM log_entries
WHERE source = 'nginx'
AND timestamp >= NOW() - INTERVAL '1 hour'
AND response_time IS NOT NULL;
```

#### Trace request through layers

```sql
SELECT 
    source,
    timestamp,
    http_status,
    response_time,
    message
FROM log_entries
WHERE request_id = 'req_abc123'
ORDER BY timestamp ASC;
```

#### Find slow endpoints

```sql
SELECT 
    request_uri,
    COUNT(*) as total_requests,
    ROUND(AVG(response_time), 2) as avg_latency,
    ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time), 2) as p99_latency,
    MAX(response_time) as max_latency
FROM log_entries
WHERE source = 'nginx'
AND timestamp >= NOW() - INTERVAL '24 hours'
AND request_uri IS NOT NULL
GROUP BY request_uri
HAVING COUNT(*) > 10
ORDER BY p99_latency DESC
LIMIT 20;
```
