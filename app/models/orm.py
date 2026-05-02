"""SQLAlchemy ORM Models"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import pytz

Base = declarative_base()

class LogEntry(Base):
    """Raw log entry model"""
    __tablename__ = "log_entries"
    
    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)  # nginx, gunicorn, uvicorn, application
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    level = Column(String(20), nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    component = Column(String(100), nullable=True)
    request_id = Column(String(100), nullable=True, index=True)
    
    # Nginx specific
    http_method = Column(String(10), nullable=True)
    http_status = Column(Integer, nullable=True)
    remote_addr = Column(String(50), nullable=True)
    request_uri = Column(String(500), nullable=True)
    response_time = Column(Float, nullable=True)  # milliseconds
    bytes_sent = Column(Integer, nullable=True)
    
    # Application specific
    user_id = Column(String(100), nullable=True)
    service_name = Column(String(100), nullable=True)
    exception_type = Column(String(100), nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    
    __table_args__ = (
        Index('idx_source_timestamp', 'source', 'timestamp'),
        Index('idx_request_id', 'request_id'),
        Index('idx_component_timestamp', 'component', 'timestamp'),
    )

class Metric(Base):
    """Aggregated metrics model"""
    __tablename__ = "metrics"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    window_size = Column(Integer, nullable=False)  # seconds
    component = Column(String(100), nullable=False)  # nginx, gunicorn, uvicorn, application
    metric_type = Column(String(50), nullable=False)  # request_count, error_rate, p99_latency, etc.
    value = Column(Float, nullable=False)
    
    # Dimensions
    http_status = Column(Integer, nullable=True)
    endpoint = Column(String(500), nullable=True)
    error_type = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    
    __table_args__ = (
        Index('idx_component_metric_timestamp', 'component', 'metric_type', 'timestamp'),
    )

class RCAAnalysis(Base):
    """Root Cause Analysis results"""
    __tablename__ = "rca_analyses"
    
    id = Column(Integer, primary_key=True)
    incident_id = Column(String(100), nullable=False, unique=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Incident details
    incident_type = Column(String(50), nullable=False)  # error, latency, timeout, crash, resource, upstream
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    affected_component = Column(String(100), nullable=False)
    
    # RCA findings
    root_cause = Column(String(500), nullable=False)
    confidence_score = Column(Float, nullable=False)  # 0-1
    
    # Evidence
    evidence_log_ids = Column(String(1000), nullable=True)  # JSON-encoded list of log IDs
    related_metrics = Column(String(1000), nullable=True)  # JSON-encoded metrics
    
    # Recommendations
    recommendations = Column(Text, nullable=True)
    
    # Timeline
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    status = Column(String(20), default="ongoing")  # ongoing, resolved, investigating
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC), onupdate=lambda: datetime.now(pytz.UTC))
    
    __table_args__ = (
        Index('idx_incident_timestamp', 'timestamp'),
        Index('idx_incident_component', 'affected_component'),
    )

class SystemMetric(Base):
    """System-level metrics (CPU, memory, disk)"""
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    hostname = Column(String(100), nullable=False)
    cpu_percent = Column(Float, nullable=True)
    memory_percent = Column(Float, nullable=True)
    disk_percent = Column(Float, nullable=True)
    load_average_1min = Column(Float, nullable=True)
    load_average_5min = Column(Float, nullable=True)
    load_average_15min = Column(Float, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    
    __table_args__ = (
        Index('idx_hostname_timestamp', 'hostname', 'timestamp'),
    )

class RequestTrace(Base):
    """Request path through system layers"""
    __tablename__ = "request_traces"
    
    id = Column(Integer, primary_key=True)
    request_id = Column(String(100), nullable=False, unique=True, index=True)
    trace_id = Column(String(100), nullable=True)
    
    # Timeline events
    nginx_received_at = Column(DateTime(timezone=True), nullable=True)
    nginx_response_time = Column(Float, nullable=True)
    
    gunicorn_worker_id = Column(String(100), nullable=True)
    gunicorn_received_at = Column(DateTime(timezone=True), nullable=True)
    
    uvicorn_received_at = Column(DateTime(timezone=True), nullable=True)
    
    app_received_at = Column(DateTime(timezone=True), nullable=True)
    app_response_time = Column(Float, nullable=True)
    
    # Results
    final_status = Column(Integer, nullable=True)
    total_latency = Column(Float, nullable=True)  # milliseconds
    error_occurred = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(pytz.UTC))
    
    __table_args__ = (
        Index('idx_trace_id', 'trace_id'),
    )
