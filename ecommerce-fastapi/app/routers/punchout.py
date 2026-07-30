from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import Response, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import punchout_service

router = APIRouter(prefix="/punchout", tags=["punchout"])


@router.post("/setup")
async def punchout_setup(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    content_type = request.headers.get("content-type", "").lower()
    raw_body = None
    form_body = None

    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        form_body = form.get("cxml-urlencoded")
    else:
        raw_body = (await request.body()).decode("utf-8")

    result = await punchout_service.handle_setup_request(db, raw_body, form_body)

    if "error" in result:
        raise HTTPException(status_code=result["status"], detail=result["error"])

    if result["mode"] == "edit":
        return JSONResponse(content={
            "mode": "edit",
            "session_id": result["session_id"],
            "items_added": result["items_added"],
            "return_url": result["return_url"],
            "buyer_cookie": result["buyer_cookie"],
            "user_id": result["user_id"],
        })

    return Response(
        content=result["cxml_response"],
        media_type="text/xml; charset=utf-8",
    )


@router.get("/session/{session_id}")
async def get_punchout_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    session = await punchout_service.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return {
        "session_id": session.session_id,
        "from_identity": session.from_identity,
        "return_url": session.return_url,
        "buyer_cookie": session.buyer_cookie,
    }
