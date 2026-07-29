from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from app.database import Base


class User(Base):
    __tablename__ = "accounts_customuser"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(150), unique=True, nullable=False)
    email = Column(String(254), unique=True, nullable=False)
    password = Column(String(128), nullable=False)
    role = Column(String(50), server_default=text("'User'"))
    buyer_identifier = Column(String(255), unique=True, nullable=True)
    is_active = Column(Boolean, server_default=text("TRUE"))
    is_staff = Column(Boolean, server_default=text("FALSE"))
    is_superuser = Column(Boolean, server_default=text("FALSE"))
    date_joined = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    last_login = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"
