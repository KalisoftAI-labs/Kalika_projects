#!/usr/bin/env python
"""
Ingest Nginx log file into RCA Dashboard
"""

import sys
import os
from datetime import datetime
from app.storage.database import get_session_local, get_engine
from app.models.orm import Base, LogEntry
import re

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

def ingest_log_file():
    """Ingest Nginx log file"""
    log_file = 'app/access_nginx_log'
    
    if not os.path.exists(log_file):
        print(f"Error: Log file not found: {log_file}")
        return
    
    print(f"Initializing database...")
    try:
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        print("✓ Database initialized")
    except Exception as e:
        print(f"✗ Failed to initialize database: {e}")
        return
    
    SessionLocal = get_session_local()
    session = SessionLocal()
    
    try:
        print(f"\nReading log file: {log_file}")
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        print(f"Parsing {len(lines)} log lines...")
        logs_created = 0
        errors = 0
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                parsed = parse_nginx_log_line(line)
                if not parsed:
                    errors += 1
                    continue
                
                log_entry = LogEntry(
                    source='nginx',
                    timestamp=parsed['timestamp'],
                    level='INFO',
                    message=f"{parsed['http_method']} {parsed['request_uri']} {parsed['http_status']}",
                    component='web-server',
                    request_id=None,
                    http_method=parsed['http_method'],
                    http_status=parsed['http_status'],
                    remote_addr=parsed['remote_addr'],
                    request_uri=parsed['request_uri'],
                    response_time=None,
                    bytes_sent=parsed['bytes_sent'],
                )
                
                session.add(log_entry)
                logs_created += 1
                
                if i % 50 == 0:
                    session.commit()
                    print(f"  ✓ Ingested {logs_created} logs...", end='\r')
            
            except Exception as e:
                errors += 1
                if errors < 5:
                    print(f"  ✗ Error parsing line {i}: {e}")
        
        session.commit()
        print(f"\n✓ Successfully ingested {logs_created} log entries ({errors} errors)")
        print(f"\nDashboard ready! Start the server with:")
        print(f"  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
        print(f"\nAccess dashboard at: http://localhost:8000")
        
    except Exception as e:
        print(f"✗ Error during ingestion: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == '__main__':
    ingest_log_file()
