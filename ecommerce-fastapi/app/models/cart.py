from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, text
from sqlalchemy.orm import relationship
from app.database import Base


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("accounts_customuser.id"), nullable=True, index=True)
    session_token = Column(String(64), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.item_id"), nullable=False)
    quantity = Column(Integer, nullable=False, server_default=text("1"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    product = relationship("Product", lazy="joined")

    def __repr__(self):
        return f"<CartItem(id={self.id}, product_id={self.product_id}, qty={self.quantity})>"
