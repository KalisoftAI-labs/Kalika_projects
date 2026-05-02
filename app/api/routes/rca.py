"""RCA analysis endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Dict
import uuid

from app.storage.database import get_db
from app.models.orm import RCAAnalysis
from app.models.schemas import RCAAnalysisResponse
from app.rca_engine.analyzer import RCAEngine

router = APIRouter()

@router.post("/analyze-error-spike")
async def analyze_error_spike(
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Analyze error spike incident and perform RCA
    """
    engine = RCAEngine(db)
    
    finding = engine.analyze_error_spike(start_time, end_time)
    
    if not finding:
        return {"status": "no_incident", "message": "No significant error spike detected"}
    
    # Store RCA result
    incident_id = str(uuid.uuid4())
    
    rca_record = RCAAnalysis(
        incident_id=incident_id,
        timestamp=datetime.utcnow(),
        incident_type="error_spike",
        severity="critical" if finding.confidence_score > 0.8 else "high",
        affected_component=finding.affected_layers[0] if finding.affected_layers else "unknown",
        root_cause=finding.root_cause,
        confidence_score=finding.confidence_score,
        evidence_log_ids=",".join(finding.evidence_logs),
        recommendations="\n".join(finding.recommendations),
        start_time=start_time,
        end_time=end_time,
        duration_seconds=int((end_time - start_time).total_seconds()),
        status="analyzed"
    )
    
    db.add(rca_record)
    db.commit()
    
    return {
        "incident_id": incident_id,
        "root_cause": finding.root_cause,
        "confidence_score": finding.confidence_score,
        "affected_layers": finding.affected_layers,
        "observations": finding.observations,
        "recommendations": finding.recommendations,
    }

@router.post("/analyze-latency-spike")
async def analyze_latency_spike(
    start_time: datetime,
    end_time: datetime,
    db: Session = Depends(get_db)
) -> Dict:
    """
    Analyze latency spike incident and perform RCA
    """
    engine = RCAEngine(db)
    
    finding = engine.analyze_latency_spike(start_time, end_time)
    
    if not finding:
        return {"status": "no_incident", "message": "No significant latency spike detected"}
    
    # Store RCA result
    incident_id = str(uuid.uuid4())
    
    rca_record = RCAAnalysis(
        incident_id=incident_id,
        timestamp=datetime.utcnow(),
        incident_type="latency_spike",
        severity="medium" if finding.confidence_score > 0.7 else "low",
        affected_component=finding.affected_layers[0] if finding.affected_layers else "unknown",
        root_cause=finding.root_cause,
        confidence_score=finding.confidence_score,
        recommendations="\n".join(finding.recommendations),
        start_time=start_time,
        end_time=end_time,
        duration_seconds=int((end_time - start_time).total_seconds()),
        status="analyzed"
    )
    
    db.add(rca_record)
    db.commit()
    
    return {
        "incident_id": incident_id,
        "root_cause": finding.root_cause,
        "confidence_score": finding.confidence_score,
        "affected_layers": finding.affected_layers,
        "observations": finding.observations,
        "recommendations": finding.recommendations,
    }

@router.get("/incidents")
async def get_incidents(
    start_time: datetime = None,
    end_time: datetime = None,
    limit: int = 50,
    db: Session = Depends(get_db)
) -> List[RCAAnalysisResponse]:
    """
    Get recent RCA incidents
    """
    query = db.query(RCAAnalysis)
    
    if start_time:
        query = query.filter(RCAAnalysis.timestamp >= start_time)
    
    if end_time:
        query = query.filter(RCAAnalysis.timestamp <= end_time)
    
    incidents = query.order_by(RCAAnalysis.timestamp.desc()).limit(limit).all()
    
    return incidents

@router.get("/incident/{incident_id}", response_model=RCAAnalysisResponse)
async def get_incident(
    incident_id: str,
    db: Session = Depends(get_db)
) -> RCAAnalysisResponse:
    """
    Get details of a specific RCA incident
    """
    incident = db.query(RCAAnalysis).filter(
        RCAAnalysis.incident_id == incident_id
    ).first()
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    return incident
