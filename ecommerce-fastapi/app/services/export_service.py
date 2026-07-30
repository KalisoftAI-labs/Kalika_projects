import csv
import io
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product

logger = logging.getLogger(__name__)

EXPORT_OPTIONS = {
    "Export Item Information": {"product_description": "item information"},
    "Export Item Price": {"price": "item price"},
    "Export Item Properties": {
        "lead_time": "Lead Time", "length": "Length", "material_type": "Material Type",
        "sys_num_images": "Sys Num Images", "sys_product_type": "Sys Product Type",
        "type": "Type", "unit_of_measure": "Unit of Measure", "unspsc": "UNSPSC",
    },
}


async def export_products_to_csv(db: AsyncSession, options: list[str] | None = None) -> str:
    result = await db.execute(select(Product).order_by(Product.item_id))
    products = result.scalars().all()

    columns = {
        "item_id": "item id",
        "product_title": "item name",
        "item_code": "item code",
    }

    if options:
        for opt in options:
            if opt in EXPORT_OPTIONS:
                columns.update(EXPORT_OPTIONS[opt])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns.values())

    for p in products:
        row = []
        for col in columns:
            val = getattr(p, col, None)
            if isinstance(val, datetime):
                val = val.isoformat()
            elif val is None:
                val = ""
            row.append(str(val))
        writer.writerow(row)

    return output.getvalue()
