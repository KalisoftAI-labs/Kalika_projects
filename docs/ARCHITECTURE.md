## 1. SYSTEM ARCHITECTURE

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          FRONTEND                               │
│                    (HTML + CSS Dashboard)                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                        FastAPI Server                           │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐   │
│  │ Health │ │  Logs  │ │Metrics │ │   RCA    │ │ Charts   │   │
│  │ Routes │ │ Routes │ │ Routes │ │ Routes   │ │ Routes   │   │
│  └────────┘ └────────┘ └────────┘ └──────────┘ └──────────┘   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼──────┐    ┌──────────▼─────────┐   ┌──────▼─────────┐
│   Collectors │    │    Processors      │   │   RCA Engine   │
│              │    │                    │   │                │
│ • Nginx      │    │ • Metrics Proc.    │   │ • Rules        │
│ • Gunicorn   │    │ • Request Corr.    │   │ • Heuristics   │
│ • Uvicorn    │    │ • Aggregation      │   │ • Correlation  │
│ • App logs   │    │                    │   │                │
│ • System     │    │                    │   │                │
└───────┬──────┘    └──────────┬─────────┘   └──────┬─────────┘
        │                      │                     │
        │ Log Parsers          │ Metrics Agg         │ Analysis
        │ (Streaming)          │                     │
        │                      │                     │
        └──────────────────────┼─────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
┌───────▼────────────┐  ┌──────▼──────────┐  ┌──────▼──────────┐
│  PostgreSQL DB     │  │ Object Storage  │  │ Visualization   │
│ • LogEntry         │  │ (Local/S3-like) │  │ • Seaborn       │
│ • Metric           │  │ • Raw logs      │  │ • Matplotlib    │
│ • RCAAnalysis      │  │ • Logs archive  │  │ • Charts        │
│ • SystemMetric     │  │                 │  │                 │
│ • RequestTrace     │  │                 │  │                 │
└────────────────────┘  └─────────────────┘  └─────────────────┘
```

### Tech Stack
- **Backend**: FastAPI + Uvicorn
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Log Parsing**: Regex-based streaming parsers (no external libraries)
- **Metrics**: Pandas + NumPy for aggregation
- **Visualization**: Seaborn + Matplotlib
- **Storage**: Local file system (S3-compatible design)
- **Frontend**: HTML + CSS (no frameworks)

### Key Design Principles

1. **Streaming Processing**: Avoid loading entire log files into memory
2. **Clean Architecture**: Clear separation between collectors, parsers, processors, RCA, and storage
3. **Correlation-Based**: Trace requests through multiple system layers
4. **Rule-Based RCA**: Use deterministic rules combined with heuristics
5. **Observability First**: Every component is self-describing and monitorable

---

## 2. MODULE BREAKDOWN

### `app/core/`
- **config.py**: Settings, configuration, constants
- **utils.py**: Utility functions (timestamps, directory management)

Responsibilities:
- Centralized configuration management
- Global constants for thresholds and event types
- Helper functions for common operations

### `app/parsers/`
- **log_parsers.py**: Log parsing strategies for all sources
  - `BaseLogParser`: Abstract base class
  - `NginxLogParser`: Access + error log parsing
  - `GunicornLogParser`: Gunicorn log parsing
  - `UvicornLogParser`: Uvicorn log parsing
  - `ApplicationLogParser`: Flexible JSON/text app logs
  - `LogParserFactory`: Factory pattern for parser instantiation

### `app/models/`
- **orm.py**: SQLAlchemy ORM models
  - `LogEntry`: Raw log data
  - `Metric`: Aggregated metrics
  - `RCAAnalysis`: RCA findings
  - `SystemMetric`: CPU/memory/disk metrics
  - `RequestTrace`: Request path through layers
- **schemas.py**: Pydantic request/response schemas

### `app/processors/`
- **metrics.py**: Metrics aggregation engine
  - `MetricsProcessor`: Aggregates metrics from logs
    - Request count, error rate, latency percentiles
    - Error distribution by status code
    - Latency by endpoint
    - Slow request identification
    - Trend calculations
  - `RequestCorrelator`: Correlates requests across layers

### `app/rca_engine/`
- **analyzer.py**: Root Cause Analysis engine
  - `RCAEngine`: Main analysis orchestrator
    - Error spike analysis
    - Latency spike analysis
    - Root cause determination (rules + heuristics)
  - `RCAFinding`: Dataclass for analysis results

### `app/storage/`
- **database.py**: PostgreSQL connection and session management
- **object_storage.py**: S3-compatible local file storage

### `app/visualization/`
- **charts.py**: Chart generation
  - Error trend charts
  - Latency distribution histograms
  - Error distribution by status
  - Endpoint latency comparison
  - System health dashboards
  - Request volume timelines

### `app/collectors/`
- Log collection adapters (to be extended)

### `app/api/routes/`
- **health.py**: `/api/health` - System health checks
- **logs.py**: `/api/logs/*` - Log ingestion and retrieval
- **metrics.py**: `/api/metrics/*` - Metrics queries
- **rca.py**: `/api/rca/*` - RCA analysis endpoints
- **dashboard.py**: `/api/dashboard/*` - Dashboard aggregations
- **charts.py**: `/api/charts/*` - Chart generation endpoints

### `frontend/`
- **index.html**: Dashboard UI with real-time updates

---

## 3. DATA FLOW (End-to-End Pipeline)

### Ingestion Flow
```
Raw Log Lines
     │
     ▼
┌──────────────────────┐
│ POST /api/logs/ingest│
│ (source, logs[])     │
└──────────┬───────────┘
           │
           ▼
    ┌────────────────┐
    │ Get Parser     │
    │ (LogParserFact)│
    └────────┬───────┘
             │
             ▼
    ┌──────────────────┐
    │ Parse Line       │
    │ (Streaming)      │
    │ • Regex match    │
    │ • Extract fields │
    │ • Parse timestamp│
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Create LogEntry  │
    │ ORM object       │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │ Commit to DB     │
    │ (Batch insert)   │
    └──────┬───────────┘
           │
           ▼
      Response
   (count, failed)
```

### Metrics Aggregation Flow
```
Query Logs
  (time window)
     │
     ▼
┌─────────────────────────┐
│ Aggregate Metrics       │
│ • Count requests        │
│ • Count errors (4xx/5xx)│
│ • Calculate percentiles │
│  - p50, p99, p999       │
│ • Group by endpoint     │
│ • Group by status code  │
└─────────────────────────┘
     │
     ▼
Return Metrics
  (request_count,
   error_rate,
   p99_latency, etc)
```

### RCA Analysis Flow
```
Query Error/Latency Spike
(time window)
     │
     ▼
┌──────────────────────┐
│ Collect Metrics      │
│ (all components)     │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────┐
│ Identify Patterns        │
│ • Highest error rate     │
│ • Error distribution     │
│ • Latency distribution   │
│ • Status code ratios     │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Apply RCA Rules          │
│ • 5xx ratio > 70%?       │
│ • 502 errors?            │
│ • Exception types?       │
│ • Resource constrained?  │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│ Determine Root Cause     │
│ • Generate hypothesis    │
│ • Calculate confidence   │
│ • Extract evidence       │
│ • Generate recommend.    │
└──────────┬───────────────┘
           │
           ▼
Store RCAAnalysis
   (DB record)
     │
     ▼
Return Finding
  (root_cause,
   confidence,
   evidence)
```

---

## 4. LOG PARSING STRATEGY

### Streaming Parser Design

**Key Principle**: Process logs line-by-line without loading entire file into memory.

### Parser Architecture

```python
class BaseLogParser:
    def parse(line: str) -> ParsedLogLine
    def parse_stream(file_obj) -> Iterator[ParsedLogLine]

# Enables:
for parsed_line in parser.parse_stream(open("nginx.log")):
    process(parsed_line)  # Memory: ~1 line at a time
```

### Nginx Log Parser

**Access Log Format** (Combined):
```
127.0.0.1 - - [10/Oct/2024:13:55:36 +0000] "GET /api/users HTTP/1.1" 200 5123 "http://example.com" "Mozilla/5.0"
```

**Regex Pattern**:
```python
r'(?P<remote_addr>[\d\.]+) - (?P<user>[\w\.\-]*) \[(?P<timestamp>[^\]]+)\] '
r'"(?P<method>\w+) (?P<uri>[^"]*) HTTP/[\d\.]+" (?P<status>\d+) (?P<bytes>[\d-]+) '
r'"(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
```

**Error Log Format**:
```
2024/10/10 13:55:36 [error] 1234#5678: *90 connect() failed (111: Connection refused)
```

### Gunicorn Log Parser

**Format**:
```
[2024-10-10 13:55:36 +0000] [1234] [INFO] Worker spawned
[2024-10-10 13:55:37 +0000] [1234] [INFO] GET /api/users HTTP/1.1 200 45.32
```

### Uvicorn Log Parser

**Format**:
```
2024-10-10 13:55:36.123 | INFO | Application startup complete
```

### Application Log Parser

**Flexible Format** (JSON preferred):
```json
{"timestamp": "2024-10-10T13:55:36Z", "level": "ERROR", "message": "DB error", "request_id": "req-123"}
```

Or text:
```
[2024-10-10 13:55:36] [ERROR] [db_service] Connection timeout
```

### Efficiency Considerations

1. **Compiled Regex**: Patterns are compiled once
2. **Streaming**: Files processed line-by-line
3. **Early Exit**: Unparseable lines skipped with log, no error
4. **Batch Insert**: Database inserts batched (not single-row)
5. **Memory**: Constant memory regardless of file size

---

## 5. METRICS AGGREGATION ENGINE

### Aggregation Patterns

#### Window-Based Aggregation

```python
def aggregate_request_metrics(
    component: str,
    start_time: datetime,
    end_time: datetime
) -> Dict[str, float]:
    """
    Returns:
    {
        'request_count': 1543,
        'error_count': 23,
        'error_rate': 0.0149,
        'p50_latency': 45.2,
        'p99_latency': 234.5,
        'p999_latency': 5230.0,
    }
    """
```

#### Percentile Calculation

```python
sorted_latencies = sorted(latencies)
p50_idx = int(len(sorted_latencies) * 0.50)
p50_latency = sorted_latencies[p50_idx]
```

#### Endpoint Aggregation

```python
endpoint_latencies: Dict[str, List[float]] = defaultdict(list)

for log in logs:
    if endpoint := log.request_uri:
        endpoint_latencies[endpoint].append(log.response_time)

result = {
    endpoint: {
        'count': len(latencies),
        'mean': mean(latencies),
        'p50': percentile(latencies, 0.50),
        'p99': percentile(latencies, 0.99),
        'p999': percentile(latencies, 0.999),
    }
    for endpoint, latencies in endpoint_latencies.items()
}
```

### Trend Calculation

```python
def get_error_rate_trend(
    component: str,
    start_time: datetime,
    end_time: datetime,
    window_size: int = 60  # seconds
) -> List[Tuple[datetime, float]]:
    """
    Returns: [(timestamp, error_rate), ...]
    
    Process time range in fixed windows:
    - [T0 - T0+60s] -> error_rate_0
    - [T0+60s - T0+120s] -> error_rate_1
    - ...
    """
```

### Performance Optimizations

1. **Strategic Indexing**:
   ```sql
   CREATE INDEX idx_source_timestamp 
   ON log_entries(source, timestamp);
   
   CREATE INDEX idx_component_metric_timestamp 
   ON metrics(component, metric_type, timestamp);
   ```

2. **Query Optimization**:
   ```python
   # BAD: Full table scan
   logs = db.query(LogEntry).all()  # Bad for GB-scale logs
   
   # GOOD: Filtered query
   logs = db.query(LogEntry).filter(
       LogEntry.source == component,
       LogEntry.timestamp >= start_time,
       LogEntry.timestamp <= end_time
   ).all()  # Only relevant rows
   ```

3. **Batch Operations**:
   ```python
   # Insert in batches, not one-by-one
   for batch in chunks(log_entries, 1000):
       db.add_all(batch)
       db.commit()
   ```

4. **Memory-Efficient Aggregation**:
   ```python
   # Stream large result sets
   for log in db.query(LogEntry).filter(...).yield_per(1000):
       process(log)  # Memory: ~1000 rows at a time
   ```

---

## 6. RCA ENGINE DESIGN

### Rule Definition

```python
class RCAEngine:
    def analyze_error_spike(self, start_time, end_time):
        """
        Rule-Based Analysis:
        
        1. Collect error metrics from all layers
        2. Identify which component(s) have highest error rate
        3. Analyze error distribution:
           - If 70%+ are 5xx errors:
             - Check for specific 5xx codes
             - 502 → Upstream gateway failure
             - 503 → Service overload
             - 500 → Check exceptions
           - Else (4xx errors):
             - Client-side errors / validation failures
        4. Calculate confidence score
        5. Generate recommendations
        """
```

### Layer Correlation Logic

```
Request Flow:
Client → Nginx → Gunicorn Worker → Uvicorn → Application → DB

Error Propagation Patterns:
- App error (500) → Uvicorn (500) → Gunicorn (500) → Nginx (502/504)
- DB error → App (500) → Up the stack
- Timeout → All layers show increased latency
- Resource exhaustion → Gunicorn queue growth → increased latency
```

### Cross-Layer Correlation

```python
def correlate_errors(self, start_time, end_time):
    """
    Find request IDs that have errors in multiple layers
    """
    errors = db.query(LogEntry).filter(
        LogEntry.timestamp >= start_time,
        LogEntry.timestamp <= end_time,
        (LogEntry.level.in_(['ERROR'])) | 
        (LogEntry.http_status >= 400)
    ).all()
    
    # Group by request_id
    correlated = defaultdict(list)
    for error in errors:
        correlated[error.request_id].append({
            'source': error.source,
            'timestamp': error.timestamp,
            'message': error.message,
            'level': error.level,
        })
    
    # Requests with errors at multiple layers indicate propagation
    multi_layer_errors = {
        req_id: errors 
        for req_id, errors in correlated.items()
        if len(set(e['source'] for e in errors)) > 1
    }
```

### Heuristic Examples

#### Latency Spike Heuristics

```python
def _determine_latency_root_cause(self, component, latencies, ...):
    """
    Heuristic 1: Layer Attribution
    - If Nginx latency >> Gunicorn: Network/LB issue
    - If Gunicorn latency >> App: Worker saturation
    - If App latency dominant: App processing bottleneck
    
    Heuristic 2: Request Distribution
    - Spike in one endpoint: Resource-intensive operation
    - Spike across all: System-level issue
    
    Heuristic 3: Error Correlation
    - High latency + errors: Cascading failure
    - High latency, no errors: Processing bottleneck
    """
```

#### Error Pattern Heuristics

```python
class ErrorPatternAnalyzer:
    def analyze_patterns(self, error_distribution):
        """
        Pattern 1: 502/503 surge
            → Upstream failures or overload
            
        Pattern 2: 500 errors with specific exception type
            → Application bug or resource issue
            
        Pattern 3: 4xx errors increase
            → Client behavior change or validation issue
            
        Pattern 4: Errors spike with latency
            → Cascading failure or resource exhaustion
        """
```

### Confidence Scoring

```python
confidence_score = 0.0

# Base score: 0.5 (moderate confidence)
confidence_score = 0.5

# Increase confidence based on evidence
if len(evidence_logs) > 10:
    confidence_score += 0.15
if error_pattern_clear:
    confidence_score += 0.20
if cross_layer_correlation:
    confidence_score += 0.10
if error_rate_is_statistically_significant:
    confidence_score += 0.05

# Cap at 1.0
confidence_score = min(confidence_score, 1.0)
```

---

## 7. VISUALIZATION MODULE

### Chart Types and Use Cases

#### Error Trend Chart
- **Type**: Line chart with fill
- **X-Axis**: Time
- **Y-Axis**: Error rate (0-1)
- **Use**: Monitor error rate over time, identify spike start/end

#### Latency Distribution
- **Type**: Histogram with percentile markers
- **X-Axis**: Latency (ms)
- **Y-Axis**: Frequency
- **Markers**: p50, p99, p999 lines
- **Use**: Understand latency distribution, detect outliers

#### Errors by Status Code
- **Type**: Bar chart with color coding
- **X-Axis**: HTTP status codes
- **Y-Axis**: Error count
- **Colors**: Red for 5xx, Orange for 4xx
- **Use**: Identify dominant error types

#### Latency by Endpoint
- **Type**: Horizontal bar chart
- **X-Axis**: p99 Latency (ms)
- **Y-Axis**: Endpoint names
- **Color**: Gradient (red=high, green=low)
- **Use**: Identify slowest endpoints

#### System Health
- **Type**: Multi-panel dashboard
- **Panels**: CPU, Memory, Disk, Load Average
- **Use**: Correlate latency/errors with resource utilization

### Implementation Details

```python
class ChartGenerator:
    def generate_error_trend_chart(trend_data, title):
        """
        Input: [(datetime, error_rate), ...]
        Output: Base64-encoded PNG image
        """
        df = pd.DataFrame(trend_data, columns=['timestamp', 'error_rate'])
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(df['timestamp'], df['error_rate'], marker='o', linewidth=2)
        ax.fill_between(df['timestamp'], df['error_rate'], alpha=0.3)
        ax.set_xlabel('Time')
        ax.set_ylabel('Error Rate')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        
        # Convert to base64 for embedding in HTML
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode()
        plt.close(fig)
        
        return image_base64
```

### Performance for Large Datasets

```python
# Downsampling for very large datasets
def downsample_data(data, target_points=500):
    """Reduce data points for visualization while preserving patterns"""
    if len(data) <= target_points:
        return data
    
    step = len(data) // target_points
    # Keep min/max for accuracyreturn [
        (data[i]['timestamp'], data[i]['value'])
        for i in range(0, len(data), step)
    ]
```

---

## 8. DATABASE SCHEMA

### Tables

#### LogEntry
```sql
CREATE TABLE log_entries (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,  -- nginx, gunicorn, uvicorn, application
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    level VARCHAR(20) NOT NULL,  -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    message TEXT NOT NULL,
    component VARCHAR(100),
    request_id VARCHAR(100),
    
    -- HTTP fields (Nginx)
    http_method VARCHAR(10),
    http_status INTEGER,
    remote_addr VARCHAR(50),
    request_uri VARCHAR(500),
    response_time FLOAT,  -- milliseconds
    bytes_sent INTEGER,
    
    -- Application fields
    user_id VARCHAR(100),
    service_name VARCHAR(100),
    exception_type VARCHAR(100),
    stack_trace TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_source_timestamp ON log_entries(source, timestamp);
CREATE INDEX idx_request_id ON log_entries(request_id);
CREATE INDEX idx_component_timestamp ON log_entries(component, timestamp);
```

#### Metric
```sql
CREATE TABLE metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    window_size  INTEGER NOT NULL,  -- seconds (60, 300, 3600, etc)
    component VARCHAR(100) NOT NULL,  -- nginx, gunicorn, etc
    metric_type VARCHAR(50) NOT NULL,  -- request_count, error_rate, p99_latency
    value FLOAT NOT NULL,
    
    -- Dimensions
    http_status INTEGER,
    endpoint VARCHAR(500),
    error_type VARCHAR(100),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_component_metric_timestamp 
ON metrics(component, metric_type, timestamp);
```

#### RCAAnalysis
```sql
CREATE TABLE rca_analyses (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) NOT NULL UNIQUE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Incident details
    incident_type VARCHAR(50) NOT NULL,  -- error, latency, timeout, etc
    severity VARCHAR(20) NOT NULL,  -- critical, high, medium, low
    affected_component VARCHAR(100) NOT NULL,
    
    -- RCA findings
    root_cause VARCHAR(500) NOT NULL,
    confidence_score FLOAT NOT NULL,  -- 0-1
    
    -- Evidence
    evidence_log_ids VARCHAR(1000),  -- JSON list of log IDs
    related_metrics VARCHAR(1000),   -- JSON-encoded metrics
    
    -- Recommendations
    recommendations TEXT,
    
    -- Timeline
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    
    status VARCHAR(20) DEFAULT 'ongoing',  -- ongoing, resolved, investigating
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_incident_timestamp ON rca_analyses(timestamp);
CREATE INDEX idx_incident_component ON rca_analyses(affected_component);
```

#### SystemMetric
```sql
CREATE TABLE system_metrics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    hostname VARCHAR(100) NOT NULL,
    cpu_percent FLOAT,
    memory_percent FLOAT,
    disk_percent FLOAT,
    load_average_1min FLOAT,
    load_average_5min FLOAT,
    load_average_15min FLOAT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_hostname_timestamp ON system_metrics(hostname, timestamp);
```

#### RequestTrace
```sql
CREATE TABLE request_traces (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(100) NOT NULL UNIQUE,
    trace_id VARCHAR(100),
    
    -- Timeline events
    nginx_received_at TIMESTAMP WITH TIME ZONE,
    nginx_response_time FLOAT,
    
    gunicorn_worker_id VARCHAR(100),
    gunicorn_received_at TIMESTAMP WITH TIME ZONE,
    
    uvicorn_received_at TIMESTAMP WITH TIME ZONE,
    
    app_received_at TIMESTAMP WITH TIME ZONE,
    app_response_time FLOAT,
    
    -- Results
    final_status INTEGER,
    total_latency FLOAT,  -- milliseconds
    error_occurred BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_trace_id ON request_traces(trace_id);
```

### Indexing Strategy

1. **Timestamp Indexes**: Every query filters by timestamp
2. **Component Indexes**: Log analysis typically scoped to component
3. **Request ID Indexes**: Cross-layer correlation requires request_id lookup
4. **Composite Indexes**: Most common filter combinations indexed together

Example query optimization:
```sql
-- Uses: idx_source_timestamp
SELECT * FROM log_entries 
WHERE source = 'nginx' 
AND timestamp >= '2024-10-10 13:00:00'
AND timestamp <= '2024-10-10 14:00:00'
LIMIT 1000;

-- Uses: idx_component_metric_timestamp
SELECT * FROM metrics
WHERE component = 'gunicorn'
AND metric_type = 'p99_latency'
AND timestamp >= '2024-10-10 13:00:00'
ORDER BY timestamp DESC
LIMIT 100;
```

---

## 9. API DESIGN

See [API_DESIGN.md](API_DESIGN.md) for comprehensive endpoint specification.

### API Principles

1. **RESTful Design**: Standard HTTP methods
2. **Pagination**: All list endpoints support `limit` and `offset`
3. **Filtering**: Query parameters for time ranges, components
4. **Versioning**: `/api/v1/*` (future-ready)
5. **Error Handling**: Consistent error response format
6. **Documentation**: Swagger/OpenAPI auto-generated

---

## 10. SAMPLE RCA REPORT

### Example: Error Spike Incident

```json
{
  "incident_id": "inc_20241010_001",
  "timestamp": "2024-10-10T14:35:00Z",
  "incident_type": "error_spike",
  "severity": "critical",
  "affected_component": "application",
  "start_time": "2024-10-10T14:30:00Z",
  "end_time": "2024-10-10T14:35:00Z",
  "duration_seconds": 300,
  
  "root_cause": "Application exception: OutOfMemoryError in database connection pool",
  "confidence_score": 0.87,
  
  "observations": [
    "Error spike detected in application layer: 28.5% error rate",
    "Dominant error status: 500 (Internal Server Error)",
    "Found 134 correlated error groups",
    "Most common exception: OutOfMemoryError (45 occurrences)",
    "Latency spike correlated with error increase (p99 latency: 8234ms)"
  ],
  
  "affected_layers": ["application"],
  
  "evidence": {
    "sample_logs": [
      {
        "timestamp": "2024-10-10T14:33:12Z",
        "source": "application",
        "level": "ERROR",
        "message": "DB pool exhausted",
        "exception_type": "OutOfMemoryError",
        "request_id": "req_e8c4a2f1"
      },
      {
        "timestamp": "2024-10-10T14:33:14Z",
        "source": "application",
        "level": "ERROR",
        "message": "Failed to acquire connection",
        "exception_type": "PoolExhaustedException",
        "request_id": "req_f9d5b3f2"
      }
    ],
    "error_distribution": {
      "500": 412,
      "503": 87,
      "504": 23
    },
    "latency_metrics": {
      "p50_latency_ms": 1200,
      "p99_latency_ms": 8234,
      "p999_latency_ms": 15630
    }
  },
  
  "recommendations": [
    "IMMEDIATE: Increase DB connection pool size",
    "IMMEDIATE: Restart application to clear memory",
    "SHORT-TERM: Monitor memory usage and connection counts",
    "SHORT-TERM: Add connection pool monitoring and alerts",
    "MEDIUM-TERM: Review database query efficiency",
    "MEDIUM-TERM: Implement circuit breaker for DB timeouts"
  ],
  
  "timeline": [
    {
      "time": "2024-10-10T14:30:00Z",
      "event": "Error rate begins increasing in application layer"
    },
    {
      "time": "2024-10-10T14:31:00Z",
      "event": "Error rate reaches 10%, p99 latency at 2500ms"
    },
    {
      "time": "2024-10-10T14:33:00Z",
      "event": "Error rate peaks at 28.5%, OutOfMemoryError dominant"
    },
    {
      "time": "2024-10-10T14:35:00Z",
      "event": "Error rate begins declining as connections freed"
    }
  ],
  
  "impact_analysis": {
    "total_requests": 15234,
    "failed_requests": 4341,
    "error_rate_percent": 28.5,
    "users_affected_estimate": 1243,
    "revenue_impact_estimate": "$2850"
  }
}
```

---

## 11. PERFORMANCE & SCALING CONSIDERATIONS

### Memory Optimization

#### 1. Streaming Log Parsing

```python
# BAD: Loads entire file into memory
with open('nginx.log') as f:
    lines = f.readlines()  # GB of data in memory!
    for line in lines:
        parse(line)

# GOOD: Streams line-by-line
with open('nginx.log') as f:
    for line in f:  # Only 1 line in memory at a time
        parse(line)
```

#### 2. Generator-Based Aggregation

```python
# BAD: Materializes all results
results = []
for log in db.query(LogEntry).all():
    results.append(process(log))
return results  # Entire result set in memory

# GOOD: Yields results incrementally
def process_logs():
    for log in db.query(LogEntry).yield_per(1000):
        yield process(log)  # Memory: ~1000 rows at a time
```

#### 3. Efficient Percentile Calculation

```python
# Bad: Too many comparisons
def percentile_bad(data, p):
    sorted_data = sorted(data)
    return sorted_data[int(len(sorted_data) * p)]

# Better: Pre-sorted, direct calculation
sorted_data = sorted(data)
p99_idx = int(len(sorted_data) * 0.99)
p99 = sorted_data[p99_idx]
```

### Streaming Techniques

#### 1. Iterator Protocol

```python
# Define your aggregations as generators
def get_metrics_stream(start_time, end_time):
    """Stream metrics without materializing all at once"""
    for component in ['nginx', 'gunicorn', 'uvicorn', 'application']:
        metrics = aggregate_metrics(component, start_time, end_time)
        yield {
            'component': component,
            'metrics': metrics
        }

# Usage
for metric_set in get_metrics_stream(t1, t2):
    send_to_client(metric_set)  # Stream responses
```

#### 2. Database Streaming

```python
# Query large result sets efficiently
def process_errors_stream(start_time, end_time):
    """Process errors without loading all into memory"""
    query = db.query(LogEntry).filter(
        LogEntry.timestamp >= start_time,
        LogEntry.timestamp <= end_time,
        LogEntry.level == 'ERROR'
    )
    
    for error_batch in query.yield_per(5000):  # 5000 rows at a time
        for error in error_batch:
            yield error
```

### Indexing Strategy

#### Query Patterns and Indexes

```sql
-- Pattern 1: Time-range queries (very common)
-- QUERY: Logs for component in time range
SELECT * FROM log_entries 
WHERE source = 'nginx' 
AND timestamp BETWEEN ? AND ?;
-- INDEX: (source, timestamp)

-- Pattern 2: Cross-layer trace
-- QUERY: All logs for request_id
SELECT * FROM log_entries WHERE request_id = ?;
-- INDEX: (request_id) or (request_id, timestamp)

-- Pattern 3: Error analysis
-- QUERY: Errors by component in time range
SELECT * FROM log_entries
WHERE source = 'application'
AND timestamp BETWEEN ? AND ?
AND (level = 'ERROR' OR http_status >= 500)
-- INDEX: (source, timestamp) or (source, level, timestamp)

-- Pattern 4: Metrics aggregation
-- QUERY: Specific metric type over time
SELECT * FROM metrics
WHERE component = 'gunicorn'
AND metric_type = 'p99_latency'
AND timestamp >= ?
-- INDEX: (component, metric_type, timestamp)
```

#### Index Maintenance

```sql
-- Regular ANALYZE to update statistics
ANALYZE log_entries;
ANALYZE metrics;

-- Vacuum to reclaim space
VACUUM ANALYZE log_entries;

-- Monitor index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0;  -- Unused indexes
```

### Database Connection Pooling

```python
# config.py
engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=20,                # Active connections
    max_overflow=0,              # Additional connections when pool exhausted
    pool_recycle=3600,           # Recycle connections hourly
    pool_pre_ping=True,          # Verify connection before using
)
```

### Bottleneck Analysis

#### 1. Log Ingestion Bottleneck
```
Problem: Slow ingestion rate
- If DB writes are slow: Use batch inserts, connection pooling
- If parsing is slow: Profile regex patterns, simplify parsing
- If network is slow: Use compression, batch multiple logs per request

Solution:
- Batch 1000 logs per commit
- Use bulk insert statements
- Compress request bodies
```

#### 2. Metrics Aggregation Bottleneck
```
Problem: Slow aggregation over large time ranges
- If query is slow: Add proper indexes, filter early
- If calculation is slow: Stream data, reduce computations
- If memory is high: Use generators, batch processing

Solution:
- Pre-aggregate metrics in time windows
- Cache recent aggregations
- Implement materialized views for common queries
```

#### 3. RCA Analysis Bottleneck
```
Problem: Slow root cause analysis
- If correlation is slow: Limit time window, pre-filter errors
- If rule matching is slow: Optimize pattern matching
- If evidence gathering is slow: Use indexed queries

Solution:
- Cache correlation results
- Limit analysis time window to 1-6 hours (not days)
- Use SQLAlchemy query optimization
```

### Scaling Strategies

#### Horizontal Scaling (Multiple API Instances)

```
        Client Requests
               │
        ┌──────┴──────┐
        │  Load       │
        │ Balancer    │
        │ (Nginx)     │
        └──────┬──────┘
               │
        ┌──────┼──────┐
        │      │      │
   ┌────▼──┐┌─▼────┐┌─▼────┐
   │API #1 ││API #2 ││API #3 │
   └────┬──┘└──┬───┘└──┬───┘
        │      │      │
        └──────┴──────┴──────┐
                             │
                    ┌────────▼──────┐
                    │ PostgreSQL    │
                    │ Shared DB     │
                    └───────────────┘

Considerations:
- All instances connect to shared DB
- Use read replicas for analytics queries
- Implement cache layer (Redis) for common queries
```

#### Vertical Scaling (Single Instance Optimization)

```
1. Increase PostgreSQL server resources
2. Increase DB memory for caching
3. Optimize indexes and queries
4. Use SSD storage for faster I/O
5. Enable PostgreSQL query parallelization
```

#### Log Storage Optimization

```
Problem: GB-scale logs consume storage
Solution:
1. Archive old logs to compressed object storage
2. Delete logs older than 30 days
3. Sample high-volume log sources
   - Keep 100% of ERROR logs
   - Keep 10% of INFO logs
   - Keep 1% of DEBUG logs

Retention policy:
- Hot data (0-7 days): PostgreSQL
- Warm data (7-30 days): Compressed files
- Cold data (30+ days): Archive/delete
```

### Monitoring System Itself

```python
# Log system performance metrics
def log_system_metrics():
    """Track RCA system performance"""
    metrics = {
        'log_ingestion_rate': logs_per_second,
        'db_query_time_ms': avg_query_time,
        'rca_analysis_time_ms': avg_analysis_time,
        'cache_hit_rate': cache_hits / total_requests,
        'api_response_time_ms': avg_api_latency,
        'memory_usage_mb': memory_used,
        'active_db_connections': connection_count,
    }
    
    # Alert if thresholds exceeded
    if metrics['db_query_time_ms'] > 1000:
        alert("DB queries slow, check indexes and load")
    if metrics['memory_usage_mb'] > 1000:
        alert("Memory high, check for leaks")
```

---

## Deployment Checklist

- [ ] Set up PostgreSQL with proper indexing
- [ ] Configure environment variables (.env file)
- [ ] Initialize database schema
- [ ] Test log parsing with real log samples
- [ ] Configure database connection pooling
- [ ] Set up monitoring and alerting
- [ ] Load test with expected log volume
- [ ] Configure log rotation and archival
- [ ] Set up backups for PostgreSQL
- [ ] Configure HTTPS for API
- [ ] Set up error tracking and logging
- [ ] Document operational procedures
