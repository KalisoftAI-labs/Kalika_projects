#!/usr/bin/env python
"""
Ingest Nginx log file into RCA Dashboard (Demo Mode - No Database Required)
"""

import sys
import os
from datetime import datetime
from collections import defaultdict, Counter
import re
import json

# Log format: 54.39.210.224 - - [12/Apr/2026:00:00:29 +0000] "GET /robots.txt HTTP/2.0" 404 148 "-" "Mozilla/..."

def parse_nginx_log_line(line):
    """Parse Nginx combined log format"""
    pattern = r'(\S+) - - \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\d+) "([^"]*)" "([^"]*)"'
    match = re.match(pattern, line)
    if not match:
        return None
    
    ip, timestamp_str, method, uri, protocol, status, bytes_sent, referer, user_agent = match.groups()
    
    # Parse timestamp: 12/Apr/2026:00:00:29 +0000
    try:
        dt = datetime.strptime(timestamp_str.split(' ')[0], '%d/%b/%Y:%H:%M:%S')
    except:
        return None
    
    return {
        'remote_addr': ip,
        'timestamp': dt,
        'http_method': method,
        'request_uri': uri,
        'protocol': protocol,
        'http_status': int(status),
        'bytes_sent': int(bytes_sent),
        'referer': referer,
        'user_agent': user_agent,
    }

def analyze_logs():
    """Analyze Nginx log file and generate dashboard demo data"""
    log_file = 'app/access_nginx_log'
    
    if not os.path.exists(log_file):
        print(f"Error: Log file not found: {log_file}", flush=True)
        return
    
    print(f"\n📊 RCA Dashboard - Log Analysis Demo\n", flush=True)
    print(f"Reading log file: {log_file}", flush=True)
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    logs = []
    errors = 0
    
    print(f"Parsing {len(lines)} log lines...")
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        try:
            parsed = parse_nginx_log_line(line)
            if parsed:
                logs.append(parsed)
        except:
            errors += 1
    
    print(f"✓ Successfully parsed {len(logs)} log entries ({errors} errors)\n", flush=True)
    
    # === METRICS ANALYSIS ===
    print("=" * 70, flush=True)
    print(" METRICS ANALYSIS", flush=True)
    print("=" * 70, flush=True)
    
    total_requests = len(logs)
    total_bytes = sum(log['bytes_sent'] for log in logs)
    
    statuses = Counter(log['http_status'] for log in logs)
    methods = Counter(log['http_method'] for log in logs)
    endpoints = Counter(log['request_uri'] for log in logs)
    ips = Counter(log['remote_addr'] for log in logs)
    
    error_count = sum(count for status, count in statuses.items() if status >= 400)
    success_count = sum(count for status, count in statuses.items() if status < 400)
    
    print(f"\n📈 Request Summary:")
    print(f"  Total Requests: {total_requests}")
    print(f"  Total Bytes: {total_bytes:,} bytes ({total_bytes/1024/1024:.2f} MB)")
    print(f"  Success Rate: {success_count}/{total_requests} ({100*success_count/total_requests:.1f}%)")
    print(f"  Error Rate: {error_count}/{total_requests} ({100*error_count/total_requests:.1f}%)")
    
    print(f"\n🌐 HTTP Status Codes:")
    for status in sorted(statuses.keys()):
        count = statuses[status]
        pct = 100 * count / total_requests
        bar = '█' * int(pct / 2)
        print(f"  {status}: {count:3d} ({pct:5.1f}%) {bar}")
    
    print(f"\n📊 HTTP Methods:")
    for method, count in methods.most_common():
        print(f"  {method}: {count} requests")
    
    print(f"\n🔝 Top 10 Endpoints:")
    for endpoint, count in endpoints.most_common(10):
        pct = 100 * count / total_requests
        endpoint_short = endpoint[:50] + "..." if len(endpoint) > 50 else endpoint
        print(f"  {endpoint_short}: {count} requests ({pct:.1f}%)")
    
    print(f"\n👥 Top 10 IP Addresses:")
    for ip, count in ips.most_common(10):
        print(f"  {ip}: {count} requests")
    
    # === ERROR ANALYSIS ===
    print("\n" + "=" * 70)
    print(" ERROR ANALYSIS")
    print("=" * 70)
    
    error_logs = [log for log in logs if log['http_status'] >= 400]
    
    if error_logs:
        error_endpoints = Counter(log['request_uri'] for log in error_logs)
        error_statuses = Counter(log['http_status'] for log in error_logs)
        
        print(f"\n⚠️  Total Errors: {len(error_logs)} ({100*len(error_logs)/total_requests:.1f}%)")
        
        print(f"\n📍 Error Status Breakdown:")
        for status in sorted(error_statuses.keys()):
            count = error_statuses[status]
            pct = 100 * count / len(error_logs)
            print(f"  HTTP {status}: {count} errors ({pct:.1f}%)")
        
        print(f"\n❌ Top Error Endpoints:")
        for endpoint, count in error_endpoints.most_common(10):
            endpoint_short = endpoint[:50] + "..." if len(endpoint) > 50 else endpoint
            print(f"  {endpoint_short}: {count} errors")
    
    # === TIME-BASED ANALYSIS ===
    print("\n" + "=" * 70)
    print(" TIME-BASED ANALYSIS")
    print("=" * 70)
    
    timestamps = [log['timestamp'] for log in logs]
    if timestamps:
        min_time = min(timestamps)
        max_time = max(timestamps)
        duration = max_time - min_time
        
        print(f"\n⏱️  Time Range:")
        print(f"  Start: {min_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  End: {max_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Duration: {duration.total_seconds():.0f} seconds ({duration.total_seconds()/60:.1f} minutes)")
        
        if duration.total_seconds() > 0:
            rps = total_requests / (duration.total_seconds() / 60)
            print(f"  Requests/Minute: {rps:.1f}")
    
    # === RCA INSIGHTS ===
    print("\n" + "=" * 70)
    print(" 🔍 ROOT CAUSE ANALYSIS INSIGHTS")
    print("=" * 70)
    
    if error_count > 0:
        error_rate = 100 * error_count / total_requests
        if error_rate > 5:
            print(f"\n⚠️  HIGH ERROR RATE DETECTED (>{error_rate:.1f}%)")
            
            # Check for specific error patterns
            not_found = statuses.get(404, 0)
            bad_req = statuses.get(400, 0)
            server_err = sum(count for status, count in statuses.items() if status >= 500)
            
            if not_found > 0:
                print(f"  • 404 Not Found: {not_found} ({100*not_found/error_count:.0f}% of errors)")
                print(f"    → Likely cause: Non-existent resources or deleted endpoints")
            if bad_req > 0:
                print(f"  • 400 Bad Request: {bad_req} ({100*bad_req/error_count:.0f}% of errors)")
                print(f"    → Likely cause: Malformed requests or protocol errors")
            if server_err > 0:
                print(f"  • 5xx Server Errors: {server_err} ({100*server_err/error_count:.0f}% of errors)")
                print(f"    → Likely cause: Backend application issues")
    
    print(f"\n" + "=" * 70)
    print(f" ✅ Analysis Complete\n")
    
    print(f"📌 NEXT STEPS:")
    print(f"  1. Set up PostgreSQL database (for persistent logging)")
    print(f"  2. Run: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
    print(f"  3. Visit: http://localhost:8000")
    print(f"  4. View real-time metrics and RCA insights on the dashboard\n")

if __name__ == '__main__':
    analyze_logs()
