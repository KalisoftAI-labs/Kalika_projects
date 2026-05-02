"""Pydantic schemas for API request/response"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any

# Log Entry Schemas
class LogEntryCreate(BaseModel):
    source: str
    timestamp: datetime
    level: str
    message: str
    component: Optional[str] = None
    request_id: Optional[str] = None
    http_method: Optional[str] = None
    http_status: Optional[int] = None
    remote_addr: Optional[str] = None
    request_uri: Optional[str] = None
    response_time: Optional[float] = None
    bytes_sent: Optional[int] = None
    user_id: Optional[str] = None
    service_name: Optional[str] = None
    exception_type: Optional[str] = None
    stack_trace: Optional[str] = None

class LogEntryResponse(LogEntryCreate):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Metric Schemas
class MetricCreate(BaseModel):
    timestamp: datetime
    window_size: int
    component: str
    metric_type: str
    value: float
    http_status: Optional[int] = None
    endpoint: Optional[str] = None
    error_type: Optional[str] = None

class MetricResponse(MetricCreate):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# RCA Analysis Schemas
class RCAFinding(BaseModel):
    root_cause: str
    confidence_score: float = Field(..., ge=0, le=1)
    evidence_summary: str
    affected_layers: List[str]

class RCAAnalysisCreate(BaseModel):
    incident_id: str
    incident_type: str
    severity: str
    affected_component: str
    root_cause: str
    confidence_score: float
    evidence_log_ids: Optional[str] = None
    related_metrics: Optional[str] = None
    recommendations: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None

class RCAAnalysisResponse(RCAAnalysisCreate):
    id: int
    duration_seconds: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# System Metrics Schemas
class SystemMetricCreate(BaseModel):
    timestamp: datetime
    hostname: str
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    load_average_1min: Optional[float] = None
    load_average_5min: Optional[float] = None
    load_average_15min: Optional[float] = None

class SystemMetricResponse(SystemMetricCreate):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Request Trace Schemas
class EventTimeline(BaseModel):
    component: str
    timestamp: datetime
    latency_ms: Optional[float] = None

class RequestTraceCreate(BaseModel):
    request_id: str
    trace_id: Optional[str] = None
    nginx_received_at: Optional[datetime] = None
    nginx_response_time: Optional[float] = None
    gunicorn_worker_id: Optional[str] = None
    gunicorn_received_at: Optional[datetime] = None
    uvicorn_received_at: Optional[datetime] = None
    app_received_at: Optional[datetime] = None
    app_response_time: Optional[float] = None
    final_status: Optional[int] = None
    total_latency: Optional[float] = None
    error_occurred: bool = False

class RequestTraceResponse(RequestTraceCreate):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Dashboard Schemas
class HealthStatus(BaseModel):
    status: str
    timestamp: datetime
    component_status: Dict[str, str]
    system_health: Dict[str, float]

class IncidentSummary(BaseModel):
    incident_id: str
    timestamp: datetime
    incident_type: str
    severity: str
    affected_component: str
    root_cause: str
    confidence_score: float
    status: str

class MetricsSnapshot(BaseModel):
    timestamp: datetime
    request_count: int
    error_count: int
    error_rate: float
    p50_latency: float
    p99_latency: float
    p99_9_latency: float
    cpu_percent: float
    memory_percent: float
    disk_percent: float

class ChartMetadata(BaseModel):
    chart_id: str
    title: str
    chart_type: str
    generated_at: datetime
    data_points: int
    file_path: str
