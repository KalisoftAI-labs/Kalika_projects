"""Metrics aggregation and processing engine"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics
import logging
from sqlalchemy.orm import Session

from app.models.orm import Metric, LogEntry
from app.core.config import Constants

logger = logging.getLogger(__name__)

class MetricsProcessor:
    """Process raw logs into aggregated metrics"""
    
    def __init__(self, db: Session, window_size: int = 60):
        """
        Initialize metrics processor
        
        Args:
            db: Database session
            window_size: Aggregation window in seconds
        """
        self.db = db
        self.window_size = window_size
    
    def aggregate_request_metrics(
        self,
        component: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, float]:
        """
        Aggregate request metrics for a component over time window
        
        Returns:
            Dictionary with: request_count, error_count, error_rate, 
                           p50_latency, p99_latency, p999_latency
        """
        logs = self.db.query(LogEntry).filter(
            LogEntry.source == component,
            LogEntry.timestamp >= start_time,
            LogEntry.timestamp <= end_time,
            LogEntry.http_status.isnot(None)
        ).all()
        
        if not logs:
            return {
                'request_count': 0,
                'error_count': 0,
                'error_rate': 0.0,
                'p50_latency': 0.0,
                'p99_latency': 0.0,
                'p999_latency': 0.0,
            }
        
        # Count metrics
        request_count = len(logs)
        error_count = sum(1 for log in logs if 400 <= log.http_status < 600)
        error_rate = error_count / request_count if request_count > 0 else 0.0
        
        # Calculate latency percentiles
        latencies = [log.response_time for log in logs if log.response_time]
        
        if latencies:
            sorted_latencies = sorted(latencies)
            p50_idx = int(len(sorted_latencies) * 0.50)
            p99_idx = int(len(sorted_latencies) * 0.99)
            p999_idx = int(len(sorted_latencies) * 0.999)
            
            # Ensure indices are valid
            p50_idx = min(p50_idx, len(sorted_latencies) - 1)
            p99_idx = min(p99_idx, len(sorted_latencies) - 1)
            p999_idx = min(p999_idx, len(sorted_latencies) - 1)
            
            p50_latency = sorted_latencies[p50_idx]
            p99_latency = sorted_latencies[p99_idx]
            p999_latency = sorted_latencies[p999_idx]
        else:
            p50_latency = p99_latency = p999_latency = 0.0
        
        return {
            'request_count': request_count,
            'error_count': error_count,
            'error_rate': round(error_rate, 4),
            'p50_latency': round(p50_latency, 2),
            'p99_latency': round(p99_latency, 2),
            'p999_latency': round(p999_latency, 2),
        }
    
    def aggregate_error_by_status(
        self,
        component: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[int, int]:
        """
        Aggregate error counts by HTTP status code
        """
        logs = self.db.query(LogEntry).filter(
            LogEntry.source == component,
            LogEntry.timestamp >= start_time,
            LogEntry.timestamp <= end_time,
            LogEntry.http_status >= 400
        ).all()
        
        error_distribution = defaultdict(int)
        for log in logs:
            error_distribution[log.http_status] += 1
        
        return dict(error_distribution)
    
    def aggregate_latency_by_endpoint(
        self,
        component: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Dict[str, float]]:
        """
        Aggregate latency metrics by endpoint
        
        Returns:
            {endpoint: {p50, p99, p999, count, mean}}
        """
        logs = self.db.query(LogEntry).filter(
            LogEntry.source == component,
            LogEntry.timestamp >= start_time,
            LogEntry.timestamp <= end_time,
            LogEntry.request_uri.isnot(None),
            LogEntry.response_time.isnot(None)
        ).all()
        
        endpoint_latencies: Dict[str, List[float]] = defaultdict(list)
        
        for log in logs:
            if log.request_uri:
                endpoint_latencies[log.request_uri].append(log.response_time)
        
        result = {}
        for endpoint, latencies in endpoint_latencies.items():
            if latencies:
                sorted_latencies = sorted(latencies)
                
                p50_idx = max(0, int(len(sorted_latencies) * 0.50) - 1)
                p99_idx = max(0, int(len(sorted_latencies) * 0.99) - 1)
                p999_idx = max(0, int(len(sorted_latencies) * 0.999) - 1)
                
                result[endpoint] = {
                    'count': len(latencies),
                    'mean': round(statistics.mean(latencies), 2),
                    'p50': round(sorted_latencies[p50_idx], 2),
                    'p99': round(sorted_latencies[p99_idx], 2),
                    'p999': round(sorted_latencies[p999_idx], 2),
                }
        
        return result
    
    def identify_slow_requests(
        self,
        component: str,
        start_time: datetime,
        end_time: datetime,
        threshold_ms: int = Constants.LATENCY_THRESHOLD_SLOW
    ) -> List[Dict]:
        """
        Identify requests exceeding latency threshold
        """
        logs = self.db.query(LogEntry).filter(
            LogEntry.source == component,
            LogEntry.timestamp >= start_time,
            LogEntry.timestamp <= end_time,
            LogEntry.response_time >= threshold_ms
        ).order_by(LogEntry.response_time.desc()).limit(100).all()
        
        return [
            {
                'timestamp': log.timestamp,
                'request_uri': log.request_uri,
                'response_time': log.response_time,
                'http_status': log.http_status,
                'request_id': log.request_id,
            }
            for log in logs
        ]
    
    def identify_errors(
        self,
        component: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        Identify error logs
        """
        logs = self.db.query(LogEntry).filter(
            LogEntry.source == component,
            LogEntry.timestamp >= start_time,
            LogEntry.timestamp <= end_time,
            (LogEntry.level.in_(['ERROR', 'CRITICAL'])) |
            ((LogEntry.http_status >= 400) & (LogEntry.http_status < 600))
        ).order_by(LogEntry.timestamp.desc()).limit(100).all()
        
        return [
            {
                'timestamp': log.timestamp,
                'level': log.level,
                'message': log.message,
                'http_status': log.http_status,
                'exception_type': log.exception_type,
                'request_id': log.request_id,
                'component': log.component,
            }
            for log in logs
        ]
    
    def get_error_rate_trend(
        self,
        component: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Tuple[datetime, float]]:
        """
        Get error rate trend over time (windowed)
        
        Returns:
            List of (timestamp, error_rate) tuples
        """
        current = start_time
        trend = []
        
        while current < end_time:
            window_end = current + timedelta(seconds=self.window_size)
            
            metrics = self.aggregate_request_metrics(
                component, current, window_end
            )
            
            trend.append((current, metrics['error_rate']))
            current = window_end
        
        return trend
    
    def get_latency_trend(
        self,
        component: str,
        start_time: datetime,
        end_time: datetime,
        percentile: float = 0.99
    ) -> List[Tuple[datetime, float]]:
        """
        Get latency percentile trend over time
        
        Args:
            percentile: 0.50, 0.99, 0.999
        """
        current = start_time
        trend = []
        
        while current < end_time:
            window_end = current + timedelta(seconds=self.window_size)
            
            metrics = self.aggregate_request_metrics(
                component, current, window_end
            )
            
            if percentile == 0.50:
                value = metrics['p50_latency']
            elif percentile == 0.99:
                value = metrics['p99_latency']
            elif percentile == 0.999:
                value = metrics['p999_latency']
            else:
                value = 0.0
            
            trend.append((current, value))
            current = window_end
        
        return trend

class RequestCorrelator:
    """Correlate requests across system layers"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_request_path(self, request_id: str) -> List[Dict]:
        """
        Find all log entries for a request across layers
        
        Returns:
            Ordered list of log entries from each layer
        """
        logs = self.db.query(LogEntry).filter(
            LogEntry.request_id == request_id
        ).order_by(LogEntry.timestamp.asc()).all()
        
        return [
            {
                'timestamp': log.timestamp,
                'source': log.source,
                'level': log.level,
                'message': log.message,
                'response_time': log.response_time,
                'http_status': log.http_status,
                'exception_type': log.exception_type,
            }
            for log in logs
        ]
    
    def correlate_errors(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, List[Dict]]:
        """
        Find correlated errors across layers within time window
        """
        errors = self.db.query(LogEntry).filter(
            LogEntry.timestamp >= start_time,
            LogEntry.timestamp <= end_time,
            (LogEntry.level.in_(['ERROR', 'CRITICAL'])) |
            ((LogEntry.http_status >= 400) & (LogEntry.http_status < 600))
        ).all()
        
        # Group by request_id
        correlated = defaultdict(list)
        
        for error in errors:
            key = error.request_id or f"{error.source}_{error.timestamp}"
            correlated[key].append({
                'source': error.source,
                'timestamp': error.timestamp,
                'message': error.message,
                'level': error.level,
                'http_status': error.http_status,
            })
        
        return dict(correlated)
