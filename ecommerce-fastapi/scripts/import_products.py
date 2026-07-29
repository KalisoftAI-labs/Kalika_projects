"""
One-time import: copy products from old DB to new DB, or create sample data.
Run: python -m scripts.import_products
"""

import asyncio
from sqlalchemy import text
from app.database import engine, async_session
from app.models.product import Product


SAMPLE_PRODUCTS = [
    {"main_category": "Safety", "sub_categories": "Gloves", "item_code": "SAF-GLOVE-001", "product_title": "Nitrile Safety Gloves", "product_description": "Blue nitrile gloves, box of 100.", "price": 249.99, "unit_of_measure": "BX", "unspsc": "46182000"},
    {"main_category": "Safety", "sub_categories": "Gloves", "item_code": "SAF-GLOVE-002", "product_title": "Cut Resistant Gloves", "product_description": "Level 5 cut resistant gloves.", "price": 599.99, "unit_of_measure": "PR", "unspsc": "46182000"},
    {"main_category": "Safety", "sub_categories": "Glasses", "item_code": "SAF-EYE-001", "product_title": "Safety Glasses, Clear", "product_description": "Impact resistant polycarbonate lenses.", "price": 149.99, "unit_of_measure": "EA", "unspsc": "46182000"},
    {"main_category": "Janitorial", "sub_categories": "Cleaning Supplies", "item_code": "JAN-CLN-001", "product_title": "All Purpose Cleaner 5L", "product_description": "Concentrated multi-surface cleaner.", "price": 399.99, "unit_of_measure": "EA", "unspsc": "47131800"},
    {"main_category": "Janitorial", "sub_categories": "Paper Products", "item_code": "JAN-PAP-001", "product_title": "Toilet Tissue Rolls, 12 Pack", "product_description": "Premium 2-ply, 12 rolls.", "price": 499.99, "unit_of_measure": "PK", "unspsc": "47131500"},
    {"main_category": "Hand & Power Tools", "sub_categories": "Power Drills", "item_code": "TLS-DRL-001", "product_title": "Cordless Drill 18V", "product_description": "18V lithium-ion cordless drill with 2 batteries.", "price": 4999.99, "unit_of_measure": "EA", "unspsc": "27112700"},
    {"main_category": "Hand & Power Tools", "sub_categories": "Hand Tools", "item_code": "TLS-WRN-001", "product_title": "Adjustable Wrench 12 inch", "product_description": "Chrome vanadium steel.", "price": 899.99, "unit_of_measure": "EA", "unspsc": "27111700"},
    {"main_category": "Packaging", "sub_categories": "Tapes", "item_code": "PKG-TAP-001", "product_title": "Packing Tape 48mm x 100m", "product_description": "Clear acrylic adhesive tape.", "price": 79.99, "unit_of_measure": "RL", "unspsc": "24131500"},
    {"main_category": "Packaging", "sub_categories": "Bubble Wrap", "item_code": "PKG-BUB-001", "product_title": "Bubble Wrap Roll 1.5m x 50m", "product_description": "Small bubble, 1.5m width.", "price": 1299.99, "unit_of_measure": "RL", "unspsc": "24131500"},
    {"main_category": "Abrasives", "sub_categories": "Sandpaper", "item_code": "ABR-SND-001", "product_title": "Sandpaper Sheets 100 Grit", "product_description": "Pack of 50, 230mm x 280mm.", "price": 199.99, "unit_of_measure": "PK", "unspsc": "23171500"},
]


async def seed_data():
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS products CASCADE"))
        await conn.execute(text("""
            CREATE TABLE products (
                item_id SERIAL PRIMARY KEY,
                action TEXT, main_category TEXT NOT NULL, sub_categories TEXT,
                item_code VARCHAR(50) UNIQUE NOT NULL, product_title TEXT NOT NULL,
                product_description TEXT, upc TEXT, brand TEXT, department TEXT,
                type TEXT, tag TEXT, list_price DECIMAL(10,2), price DECIMAL(10,2) NOT NULL,
                inventory BIGINT, min_order_qty BIGINT, available TEXT,
                large_image TEXT, additional_images TEXT, status VARCHAR(50) DEFAULT 'New',
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                lead_time VARCHAR(255), length VARCHAR(255), material_type VARCHAR(255),
                sys_discount_group VARCHAR(255), sys_num_images VARCHAR(255),
                sys_product_type VARCHAR(255), unit_of_measure VARCHAR(255), unspsc VARCHAR(20)
            )
        """))

    async with async_session() as db:
        for data in SAMPLE_PRODUCTS:
            db.add(Product(**data))
        await db.commit()

    print(f"Seeded {len(SAMPLE_PRODUCTS)} products.")


if __name__ == "__main__":
    asyncio.run(seed_data())
