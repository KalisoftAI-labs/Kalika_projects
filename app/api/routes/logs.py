"""Log collection and retrieval endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.storage.database import get_db
from app.models.orm import LogEntry
from app.models.schemas import LogEntryCreate, LogEntryResponse
from app.parsers.log_parsers import LogParserFactory

router = APIRouter()

@router.post("/ingest", response_model=dict)
async def ingest_logs(
    source: str,
    logs: List[str],
    db: Session = Depends(get_db)
):
    """
    Ingest logs from a source
    
    Args:
        source: Log source (nginx, gunicorn, uvicorn, application)
        logs: List of raw log lines
    """
    try:
        parser = LogParserFactory.get_parser(source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    ingested_count = 0
    failed_count = 0
    
    for log_line in logs:
        try:
            parsed = parser.parse(log_line)
            if parsed:
                # Create database entry (if db is available)
                if db is not None:
                    entry = LogEntry(
                        source=parsed.source,
                        timestamp=parsed.timestamp,
                        level=parsed.level,
                        message=parsed.message,
                        **parsed.components
                    )
                    db.add(entry)
                ingested_count += 1
        except Exception as e:
            failed_count += 1
    
    if db is not None:
        db.commit()
    
    return {
        "source": source,
        "ingested": ingested_count,
        "failed": failed_count,
        "total": len(logs),
        "note": "Running in demo mode - logs not persisted to database" if db is None else "Logs ingested successfully"
    }

@router.get("/recent", response_model=List[LogEntryResponse])
async def get_recent_logs(
    source: str = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get recent logs
    """
    if db is None:
        # Return empty list in demo mode
        return []
    
    query = db.query(LogEntry)
    
    if source:
        query = query.filter(LogEntry.source == source)
    
    logs = query.order_by(LogEntry.timestamp.desc()).limit(limit).all()
    
    return logs

@router.get("/by-request-id/{request_id}", response_model=List[LogEntryResponse])
async def get_logs_by_request_id(
    request_id: str,
    db: Session = Depends(get_db)
):
    """
    Get all logs for a request ID (trace request through layers)
    """
    if db is None:
        return []
    
    logs = db.query(LogEntry).filter(
        LogEntry.request_id == request_id
    ).order_by(LogEntry.timestamp.asc()).all()
    
    return logs

@router.get("/errors", response_model=List[LogEntryResponse])
async def get_error_logs(
    start_time: datetime = None,
    end_time: datetime = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get error logs
    """
    if db is None:
        return []
    
    query = db.query(LogEntry).filter(
        (LogEntry.level.in_(['ERROR', 'CRITICAL'])) |
        ((LogEntry.http_status >= 400) & (LogEntry.http_status < 600))
    )
    
    if start_time:
        query = query.filter(LogEntry.timestamp >= start_time)
    
    if end_time:
        query = query.filter(LogEntry.timestamp <= end_time)
    
    logs = query.order_by(LogEntry.timestamp.desc()).limit(limit).all()
    
    return logs
