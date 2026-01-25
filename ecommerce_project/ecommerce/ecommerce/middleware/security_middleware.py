# ecommerce/middleware/security_middleware.py
from django.http import HttpResponseForbidden
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

# Known malicious IPs from log analysis
BLOCKED_IPS = {
    '216.180.246.246',
    '216.180.246.248',
    '216.180.246.201',
    '185.177.72.38',
    '4.190.210.95',
    '20.192.24.172',
    '20.89.17.172',
    '167.172.95.178',
    '141.98.11.98',     # WordPress brute force scanner
    '34.72.138.173',    # WordPress enumeration (Google Cloud abuse)
    '87.121.84.125',    # Bitrix CMS exploit attempt
    '168.76.20.229',    # Suspicious bad requests
}

# Suspicious paths that trigger automatic blocking
SUSPICIOUS_PATHS = [
    '.env', '.git', 'phpinfo.php', 'info.php', 'config.php',
    'adminer.php', 'sql.conf', 'db.conf', '.ini', '.bak',
    'login.asp', 'ultra.php', 'function.php', '/root/.aws'
]


class SecurityMiddleware:
    """
    Middleware to block known malicious IPs and suspicious requests.
    Implements rate limiting and path-based blocking.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Get client IP (handle proxy headers)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Block known malicious IPs
        if ip in BLOCKED_IPS:
            logger.warning(f"Blocked request from known malicious IP: {ip} to {request.path}")
            return HttpResponseForbidden("Access Denied")
        
        # Check for suspicious paths
        path_lower = request.path.lower()
        if any(suspicious in path_lower for suspicious in SUSPICIOUS_PATHS):
            logger.warning(f"Blocked suspicious path access from {ip}: {request.path}")
            
            # Add to temporary block list (5 minutes)
            cache_key = f"suspicious_ip_{ip}"
            attempts = cache.get(cache_key, 0)
            cache.set(cache_key, attempts + 1, 300)  # 5 minutes
            
            # Block IP if more than 3 suspicious attempts
            if attempts >= 3:
                BLOCKED_IPS.add(ip)
                logger.error(f"IP {ip} permanently blocked after {attempts + 1} suspicious requests")
            
            return HttpResponseForbidden("Access Denied")
        
        # Check for path traversal attempts (double slashes, etc.)
        if '//' in request.path or '..' in request.path:
            logger.warning(f"Blocked path traversal attempt from {ip}: {request.path}")
            return HttpResponseForbidden("Invalid Request")
        
        response = self.get_response(request)
        return response


class RateLimitMiddleware:
    """
    Simple rate limiting middleware to prevent brute force attacks.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Get client IP
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Rate limit admin and authentication endpoints
        if request.path.startswith(('/admin/', '/accounts/login/', '/punchout/')):
            cache_key = f"rate_limit_{ip}_{request.path}"
            requests = cache.get(cache_key, 0)
            
            # Allow 20 requests per minute to these endpoints
            if requests > 20:
                logger.warning(f"Rate limit exceeded for {ip} on {request.path}")
                return HttpResponseForbidden("Rate limit exceeded. Please try again later.")
            
            cache.set(cache_key, requests + 1, 60)  # 1 minute window
        
        response = self.get_response(request)
        return response
