"""Visualization module for generating charts with Seaborn"""

import os
import io
import base64
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

from app.core.config import get_settings
from app.storage.object_storage import get_object_storage

logger = logging.getLogger(__name__)

class ChartGenerator:
    """Generate visualizations for RCA dashboard"""
    
    def __init__(self):
        self.settings = get_settings()
        self.storage = get_object_storage()
        self._configure_style()
    
    def _configure_style(self):
        """Configure Seaborn and Matplotlib style"""
        sns.set_style(self.settings.chart_style)
        plt.rcParams['figure.dpi'] = self.settings.chart_dpi
        plt.rcParams['savefig.dpi'] = self.settings.chart_dpi
    
    def generate_error_trend_chart(
        self,
        trend_data: List[Tuple[datetime, float]],
        title: str = "Error Rate Trend"
    ) -> str:
        """
        Generate error rate trend chart
        
        Args:
            trend_data: List of (timestamp, error_rate) tuples
            
        Returns:
            Base64 encoded image
        """
        if not trend_data:
            return ""
        
        df = pd.DataFrame(trend_data, columns=['timestamp', 'error_rate'])
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.plot(df['timestamp'], df['error_rate'], marker='o', linewidth=2, markersize=4)
        ax.fill_between(df['timestamp'], df['error_rate'], alpha=0.3)
        
        ax.set_xlabel('Time')
        ax.set_ylabel('Error Rate')
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        return self._fig_to_base64(fig)
    
    def generate_latency_distribution_chart(
        self,
        latencies: List[float],
        title: str = "Latency Distribution"
    ) -> str:
        """
        Generate latency distribution histogram
        """
        if not latencies:
            return ""
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        ax.hist(latencies, bins=50, edgecolor='black', alpha=0.7)
        
        # Add percentile lines
        p50 = np.percentile(latencies, 50)
        p99 = np.percentile(latencies, 99)
        p999 = np.percentile(latencies, 99.9)
        
        ax.axvline(p50, color='green', linestyle='--', label=f'p50={p50:.0f}ms')
        ax.axvline(p99, color='orange', linestyle='--', label=f'p99={p99:.0f}ms')
        ax.axvline(p999, color='red', linestyle='--', label=f'p999={p999:.0f}ms')
        
        ax.set_xlabel('Latency (ms)')
        ax.set_ylabel('Frequency')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        return self._fig_to_base64(fig)
    
    def generate_error_by_status_chart(
        self,
        error_distribution: Dict[int, int],
        title: str = "Errors by Status Code"
    ) -> str:
        """
        Generate bar chart of errors by HTTP status code
        """
        if not error_distribution:
            return ""
        
        df = pd.DataFrame(
            list(error_distribution.items()),
            columns=['status_code', 'count']
        )
        df['status_code'] = df['status_code'].astype(str)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        colors = ['#d62728' if int(code) >= 500 else '#ff7f0e' for code in df['status_code']]
        ax.bar(df['status_code'], df['count'], color=colors, edgecolor='black')
        
        ax.set_xlabel('HTTP Status Code')
        ax.set_ylabel('Error Count')
        ax.set_title(title)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        return self._fig_to_base64(fig)
    
    def generate_latency_by_endpoint_chart(
        self,
        endpoint_data: Dict[str, Dict[str, float]],
        title: str = "Latency by Endpoint (p99)"
    ) -> str:
        """
        Generate latency comparison by endpoint
        """
        if not endpoint_data:
            return ""
        
        # Convert to DataFrame
        endpoints = []
        latencies = []
        
        for endpoint, metrics in endpoint_data.items():
            endpoints.append(endpoint[-30:])  # Truncate for display
            latencies.append(metrics['p99'])
        
        df = pd.DataFrame({'endpoint': endpoints, 'p99_latency': latencies})
        df = df.sort_values('p99_latency', ascending=False).head(15)
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        colors = plt.cm.RdYlGn_r(df['p99_latency'] / df['p99_latency'].max())
        ax.barh(range(len(df)), df['p99_latency'], color=colors, edgecolor='black')
        
        ax.set_yticks(range(len(df)))
        ax.set_yticklabels(df['endpoint'], fontsize=9)
        ax.set_xlabel('p99 Latency (ms)')
        ax.set_title(title)
        ax.grid(True, alpha=0.3, axis='x')
        
        plt.tight_layout()
        
        return self._fig_to_base64(fig)
    
    def generate_system_health_chart(
        self,
        system_metrics: List[Dict],
        title: str = "System Health Metrics"
    ) -> str:
        """
        Generate system health metrics visualization
        """
        if not system_metrics:
            return ""
        
        df = pd.DataFrame(system_metrics)
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # CPU
        if 'cpu_percent' in df.columns:
            ax = axes[0, 0]
            ax.plot(df.index, df['cpu_percent'], marker='o', linewidth=2, color='#1f77b4')
            ax.axhline(80, color='orange', linestyle='--', alpha=0.7)
            ax.axhline(95, color='red', linestyle='--', alpha=0.7)
            ax.set_ylabel('CPU %')
            ax.set_title('CPU Usage')
            ax.set_ylim(0, 100)
            ax.grid(True, alpha=0.3)
        
        # Memory
        if 'memory_percent' in df.columns:
            ax = axes[0, 1]
            ax.plot(df.index, df['memory_percent'], marker='o', linewidth=2, color='#ff7f0e')
            ax.axhline(80, color='orange', linestyle='--', alpha=0.7)
            ax.axhline(95, color='red', linestyle='--', alpha=0.7)
            ax.set_ylabel('Memory %')
            ax.set_title('Memory Usage')
            ax.set_ylim(0, 100)
            ax.grid(True, alpha=0.3)
        
        # Disk
        if 'disk_percent' in df.columns:
            ax = axes[1, 0]
            ax.plot(df.index, df['disk_percent'], marker='o', linewidth=2, color='#2ca02c')
            ax.axhline(80, color='orange', linestyle='--', alpha=0.7)
            ax.axhline(95, color='red', linestyle='--', alpha=0.7)
            ax.set_ylabel('Disk %')
            ax.set_title('Disk Usage')
            ax.set_ylim(0, 100)
            ax.grid(True, alpha=0.3)
        
        # Load Average
        if 'load_average_1min' in df.columns:
            ax = axes[1, 1]
            ax.plot(df.index, df['load_average_1min'], marker='o', label='1min', linewidth=2)
            if 'load_average_5min' in df.columns:
                ax.plot(df.index, df['load_average_5min'], marker='s', label='5min', linewidth=2)
            if 'load_average_15min' in df.columns:
                ax.plot(df.index, df['load_average_15min'], marker='^', label='15min', linewidth=2)
            ax.set_ylabel('Load Average')
            ax.set_title('System Load')
            ax.legend()
            ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        return self._fig_to_base64(fig)
    
    def generate_request_volume_chart(
        self,
        volume_data: List[Tuple[datetime, int]],
        title: str = "Request Volume Trend"
    ) -> str:
        """
        Generate request volume timeline
        """
        if not volume_data:
            return ""
        
        df = pd.DataFrame(volume_data, columns=['timestamp', 'count'])
        
        fig, ax = plt.subplots(figsize=(14, 6))
        
        ax.bar(df['timestamp'], df['count'], edgecolor='black', alpha=0.7)
        ax.plot(df['timestamp'], df['count'], marker='o', color='red', linewidth=2, label='Trend')
        
        ax.set_xlabel('Time')
        ax.set_ylabel('Request Count')
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        return self._fig_to_base64(fig)
    
    @staticmethod
    def _fig_to_base64(fig) -> str:
        """Convert Matplotlib figure to base64 string"""
        try:
            buffer = io.BytesIO()
            fig.savefig(buffer, format='png', bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode()
            plt.close(fig)
            return image_base64
        except Exception as e:
            logger.error(f"Failed to convert figure to base64: {e}")
            plt.close(fig)
            return ""
