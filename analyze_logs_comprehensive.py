#!/usr/bin/env python
"""
Comprehensive Log Analyzer for Multiple Sources
Supports: Nginx, Gunicorn, Uvicorn logs
Generates detailed analytics and visualizations
"""

import os
import re
from datetime import datetime
from collections import defaultdict, Counter
import json

def parse_nginx_log(line):
    """Parse Nginx combined log format"""
    pattern = r'(\S+) - - \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\d+) "([^"]*)" "([^"]*)"'
    match = re.match(pattern, line)
    if not match:
        return None
    
    ip, timestamp_str, method, uri, protocol, status, bytes_sent, referer, user_agent = match.groups()
    
    try:
        dt = datetime.strptime(timestamp_str.split(' ')[0], '%d/%b/%Y:%H:%M:%S')
    except:
        return None
    
    return {
        'source': 'nginx',
        'remote_addr': ip,
        'timestamp': dt,
        'http_method': method,
        'request_uri': uri,
        'protocol': protocol,
        'http_status': int(status),
        'bytes_sent': int(bytes_sent),
        'latency_ms': 0,
        'user_agent': user_agent,
    }

def parse_gunicorn_log(line):
    """Parse Gunicorn log format: [TIMESTAMP] "METHOD PATH HTTP/VERSION" STATUS BYTES LATENCY_MS"""
    pattern = r'\[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\d+) ([\d.]+)ms'
    match = re.match(pattern, line)
    if not match:
        return None
    
    timestamp_str, method, uri, protocol, status, bytes_sent, latency = match.groups()
    
    try:
        dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    except:
        return None
    
    return {
        'source': 'gunicorn',
        'remote_addr': '127.0.0.1',
        'timestamp': dt,
        'http_method': method,
        'request_uri': uri,
        'protocol': protocol,
        'http_status': int(status),
        'bytes_sent': int(bytes_sent),
        'latency_ms': float(latency),
        'user_agent': 'gunicorn',
    }

def parse_uvicorn_log(line):
    """Parse Uvicorn log format: TIMESTAMP LEVEL PATH STATUS BYTES (LATENCY_MS)"""
    pattern = r'(\d{4}-\d{2}-\d{2}T[\d:.Z]+)\s+(\w+)\s+(\S+) (\S+) (\d+) (\d+) \(([\d.]+)ms\)'
    match = re.match(pattern, line)
    if not match:
        return None
    
    timestamp_str, level, path, method, status, bytes_sent, latency = match.groups()
    
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except:
        try:
            dt = datetime.strptime(timestamp_str[:19], '%Y-%m-%dT%H:%M:%S')
        except:
            return None
    
    # Parse path to extract method if needed
    if method.isdigit():
        status = int(method)
        bytes_sent = int(status)
        method = 'GET'
    
    return {
        'source': 'uvicorn',
        'remote_addr': '127.0.0.1',
        'timestamp': dt,
        'http_method': 'GET',
        'request_uri': path,
        'protocol': 'HTTP/1.1',
        'http_status': status,
        'bytes_sent': int(bytes_sent),
        'latency_ms': float(latency),
        'user_agent': f'uvicorn ({level})',
    }

def load_logs_from_file(file_path, log_type):
    """Load and parse logs from a file based on type"""
    logs = []
    errors = 0
    
    if not os.path.exists(file_path):
        return logs, errors
    
    parsers = {
        'nginx': parse_nginx_log,
        'gunicorn': parse_gunicorn_log,
        'uvicorn': parse_uvicorn_log,
    }
    
    parser = parsers.get(log_type)
    if not parser:
        return logs, errors
    
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = parser(line)
                if parsed:
                    logs.append(parsed)
            except:
                errors += 1
    
    return logs, errors

def analyze_logs():
    """Analyze logs from multiple sources"""
    print("\n" + "=" * 80)
    print("  🚀 COMPREHENSIVE LOG ANALYZER - MULTI-SOURCE")
    print("=" * 80)
    
    # Define log sources
    log_sources = [
        ('app/access_nginx_log', 'nginx'),
        ('app/gunicorn.log', 'gunicorn'),
        ('app/uvicorn.log', 'uvicorn'),
    ]
    
    all_logs = []
    source_stats = {}
    
    # Load logs from all sources
    print("\n📂 Loading logs from multiple sources...\n")
    
    for file_path, log_type in log_sources:
        logs, errors = load_logs_from_file(file_path, log_type)
        if logs:
            all_logs.extend(logs)
            source_stats[log_type] = {
                'count': len(logs),
                'errors': errors,
                'file': file_path
            }
            print(f"  ✓ {log_type.upper():12} | {len(logs):4} entries | {errors:2} errors | {file_path}")
    
    total_logs = len(all_logs)
    
    if total_logs == 0:
        print("  ❌ No logs found!")
        return
    
    print(f"\n  📊 Total entries combined: {total_logs}\n")
    
    # === GLOBAL METRICS ===
    print("=" * 80)
    print(" GLOBAL METRICS ANALYSIS")
    print("=" * 80)
    
    total_bytes = sum(log['bytes_sent'] for log in all_logs)
    avg_latency = sum(log['latency_ms'] for log in all_logs) / total_logs if all_logs else 0
    
    statuses = Counter(log['http_status'] for log in all_logs)
    methods = Counter(log['http_method'] for log in all_logs)
    sources = Counter(log['source'] for log in all_logs)
    
    error_count = sum(count for status, count in statuses.items() if int(status) >= 400)
    success_count = sum(count for status, count in statuses.items() if int(status) < 400)
    
    print(f"\n📈 Overall Statistics:")
    print(f"  Total Requests: {total_logs}")
    print(f"  Total Data: {total_bytes:,} bytes ({total_bytes/1024/1024:.2f} MB)")
    print(f"  Avg Response Time: {avg_latency:.2f}ms")
    print(f"  Success Rate: {success_count}/{total_logs} ({100*success_count/total_logs:.1f}%)")
    print(f"  Error Rate: {error_count}/{total_logs} ({100*error_count/total_logs:.1f}%)")
    
    print(f"\n🔸 Sources Distribution:")
    for source in sorted(sources.keys()):
        count = sources[source]
        pct = 100 * count / total_logs
        bar = '█' * int(pct / 2)
        print(f"  {source.upper():12} | {count:4} requests ({pct:5.1f}%) {bar}")
    
    print(f"\n🌐 HTTP Status Codes (All Sources):")
    for status in sorted(statuses.keys(), key=int):
        count = statuses[status]
        pct = 100 * count / total_logs
        bar = '█' * int(pct / 2)
        status_int = int(status)
        status_text = "✓" if status_int < 300 else ("➜" if status_int < 400 else "✗")
        print(f"  {status_text} {status}: {count:3d} ({pct:5.1f}%) {bar}")
    
    print(f"\n📊 HTTP Methods:")
    for method, count in methods.most_common(10):
        pct = 100 * count / total_logs
        print(f"  {method:6} | {count:4} requests ({pct:.1f}%)")
    
    # === SOURCE-SPECIFIC ANALYSIS ===
    print("\n" + "=" * 80)
    print(" SOURCE-SPECIFIC ANALYSIS")
    print("=" * 80)
    
    for log_type in ['nginx', 'gunicorn', 'uvicorn']:
        source_logs = [log for log in all_logs if log['source'] == log_type]
        if not source_logs:
            continue
        
        print(f"\n📍 {log_type.upper()}:")
        
        src_errors = sum(1 for log in source_logs if log['http_status'] >= 400)
        src_latencies = [log['latency_ms'] for log in source_logs if log['latency_ms'] > 0]
        
        print(f"  Total: {len(source_logs)} requests")
        print(f"  Success Rate: {100*(len(source_logs)-src_errors)/len(source_logs):.1f}%")
        
        if src_latencies:
            src_latencies.sort()
            p50 = src_latencies[int(len(src_latencies) * 0.5)]
            p99 = src_latencies[int(len(src_latencies) * 0.99)] if len(src_latencies) > 1 else src_latencies[0]
            print(f"  Latency: p50={p50:.1f}ms, p99={p99:.1f}ms, max={src_latencies[-1]:.1f}ms")
        
        if src_errors > 0:
            print(f"  Errors: {src_errors} ({100*src_errors/len(source_logs):.1f}%)")
    
    # === ERROR ANALYSIS ===
    print("\n" + "=" * 80)
    print(" ERROR ANALYSIS")
    print("=" * 80)
    
    error_logs = [log for log in all_logs if log['http_status'] >= 400]
    
    if error_logs:
        error_endpoints = Counter(log['request_uri'] for log in error_logs)
        error_statuses = Counter(log['http_status'] for log in error_logs)
        error_sources = Counter(log['source'] for log in error_logs)
        
        print(f"\n⚠️  Total Errors: {len(error_logs)} ({100*len(error_logs)/total_logs:.1f}%)")
        
        print(f"\n📍 Error Status Breakdown:")
        for status in sorted(error_statuses.keys(), key=int):
            count = error_statuses[status]
            pct = 100 * count / len(error_logs)
            print(f"  HTTP {status}: {count:3} errors ({pct:5.1f}%)")
        
        print(f"\n📂 Errors by Source:")
        for source in sorted(error_sources.keys()):
            count = error_sources[source]
            print(f"  {source.upper():12} | {count:3} errors")
        
        print(f"\n❌ Top Error Endpoints:")
        for endpoint, count in error_endpoints.most_common(10):
            endpoint_short = endpoint[:50] + "..." if len(endpoint) > 50 else endpoint
            print(f"  {endpoint_short}: {count} errors")
    
    # === PERFORMANCE ANALYSIS ===
    print("\n" + "=" * 80)
    print(" PERFORMANCE ANALYSIS")
    print("=" * 80)
    
    all_latencies = [log['latency_ms'] for log in all_logs if log['latency_ms'] > 0]
    
    if all_latencies:
        all_latencies.sort()
        p50 = all_latencies[int(len(all_latencies) * 0.50)]
        p95 = all_latencies[int(len(all_latencies) * 0.95)]
        p99 = all_latencies[int(len(all_latencies) * 0.99)]
        
        print(f"\n⏱️  Response Time Distribution:")
        print(f"  Minimum: {min(all_latencies):.2f}ms")
        print(f"  P50 (Median): {p50:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {p99:.2f}ms")
        print(f"  Maximum: {max(all_latencies):.2f}ms")
        print(f"  Average: {sum(all_latencies)/len(all_latencies):.2f}ms")
        
        # Find slow requests
        slow_threshold = max(1000, p99 * 2)  # 2x p99 or 1000ms minimum
        slow_requests = [log for log in all_logs if log['latency_ms'] > slow_threshold]
        
        if slow_requests:
            print(f"\n🐢 Slow Requests (> {slow_threshold:.0f}ms): {len(slow_requests)}")
            for log in sorted(slow_requests, key=lambda x: x['latency_ms'], reverse=True)[:5]:
                print(f"  {log['request_uri'][:50]:50} | {log['latency_ms']:7.1f}ms | {log['source']}")
    
    # === TIME-BASED ANALYSIS ===
    print("\n" + "=" * 80)
    print(" TIME-BASED ANALYSIS")
    print("=" * 80)
    
    timestamps = [log['timestamp'] for log in all_logs]
    if timestamps:
        min_time = min(timestamps)
        max_time = max(timestamps)
        duration = max_time - min_time
        
        print(f"\n⏱️  Time Range:")
        print(f"  Start: {min_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  End: {max_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Duration: {duration.total_seconds():.0f} seconds")
        
        if duration.total_seconds() > 0:
            rps = total_logs / (duration.total_seconds() / 60)
            print(f"  Throughput: {rps:.2f} requests/minute")
    
    # === EXPORT DATA ===
    print("\n" + "=" * 80)
    print(" EXPORTING ANALYTICS DATA")
    print("=" * 80)
    
    analytics_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'total_requests': total_logs,
        'success_rate': success_count / total_logs * 100 if total_logs > 0 else 0,
        'error_rate': error_count / total_logs * 100 if total_logs > 0 else 0,
        'avg_latency': avg_latency,
        'sources': {
            source: {
                'count': count,
                'percentage': count / total_logs * 100
            }
            for source, count in sources.items()
        },
        'status_distribution': {
            str(status): count for status, count in statuses.items()
        },
        'performance': {}
    }
    
    if all_latencies:
        analytics_data['performance'] = {
            'p50': float(p50),
            'p95': float(p95),
            'p99': float(p99),
            'min': float(min(all_latencies)),
            'max': float(max(all_latencies)),
            'avg': sum(all_latencies) / len(all_latencies)
        }
    
    # Save to JSON
    with open('analytics.json', 'w') as f:
        json.dump(analytics_data, f, indent=2)
    
    print(f"\n✓ Analytics exported to analytics.json")
    
    # === SUMMARY ===
    print("\n" + "=" * 80)
    print(" ✅ ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\n  📊 Files processed: {len([s for s in source_stats if source_stats[s]['count'] > 0])}")
    print(f"  📈 Total entries analyzed: {total_logs}")
    print(f"  ⚙️  Average latency: {avg_latency:.2f}ms")
    print(f"  ✓ Success rate: {100*success_count/total_logs:.1f}%")
    print(f"  ✗ Error rate: {100*error_count/total_logs:.1f}%\n")

if __name__ == '__main__':
    analyze_logs()
