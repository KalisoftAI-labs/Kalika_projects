"""Error code testing endpoints"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

class ErrorResponse(BaseModel):
    status_code: int
    message: str
    detail: str

@router.get("/error/400")
async def error_400():
    """Return 400 Bad Request"""
    raise HTTPException(
        status_code=400,
        detail="Bad Request: Invalid request parameters"
    )

@router.get("/error/401")
async def error_401():
    """Return 401 Unauthorized"""
    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Authentication credentials are missing or invalid"
    )

@router.get("/error/403")
async def error_403():
    """Return 403 Forbidden"""
    raise HTTPException(
        status_code=403,
        detail="Forbidden: You do not have permission to access this resource"
    )

@router.get("/error/404")
async def error_404():
    """Return 404 Not Found"""
    raise HTTPException(
        status_code=404,
        detail="Not Found: The requested resource does not exist"
    )

@router.get("/error/422")
async def error_422():
    """Return 422 Unprocessable Entity"""
    raise HTTPException(
        status_code=422,
        detail="Unprocessable Entity: The request was well-formed but contains semantic errors"
    )

@router.get("/error/429")
async def error_429():
    """Return 429 Too Many Requests"""
    raise HTTPException(
        status_code=429,
        detail="Too Many Requests: Rate limit exceeded"
    )

@router.get("/error/500")
async def error_500():
    """Return 500 Internal Server Error"""
    raise HTTPException(
        status_code=500,
        detail="Internal Server Error: An unexpected error occurred"
    )

@router.get("/error/502")
async def error_502():
    """Return 502 Bad Gateway"""
    raise HTTPException(
        status_code=502,
        detail="Bad Gateway: Invalid response from upstream server"
    )

@router.get("/error/503")
async def error_503():
    """Return 503 Service Unavailable"""
    raise HTTPException(
        status_code=503,
        detail="Service Unavailable: Server is temporarily down"
    )

@router.get("/error/{status_code}")
async def error_generic(status_code: int):
    """Return any HTTP error status code"""
    error_messages = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        406: "Not Acceptable",
        408: "Request Timeout",
        409: "Conflict",
        410: "Gone",
        411: "Length Required",
        412: "Precondition Failed",
        413: "Payload Too Large",
        414: "URI Too Long",
        415: "Unsupported Media Type",
        418: "I'm a teapot",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        431: "Request Header Fields Too Large",
        500: "Internal Server Error",
        501: "Not Implemented",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
        505: "HTTP Version Not Supported",
    }
    
    message = error_messages.get(status_code, f"HTTP Error {status_code}")
    
    if 200 <= status_code < 400:
        raise HTTPException(
            status_code=400,
            detail="Error endpoint only returns error status codes (4xx, 5xx)"
        )
    
    raise HTTPException(
        status_code=status_code,
        detail=f"{message}: Test error response"
    )
