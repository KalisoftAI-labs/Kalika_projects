from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from fastapi_app.db import get_db_connection, get_user_count, get_product_count, get_total_sales, get_pending_orders_count, get_recent_orders, get_product_category_counts
from passlib.context import CryptContext
import logging
import uvicorn
import csv
import io
import os
import time
from ecommerce.settings import SECRET_KEY
import threading
import pandas as pd
import uuid # Import uuid for unique filenames
import json # Import json for handling item_properties
from datetime import datetime # Import datetime for date formatting
import boto3 # For S3 upload
from botocore.exceptions import ClientError

# Pydantic for request body validation
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# Define a Pydantic model for the /api/product-details payload
class ItemIDPayload(BaseModel):
    item_id: Optional[int] = None
    item_code: Optional[str] = None

class ExportRequest(BaseModel):
    export_options: List[str]

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)  # SECRET_KEY is already imported from settings

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = 'us-east-1'
AWS_S3_BUCKET_NAME = 'kalika-ecom'

# Initialize S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

def upload_image_to_s3(file_content: bytes, filename: str, content_type: str = None) -> str:
    """
    Uploads an image to S3 and returns the S3 key path.
    Supports: jpg, jpeg, png, gif, webp, bmp, svg, ico
    Returns the path in format: /kalika-images/filename
    """
    try:
        # Get file extension
        file_extension = os.path.splitext(filename)[1].lower()
        
        # Map file extensions to content types
        content_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon'
        }
        
        # Auto-detect content type if not provided
        if not content_type:
            content_type = content_type_map.get(file_extension, 'image/jpeg')
            logger.info(f"Auto-detected content type: {content_type} for {file_extension}")
        
        # Validate file extension
        if file_extension not in content_type_map:
            logger.warning(f"Unsupported image format: {file_extension}, treating as JPEG")
        
        # Generate unique filename preserving extension
        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        s3_key = f"kalika-images/{unique_filename}"
        
        # Upload to S3
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type
        )
        
        logger.info(f"Successfully uploaded {content_type} image to S3: {s3_key}")
        return f"/{s3_key}"  # Return path with leading slash for consistency
    except ClientError as e:
        logger.error(f"Failed to upload image to S3: {e}")
        return None

# Define the directory for static files, including uploaded images (local fallback)
STATIC_DIR = "fastapi_app/static"
UPLOAD_DIR = os.path.join(STATIC_DIR, "images", "products")

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

app.mount("/admin-static", StaticFiles(directory=STATIC_DIR), name="admin-static")

templates = Jinja2Templates(directory="fastapi_app/templates")
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# In-memory store for export jobs
export_jobs = []
job_counter = 0
# --- Helper functions for database operations (from your existing app.py) ---

def update_product_price_in_db(item_id: int, new_price: float):
    """Updates the price of a product in the database. Returns True if a row was updated."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed in update_product_price_in_db")
            return False
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE products SET price = %s WHERE item_id = %s",
            (new_price, item_id)
        )
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Successfully updated price for item_id {item_id} to {new_price}.")
            return True
        else:
            logger.warning(f"No product found with item_id {item_id} to update price.")
            return False
    except Exception as e:
        logger.error(f"Error updating product price for item_id {item_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def update_product_description_in_db(item_id: int, new_description: str):
    """Updates the description of a product in the database. Returns True if a row was updated."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed in update_product_description_in_db")
            return False
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE products SET product_description = %s WHERE item_id = %s",
            (new_description, item_id)
        )
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Successfully updated description for item_id {item_id}.")
            return True
        else:
            logger.warning(f"No product found with item_id {item_id} to update description.")
            return False
    except Exception as e:
        logger.error(f"Error updating product description for item_id {item_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
def add_product_to_db(product_data: dict):
    """
    Adds a new product to the database.
    Handles auto-incrementing item_id by not including it in the insert statement.
    """
    conn = None
    cursor = None

    # Clean keys
    data = {k.lower(): v for k, v in product_data.items()}

    # Check for required fields (only item_code now, as item_id is auto-generated)
    # REMOVE THE 'item_id' CHECK HERE
    if not data.get('item_code'):
        logger.error("Cannot add product: 'item_code' is required.")
        return False

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Master list of all possible insertable columns
        # REMOVE 'item_id' from this list for 'add' operations
        all_insertable_columns = [
            'action', 'main_category', 'sub_categories', 'item_code',
            'product_title', 'product_description', 'upc', 'brand', 'department',
            'type', 'tag', 'list_price', 'price', 'inventory', 'min_order_qty',
            'available', 'large_image', 'additional_images', 'status',
            'lead_time', 'length', 'material_type', 'sys_discount_group',
            'sys_num_images', 'sys_product_type', 'unit_of_measure', 'unspsc'
        ]

        # Filter the data to only include columns that exist in our master list and have a value
        # Ensure 'item_id' is NOT in the filtered_data for insertion
        filtered_data = {key: data.get(key) for key in all_insertable_columns if data.get(key) is not None and str(data.get(key)).strip() != ''}

        columns_to_insert = list(filtered_data.keys())
        placeholders = ', '.join(['%s'] * len(columns_to_insert))
        data_values = list(filtered_data.values())

        # Use RETURNING item_id to get the auto-generated ID if you need it
        insert_query = f"INSERT INTO products ({', '.join(columns_to_insert)}) VALUES ({placeholders}) RETURNING item_id;"

        cursor.execute(insert_query, tuple(data_values))
        new_item_id = cursor.fetchone()[0] # Fetch the auto-generated item_id
        conn.commit()
        logger.info(f"Product '{data.get('product_title')}' successfully added with auto-generated item_id {new_item_id}.")
        return True
    except Exception as e:
        logger.error(f"Error adding product {data.get('product_title')}: {e}", exc_info=True)
        if conn: conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def update_product_in_db(item_id: int, product_data: dict):
    """
    Updates an existing product in the database based on its item_id.
    This version dynamically builds the update query from the provided data.
    """
    conn = None
    cursor = None
    
    data = {k.lower().replace(' ', '_'): v for k, v in product_data.items()}
    
    # Remove keys that should not be updated or identify the row
    data.pop('item_id', None)
    # data.pop('item_code', None) # We keep item_code to allow it to be updated
    data.pop('action', None)
    
    # This mapping helps if the form uses different names than the database
    # CORRECTED: Added 'itemcode' to map to 'item_code'
    field_to_column_map = {
        'productname': 'product_title',
        'productcategory': 'main_category',
        'productsubcategory': 'sub_categories',
        'productdescription': 'product_description',
        'listprice': 'list_price',
        'minorderqty': 'min_order_qty',
        'leadtime': 'lead_time',
        'materialtype': 'material_type',
        'sysnumimages': 'sys_num_images',
        'sysproducttype': 'sys_product_type',
        'unitofmeasure': 'unit_of_measure',
        'itemcode': 'item_code' , # This is the fix
         'barcode': 'upc'
    }
    mapped_data = {}
    for key, value in data.items():
        db_key = field_to_column_map.get(key, key)
        mapped_data[db_key] = value

    if not mapped_data:
        logger.warning(f"No valid data provided to update for item_id {item_id}.")
        return False

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        set_clauses = [f"{key} = %s" for key in mapped_data.keys()]
        values = list(mapped_data.values())
        values.append(item_id)

        update_query = f"UPDATE products SET {', '.join(set_clauses)}, last_modified = CURRENT_TIMESTAMP WHERE item_id = %s"
        cursor.execute(update_query, tuple(values))
        conn.commit()
        # Check if any row was actually changed
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error updating product with item_id {item_id}: {e}", exc_info=True)
        if conn: conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def parse_item_properties(properties_string: str) -> dict:
    """
    Parses the 'Item Properties' string into a dictionary of key-value pairs.
    Keys are cleaned to match database column names (lowercase, no spaces).
    """
    properties_dict = {}
    if not properties_string or not isinstance(properties_string, str):
        return properties_dict
        
    parts = properties_string.split(',')
    for part in parts:
        if ' - ' in part:
            key, value = part.split(' - ', 1)
            clean_key = key.strip().lower().replace(' ', '_')
            properties_dict[clean_key] = value.strip()
    return properties_dict

@app.post("/bulk-modify-properties")
async def bulk_modify_properties_post(
    request: Request,
    file: UploadFile = File(...)
):
    """
    Handles CSV upload to specifically update item properties based on item_code.
    """
    if 'user' not in request.session:
        return JSONResponse(status_code=401, content={"message": "Please log in."})

    if not file.filename.endswith('.csv'):
        return JSONResponse(status_code=400, content={"message": "Please upload a valid CSV file."})

    success_count = 0
    error_count = 0
    error_messages = []
    
    conn = None
    cursor = None

    try:
        contents = await file.read()
        csv_data_str = contents.decode('utf-8-sig')
        csv_data = io.StringIO(csv_data_str)
        reader = csv.DictReader(csv_data)

        conn = get_db_connection()
        if not conn:
            raise HTTPException(status_code=500, detail="Database connection failed.")
        
        cursor = conn.cursor()

        for row_num, original_row in enumerate(reader, start=1):
            processed_row = {k.strip().lower().replace(' ', '_'): v for k, v in original_row.items()}
            
            item_code = processed_row.get('item_code')
            item_properties_str = processed_row.get('item_properties')

            if not item_code or not item_properties_str:
                error_count += 1
                error_messages.append(f"Row {row_num}: Missing 'item_code' or 'Item Properties'.")
                continue

            properties_to_update = parse_item_properties(item_properties_str)

            if not properties_to_update:
                error_count += 1
                error_messages.append(f"Row {row_num}: Could not parse any properties for item_code {item_code}.")
                continue

            set_clauses = [f"{key} = %s" for key in properties_to_update.keys()]
            values = list(properties_to_update.values())
            values.append(item_code)

            update_query = f"UPDATE products SET {', '.join(set_clauses)} WHERE item_code = %s"

            try:
                cursor.execute(update_query, tuple(values))
                if cursor.rowcount > 0:
                    success_count += 1
                else:
                    error_count += 1
                    error_messages.append(f"Row {row_num}: No product found with item_code '{item_code}'.")
            except Exception as e:
                error_count += 1
                error_messages.append(f"Row {row_num}: Database error for item_code '{item_code}': {e}")
                conn.rollback() # Rollback this specific transaction

        conn.commit()
        
        message = f"Properties update completed. {success_count} successes, {error_count} errors."
        if error_messages:
            message += " See console for details."
            logger.error(f"Bulk properties update errors: {error_messages}")
            
        return JSONResponse(status_code=200, content={"message": message})

    except Exception as e:
        logger.error(f"Error processing properties CSV: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"message": f"Error processing file: {e}"})
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def delete_product_by_identifier(item_id: int = None, item_code: str = None):
    """Deletes a product from the database by item_id or item_code.
    Returns True if a row was deleted.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed in delete_product_by_identifier")
            return False
        cursor = conn.cursor()

        if item_id:
            cursor.execute("DELETE FROM products WHERE item_id = %s", (item_id,))
            identifier_log = f"item_id {item_id}"
        elif item_code:
            cursor.execute("DELETE FROM products WHERE item_code = %s", (item_code,))
            identifier_log = f"item_code {item_code}"
        else:
            logger.warning("No identifier (item_id or item_code) provided for deletion.")
            return False

        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Successfully deleted product with {identifier_log}.")
            return True
        else:
            logger.warning(f"No product found with {identifier_log} to delete.")
            return False
    except Exception as e:
        logger.error(f"Error deleting product with {identifier_log}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_product_by_identifier(item_id: int = None, item_code: str = None, product_title: str = None):
    """Fetches a single product from the database by item_id, item_code, or product_title."""
    conn = None
    cursor = None
    product_data = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed in get_product_by_identifier")
            return None
        cursor = conn.cursor()

        # Include all relevant columns in the select query, 'item_properties' removed
        query = """
            SELECT item_id, main_category, sub_categories, item_code, product_title, product_description,
                   price, large_image, upc, brand, department, type, tag,
                   list_price, inventory, min_order_qty, available, status, lead_time, length,
                   material_type, sys_num_images, sys_product_type, unit_of_measure, unspsc, additional_images, last_modified
            FROM products WHERE 
        """
        params = []
        
        if item_id:
            query += "item_id = %s"
            params.append(item_id)
        elif item_code:
            query += "item_code = %s"
            params.append(item_code)
        elif product_title:
            query += "product_title = %s"
            params.append(product_title)
        else:
            logger.warning("No identifier provided to fetch product.")
            return None

        cursor.execute(query, tuple(params))
        p = cursor.fetchone()

        if p:
            # Map fetched data to a dictionary using column names
            product_data = {
                "item_id": p[0],
                "main_category": p[1],
                "sub_categories": p[2] if p[2] is not None else "",
                "item_code": p[3],
                "product_title": p[4],
                "product_description": p[5] if p[5] is not None else "",
                "price": float(p[6]) if p[6] is not None else 0.0,
                "large_image": p[7], # This will be processed below for URL
                "upc": p[8] if p[8] is not None else "",
                "brand": p[9] if p[9] is not None else "",
                "department": p[10] if p[10] is not None else "",
                "type": p[11] if p[11] is not None else "",
                "tag": p[12] if p[12] is not None else "",
                "list_price": float(p[13]) if p[13] is not None else 0.0,
                "inventory": int(p[14]) if p[14] is not None else 0,
                "min_order_qty": int(p[15]) if p[15] is not None else 0,
                "available": p[16] if p[16] is not None else "",
                "status": p[17] if p[17] is not None else "New",
                "lead_time": p[18] if p[18] is not None else "",
                "length": p[19] if p[19] is not None else "",
                "material_type": p[20] if p[20] is not None else "",
                "sys_num_images": p[21] if p[21] is not None else "",
                "sys_product_type": p[22] if p[22] is not None else "",
                "unit_of_measure": p[23] if p[23] is not None else "",
                "unspsc": p[24] if p[24] is not None else "",
                "last_modified": p[26].isoformat() if p[26] else "" # Get last_modified
            }
            # Robustly parse additional_images
            additional_images_data = []
            if p[25] and isinstance(p[25], str) and p[25].strip():
                try:
                    additional_images_data = json.loads(p[25])
                except json.JSONDecodeError:
                    logger.warning(f"JSONDecodeError for additional_images in item_id {p[0]}: '{p[25]}'. Defaulting to empty list.")
                    additional_images_data = []
            product_data["additional_images"] = additional_images_data


            # Handle large_image URL formatting
            large_image_from_db = product_data["large_image"]
            if large_image_from_db:
                if large_image_from_db.startswith('http://') or large_image_from_db.startswith('https://'):
                    product_data["large_image"] = large_image_from_db
                elif large_image_from_db.startswith(f'/{STATIC_DIR}/'):
                    product_data["large_image"] = large_image_from_db
                else:
                    cleaned_path = large_image_from_db.lstrip('/')
                    product_data["large_image"] = f"/{STATIC_DIR}/{cleaned_path}"
            else:
                product_data["large_image"] = "/static/images/noimage.jpg"
            
        return product_data
    except Exception as e:
        logger.error(f"Error fetching product by identifier: {e}", exc_info=True)
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
# Export 

# --- Export Logic ---
# In app.py, replace the entire simulate_export function

def simulate_export(job_id: int, options: List[str]):
    """
    A background task that fetches data from the database based on selected
    options, merges them, and writes the result to a single CSV file.
    """
    global export_jobs
    
    try:
        # --- 1. Determine the complete set of columns to fetch ---
        # Base columns that are always included, with their desired CSV header names.
        select_columns = {
            "'edit'": "action",
            "item_id": "item id",
            "product_title": "item name",
            "item_code": "item code"
        }
        
        # Map of export options to their corresponding database columns and CSV headers.
        option_to_column_map = {
            "Export Item Information": {"product_description": "item information"},
            "Export Item Price": {"price": "item price"},
            # Add other export options and their column mappings here
            "Export Item Properties": {
                "lead_time": "Lead_Time",
                "length": "length",
                "material_type": "Material_Type",
                "sys_num_images": "Sys_Num_Images",
                "sys_product_type": "Sys_Product_Type",
                "type": "type",
                "unit_of_measure": "Unit_of_Measure",
                "unspsc": "UNSPSC"
            }
        }

        # Add columns to the select list based on the user's chosen options
        for option in options:
            if option in option_to_column_map:
                select_columns.update(option_to_column_map[option])
        
        # --- 2. Fetch data from the database ---
        conn = get_db_connection()
        if not conn:
            raise Exception("Database connection failed")

        # Dynamically construct the SQL query string
        query_cols = ", ".join([f"{db_col} as \"{header_name}\"" for db_col, header_name in select_columns.items()])
        query = f"SELECT {query_cols} FROM products"
        
        # Use pandas to execute the query and load data directly into a DataFrame
        df = pd.read_sql_query(query, conn)
        
        conn.close()

        # --- 3. Write DataFrame to a CSV file and update the job status ---
        export_dir = os.path.join(STATIC_DIR, "exports")
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, f"export_{job_id}.csv")
        
        # Save the DataFrame to a CSV file without the pandas index column
        df.to_csv(file_path, index=False)

        # Find the current job and update its status to "Success"
        for job in export_jobs:
            if job["id"] == job_id:
                job["status"] = "Success"
                job["status_message"] = "Step 2 / 2: FILE EXPORTED SUCCESSFULLY"
                job["thread"] = "None"
                # FIXED: The URL now correctly points to the static path configured in app.mount
                job["download_url"] = f"/admin-static/exports/export_{job_id}.csv"
                break
                
    except Exception as e:
        # If any error occurs, update the job status to "Failed"
        logger.error(f"Export job {job_id} failed: {e}", exc_info=True)
        for job in export_jobs:
            if job["id"] == job_id:
                job["status"] = "Failed"
                job["status_message"] = f"Error: {str(e)}"
                job["thread"] = "None"
                break

@app.post("/api/initiate-export")
async def initiate_export(request: Request, export_request: ExportRequest):
    """
    Initiates a single export job for all selected options.
    """
    if 'user' not in request.session:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})

    global export_jobs, job_counter
    
    admin_name = request.session.get('user', {}).get('username', 'Unknown')
    options = export_request.export_options

    if not options:
        return JSONResponse(status_code=400, content={"message": "No export options selected."})

    job_counter += 1
    job_id = job_counter
    
    # Create a more descriptive task name from all selected options
    task_name_description = ", ".join(options)
    
    new_job = {
        "id": job_id,
        "task_name": f"20190501314 {task_name_description}",
        "information": "Kalika_User",
        "admin_name": admin_name,
        "start_time": datetime.now().isoformat(),
        "task_type": "export",
        "thread": "Alive",
        "status": "Doing Job",
        "status_message": "Waiting",
        "download_url": None,
    }
    export_jobs.insert(0, new_job)

    # Start the background task, passing the list of selected options
    thread = threading.Thread(target=simulate_export, args=(job_id, options))
    thread.start()

    return JSONResponse(status_code=200, content={"message": "Export process initiated."})


# --- New API Endpoints for Product Catalog Modification ---

@app.get("/api/products-for-dropdown")
async def get_products_for_dropdown(request: Request):
    """API endpoint to return a list of products (id, title, code) for dropdowns."""
    if 'user' not in request.session:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})

    conn = None
    cursor = None
    products_list = []
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed in get_products_for_dropdown")
            return JSONResponse(status_code=500, content={"error": "Database connection failed"})
        
        cursor = conn.cursor()
        cursor.execute("SELECT item_id, product_title, item_code FROM products ORDER BY product_title ASC")
        rows = cursor.fetchall()
        for row in rows:
            products_list.append({
                "item_id": row[0],
                "product_title": row[1],
                "item_code": row[2]
            })
        return JSONResponse(content=products_list)
    except Exception as e:
        logger.error(f"Error fetching products for dropdown: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Failed to fetch products: {e}"})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/items", name="items_page")
async def items_page(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("items.html", {
        "request": request,
        "breadcrumb": [
            {"name": "Home", "url": "/admin/"},
            {"name": "Catalog", "url": "#"},
            {"name": "Items", "url": "/admin/items"}
        ],
        "active_menu": "catalog",
        "active_sub_menu": "items"
    })

@app.get("/edit-product", name="edit_product_page")
async def edit_product_page(request: Request, item_id: str = Query(None)):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin/", status_code=302)
    # The item_id is passed as a query parameter and will be read by the frontend JS
    return templates.TemplateResponse("edit_product.html", {
        "request": request,
        "breadcrumb": [
            {"name": "Home", "url": "/admin/"},
            {"name": "Items", "url": "/admin/items"},
            {"name": "Edit Product", "url": "#"}
        ],
        "active_menu": "catalog",
        "active_sub_menu": "items"
    })

@app.get("/advance-edit", name="advance_edit_page")
async def advance_edit_page(request: Request, item_id: str = Query(None)):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    # The item_id is passed as a query parameter and will be read by the frontend JS
    return templates.TemplateResponse("advance_edit.html", {
        "request": request,
        "breadcrumb": [
            {"name": "Home", "url": "/admin/dashboard"},
            {"name": "Items", "url": "/admin/items"},
            {"name": "Advance Edit", "url": "#"}
        ],
        "active_menu": "catalog",
        "active_sub_menu": "items"
    })

@app.post("/api/product-details")
async def get_single_product_details(
    request: Request,
    payload: ItemIDPayload # Use Pydantic model for JSON body
):
    """API endpoint to return full details of a single product by item_id or item_code."""
    if 'user' not in request.session:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})

    item_id = payload.item_id
    item_code = payload.item_code

    if not item_id and not item_code:
        return JSONResponse(status_code=400, content={"message": "Either item_id or item_code must be provided."})

    product = get_product_by_identifier(item_id=item_id, item_code=item_code)
    if product:
        return JSONResponse(content=product)
    else:
        return JSONResponse(status_code=404, content={"message": "Product not found."})

@app.post("/products/update")
async def update_product_post(
    request: Request,
    itemId: int = Form(...), # This is the item_id of the product to update
    productName: str = Form(...),
    productCategory: str = Form(...),
    productSubCategory: Optional[str] = Form(None), # Made optional
    productSubSubCategory: Optional[str] = Form(None), # Made optional
    itemCode: str = Form(...),
    productDescription: Optional[str] = Form(None), # Made optional
    price: float = Form(...),
    barcode: Optional[str] = Form(None), # Added barcode to form data, made optional
    imageUrl: Optional[str] = Form(None),
    imageFile: Optional[UploadFile] = File(None),
    # Add new optional form fields for other columns if they can be updated via this form
    brand: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    type_field: Optional[str] = Form(None, alias="type"), # Use alias for 'type' to avoid Python keyword clash
    tag: Optional[str] = Form(None),
    listPrice: Optional[float] = Form(None), # Assuming this is passed from the edit form
    inventory: Optional[int] = Form(None),
    minOrderQty: Optional[int] = Form(None, alias="min_order_qty"), # Use alias for 'min_order_qty'
    available: Optional[str] = Form(None),
    status: Optional[str] = Form(None), # Added status to form data
    leadTime: Optional[str] = Form(None, alias="lead_time"), # Use alias for 'lead_time'
    length: Optional[str] = Form(None),
    materialType: Optional[str] = Form(None, alias="material_type"), # Use alias for 'material_type'
    sysNumImages: Optional[str] = Form(None, alias="sys_num_images"), # Use alias for 'sys_num_images'
    sysProductType: Optional[str] = Form(None, alias="sys_product_type"), # Use alias for 'sys_product_type'
    unitOfMeasure: Optional[str] = Form(None),
    unspsc: Optional[str] = Form(None)
):
    if 'user' not in request.session:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})

    product_image_url = None
    try:
        if imageFile and imageFile.filename:
            # Read file content
            file_content = await imageFile.read()
            
            # Upload to S3
            s3_path = upload_image_to_s3(
                file_content, 
                imageFile.filename,
                imageFile.content_type or 'image/jpeg'
            )
            
            if s3_path:
                product_image_url = s3_path  # Store S3 path like /kalika-images/abc123.jpg
                logger.info(f"Image uploaded to S3: {product_image_url}")
            else:
                # Fallback: Save locally if S3 upload fails
                file_extension = os.path.splitext(imageFile.filename)[1]
                unique_filename = f"{uuid.uuid4().hex}{file_extension}"
                file_path = os.path.join(UPLOAD_DIR, unique_filename)
                
                with open(file_path, "wb") as buffer:
                    buffer.write(file_content)
                
                product_image_url = f"/{STATIC_DIR}/images/products/{unique_filename}"
                logger.warning(f"S3 upload failed, saved locally: {product_image_url}")
                
        elif imageUrl:
            product_image_url = imageUrl
            logger.info(f"Using provided image URL: {product_image_url}")
        else:
            # If neither new file nor URL is provided, try to retain existing image
            existing_product = get_product_by_identifier(item_id=itemId)
            if existing_product and existing_product.get('large_image'):
                product_image_url = existing_product['large_image']
            else:
                product_image_url = "/static/images/noimage.jpg"
            logger.info("No new image provided, retaining existing or using default.")

    except Exception as e:
        logger.error(f"Error processing image for product {itemId}: {e}", exc_info=True)
        # If image processing fails, product_image_url remains None, and we proceed without updating the image field.
        # This allows other fields to be updated.
        product_image_url = None # Explicitly set to None if an error occurred

    combined_sub_category = productSubCategory if productSubCategory is not None else ""
    if productSubSubCategory:
        if productSubSubCategory not in combined_sub_category.split(','):
            combined_sub_category = f"{combined_sub_category}, {productSubSubCategory}"
    
    product_data = {
        'productName': productName,
        'productCategory': productCategory,
        'productSubCategory': combined_sub_category,
        'itemCode': itemCode,
        'productDescription': productDescription,
        'price': price,
        'barcode': barcode, # Pass barcode to update function
        'listPrice': listPrice,
        'inventory': inventory,
        'minOrderQty': minOrderQty,
        'available': available,
        'status': status, # Pass status to update function
        'leadTime': leadTime,
        'length': length,
        'materialType': materialType,
        'sysNumImages': sysNumImages,
        'sysProductType': sysProductType,
        'unitOfMeasure': unitOfMeasure,
        'unspsc': unspsc,
        'brand': brand,
        'department': department,
        'type': type_field, # Use type_field to match alias
        'tag': tag
    }

    # Only add 'large_image' to product_data if a valid URL was determined
    if product_image_url is not None:
        product_data['large_image'] = product_image_url

    try:
        if update_product_in_db(itemId, product_data):
            request.session['flash_messages'] = [f"Product '{productName}' (ID: {itemId}) updated successfully!"]
            logger.info(f"Product '{productName}' (ID: {itemId}) updated by user {request.session['user']['username']}")
            return JSONResponse(status_code=200, content={"message": f"Product '{productName}' updated successfully!"})
        else:
            return JSONResponse(status_code=500, content={"message": "Failed to update product. Product might not exist."})
    except Exception as e:
        logger.error(f"Error updating product {itemId}: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"message": f"Error updating product: {e}"})

@app.post("/products/update_properties")
async def update_product_properties_post(
    request: Request,
    item_id: int = Form(...),
    sys_num_images: Optional[str] = Form(None), # Changed to str as per DB schema
    unit_of_measure: Optional[str] = Form(None),
    upc: Optional[str] = Form(None) # UPC from the properties form
):
    """API endpoint to update specific product properties (sys_num_images, unit_of_measure, upc)."""
    if 'user' not in request.session:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed in update_product_properties_post")
            return JSONResponse(status_code=500, content={"message": "Database connection failed."})
        
        cursor = conn.cursor()

        set_clauses = []
        values = []

        if sys_num_images is not None:
            set_clauses.append("sys_num_images = %s")
            values.append(sys_num_images)
        if unit_of_measure is not None:
            set_clauses.append("unit_of_measure = %s")
            values.append(unit_of_measure)
        if upc is not None:
            set_clauses.append("upc = %s")
            values.append(upc)

        if not set_clauses:
            return JSONResponse(status_code=400, content={"message": "No properties provided for update."})

        update_query = f"""
        UPDATE products
        SET {', '.join(set_clauses)}
        WHERE item_id = %s;
        """
        values.append(item_id)

        cursor.execute(update_query, tuple(values))
        conn.commit()

        if cursor.rowcount > 0:
            logger.info(f"Successfully updated properties for item_id {item_id}.")
            return JSONResponse(status_code=200, content={"message": "Product properties updated successfully!"})
        else:
            logger.warning(f"No product found with item_id {item_id} to update properties.")
            return JSONResponse(status_code=404, content={"message": "Product not found or failed to update properties."})

    except Exception as e:
        logger.error(f"Error updating product properties for item_id {item_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        return JSONResponse(status_code=500, content={"message": f"Error updating product properties: {e}"})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.post("/products/delete")
async def delete_product_post(
    request: Request,
    deleteById: int = Form(None),
    deleteByCode: str = Form(None)
):
    if 'user' not in request.session:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})

    if not deleteById and not deleteByCode:
        return JSONResponse(status_code=400, content={"message": "Either Item ID or Item Code must be provided for deletion."})

    if delete_product_by_identifier(item_id=deleteById, item_code=deleteByCode):
        identifier_used = f"ID: {deleteById}" if deleteById else f"Code: {deleteByCode}"
        request.session['flash_messages'] = [f"Product ({identifier_used}) deleted successfully!"]
        logger.info(f"Product ({identifier_used}) deleted by user {request.session['user']['username']}")
        return JSONResponse(status_code=200, content={"message": f"Product ({identifier_used}) deleted successfully!"})
    else:
        return JSONResponse(status_code=404, content={"message": "Product not found or failed to delete."})


# --- Existing Routes ---
@app.get("/dashboard", name="dashboard") # Added name
async def dashboard(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access the dashboard."]
        return RedirectResponse(url="/admin", status_code=302)
    
    # These functions are imported from db.py, so their SQL queries needs to be correct in db.py
    total_sales = get_total_sales() 
    total_products = get_product_count()
    total_users = get_user_count()
    pending_orders_count = get_pending_orders_count()
    recent_orders = get_recent_orders() 
    category_data = get_product_category_counts()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Dashboard", "url": "/admin/dashboard"}],
        "active_menu": "dashboard",
        "total_sales": total_sales,
        "total_products": total_products,
        "total_users": total_users,
        "pending_orders_count": pending_orders_count,
        "recent_orders": recent_orders,
        "category_data": category_data
    })

# NEW: API endpoint to get product data as JSON with server-side processing
@app.get("/api/products-list", name="api_products_list")
async def api_products_list(
    request: Request,
    draw: int = Query(..., alias="draw"),
    start: int = Query(..., alias="start"),
    length: int = Query(..., alias="length"),
    search_value: str = Query(None, alias="search[value]"),
    order_column: int = Query(None, alias="order[0][column]"),
    order_dir: str = Query(None, alias="order[0][dir]")
):
    if 'user' not in request.session:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    conn = None
    cursor = None
    products_list = []
    records_total = 0
    records_filtered = 0

    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed for /api/products-list")
            raise HTTPException(status_code=500, detail="Database connection error. Please try again later.")
        
        cursor = conn.cursor()

        # Get total records (before filtering)
        cursor.execute("SELECT COUNT(*) FROM products")
        records_total = cursor.fetchone()[0]

        # Base query for data retrieval
        query = """
            SELECT item_id, main_category, sub_categories, item_code, product_title, product_description,
                   price, large_image, upc, brand, department, type, tag,
                   list_price, inventory, min_order_qty, available, status, last_modified, lead_time, length,
                   material_type, sys_num_images, sys_product_type, unit_of_measure, unspsc, additional_images
            FROM products
        """
        count_query = "SELECT COUNT(*) FROM products"
        where_clauses = []
        query_params = []

        # Handle search/filter
        if search_value:
            search_pattern = f"%{search_value}%"
            where_clauses.append("""
                (product_title ILIKE %s OR item_code ILIKE %s OR status ILIKE %s OR main_category ILIKE %s)
            """)
            query_params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            count_query += " WHERE " + " AND ".join(where_clauses)
        
        # Get filtered records count
        cursor.execute(count_query, tuple(query_params))
        records_filtered = cursor.fetchone()[0]

        # Handle ordering
        orderable_columns = [
            "item_id", "product_title", "item_code", "status", None, "last_modified", None # Map to actual DB columns
        ]
        order_clause = ""
        if order_column is not None and order_column < len(orderable_columns) and orderable_columns[order_column] is not None:
            column_name = orderable_columns[order_column]
            order_direction = "ASC" if order_dir == "asc" else "DESC"
            order_clause = f" ORDER BY {column_name} {order_direction}"
        else:
            order_clause = " ORDER BY item_id ASC" # Default order

        # Handle pagination
        limit_clause = f" LIMIT %s OFFSET %s"
        query_params.extend([length, start])

        final_query = query + order_clause + limit_clause
        
        logger.info(f"Executing query: {final_query} with params: {query_params}")
        cursor.execute(final_query, tuple(query_params))
        products_data = cursor.fetchall()
        
        for p in products_data:
            # Ensure image URL is correctly prefixed for static files
            large_image_url = p[7] if p[7] is not None else "/static/images/noimage.jpg"
            if large_image_url and not large_image_url.startswith('/static/') and not large_image_url.startswith('http'):
                large_image_url = f"/static/{large_image_url}"

            # Robustly parse additional_images
            additional_images_parsed = []
            if p[26] and isinstance(p[26], str) and p[26].strip():
                try:
                    additional_images_parsed = json.loads(p[26])
                except json.JSONDecodeError:
                    logger.warning(f"JSONDecodeError for additional_images in item_id {p[0]}: '{p[26]}'. Defaulting to empty list.")
                    additional_images_parsed = []

            # Format last_modified to a string for JSON serialization
            last_modified_formatted = p[18].isoformat() if p[18] else ""

            products_list.append({
                "item_id": p[0],
                "main_category": p[1],
                "sub_categories": p[2] if p[2] is not None else "None",
                "item_code": p[3],
                "product_title": p[4],
                "product_description": p[5] if p[5] is not None else "",
                "price": float(p[6]) if p[6] is not None else 0.0,
                "large_image": large_image_url,
                "upc": p[8] if p[8] is not None else "",
                "brand": p[9] if p[9] is not None else "",
                "department": p[10] if p[10] is not None else "",
                "type": p[11] if p[11] is not None else "",
                "tag": p[12] if p[12] is not None else "",
                "list_price": float(p[13]) if p[13] is not None else 0.0,
                "inventory": int(p[14]) if p[14] is not None else 0,
                "min_order_qty": int(p[15]) if p[15] is not None else 0,
                "available": p[16] if p[16] is not None else "",
                "status": p[17] if p[17] is not None else "New",
                "last_modified": last_modified_formatted, # Use formatted date
                "lead_time": p[19] if p[19] is not None else "",
                "length": p[20] if p[20] is not None else "",
                "material_type": p[21] if p[21] is not None else "",
                "sys_num_images": p[22] if p[22] is not None else "",
                "sys_product_type": p[23] if p[23] is not None else "",
                "unit_of_measure": p[24] if p[24] is not None else "",
                "unspsc": p[25] if p[25] is not None else "",
                "additional_images": additional_images_parsed
            })
        
        return JSONResponse({
            "draw": draw,
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "data": products_list
        })
    except Exception as e:
        logger.error(f"Error fetching products for /api/products-list: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching products: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/products", name="items_page") # Renamed from 'products' to 'items_page' for clarity in menu
async def products(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access the dashboard."]
        return RedirectResponse(url="/admin", status_code=302)
    
    # This endpoint now primarily serves the HTML page structure.
    # The data fetching is handled by the /api/products-list endpoint in JavaScript.
    return templates.TemplateResponse("items.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Products", "url": "/admin/products"}],
        "active_menu": "catalog", # Changed to catalog
        "active_sub_menu": "items", # Changed to items
        "products": [] # No longer passing products directly, JavaScript will fetch
    })

@app.get("/products/add", name="add_products_get") # Route name changed to match template
async def product_modification_get(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("single_modify.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Products", "url": "/admin/products"}, {"name": "Modify Product", "url": "/admin/products/add"}],
        "active_menu": "catalog", # Changed to catalog
        "active_sub_menu": "single_modify" # Added for single modify
    })

@app.post("/products/add")
async def add_products_post(
    request: Request,
    productName: str = Form(...),
    productCategory: str = Form(...),
    productSubCategory: Optional[str] = Form(None), # Made optional
    productSubSubCategory: Optional[str] = Form(None), # Made optional
    itemCode: str = Form(...),
    productDescription: Optional[str] = Form(None), # Made optional
    price: float = Form(...),
    barcode: Optional[str] = Form(None), # Added barcode for new product, made optional
    imageUrl: Optional[str] = Form(None), # Existing URL input
    imageFile: Optional[UploadFile] = File(None), # New file upload input
    # Add new optional form fields for other columns if they can be updated via this form
    brand: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    type_field: Optional[str] = Form(None, alias="type"), # Use alias for 'type' to avoid Python keyword clash
    tag: Optional[str] = Form(None),
    listPrice: Optional[float] = Form(None), # Assuming listPrice is from form, maps to list_price
    inventory: Optional[int] = Form(None),
    minOrderQty: Optional[int] = Form(None, alias="min_order_qty"), # Use alias for 'min_order_qty'
    available: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    leadTime: Optional[str] = Form(None, alias="lead_time"), # Use alias for 'lead_time'
    length: Optional[str] = Form(None),
    materialType: Optional[str] = Form(None, alias="material_type"), # Use alias for 'material_type'
    sysNumImages: Optional[str] = Form(None, alias="sys_num_images"), # Use alias for 'sys_num_images'
    sysProductType: Optional[str] = Form(None, alias="sys_product_type"), # Use alias for 'sys_product_type'
    unitOfMeasure: Optional[str] = Form(None),
    unspsc: Optional[str] = Form(None)
):
    if 'user' not in request.session:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})
    
    product_image_url = None
    conn = None # Initialize conn to None
    cursor = None # Initialize cursor to None
    try:
        # Determine the image URL to save
        if imageFile and imageFile.filename:
            # Read file content
            file_content = await imageFile.read()
            
            # Upload to S3
            s3_path = upload_image_to_s3(
                file_content, 
                imageFile.filename,
                imageFile.content_type or 'image/jpeg'
            )
            
            if s3_path:
                product_image_url = s3_path  # Store S3 path like /kalika-images/abc123.jpg
                logger.info(f"Image uploaded to S3: {product_image_url}")
            else:
                # Fallback: Save locally if S3 upload fails
                file_extension = os.path.splitext(imageFile.filename)[1]
                unique_filename = f"{uuid.uuid4().hex}{file_extension}"
                file_path = os.path.join(UPLOAD_DIR, unique_filename)
                
                with open(file_path, "wb") as buffer:
                    buffer.write(file_content)
                
                product_image_url = f"/{STATIC_DIR}/images/products/{unique_filename}"
                logger.warning(f"S3 upload failed, saved locally: {product_image_url}")
                
        elif imageUrl:
            product_image_url = imageUrl
            logger.info(f"Using provided image URL: {product_image_url}")
        else:
            product_image_url = "/static/images/noimage.jpg" # Default image if neither is provided
            logger.info("No image provided, using default placeholder.")

    except Exception as e:
        logger.error(f"Error processing image for new product: {e}", exc_info=True)
        product_image_url = "/static/images/noimage.jpg" # Fallback to default if image processing fails

    # Combine sub_category and sub_sub_category if sub_sub_category is provided
    combined_sub_category = productSubCategory if productSubCategory is not None else ""
    if productSubSubCategory:
        # Ensure no duplicates if subSubCategory is already part of productSubCategory
        if productSubSubCategory not in combined_sub_category.split(','):
            combined_sub_category = f"{combined_sub_category}, {productSubSubCategory}"

    product_data = {
        'product_title': productName, 
        'main_category': productCategory, 
        'sub_categories': combined_sub_category, 
        'item_code': itemCode, 
        'product_description': productDescription, 
        'price': price,
        'large_image': product_image_url,
        'upc': barcode, # Store barcode as UPC
        'brand': brand,
        'department': department,
        'type': type_field, # Use type_field to match alias
        'tag': tag,
        'list_price': listPrice,
        'inventory': inventory,
        'min_order_qty': minOrderQty,
        'available': available,
        'status': status,
        'lead_time': leadTime,
        'length': length,
        'material_type': materialType,
        'sys_num_images': sysNumImages,
        'sys_product_type': sysProductType,
        'unit_of_measure': unitOfMeasure,
        'unspsc': unspsc,
    }

    try:
        if add_product_to_db(product_data):
            request.session['flash_messages'] = [f"Product '{productName}' added successfully!"]
            logger.info(f"Product '{productName}' added by user {request.session['user']['username']}")
            return JSONResponse(status_code=200, content={"message": f"Product '{productName}' added successfully!"})
        else:
            return JSONResponse(status_code=500, content={"message": "Failed to add product."})
    except Exception as e:
        logger.error(f"Error adding product: {e}", exc_info=True)
        request.session['flash_messages'] = [f"Error adding product: {e}"]
        return JSONResponse(status_code=500, content={"message": f"Error adding product: {e}"})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/bulk-modify", name="import_from_xl_page") # Added name
async def bulk_modify_get(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role FROM accounts_customuser WHERE id = %s", (request.session['user']['id'],))
            user_role = cursor.fetchone()[0]
            if user_role != 'Admin':
                request.session['flash_messages'] = ["You don't have permission to access this page."]
                return RedirectResponse(url="/admin/dashboard", status_code=302)
    except Exception as e:
        logger.error(f"Error checking user role: {e}")
        request.session['flash_messages'] = ["Error verifying permissions."]
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    finally:
        if conn:
            conn.close()
    
    return templates.TemplateResponse("import_from_xl.html", { # Changed from modification.html to bulk_modify.html
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Products", "url": "/admin/products"}, {"name": "Bulk Modify", "url": "/admin/bulk-modify"}],
        "active_menu": "catalog", # Changed to catalog
        "active_sub_menu": "import_from_xl" # Changed to import_from_xl
    })

@app.post("/bulk-modify")
async def bulk_modify_post(
    request: Request,
    file: UploadFile = File(...),
    modification_type: str = Form(...)
):
    # Ensure user is logged in
    if 'user' not in request.session:
        return JSONResponse(status_code=401, content={"message": "Please log in to perform this action."})
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT role FROM accounts_customuser WHERE id = %s", (request.session['user']['id'],))
            user_role = cursor.fetchone()[0]
            if user_role != 'Admin':
                return JSONResponse(status_code=403, content={"message": "You don't have permission to perform this action."})
    except Exception as e:
        logger.error(f"Error checking user role: {e}")
        return JSONResponse(status_code=500, content={"message": "Error verifying permissions."})
    finally:
        if conn:
            conn.close()
    
    # Validate file type
    if not file.filename.endswith('.csv'):
        return JSONResponse(status_code=400, content={"message": "Please upload a valid CSV file."})
    
    success_count = 0
    error_count = 0
    error_messages = []

    try:
        contents = await file.read()
        csv_data_str = None
        
        # Try decoding with utf-8-sig first, then latin-1 as a fallback
        try:
            csv_data_str = contents.decode('utf-8-sig')
        except UnicodeDecodeError:
            logger.warning("UTF-8-SIG decoding failed, trying latin-1.")
            try:
                csv_data_str = contents.decode('latin-1')
            except UnicodeDecodeError as latin1_e:
                logger.error(f"Latin-1 decoding also failed: {latin1_e}", exc_info=True)
                return JSONResponse(
                    status_code=400,
                    content={"message": "Could not decode CSV file. Please ensure it's saved as UTF-8 or a compatible format (e.g., CSV UTF-8, or Comma Separated Values from Excel)."}
                )

        csv_data = io.StringIO(csv_data_str)
        reader = csv.DictReader(csv_data)
        
        # This list defines the expected columns in your database 'products' table.
        # It's crucial for mapping CSV data to DB columns.
        # Removed 'item_properties' from this list
        ALL_PRODUCT_DB_COLUMNS = [
            'action', 'main_category', 'sub_categories', 'item_code',
            'product_title', 'product_description', 'upc', 'brand', 'department',
            'type', 'tag', 'list_price', 'price', 'inventory', 'min_order_qty',
            'available', 'large_image', 'additional_images', 'status',
            'lead_time', 'length', 'material_type', 'sys_num_images',
            'sys_product_type', 'unit_of_measure', 'unspsc'
        ]

        REQUIRED_ADD_FIELDS = [
            'main_category', 'item_code', 'product_title', 'price'
        ]
        
        for row_num, original_row in enumerate(reader, start=1):
            processed_row = {}
            for original_key, value in original_row.items():
                if original_key is None:
                    logger.warning(f"Skipping None original_key in row {row_num}: {original_row}")
                    continue

                # Clean the key: strip whitespace, replace spaces with underscores, remove BOM, convert to lowercase
                cleaned_key = original_key.strip().replace(' ', '_').replace('\ufeff', '').lower()
                processed_row[cleaned_key] = value

            try:
                if modification_type == 'add':
                    missing_fields = [
                        field for field in REQUIRED_ADD_FIELDS
                        if field not in processed_row or processed_row[field] is None or str(processed_row[field]).strip() == ''
                    ]
                    if missing_fields:
                        raise ValueError(f"Missing or empty required fields for adding product: {missing_fields}")
                    
                    # Construct product_data_for_db by iterating through ALL_PRODUCT_DB_COLUMNS
                    # and getting values from processed_row. This ensures all expected DB columns are considered.
                    product_data_for_db = {}
                    for col in ALL_PRODUCT_DB_COLUMNS:
                        if col == 'item_id': # item_id is auto-generated for 'add' operations
                            continue
                        # Use the cleaned key for lookup in processed_row
                        product_data_for_db[col] = processed_row.get(col)
                    
                    # Special handling for 'type' column to avoid Python keyword conflict
                    if 'type' in processed_row:
                        product_data_for_db['type'] = processed_row['type']
                    
                    # Handle additional_images if present in CSV, assuming it's a JSON string of a list
                    if 'additional_images' in processed_row and processed_row['additional_images'].strip():
                        try:
                            product_data_for_db['additional_images'] = json.dumps(json.loads(processed_row['additional_images']))
                        except json.JSONDecodeError:
                            product_data_for_db['additional_images'] = "[]" # Default to empty JSON array if invalid
                    else:
                        product_data_for_db['additional_images'] = "[]" # Default to empty JSON array

                    if add_product_to_db(product_data_for_db):
                        success_count += 1
                    else:
                        error_count += 1
                        error_messages.append(f"Failed to add product {processed_row.get('product_title', 'unknown')} from row {row_num}.")

                elif modification_type == 'update_price':
                    item_id_str = processed_row.get('item_id')
                    price_str = processed_row.get('price')
                    if not item_id_str:
                        raise ValueError(f"Missing 'item_id' for update_price in row {row_num}")
                    if not price_str: # Price can be 0 or empty string, handle conversion
                        new_price = 0.0 # Default to 0 if price is missing or empty
                        logger.warning(f"Price not provided for item_id {item_id_str} in row {row_num}. Setting price to 0.0.")
                    else:
                        try:
                            new_price = float(price_str)
                        except ValueError:
                            raise ValueError(f"Invalid price format '{price_str}' for item_id {item_id_str} in row {row_num}")
                    
                    item_id = int(item_id_str)
                    if update_product_price_in_db(item_id, new_price):
                        success_count += 1
                    else:
                        error_count += 1
                        error_messages.append(f"Failed to update price for item_id {item_id} from row {row_num} (Product not found or update failed).")

                elif modification_type == 'update_description': 
                    item_id_str = processed_row.get('item_id')
                    new_description = processed_row.get('product_description')
                    if not item_id_str:
                        raise ValueError(f"Missing 'item_id' for update_description in row {row_num}")
                    # new_description can legitimately be an empty string, so no 'is None' check for it
                    if new_description is None:
                        new_description = "" # Default to empty string if description is missing

                    item_id = int(item_id_str)
                    if update_product_description_in_db(item_id, new_description):
                        success_count += 1
                    else:
                        error_count += 1
                        error_messages.append(f"Failed to update description for item_id {item_id} from row {row_num} (Product not found or update failed).")

                elif modification_type == 'delete':
                    item_id_str = processed_row.get('item_id')
                    if not item_id_str:
                        raise ValueError(f"Missing 'item_id' for delete in row {row_num}")
                    
                    item_id = int(item_id_str)
                    if delete_product_by_identifier(item_id=item_id): # Use the new flexible delete function
                        success_count += 1
                    else:
                        error_count += 1
                        error_messages.append(f"Failed to delete product with item_id {item_id} from row {row_num} (Product not found or delete failed).")
                else:
                    error_count += 1
                    error_messages.append(f"Unknown modification type: {modification_type} for row {row_num}.")

            except (KeyError, ValueError) as e:
                error_count += 1
                error_messages.append(f"Data error in row {row_num}: {e} - Original row: {original_row}")
                logger.error(f"Data error in row {row_num}: {e} - Original row: {original_row}")
            except Exception as e:
                error_count += 1
                error_messages.append(f"Unhandled error processing row {row_num}: {str(e)} - Original row: {original_row}")
                logger.error(f"Unhandled error processing row {row_num}: {e}", exc_info=True)

        if error_count == 0:
            return JSONResponse(status_code=200, content={"message": f"Bulk modification completed. Successfully processed {success_count} items."})
        else:
            return JSONResponse(status_code=200, content={
                "message": f"Bulk modification completed with {success_count} successes and {error_count} errors.",
                "errors": error_messages[:10]
            })

    except Exception as e:
        logger.error(f"Error reading or processing CSV file: {e}", exc_info=True)
        # This catch-all is for errors outside the row-by-row processing, like file reading
        return JSONResponse(status_code=500, content={"message": f"Error processing CSV file: {str(e)}"})



@app.post("/bulk-modify-properties-column")
async def bulk_modify_properties_column_post(request: Request, file: UploadFile = File(...)):
    # This endpoint is for Section 2
    if 'user' not in request.session:
        return JSONResponse(status_code=401, content={"message": "Please log in."})

    success_count, error_count = 0, 0
    
    header_map = {
        'Action': 'action', 'Item Id': 'item_id', 'Main Category': 'main_category',
        'Sub Categories': 'sub_categories', 'Item Code': 'item_code', 'Product Title': 'product_title',
        'Product Description': 'product_description', 'UPC': 'upc', 'Brand': 'brand',
        'Department': 'department', 'Type': 'type', 'Tag': 'tag', 'List Price': 'list_price',
        'Price': 'price', 'Inventory': 'inventory', 'Min Order Qty': 'min_order_qty',
        'Available': 'available', 'Large Image': 'large_image', 'Additional Images': 'additional_images',
        'Status': 'status'
    }
    
    try:
        contents = await file.read()
        csv_data_str = contents.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(csv_data_str))
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": f"Error reading file: {e}"})

    for row in reader:
        product_data = {}
        for user_header, value in row.items():
            if user_header is None: continue
            db_key = header_map.get(user_header.strip())
            if db_key: product_data[db_key] = value
        
        if 'Item Properties' in row and row['Item Properties']:
            product_data.update(parse_item_properties(row['Item Properties']))

        action = product_data.get('action', '').lower()
        item_code = product_data.get('item_code')

        if not action or not item_code:
            error_count += 1
            continue

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT item_id FROM products WHERE item_code = %s", (item_code,))
        existing_product = cursor.fetchone()
        cursor.close()
        conn.close()

        if action in ['add', 'add/edit', 'update']:
            if existing_product:
                if update_product_in_db(existing_product[0], product_data): success_count += 1
                else: error_count += 1
            else:
                if add_product_to_db(product_data): success_count += 1
                else: error_count += 1
        elif action == 'delete':
            if delete_product_by_identifier(item_code=item_code): success_count += 1
            else: error_count += 1

    return JSONResponse({"message": f"Properties import complete. Success: {success_count}, Errors: {error_count}"})



@app.get("/api/nested-categories")
async def get_nested_categories_from_db():
    """
    API endpoint to return nested category data (Main -> Sub -> Sub-Sub) from the database.
    This will be used to populate the dynamic dropdowns in the UI.
    Assumes sub_categories might contain comma-separated values where the first part is the primary sub-category
    and subsequent parts could be treated as sub-sub-categories for UI purposes.
    """
    conn = None
    cursor = None
    nested_categories = {} # Structure: {main_cat: {sub_cat: [sub_sub_cats]}}
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed in get_nested_categories_from_db")
            return JSONResponse(status_code=500, content={"error": "Database connection failed"})
        
        cursor = conn.cursor()
        # Fetch distinct main_category and sub_categories
        cursor.execute("""
            SELECT DISTINCT main_category, sub_categories
            FROM products
            WHERE main_category IS NOT NULL
            ORDER BY main_category, sub_categories;
        """)
        
        rows = cursor.fetchall()
        for row in rows:
            main_cat = row[0].strip() if row[0] else None
            sub_cat_str = row[1] # This might be a comma-separated string

            if not main_cat: # Skip if main category is null or empty
                continue

            if main_cat not in nested_categories:
                nested_categories[main_cat] = {} # Initialize sub-category dict for this main category
            
            if sub_cat_str:
                # Split by comma and strip whitespace for each sub-category part
                sub_cat_parts = [s.strip() for s in sub_cat_str.split(',') if s.strip()]
                
                if sub_cat_parts:
                    # The first part is considered the primary sub-category
                    primary_sub_cat = sub_cat_parts[0]
                    
                    if primary_sub_cat not in nested_categories[main_cat]:
                        nested_categories[main_cat][primary_sub_cat] = [] # Initialize sub-sub list for this sub category
                    
                    # Subsequent parts are considered sub-sub-categories
                    for i in range(1, len(sub_cat_parts)):
                        sub_sub_cat = sub_cat_parts[i]
                        if sub_sub_cat not in nested_categories[main_cat][primary_sub_cat]:
                            nested_categories[main_cat][primary_sub_cat].append(sub_sub_cat)
        
        # Sort sub-categories and sub-sub-categories for consistent UI display
        for main_cat in nested_categories:
            # Sort sub-category keys
            sorted_sub_cats = sorted(nested_categories[main_cat].keys())
            temp_sub_cat_dict = {}
            for sub_cat_key in sorted_sub_cats:
                temp_sub_cat_dict[sub_cat_key] = sorted(nested_categories[main_cat][sub_cat_key])
            nested_categories[main_cat] = temp_sub_cat_dict
        
        logger.info(f"Fetched nested categories: {nested_categories}")
        return JSONResponse(content=nested_categories)
    except Exception as e:
        logger.error(f"Error fetching nested categories from database: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": f"Failed to fetch categories: {e}"})
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
# export from xl 

# --- Export Logic ---
# def simulate_export(job_id: int, options: List[str]):
#     """
#     A background task that fetches data from the database based on selected
#     options, merges them, and writes the result to a single CSV file.
#     """
#     global export_jobs
    
#     try:
#         # --- 1. Determine the complete set of columns to fetch ---
#         # Base columns that are always included, with their desired CSV header names.
#         select_columns = {
#             "'edit'": "action",
#             "item_id": "item id",
#             "product_title": "item name",
#             "item_code": "item code"
#         }
        
#         # Map of export options to their corresponding database columns and CSV headers.
#         option_to_column_map = {
#             "Export Item Information": {"product_description": "item information"},
#             "Export Item Price": {"price": "item price"}
#             # Add other export options and their column mappings here
#         }

#         # Add columns to the select list based on the user's chosen options
#         for option in options:
#             if option in option_to_column_map:
#                 select_columns.update(option_to_column_map[option])
        
#         # --- 2. Fetch data from the database ---
#         conn = get_db_connection()
#         if not conn:
#             raise Exception("Database connection failed")

#         # Dynamically construct the SQL query string
#         query_cols = ", ".join([f"{db_col} as \"{header_name}\"" for db_col, header_name in select_columns.items()])
#         query = f"SELECT {query_cols} FROM products"
        
#         # Use pandas to execute the query and load data directly into a DataFrame
#         df = pd.read_sql_query(query, conn)
        
#         conn.close()

#         # --- 3. Write DataFrame to a CSV file and update the job status ---
#         export_dir = os.path.join(STATIC_DIR, "exports")
#         os.makedirs(export_dir, exist_ok=True)
#         file_path = os.path.join(export_dir, f"export_{job_id}.csv")
        
#         # Save the DataFrame to a CSV file without the pandas index column
#         df.to_csv(file_path, index=False)

#         # Find the current job and update its status to "Success"
#         for job in export_jobs:
#             if job["id"] == job_id:
#                 job["status"] = "Success"
#                 job["status_message"] = "Step 2 / 2: FILE EXPORTED SUCCESSFULLY"
#                 job["thread"] = "None"
#                 job["download_url"] = f"/{STATIC_DIR}/exports/export_{job_id}.csv"
#                 break
                
#     except Exception as e:
#         # If any error occurs, update the job status to "Failed"
#         logger.error(f"Export job {job_id} failed: {e}", exc_info=True)
#         for job in export_jobs:
#             if job["id"] == job_id:
#                 job["status"] = "Failed"
#                 job["status_message"] = f"Error: {str(e)}"
#                 job["thread"] = "None"
#                 break

# @app.post("/admin/api/initiate-export")
# async def initiate_export(request: Request, export_request: ExportRequest):
#     """
#     Initiates a single export job for all selected options.
#     """
#     if 'user' not in request.session:
#         return JSONResponse(status_code=401, content={"message": "Unauthorized"})

#     global export_jobs, job_counter
    
#     admin_name = request.session.get('user', {}).get('username', 'Unknown')
#     options = export_request.export_options

#     if not options:
#         return JSONResponse(status_code=400, content={"message": "No export options selected."})

#     job_counter += 1
#     job_id = job_counter
    
#     # Create a more descriptive task name from all selected options
#     task_name_description = ", ".join(options)
    
#     new_job = {
#         "id": job_id,
#         "task_name": f"20190501314 {task_name_description}",
#         "information": "Kalika_User",
#         "admin_name": admin_name,
#         "start_time": datetime.now().isoformat(),
#         "task_type": "export",
#         "thread": "Alive",
#         "status": "Doing Job",
#         "status_message": "Waiting",
#         "download_url": None,
#     }
#     export_jobs.insert(0, new_job)

#     # Start the background task, passing the list of selected options
#     thread = threading.Thread(target=simulate_export, args=(job_id, options))
#     thread.start()

#     return JSONResponse(status_code=200, content={"message": "Export process initiated."})

@app.get("/api/export-status")
async def get_export_status(request: Request):
    if 'user' not in request.session:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})
    return JSONResponse(content=export_jobs)


@app.get("/export-status", name="export_status_page")
async def export_status_page(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin/", status_code=302)
    
    return templates.TemplateResponse("export_status.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Catalog", "url": "#"}, {"name": "Export Status", "url": "/admin/export-status"}],
        "active_menu": "catalog",
        "active_sub_menu": "export_file"
    })

@app.get("/api/categories")
async def get_categories():
    conn = None
    cursor = None
    categories = {}
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return {"error": "Database connection failed"}
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT main_category, sub_categories 
            FROM products 
            WHERE main_category IS NOT NULL 
            ORDER BY main_category, sub_categories
        """)
        
        rows = cursor.fetchall()
        for row in rows:
            main_cat = row[0]
            sub_cat = row[1]
            
            if main_cat not in categories:
                categories[main_cat] = []
            
            if sub_cat and sub_cat not in categories[main_cat]:
                categories[main_cat].append(sub_cat)
        
        return categories
    except Exception as e:
        logger.error(f"Error fetching categories from database: {e}")
        return {"error": f"Failed to fetch categories: {e}"}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/api/categories-from-db")
async def get_categories_from_db():
    conn = None
    cursor = None
    categories = {}
    try:
        conn = get_db_connection()
        if not conn:
            return {"error": "Database connection failed"}
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT main_category, sub_categories 
            FROM products 
            WHERE main_category IS NOT NULL 
            ORDER BY main_category, sub_categories
        """)
        
        rows = cursor.fetchall()
        for row in rows:
            main_cat = row[0]
            sub_cat = row[1]
            
            if main_cat not in categories:
                categories[main_cat] = []
            
            if sub_cat and sub_cat not in categories[main_cat]:
                categories[main_cat].append(sub_cat)
        
        if not categories:
            return {}
            
        return categories
    except Exception as e:
        logger.error(f"Error fetching categories from database: {e}")
        return {}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/pending-orders", name="pending_orders") # Added name
async def pending_orders(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    
    conn = None
    cursor = None
    pending_orders_list = []
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            request.session['flash_messages'] = ["Database connection error. Please try again later."]
            return templates.TemplateResponse("pending_orders.html", {"request": request, "orders": []})
        
        cursor = conn.cursor()
        # Modified query: Assuming 'user_id' instead of 'customer_id' and 'item_price' instead of 'price'
        cursor.execute("""
            SELECT
                o.order_id,
                au.username AS customer_name,
                p.product_title,
                o.quantity,
                o.item_price, -- Changed from o.price
                o.order_date,
                o.status
            FROM
                orders o
            JOIN
                accounts_customuser au ON o.user_id = au.id -- Changed from o.customer_id
            JOIN
                products p ON o.product_id = p.item_id
            WHERE o.status = 'Pending'
            ORDER BY o.order_date DESC;
        """)
        orders_data = cursor.fetchall()

        for ord_data in orders_data:
            pending_orders_list.append({
                "order_id": ord_data[0],
                "customer_name": ord_data[1],
                "product_title": ord_data[2],
                "quantity": ord_data[3],
                "price": ord_data[4], # Still refer to it as 'price' in the dict for consistency with front-end
                "total_amount": ord_data[3] * ord_data[4],
                "created_at": ord_data[5],
                "status": ord_data[6]
            })
    except Exception as e:
        logger.error(f"Error fetching pending orders: {e}", exc_info=True)
        request.session['flash_messages'] = ["Error fetching pending orders. Please try again."]
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return templates.TemplateResponse("pending_orders.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Orders", "url": "#"}, {"name": "Pending Orders", "url": "/admin/pending-orders"}],
        "active_menu": "orders",
        "active_sub_menu": "pending_orders",
        "orders": pending_orders_list
    })

@app.get("/orders", name="completed_orders") # Added name
async def completed_orders(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    
    conn = None
    cursor = None
    orders_list = []
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            request.session['flash_messages'] = ["Database connection error. Please try again later."]
            return templates.TemplateResponse("orders.html", {"request": request, "orders": []})
        
        cursor = conn.cursor()
        # Modified query: Assuming 'user_id' instead of 'customer_id' and 'item_price' instead of 'price'
        cursor.execute("""
            SELECT
                o.order_id,
                au.username AS customer_name,
                p.product_title,
                o.quantity,
                o.item_price, -- Changed from o.price
                o.order_date,
                o.status
            FROM
                orders o
            JOIN
                accounts_customuser au ON o.user_id = au.id -- Changed from o.customer_id
            JOIN
                products p ON o.product_id = p.item_id
            WHERE o.status = 'Completed' OR o.status = 'Shipped'
            ORDER BY o.order_date DESC;
        """)
        orders_data = cursor.fetchall()

        for ord_data in orders_data:
            orders_list.append({
                "order_id": ord_data[0],
                "customer_name": ord_data[1],
                "product_title": ord_data[2],
                "quantity": ord_data[3],
                "price": ord_data[4], # Still refer to it as 'price' in the dict for consistency with front-end
                "total_amount": ord_data[3] * ord_data[4],
                "order_date": ord_data[5],
                "status": ord_data[6]
            })
    except Exception as e:
        logger.error(f"Error fetching completed orders: {e}", exc_info=True)
        request.session['flash_messages'] = ["Error fetching completed orders. Please try again."]
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return templates.TemplateResponse("orders.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Orders", "url": "#"}, {"name": "Completed Orders", "url": "/admin/orders"}],
        "active_menu": "orders",
        "active_sub_menu": "completed_orders",
        "orders": orders_list
    })

@app.get("/users", name="user_list") # Added name
async def user_list(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    
    conn = None
    cursor = None
    users_data = []
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            request.session['flash_messages'] = ["Database connection error. Please try again later."]
            return templates.TemplateResponse("userlist.html", {"request": request, "users": []})
        
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, role, is_active, date_joined FROM accounts_customuser")
        users_raw = cursor.fetchall()
        
        for user_row in users_raw:
            users_data.append({
                "user_id": user_row[0],
                "username": user_row[1],
                "email": user_row[2],
                "role": user_row[3],
                "active": user_row[4],
                "created_at": user_row[5]
            })
    except Exception as e:
        logger.error(f"Error fetching users: {e}", exc_info=True)
        request.session['flash_messages'] = ["Error fetching user list. Please try again."]
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return templates.TemplateResponse("userlist.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Users", "url": "/admin/users"}],
        "active_menu": "users",
        "active_sub_menu": "user_list",
        "users": users_data
    })

@app.get("/users/add", name="add_user_get") # Added name
async def add_user_get(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("add_user.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Users", "url": "/admin/users"}, {"name": "Add User", "url": "/users/add"}],
        "active_menu": "users",
        "active_sub_menu": "add_user"
    })

@app.get("/users/edit/{user_id}", name="edit_user") # Added name
async def edit_user_get(user_id: int, request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    
    conn = None
    cursor = None
    user_data = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            request.session['flash_messages'] = ["Database connection error. Please try again later."]
            return RedirectResponse(url="/admin/users", status_code=302)
        
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, role, is_active FROM accounts_customuser WHERE id = %s", (user_id,))
        user_raw = cursor.fetchone()
        
        if user_raw:
            user_data = {
                "user_id": user_raw[0],
                "username": user_raw[1],
                "email": user_raw[2],
                "role": user_raw[3],
                "is_active": user_raw[4]
            }
        else:
            request.session['flash_messages'] = ["User not found."]
            return RedirectResponse(url="/admin/users", status_code=302)

    except Exception as e:
        logger.error(f"Error fetching user for edit: {e}", exc_info=True)
        request.session['flash_messages'] = ["Error fetching user data. Please try again."]
        return RedirectResponse(url="/admin/users", status_code=302)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return templates.TemplateResponse("edit_user.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Users", "url": "/admin/users"}, {"name": "Edit User", "url": f"/users/edit/{user_id}"}],
        "active_menu": "users",
        "active_sub_menu": "user_list",
        "user": user_data
    })

@app.post("/users/edit/{user_id}", name="edit_user_post") # Added name
async def edit_user_post(
    user_id: int,
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    is_active: bool = Form(False)
):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to perform this action."]
        return RedirectResponse(url="/admin", status_code=302)

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            request.session['flash_messages'] = ["Database connection error. Please try again later."]
            return RedirectResponse(url=f"/admin/users/edit/{user_id}", status_code=302)
        
        cursor = conn.cursor()
        update_query = """
        UPDATE accounts_customuser
        SET username = %s, email = %s, role = %s, is_active = %s
        WHERE id = %s
        """
        cursor.execute(update_query, (username, email, role, is_active, user_id))
        conn.commit()
        request.session['flash_messages'] = [f"User '{username}' updated successfully!"]
        logger.info(f"User '{username}' (ID: {user_id}) updated by user {request.session['user']['username']}")
        return RedirectResponse(url="/admin/users", status_code=302)
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}", exc_info=True)
        request.session['flash_messages'] = [f"Error updating user: {e}"]
        return RedirectResponse(url=f"/admin/users/edit/{user_id}", status_code=302)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.post("/users/add")
async def add_user_post(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("User"),
    is_active: bool = Form(True)
):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to perform this action."]
        return RedirectResponse(url="/admin", status_code=302)
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            request.session['flash_messages'] = ["Database connection error. Please try again later."]
            return RedirectResponse(url="/admin/users/add", status_code=302)
        
        cursor = conn.cursor()
        hashed_password = pwd_context.hash(password)
        cursor.execute(
            "INSERT INTO accounts_customuser (username, email, password, role, is_active, date_joined) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP);",
            (username, email, hashed_password, role, is_active)
        )
        conn.commit()
        request.session['flash_messages'] = [f"User '{username}' added successfully."]
        logger.info(f"User '{username}' added by admin {request.session['user']['username']}")
        return RedirectResponse(url="/admin/users", status_code=302)
    except Exception as e:
        logger.error(f"Error adding user: {e}", exc_info=True)
        request.session['flash_messages'] = [f"Error adding user: {e}"]
        return RedirectResponse(url="/admin/users/add", status_code=302)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.get("/punchout", name="punchout_list") # Added name
async def punchout_list(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    
    conn = None
    cursor = None
    punchout_data = []
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            request.session['flash_messages'] = ["Database connection error. Please try again later."]
            return templates.TemplateResponse("punchout.html", {"request": request, "punchout_list": []})
        
        cursor = conn.cursor()
        cursor.execute("SELECT id, response, created_at FROM punchout_responses")
        punchout_raw = cursor.fetchall()
        
        for row in punchout_raw:
            punchout_data.append({
                "id": row[0],
                "response": row[1],
                "created_at": row[2]
            })
    except Exception as e:
        logger.error(f"Error fetching punchout responses: {e}", exc_info=True)
        request.session['flash_messages'] = ["Error fetching punchout responses. Please try again."]
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return templates.TemplateResponse("punchout.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Punchout Responses", "url": "/admin/punchout"}],
        "active_menu": "punchout",
        "active_sub_menu": "punchout_list",
        "punchout_list": punchout_data
    })

@app.get("/analytics", name="analytics") # Added name
async def analytics(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    
    category_data = get_product_category_counts()
    
    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Analytics", "url": "/admin/analytics"}],
        "active_menu": "analytics",
        "category_data": category_data
    })

@app.get("/settings", name="settings") # Added name
async def settings(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Settings", "url": "/admin/settings"}],
        "active_menu": "settings"
    })

@app.get("/help", name="help_page") # Added name
async def help_page(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("help.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Help", "url": "/admin/help"}],
        "active_menu": "help"
    })

@app.get("/", name="fastapi_root") # This route will catch the '/' passed by Mount('/admin', ...)
async def read_root(request: Request):
    flash_messages = request.session.pop('flash_messages', [])
    if 'user' in request.session:
        # User is logged in, redirect to the dashboard within the /admin path
        return RedirectResponse(url="/admin/dashboard", status_code=302)
    # User is not logged in, show the login page
    # The login form's action should point to /admin/login (as updated previously)
    return templates.TemplateResponse("login.html", {"request": request, "flash_messages": flash_messages})
@app.get("/logout", name="logout") # Added name
async def logout(request: Request):
    request.session.pop('user', None)
    request.session['flash_messages'] = ["You have been logged out."]
    logger.info("User logged out")
    return RedirectResponse(url="/admin/", status_code=302)

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            request.session['flash_messages'] = ["Database connection error. Please try again later."]
            return RedirectResponse(url="/admin", status_code=302)
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, password FROM accounts_customuser WHERE username = %s",
                (username,)
            )
            user = cursor.fetchone()
            if user and pwd_context.verify(password, user[2]):
                request.session['user'] = {'id': user[0], 'username': user[1]}
                request.session['flash_messages'] = ["Welcome to the Kalika E-Commerce."]
                logger.info(f"User {username} logged in successfully")
                return RedirectResponse(url="/admin/dashboard", status_code=302)
            logger.warning(f"Failed login attempt for username: {username}")
            request.session['flash_messages'] = ["Invalid username or password. Please try again."]
            return RedirectResponse(url="/admin", status_code=302)
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        request.session['flash_messages'] = ["Login error. Please try again later."]
        return RedirectResponse(url="/admin", status_code=302)
    finally:
        if 'conn' in locals():
            conn.close()

# --- NEW CATALOG SUBMENU ROUTES ---

@app.get("/categories", name="categories_page")
async def categories_page(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("categories.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Catalog", "url": "#"}, {"name": "Categories", "url": "/admin/categories"}],
        "active_menu": "catalog",
        "active_sub_menu": "categories"
    })

@app.get("/item-options", name="item_options_page")
async def item_options_page(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("item_options.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Catalog", "url": "#"}, {"name": "Item Options", "url": "/admin/item-options"}],
        "active_menu": "catalog",
        "active_sub_menu": "item_options"
    })

@app.get("/inventory", name="inventory_page")
async def inventory_page(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Catalog", "url": "#"}, {"name": "Inventory", "url": "/admin/inventory"}],
        "active_menu": "catalog",
        "active_sub_menu": "inventory"
    })

@app.get("/export-file", name="export_file_page")
async def export_file_page(request: Request):
    if 'user' not in request.session:
        request.session['flash_messages'] = ["Please log in to access this page."]
        return RedirectResponse(url="/admin", status_code=302)
    return templates.TemplateResponse("export_to_xl.html", { # Changed from export_to_csv.html
        "request": request,
        "breadcrumb": [{"name": "Home", "url": "/admin/dashboard"}, {"name": "Catalog", "url": "#"}, {"name": "Export File", "url": "/admin/export-file"}],
        "active_menu": "catalog",
        "active_sub_menu": "export_file"
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
