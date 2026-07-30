import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

BLOCKED_IPS = frozenset({
    "216.180.246.246", "216.180.246.248", "216.180.246.201",
    "185.177.72.38", "4.190.210.95", "20.192.24.172",
    "20.89.17.172", "167.172.95.178", "141.98.11.98",
    "34.72.138.173", "87.121.84.125", "168.76.20.229",
})

_auto_blocked: set[str] = set()

SUSPICIOUS_PATHS = [
    ".env", ".git", "phpinfo.php", "info.php", "config.php",
    "adminer.php", "sql.conf", "db.conf", ".ini", ".bak",
    "login.asp", "ultra.php", "function.php", "/root/.aws",
]

RATE_LIMIT_PATHS = ("/api/auth/", "/api/admin/", "/api/punchout/")
RATE_LIMIT_MAX = 20
RATE_LIMIT_WINDOW = 60

_suspicious_attempts: dict[str, list[float]] = {}
_rate_limit_store: dict[str, list[float]] = {}


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = _get_client_ip(request)

        if ip in BLOCKED_IPS or ip in _auto_blocked:
            logger.warning(f"Blocked known malicious IP: {ip} → {request.url.path}")
            return Response("Access Denied", status_code=403)

        path_lower = request.url.path.lower()
        for suspicious in SUSPICIOUS_PATHS:
            if suspicious in path_lower:
                logger.warning(f"Suspicious path from {ip}: {request.url.path}")
                now = time.time()
                attempts = _suspicious_attempts.setdefault(ip, [])
                attempts.append(now)
                attempts[:] = [t for t in attempts if t > now - 300]
                if len(attempts) >= 3:
                    _auto_blocked.add(ip)
                    logger.error(f"IP {ip} auto-blocked after {len(attempts)} suspicious requests")
                return Response("Access Denied", status_code=403)

        if "//" in request.url.path or ".." in request.url.path:
            logger.warning(f"Path traversal from {ip}: {request.url.path}")
            return Response("Invalid Request", status_code=400)

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = _get_client_ip(request)

        if request.url.path.startswith(RATE_LIMIT_PATHS):
            now = time.time()
            key = f"{ip}:{request.url.path}"
            timestamps = _rate_limit_store.setdefault(key, [])
            timestamps.append(now)
            timestamps[:] = [t for t in timestamps if t > now - RATE_LIMIT_WINDOW]

            if len(timestamps) > RATE_LIMIT_MAX:
                logger.warning(f"Rate limit exceeded for {ip} on {request.url.path}")
                return Response("Rate limit exceeded. Try again later.", status_code=429)

        return await call_next(request)
