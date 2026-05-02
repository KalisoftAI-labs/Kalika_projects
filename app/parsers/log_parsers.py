"""Log parsing strategies for different sources"""

import re
import json
from datetime import datetime, timezone
from typing import Dict, Any, Iterator, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ParsedLogLine:
    """Represents a parsed log line"""
    source: str
    timestamp: datetime
    level: str
    message: str
    components: Dict[str, Any]  # Additional parsed fields

class BaseLogParser:
    """Base class for log parsers"""
    
    def __init__(self, source_name: str):
        self.source = source_name
    
    def parse(self, line: str) -> Optional[ParsedLogLine]:
        """Parse a single log line"""
        raise NotImplementedError
    
    def parse_stream(self, file_obj, max_lines: Optional[int] = None) -> Iterator[ParsedLogLine]:
        """Parse log file as stream to avoid memory overhead"""
        line_count = 0
        for line in file_obj:
            if max_lines and line_count >= max_lines:
                break
            
            try:
                parsed = self.parse(line.rstrip('\n'))
                if parsed:
                    yield parsed
                    line_count += 1
            except Exception as e:
                logger.debug(f"Failed to parse line in {self.source}: {e}")
                continue

class NginxLogParser(BaseLogParser):
    """Parse Nginx access and error logs"""
    
    # Combined log format: 127.0.0.1 - - [timestamp] "METHOD /path HTTP/1.1" status bytes "referrer" "user-agent"
    NGINX_PATTERN = re.compile(
        r'(?P<remote_addr>[\d\.]+) - (?P<user>[\w\.\-]*) \[(?P<timestamp>[^\]]+)\] '
        r'"(?P<method>\w+) (?P<uri>[^"]*) HTTP/[\d\.]+" (?P<status>\d+) (?P<bytes>[\d-]+) '
        r'"(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"'
    )
    
    # Error log format: timestamp [level] pid#tid: *connid error, ...
    NGINX_ERROR_PATTERN = re.compile(
        r'(?P<timestamp>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) '
        r'\[(?P<level>\w+)\] (?P<pid>\d+)#(?P<tid>\d+): '
        r'\*(?P<connid>\d+) (?P<message>.*)'
    )
    
    def __init__(self):
        super().__init__("nginx")
    
    def parse(self, line: str) -> Optional[ParsedLogLine]:
        """Parse Nginx log line"""
        # Try access log format first
        match = self.NGINX_PATTERN.match(line)
        if match:
            groups = match.groupdict()
            
            ts = self._parse_nginx_timestamp(groups['timestamp'])
            
            return ParsedLogLine(
                source=self.source,
                timestamp=ts,
                level="INFO",
                message=f"{groups['method']} {groups['uri']} {groups['status']}",
                components={
                    'http_method': groups['method'],
                    'http_status': int(groups['status']),
                    'remote_addr': groups['remote_addr'],
                    'request_uri': groups['uri'],
                    'bytes_sent': int(groups['bytes']) if groups['bytes'] != '-' else None,
                    'referrer': groups['referrer'],
                    'user_agent': groups['user_agent'],
                }
            )
        
        # Try error log format
        match = self.NGINX_ERROR_PATTERN.match(line)
        if match:
            groups = match.groupdict()
            
            ts = self._parse_nginx_error_timestamp(groups['timestamp'])
            
            return ParsedLogLine(
                source=self.source,
                timestamp=ts,
                level=groups['level'],
                message=groups['message'],
                components={
                    'pid': groups['pid'],
                    'tid': groups['tid'],
                    'connid': groups['connid'],
                }
            )
        
        return None
    
    @staticmethod
    def _parse_nginx_timestamp(ts_str: str) -> datetime:
        """Parse Nginx log timestamp: 10/Oct/2024:13:55:36 +0000"""
        try:
            return datetime.strptime(ts_str.split()[0], '%d/%b/%Y:%H:%M:%S')
        except Exception:
            return datetime.now(timezone.utc)
    
    @staticmethod
    def _parse_nginx_error_timestamp(ts_str: str) -> datetime:
        """Parse Nginx error timestamp: 2024/10/10 13:55:36"""
        try:
            return datetime.strptime(ts_str, '%Y/%m/%d %H:%M:%S')
        except Exception:
            return datetime.now(timezone.utc)

class GunicornLogParser(BaseLogParser):
    """Parse Gunicorn logs"""
    
    # Gunicorn format: timestamp [pid] level module message
    GUNICORN_PATTERN = re.compile(
        r'\[(?P<timestamp>[\d\-\s:]+)\] \[(?P<pid>\d+)\] \[(?P<level>\w+)\] '
        r'(?P<message>.+)$'
    )
    
    # Request format: "GET /path HTTP/1.1" status latency
    REQUEST_PATTERN = re.compile(
        r'(?P<method>\w+) (?P<uri>\S+) HTTP/[\d\.]+["\']? (?P<status>\d+) (?P<latency>[\d\.]+)'
    )
    
    def __init__(self):
        super().__init__("gunicorn")
    
    def parse(self, line: str) -> Optional[ParsedLogLine]:
        """Parse Gunicorn log line"""
        match = self.GUNICORN_PATTERN.match(line)
        if not match:
            return None
        
        groups = match.groupdict()
        ts = self._parse_timestamp(groups['timestamp'])
        
        # Try to extract request details
        message = groups['message']
        req_match = self.REQUEST_PATTERN.search(message)
        
        components = {'pid': groups['pid']}
        
        if req_match:
            req_groups = req_match.groupdict()
            components['http_method'] = req_groups['method']
            components['http_status'] = int(req_groups['status'])
            components['request_uri'] = req_groups['uri']
            components['response_time'] = float(req_groups['latency'])
        
        return ParsedLogLine(
            source=self.source,
            timestamp=ts,
            level=groups['level'],
            message=message,
            components=components
        )
    
    @staticmethod
    def _parse_timestamp(ts_str: str) -> datetime:
        """Parse Gunicorn timestamp"""
        try:
            return datetime.fromisoformat(ts_str.replace(' ', 'T'))
        except Exception:
            return datetime.now(timezone.utc)

class UvicornLogParser(BaseLogParser):
    """Parse Uvicorn logs"""
    
    # Uvicorn format: timestamp level module_or_request
    UVICORN_PATTERN = re.compile(
        r'(?P<timestamp>[\d\-:\.\s]+) \| (?P<level>\w+) \| (?P<message>.*)'
    )
    
    def __init__(self):
        super().__init__("uvicorn")
    
    def parse(self, line: str) -> Optional[ParsedLogLine]:
        """Parse Uvicorn log line"""
        match = self.UVICORN_PATTERN.match(line)
        if not match:
            return None
        
        groups = match.groupdict()
        ts = self._parse_timestamp(groups['timestamp'])
        
        return ParsedLogLine(
            source=self.source,
            timestamp=ts,
            level=groups['level'],
            message=groups['message'],
            components={}
        )
    
    @staticmethod
    def _parse_timestamp(ts_str: str) -> datetime:
        """Parse Uvicorn timestamp"""
        try:
            # Remove milliseconds if present
            ts_clean = re.sub(r'\.\d+', '', ts_str).strip()
            return datetime.fromisoformat(ts_clean)
        except Exception:
            return datetime.now(timezone.utc)

class ApplicationLogParser(BaseLogParser):
    """Parse application logs (JSON or text format)"""
    
    def __init__(self):
        super().__init__("application")
    
    def parse(self, line: str) -> Optional[ParsedLogLine]:
        """Parse application log line"""
        # Try JSON format first
        try:
            data = json.loads(line)
            
            ts_str = data.get('timestamp', data.get('time', data.get('ts')))
            ts = self._parse_timestamp(ts_str) if ts_str else datetime.now(timezone.utc)
            
            return ParsedLogLine(
                source=self.source,
                timestamp=ts,
                level=data.get('level', 'INFO').upper(),
                message=data.get('message', data.get('msg', '')),
                components={
                    'request_id': data.get('request_id', data.get('trace_id')),
                    'user_id': data.get('user_id'),
                    'service_name': data.get('service', data.get('service_name')),
                    'exception_type': data.get('exception', data.get('error_type')),
                    'stack_trace': data.get('stack_trace', data.get('traceback')),
                }
            )
        except json.JSONDecodeError:
            pass
        
        # Try text format: [timestamp] [level] [component] message
        match = re.match(
            r'\[(?P<timestamp>[^\]]+)\] \[(?P<level>\w+)\] \[(?P<component>[^\]]+)\] (?P<message>.*)',
            line
        )
        
        if match:
            groups = match.groupdict()
            ts = self._parse_timestamp(groups['timestamp'])
            
            return ParsedLogLine(
                source=self.source,
                timestamp=ts,
                level=groups['level'].upper(),
                message=groups['message'],
                components={'component': groups['component']}
            )
        
        return None
    
    @staticmethod
    def _parse_timestamp(ts_str: str) -> datetime:
        """Parse application timestamp (flexible)"""
        try:
            # Try ISO format
            return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        except Exception:
            try:
                # Try common format
                return datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            except Exception:
                return datetime.now(timezone.utc)

class LogParserFactory:
    """Factory for creating appropriate log parsers"""
    
    _parsers = {
        'nginx': NginxLogParser,
        'gunicorn': GunicornLogParser,
        'uvicorn': UvicornLogParser,
        'application': ApplicationLogParser,
    }
    
    @classmethod
    def get_parser(cls, source: str) -> BaseLogParser:
        """Get parser for log source"""
        parser_class = cls._parsers.get(source.lower())
        if not parser_class:
            raise ValueError(f"Unknown log source: {source}")
        return parser_class()
