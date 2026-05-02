## API DESIGN SPECIFICATION

### Base URL
```
http://localhost:8000/api
```

### Authentication
Currently: None (add as needed)
Recommended: JWT tokens for production

### Response Format
All responses are JSON unless otherwise specified.

---

## Health & Status

### GET /health
System health check

**Response (200)**:
```json
{
  "status": "operational",
  "timestamp": "2024-10-10T14:00:00Z",
  "component_status": {
    "database": "healthy",
    "api": "healthy"
  },
  "system_health": {
    "response_time_ms": 10.5,
    "uptime_seconds": 3600
  }
}
```

---

## Log Management

### POST /logs/ingest
Ingest logs from a source

**Parameters**:
- `source` (query): Log source - `nginx`, `gunicorn`, `uvicorn`, `application`
- `logs` (body): Array of log line strings

**Request Body**:
```json
{
  "source": "nginx",
  "logs": [
    "127.0.0.1 - - [10/Oct/2024:14:00:00 +0000] \"GET /api/users HTTP/1.1\" 200 1234 \"-\" \"curl/7.64.1\"",
    "127.0.0.1 - - [10/Oct/2024:14:00:01 +0000] \"POST /api/users HTTP/1.1\" 201 567 \"-\" \"curl/7.64.1\""
  ]
}
```

**Response (200)**:
```json
{
  "source": "nginx",
  "ingested": 2,
  "failed": 0,
  "total": 2
}
```

---

### GET /logs/recent
Get recent logs

**Query Parameters**:
- `source` (optional): Filter by source
- `limit` (optional): Max results, default 100, max 1000

**Response (200)**:
```json
[
  {
    "id": 1,
    "source": "nginx",
    "timestamp": "2024-10-10T14:00:00Z",
    "level": "INFO",
    "message": "GET /api/users 200",
    "http_method": "GET",
    "http_status": 200,
    "remote_addr": "127.0.0.1",
    "request_uri": "/api/users",
    "response_time": 45.2,
    "bytes_sent": 1234,
    "created_at": "2024-10-10T14:00:00Z"
  }
]
```

---

### GET /logs/by-request-id/{request_id}
Get all logs for a request (trace through layers)

**Parameters**:
- `request_id` (path): Request ID to trace

**Response (200)**:
```json
[
  {
    "id": 1,
    "timestamp": "2024-10-10T14:00:00.000Z",
    "source": "nginx",
    "level": "INFO",
    "message": "GET /api/users",
    "component": null
  },
  {
    "id": 2,
    "timestamp": "2024-10-10T14:00:00.005Z",
    "source": "gunicorn",
    "level": "INFO",
    "message": "Worker processing request"
  },
  {
    "id": 3,
    "timestamp": "2024-10-10T14:00:00.010Z",
    "source": "application",
    "level": "INFO",
    "message": "Query users from DB"
  },
  {
    "id": 4,
    "timestamp": "2024-10-10T14:00:00.045Z",
    "source": "nginx",
    "level": "INFO",
    "message": "Response sent: 200, 45ms"
  }
]
```

---

### GET /logs/errors
Get error logs

**Query Parameters**:
- `start_time` (optional): ISO format datetime
- `end_time` (optional): ISO format datetime
- `limit` (optional): Max results, default 100, max 1000

**Response (200)**:
```json
[
  {
    "id": 125,
    "source": "application",
    "timestamp": "2024-10-10T14:00:12Z",
    "level": "ERROR",
    "message": "Database connection timeout",
    "http_status": 500,
    "exception_type": "ConnectionTimeoutError",
    "request_id": "req_abc123",
    "component": "db_service",
    "created_at": "2024-10-10T14:00:12Z"
  }
]
```

---

## Metrics

### GET /metrics/request-metrics
Get aggregated request metrics for component

**Query Parameters**:
- `component` (required): `nginx`, `gunicorn`, `uvicorn`, `application`
- `start_time` (required): ISO format datetime
- `end_time` (required): ISO format datetime

**Response (200)**:
```json
{
  "request_count": 1543,
  "error_count": 23,
  "error_rate": 0.0149,
  "p50_latency": 45.2,
  "p99_latency": 234.5,
  "p999_latency": 5230.0
}
```

---

### GET /metrics/error-distribution
Get error count by HTTP status code

**Query Parameters**:
- `component` (required)
- `start_time` (required)
- `end_time` (required)

**Response (200)**:
```json
{
  "400": 5,
  "401": 2,
  "404": 8,
  "500": 23,
  "502": 15,
  "503": 45
}
```

---

### GET /metrics/latency-by-endpoint
Get latency metrics aggregated by endpoint

**Query Parameters**:
- `component` (required)
- `start_time` (required)
- `end_time` (required)

**Response (200)**:
```json
{
  "/api/users": {
    "count": 523,
    "mean": 89.2,
    "p50": 45.0,
    "p99": 245.0,
    "p999": 1230.0
  },
  "/api/users/{id}": {
    "count": 234,
    "mean": 52.1,
    "p50": 30.0,
    "p99": 156.0,
    "p999": 890.0
  }
}
```

---

### GET /metrics/slow-requests
Get requests exceeding latency threshold

**Query Parameters**:
- `component` (required)
- `start_time` (required)
- `end_time` (required)
- `threshold_ms` (optional): Latency threshold, default 1000

**Response (200)**:
```json
[
  {
    "timestamp": "2024-10-10T14:00:12Z",
    "request_uri": "/api/users",
    "response_time": 5230.0,
    "http_status": 200,
    "request_id": "req_xyz789"
  }
]
```

---

### GET /metrics/error-rate-trend
Get error rate trend over time

**Query Parameters**:
- `component` (required)
- `start_time` (required)
- `end_time` (required)

**Response (200)**:
```json
[
  {
    "timestamp": "2024-10-10T14:00:00Z",
    "error_rate": 0.012
  },
  {
    "timestamp": "2024-10-10T14:01:00Z",
    "error_rate": 0.018
  },
  {
    "timestamp": "2024-10-10T14:02:00Z",
    "error_rate": 0.028
  }
]
```

---

### GET /metrics/latency-trend
Get latency percentile trend over time

**Query Parameters**:
- `component` (required)
- `start_time` (required)
- `end_time` (required)
- `percentile` (optional): 0.50, 0.99, 0.999, default 0.99

**Response (200)**:
```json
[
  {
    "timestamp": "2024-10-10T14:00:00Z",
    "latency_ms": 125.5
  },
  {
    "timestamp": "2024-10-10T14:01:00Z",
    "latency_ms": 234.2
  }
]
```

---

## Root Cause Analysis

### POST /rca/analyze-error-spike
Analyze error spike incident

**Query Parameters**:
- `start_time` (required): ISO format datetime
- `end_time` (required): ISO format datetime

**Response (200)**:
```json
{
  "incident_id": "inc_20241010_a1b2c3",
  "root_cause": "Database connection pool exhausted - OutOfMemoryError",
  "confidence_score": 0.87,
  "affected_layers": ["application"],
  "observations": [
    "Error spike detected in application layer: 28.5% error rate",
    "Dominant error status: 500 (Internal Server Error)",
    "Found 134 correlated error groups",
    "Most common exception: OutOfMemoryError (45 occurrences)"
  ],
  "recommendations": [
    "IMMEDIATE: Increase DB connection pool size",
    "IMMEDIATE: Restart application to clear memory",
    "SHORT-TERM: Monitor memory usage and connection counts",
    "MEDIUM-TERM: Review database query efficiency"
  ]
}
```

**Response (200) - No incident**:
```json
{
  "status": "no_incident",
  "message": "No significant error spike detected"
}
```

---

### POST /rca/analyze-latency-spike
Analyze latency spike incident

**Query Parameters**:
- `start_time` (required)
- `end_time` (required)

**Response (200)**:
```json
{
  "incident_id": "inc_20241010_x9y8z7",
  "root_cause": "Application processing bottleneck - CPU-intensive operation",
  "confidence_score": 0.75,
  "affected_layers": ["application"],
  "observations": [
    "High latency detected in application layer: p99=8234ms",
    "Found 87 slow requests",
    "Most affected endpoints: /api/reports/generate, /api/analytics/compute"
  ],
  "recommendations": [
    "Optimize slow database queries",
    "Cache computation results",
    "Consider horizontal scaling"
  ]
}
```

---

### GET /rca/incidents
Get recent RCA incidents

**Query Parameters**:
- `start_time` (optional): ISO format datetime
- `end_time` (optional): ISO format datetime
- `limit` (optional): Max results, default 50, max 500

**Response (200)**:
```json
[
  {
    "id": 1,
    "incident_id": "inc_20241010_a1b2c3",
    "timestamp": "2024-10-10T14:35:00Z",
    "incident_type": "error_spike",
    "severity": "critical",
    "affected_component": "application",
    "root_cause": "Database connection pool exhausted",
    "confidence_score": 0.87,
    "status": "analyzed",
    "start_time": "2024-10-10T14:30:00Z",
    "end_time": "2024-10-10T14:35:00Z",
    "duration_seconds": 300,
    "created_at": "2024-10-10T14:35:00Z"
  }
]
```

---

### GET /rca/incident/{incident_id}
Get details of specific incident

**Parameters**:
- `incident_id` (path): Incident ID

**Response (200)**:
```json
{
  "id": 1,
  "incident_id": "inc_20241010_a1b2c3",
  "timestamp": "2024-10-10T14:35:00Z",
  "incident_type": "error_spike",
  "severity": "critical",
  "affected_component": "application",
  "root_cause": "Database connection pool exhausted - OutOfMemoryError",
  "confidence_score": 0.87,
  "evidence_log_ids": "req_123,req_124,req_125",
  "related_metrics": "{error_rate: 0.285, p99_latency: 8234}",
  "recommendations": "Increase DB connection pool\nRestart application\nMonitor memory usage",
  "status": "analyzed",
  "start_time": "2024-10-10T14:30:00Z",
  "end_time": "2024-10-10T14:35:00Z",
  "duration_seconds": 300,
  "created_at": "2024-10-10T14:35:00Z",
  "updated_at": "2024-10-10T14:35:30Z"
}
```

**Response (404)**:
```json
{
  "detail": "Incident not found"
}
```

---

## Dashboard

### GET /dashboard/metrics-snapshot
Get current system metrics snapshot (last 1 minute)

**Response (200)**:
```json
{
  "timestamp": "2024-10-10T14:00:00Z",
  "request_count": 4521,
  "error_count": 67,
  "error_rate": 0.0148,
  "p50_latency": 45.2,
  "p99_latency": 234.5,
  "p99_9_latency": 5230.0,
  "cpu_percent": 45.2,
  "memory_percent": 62.8,
  "disk_percent": 58.5
}
```

---

### GET /dashboard/component-health
Get health status of all components

**Response (200)**:
```json
{
  "nginx": {
    "status": "healthy",
    "health_score": 95,
    "request_count": 1234,
    "error_rate": 0.005,
    "p99_latency": 45.2
  },
  "gunicorn": {
    "status": "healthy",
    "health_score": 90,
    "request_count": 1234,
    "error_rate": 0.008,
    "p99_latency": 89.5
  },
  "uvicorn": {
    "status": "healthy",
    "health_score": 92,
    "request_count": 1234,
    "error_rate": 0.006,
    "p99_latency": 125.3
  },
  "application": {
    "status": "warning",
    "health_score": 65,
    "request_count": 1234,
    "error_rate": 0.028,
    "p99_latency": 456.7
  }
}
```

---

### GET /dashboard/recent-incidents
Get recent RCA incidents for dashboard

**Query Parameters**:
- `limit` (optional): Max results, default 10, max 100

**Response (200)**:
```json
{
  "total_incidents": 8,
  "incidents": [
    {
      "incident_id": "inc_20241010_a1b2c3",
      "incident_type": "error_spike",
      "severity": "critical",
      "timestamp": "2024-10-10T14:35:00Z",
      "root_cause": "Database connection pool exhausted",
      "confidence_score": 0.87
    }
  ]
}
```

---

## Charts & Visualization

### GET /charts/error-trend
Generate error rate trend chart

**Query Parameters**:
- `component` (required)
- `start_time` (required)
- `end_time` (required)

**Response (200)**:
```json
{
  "chart_type": "error_trend",
  "component": "nginx",
  "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "generated_at": "2024-10-10T14:00:00Z"
}
```

---

### GET /charts/latency-distribution
Generate latency distribution chart

**Query Parameters**:
- `component` (required)
- `start_time` (required)
- `end_time` (required)

**Response (200)**:
```json
{
  "chart_type": "latency_distribution",
  "component": "gunicorn",
  "data_points": 5432,
  "image": "data:image/png;base64,...",
  "generated_at": "2024-10-10T14:00:00Z"
}
```

---

### GET /charts/errors-by-status
Generate errors by status code chart

**Query Parameters**:
- `component` (required)
- `start_time` (required)
- `end_time` (required)

**Response (200)**:
```json
{
  "chart_type": "errors_by_status",
  "component": "application",
  "image": "data:image/png;base64,...",
  "generated_at": "2024-10-10T14:00:00Z"
}
```

---

### GET /charts/latency-by-endpoint
Generate latency comparison by endpoint

**Query Parameters**:
- `component` (required)
- `start_time` (required)
- `end_time` (required)

**Response (200)**:
```json
{
  "chart_type": "latency_by_endpoint",
  "component": "nginx",
  "endpoints": 45,
  "image": "data:image/png;base64,...",
  "generated_at": "2024-10-10T14:00:00Z"
}
```

---

### GET /charts/system-health
Generate system health metrics visualization

**Query Parameters**:
- `start_time` (required)
- `end_time` (required)

**Response (200)**:
```json
{
  "chart_type": "system_health",
  "image": "data:image/png;base64,...",
  "generated_at": "2024-10-10T14:00:00Z"
}
```

---

### GET /charts/request-volume
Generate request volume timeline

**Query Parameters**:
- `component` (required)
- `start_time` (required)
- `end_time` (required)

**Response (200)**:
```json
{
  "chart_type": "request_volume",
  "component": "nginx",
  "image": "data:image/png;base64,...",
  "generated_at": "2024-10-10T14:00:00Z"
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid query parameters or request body"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error. Check logs for details."
}
```

---

## Rate Limiting

Not implemented by default. Recommended for production:
- 1000 requests/minute per IP
- 10000 requests/minute total

---

## Pagination

List endpoints support:
- `limit`: Max results (default varies by endpoint, max 1000)
- `offset`: Starting position (default 0)

Example:
```
GET /logs/recent?limit=50&offset=100
```

---

## Date/Time Format

All dates must be in ISO 8601 format with timezone:
```
2024-10-10T14:00:00Z
2024-10-10T14:00:00+00:00
```
