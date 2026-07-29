from sqlalchemy import Column, Integer, BigInteger, String, Text, Numeric, DateTime, text
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    item_id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(Text, nullable=True)
    main_category = Column(String(100), nullable=False)
    sub_categories = Column(String(100), nullable=True)
    item_code = Column(String(50), unique=True, nullable=False)
    product_title = Column(String(255), nullable=False)
    product_description = Column(Text, nullable=True)
    upc = Column(Text, nullable=True)
    brand = Column(Text, nullable=True)
    department = Column(Text, nullable=True)
    type = Column(Text, nullable=True)
    tag = Column(Text, nullable=True)
    list_price = Column(Numeric(10, 2), nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    inventory = Column(BigInteger, nullable=True)
    min_order_qty = Column(BigInteger, nullable=True)
    available = Column(Text, nullable=True)
    large_image = Column(Text, nullable=True)
    additional_images = Column(Text, nullable=True)
    status = Column(String(50), server_default=text("'New'"))
    last_modified = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    lead_time = Column(String(255), nullable=True)
    length = Column(String(255), nullable=True)
    material_type = Column(String(255), nullable=True)
    sys_discount_group = Column(String(255), nullable=True)
    sys_num_images = Column(String(255), nullable=True)
    sys_product_type = Column(String(255), nullable=True)
    unit_of_measure = Column(String(255), nullable=True)
    unspsc = Column(String(20), nullable=True)

    def __repr__(self):
        return f"<Product(item_id={self.item_id}, code={self.item_code})>"
