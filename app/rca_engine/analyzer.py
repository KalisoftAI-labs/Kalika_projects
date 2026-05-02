"""Root Cause Analysis Engine"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import logging
from sqlalchemy.orm import Session

from app.core.config import Constants
from app.models.orm import LogEntry, Metric, RCAAnalysis
from app.processors.metrics import MetricsProcessor, RequestCorrelator

logger = logging.getLogger(__name__)

@dataclass
class RCAFinding:
    """RCA finding"""
    root_cause: str
    confidence_score: float  # 0-1
    evidence_logs: List[str]  # Log IDs
    affected_layers: List[str]
    observations: List[str]
    recommendations: List[str]

class RCAEngine:
    """
    Root Cause Analysis Engine
    
    Uses rule-based and heuristic-based analysis to identify root causes
    of incidents by correlating logs across system layers.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.processor = MetricsProcessor(db, window_size=60)
        self.correlator = RequestCorrelator(db)
    
    def analyze_error_spike(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[RCAFinding]:
        """
        Analyze error spike incident
        """
        window = end_time - start_time
        correlation_start = start_time - timedelta(seconds=30)
        
        # Collect metrics for all components
        nginx_metrics = self.processor.aggregate_request_metrics('nginx', start_time, end_time)
        gunicorn_metrics = self.processor.aggregate_request_metrics('gunicorn', start_time, end_time)
        app_metrics = self.processor.aggregate_request_metrics('application', start_time, end_time)
        
        # Identify which component has highest error rate
        error_rates = {
            'nginx': nginx_metrics.get('error_rate', 0),
            'gunicorn': gunicorn_metrics.get('error_rate', 0),
            'application': app_metrics.get('error_rate', 0),
        }
        
        most_affected = max(error_rates, key=error_rates.get)
        max_error_rate = error_rates[most_affected]
        
        if max_error_rate == 0:
            return None
        
        # Analyze errors in detail
        observations = [
            f"Error spike detected in {most_affected}: {max_error_rate*100:.2f}% error rate",
        ]
        
        # Get error distribution
        error_dist = self.processor.aggregate_error_by_status(most_affected, start_time, end_time)
        
        # Identify patterns
        dominant_status = max(error_dist, key=error_dist.get) if error_dist else None
        
        if dominant_status:
            observations.append(f"Dominant error status: {dominant_status}")
        
        # Get correlated errors
        correlated_errors = self.correlator.correlate_errors(correlation_start, end_time)
        observations.append(f"Found {len(correlated_errors)} correlated error groups")
        
        # Determine root cause based on patterns
        root_cause, confidence = self._determine_error_root_cause(
            most_affected, 
            error_dist, 
            observations,
            correlation_start,
            end_time
        )
        
        # Get evidence logs
        error_logs = self.processor.identify_errors(most_affected, start_time, end_time)
        evidence_log_ids = [f"{log['request_id']}" for log in error_logs[:10] if log['request_id']]
        
        recommendations = self._get_recommendations(root_cause, most_affected)
        
        return RCAFinding(
            root_cause=root_cause,
            confidence_score=confidence,
            evidence_logs=evidence_log_ids,
            affected_layers=[most_affected],
            observations=observations,
            recommendations=recommendations
        )
    
    def analyze_latency_spike(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Optional[RCAFinding]:
        """
        Analyze latency spike incident
        """
        # Collect latency metrics for all components
        nginx_metrics = self.processor.aggregate_request_metrics('nginx', start_time, end_time)
        gunicorn_metrics = self.processor.aggregate_request_metrics('gunicorn', start_time, end_time)
        app_metrics = self.processor.aggregate_request_metrics('application', start_time, end_time)
        
        # Identify which layer has highest latency
        latencies = {
            'nginx': nginx_metrics.get('p99_latency', 0),
            'gunicorn': gunicorn_metrics.get('p99_latency', 0),
            'application': app_metrics.get('p99_latency', 0),
        }
        
        most_affected = max(latencies, key=latencies.get)
        max_latency = latencies[most_affected]
        
        if max_latency < Constants.LATENCY_THRESHOLD_SLOW:
            return None
        
        observations = [
            f"High latency detected in {most_affected}: p99={max_latency}ms",
        ]
        
        # Get slow requests
        slow_requests = self.processor.identify_slow_requests(
            most_affected,
            start_time,
            end_time,
            threshold_ms=Constants.LATENCY_THRESHOLD_SLOW
        )
        
        observations.append(f"Found {len(slow_requests)} slow requests")
        
        # Analyze by endpoint
        latency_by_endpoint = self.processor.aggregate_latency_by_endpoint(
            most_affected,
            start_time,
            end_time
        )
        
        # Find most affected endpoint
        affected_endpoints = sorted(
            latency_by_endpoint.items(),
            key=lambda x: x[1]['p99'],
            reverse=True
        )[:3]
        
        observations.append(
            f"Most affected endpoints: {', '.join(ep[0] for ep in affected_endpoints)}"
        )
        
        # Determine root cause
        root_cause, confidence = self._determine_latency_root_cause(
            most_affected,
            latencies,
            observations,
            start_time,
            end_time
        )
        
        recommendations = self._get_recommendations(root_cause, most_affected)
        
        return RCAFinding(
            root_cause=root_cause,
            confidence_score=confidence,
            evidence_logs=[],
            affected_layers=[most_affected],
            observations=observations,
            recommendations=recommendations
        )
    
    def _determine_error_root_cause(
        self,
        component: str,
        error_distribution: Dict[int, int],
        observations: List[str],
        start_time: datetime,
        end_time: datetime
    ) -> Tuple[str, float]:
        """
        Determine error root cause based on patterns
        
        Returns:
            (root_cause_description, confidence_score)
        """
        if not error_distribution:
            return "Unknown error", 0.3
        
        # Analyze error patterns
        error_500_count = sum(v for k, v in error_distribution.items() if 500 <= k < 600)
        error_400_count = sum(v for k, v in error_distribution.items() if 400 <= k < 500)
        
        total_errors = error_500_count + error_400_count
        ratio_5xx = error_500_count / total_errors if total_errors > 0 else 0
        
        # Rules
        if ratio_5xx > 0.7:
            observations.append("High ratio of 5xx errors indicates server-side issue")
            
            # Check for specific errors
            error_codes = {k: v for k, v in error_distribution.items() if 500 <= k < 600}
            
            if 502 in error_codes:
                return (
                    "Upstream gateway timeout or bad gateway - check load balancing or upstream services",
                    0.85
                )
            elif 503 in error_codes:
                return (
                    "Service overload or unavailable - check resource utilization and scaling",
                    0.80
                )
            elif 500 in error_codes:
                # Check for exceptions
                exception_logs = self.db.query(LogEntry).filter(
                    LogEntry.source == component,
                    LogEntry.timestamp >= start_time,
                    LogEntry.timestamp <= end_time,
                    LogEntry.exception_type.isnot(None)
                ).all()
                
                if exception_logs:
                    exception_types = {}
                    for log in exception_logs:
                        exception_types[log.exception_type] = exception_types.get(log.exception_type, 0) + 1
                    
                    most_common_exception = max(exception_types, key=exception_types.get)
                    observations.append(f"Most common exception: {most_common_exception}")
                    
                    return (
                        f"Application error - uncaught exception of type {most_common_exception}",
                        0.75
                    )
                else:
                    return (
                        "Internal server error - check application logs for details",
                        0.70
                    )
        else:
            observations.append("High ratio of 4xx errors indicates client or request validation issue")
            return (
                "Client-side error or invalid requests - check request validation and client behavior",
                0.65
            )
        
        return "Unexpected error pattern", 0.5
    
    def _determine_latency_root_cause(
        self,
        component: str,
        latencies: Dict[str, float],
        observations: List[str],
        start_time: datetime,
        end_time: datetime
    ) -> Tuple[str, float]:
        """
        Determine latency root cause
        """
        # Check progression through layers
        app_latency = latencies.get('application', 0)
        gunicorn_latency = latencies.get('gunicorn', 0)
        nginx_latency = latencies.get('nginx', 0)
        
        # If latency is highest at Nginx, it's likely upstream or routing
        if nginx_latency >= gunicorn_latency and nginx_latency >= app_latency:
            observations.append("Latency originates at Nginx layer - likely network or load balancing")
            return (
                "Network latency or load balancer congestion - check network health and LB configuration",
                0.70
            )
        
        # If highest in Gunicorn, it's worker-related
        elif gunicorn_latency >= app_latency:
            observations.append("Latency originates in Gunicorn workers")
            return (
                "Gunicorn worker pool saturation or slow app processing - consider increasing workers",
                0.75
            )
        
        # If highest in application layer, it's app-specific
        else:
            observations.append("Latency originates in application layer")
            
            # Check for resource constraints
            # In production, check system metrics
            return (
                "Application processing bottleneck - check CPU-intensive operations and database queries",
                0.70
            )
    
    def _get_recommendations(self, root_cause: str, component: str) -> List[str]:
        """
        Generate recommendations based on root cause
        """
        recommendations = []
        
        common_recommendations = {
            "scaling": "Scale up the affected component horizontally or vertically",
            "monitoring": "Increase monitoring granularity for early warning",
            "caching": "Implement or increase caching layers",
            "database": "Optimize database queries or add read replicas",
            "network": "Check network connectivity and latency",
            "logs": "Enable debug logging to trace the issue",
        }
        
        # Generic recommendations based on root cause
        if "timeout" in root_cause.lower():
            recommendations.append(common_recommendations["scaling"])
            recommendations.append("Increase timeout thresholds cautiously")
        elif "database" in root_cause.lower():
            recommendations.append(common_recommendations["database"])
            recommendations.append("Add database indexing and optimize slow queries")
        elif "exception" in root_cause.lower():
            recommendations.append(common_recommendations["logs"])
            recommendations.append("Review and fix application code")
        elif "overload" in root_cause.lower():
            recommendations.append(common_recommendations["scaling"])
            recommendations.append("Implement rate limiting")
        else:
            recommendations.append("Investigate further with detailed component logs")
        
        recommendations.append(common_recommendations["monitoring"])
        
        return recommendations
