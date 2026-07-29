from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from app.database import Base


class PunchOutOrder(Base):
    __tablename__ = "punchout_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("accounts_customuser.id"), nullable=True)
    session_token = Column(String(64), nullable=True, index=True)
    total_cost = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), server_default=text("'INR'"))
    cxml_payload = Column(Text, nullable=False)
    buyer_cookie = Column(String(255), nullable=True)
    return_url = Column(Text, nullable=True)
    status = Column(String(50), server_default=text("'completed'"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    items = relationship("PunchOutOrderItem", back_populates="order", lazy="joined")


class PunchOutOrderItem(Base):
    __tablename__ = "punchout_order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("punchout_orders.id"), nullable=False)
    product_title = Column(String(255), nullable=False)
    item_code = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)
    unit_of_measure = Column(String(20), server_default=text("'EA'"))
    unspsc = Column(String(20), nullable=True)

    order = relationship("PunchOutOrder", back_populates="items")
