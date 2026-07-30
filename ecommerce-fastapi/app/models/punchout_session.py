from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, text
from app.database import Base


class PunchOutSession(Base):
    __tablename__ = "punchout_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("accounts_customuser.id"), nullable=True)
    from_identity = Column(String(255), nullable=False)
    return_url = Column(Text, nullable=False)
    buyer_cookie = Column(String(255), nullable=False)
    shared_secret = Column(String(255), nullable=True)
    is_active = Column(Boolean, server_default=text("TRUE"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    expires_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<PunchOutSession(id={self.session_id}, buyer={self.buyer_cookie})>"
