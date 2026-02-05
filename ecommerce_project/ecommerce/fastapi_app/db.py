# db.py
import psycopg2
from tabulate import tabulate
from datetime import datetime
import logging
from passlib.context import CryptContext
import os

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Database connection parameters from environment variables
db_host = os.getenv('DB_HOST', 'localhost')
db_name = os.getenv('DB_NAME', 'ecom_prod_catalog')
db_user = os.getenv('DB_USER', 'vikas')
db_password = os.getenv('DB_PASSWORD', 'kalika1667')

# Note: In production, ensure these are set in .env file for security
if not all([db_name, db_user, db_password]):
    logger.warning("Database credentials not fully configured. Using defaults.")

def get_db_connection():
    try:
        connection = psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password,
            port='5432'
        )
        logger.info("Database connected")
        return connection
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def view_tables_and_data():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return
        cursor = connection.cursor()
        cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public';
        """)
        tables = cursor.fetchall()
        print("Tables in the database:")
        for table in tables:
            print(f"- {table[0]}")

        # Fetch and display data from accounts_customuser
        cursor.execute("SELECT id, username, email, role, is_active, date_joined FROM accounts_customuser LIMIT 10")
        rows = cursor.fetchall()
        colnames = [desc[0] for desc in cursor.description]
        if rows:
            print(f"\nData from table 'accounts_customuser':")
            print(tabulate(rows, headers=colnames, tablefmt="grid"))
        else:
            print(f"\nNo data found in table 'accounts_customuser'.")

        # Fetch and display data from products
        cursor.execute("SELECT item_id, product_title, price, main_category, sub_categories FROM products LIMIT 5")
        rows = cursor.fetchall()
        colnames = [desc[0] for desc in cursor.description]
        if rows:
            print(f"\nData from table 'products':")
            print(tabulate(rows, headers=colnames, tablefmt="grid"))
        else:
            print(f"\nNo data found in table 'products'.")

        # Fetch and display data from orders
        cursor.execute("SELECT order_id, user_id, order_date, status, total_amount, payment_status FROM orders LIMIT 5")
        rows = cursor.fetchall()
        colnames = [desc[0] for desc in cursor.description]
        if rows:
            print(f"\nData from table 'orders':")
            print(tabulate(rows, headers=colnames, tablefmt="grid"))
        else:
            print(f"\nNo data found in table 'orders'.")

        # Describe the schema of the 'orders' table to verify columns
        print("\n--- Schema of 'orders' table ---")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'orders'
            ORDER BY ordinal_position;
        """)
        orders_schema = cursor.fetchall()
        if orders_schema:
            print(tabulate(orders_schema, headers=["Column Name", "Data Type", "Is Nullable"], tablefmt="grid"))
        else:
            print("Table 'orders' does not exist or has no columns.")

        # Describe the schema of the 'accounts_customuser' table to verify columns
        print("\n--- Schema of 'accounts_customuser' table ---")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'accounts_customuser'
            ORDER BY ordinal_position;
        """)
        user_schema = cursor.fetchall()
        if user_schema:
            print(tabulate(user_schema, headers=["Column Name", "Data Type", "Is Nullable"], tablefmt="grid"))
        else:
            print("Table 'accounts_customuser' does not exist or has no columns.")

        # Describe the schema of the 'punchout_responses' table to verify columns
        print("\n--- Schema of 'punchout_responses' table ---")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'punchout_responses'
            ORDER BY ordinal_position;
        """)
        punchout_schema = cursor.fetchall()
        if punchout_schema:
            print(tabulate(punchout_schema, headers=["Column Name", "Data Type", "Is Nullable"], tablefmt="grid"))
        else:
            print("Table 'punchout_responses' does not exist or has no columns.")


    except Exception as e:
        logger.error(f"Error in view_tables_and_data: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def create_accounts_customuser_table():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return
        cursor = connection.cursor()
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS accounts_customuser (
            id SERIAL PRIMARY KEY,
            username VARCHAR(150) UNIQUE NOT NULL,
            email VARCHAR(254) UNIQUE NOT NULL,
            password VARCHAR(128) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            is_staff BOOLEAN DEFAULT FALSE,
            is_superuser BOOLEAN DEFAULT FALSE,
            date_joined TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP WITH TIME ZONE,
            role VARCHAR(50) DEFAULT 'User',
            buyer_identifier VARCHAR(255) UNIQUE
        );
        '''
        cursor.execute(create_table_query)
        connection.commit()
        logger.info("Table 'accounts_customuser' created or updated successfully")
    except Exception as e:
        logger.error(f"Error creating table 'accounts_customuser': {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def create_users_table():
    """Creates the 'users' table to match dbtest2.py schema."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return
        cursor = connection.cursor()
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        '''
        cursor.execute(create_table_query)
        connection.commit()
        logger.info("Table 'users' created or updated successfully")
    except Exception as e:
        logger.error(f"Error creating table 'users': {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def create_products_table():
    """Creates the 'products' table with item_id as a SERIAL PRIMARY KEY."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection: return
        cursor = connection.cursor()
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS products (
            item_id SERIAL PRIMARY KEY,  -- Changed from INTEGER to SERIAL
            action TEXT,
            main_category TEXT NOT NULL,
            sub_categories TEXT,
            item_code VARCHAR(50) UNIQUE NOT NULL,
            product_title TEXT NOT NULL,
            product_description TEXT,
            upc TEXT,
            brand TEXT,
            department TEXT,
            type TEXT,
            tag TEXT,
            list_price DECIMAL(10, 2),
            price DECIMAL(10, 2) NOT NULL,
            inventory BIGINT,
            min_order_qty BIGINT,
            available TEXT,
            large_image TEXT,
            additional_images TEXT,
            status VARCHAR(50) DEFAULT 'New',
            last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            lead_time VARCHAR(255),
            length VARCHAR(255),
            material_type VARCHAR(255),
            sys_discount_group VARCHAR(255),
            sys_num_images VARCHAR(255),
            sys_product_type VARCHAR(255),
            unit_of_measure VARCHAR(255),
            unspsc VARCHAR(255)
        );
        '''
        cursor.execute(create_table_query)
        connection.commit()
        logger.info("Table 'products' with auto-incrementing item_id ensured to exist.")
    except Exception as error:
        logger.error(f"Error creating 'products' table: {error}")
    finally:
        if cursor: cursor.close()
        if connection: connection.close()

def create_punchout_table():
    create_table_query = """
    CREATE TABLE IF NOT EXISTS punchout_responses (
        id SERIAL PRIMARY KEY,
        response TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return
        cursor = connection.cursor()
        cursor.execute(create_table_query)
        connection.commit()
        logger.info("Table 'punchout_responses' created successfully")
    except Exception as e:
        logger.error(f"Error while creating table: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def insert_sample_data():
    sample_response = """<PunchOutSetupResponse>
        <Response>
            <Status code="200" text="OK" />
        </Response>
        <StartPage>
            <URL>https://example.com/punchout</URL>
        </StartPage>
    </PunchOutSetupResponse>"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return
        cursor = connection.cursor()
        insert_query = "INSERT INTO punchout_responses (response) VALUES (%s);"
        cursor.execute(insert_query, (sample_response,))
        connection.commit()
        logger.info("Sample data inserted into punchout_responses successfully")
    except Exception as e:
        logger.error(f"Error while inserting sample data: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def create_admin_user(username, plain_password, email="admin@example.com", role="Admin", is_active=True):
    """Creates admin user in both users and accounts_customuser tables"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return
        cursor = connection.cursor()

        # Insert into users table (for orders FK)
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        if not cursor.fetchone():
            hashed_password = pwd_context.hash(plain_password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s);",
                (username, email, hashed_password)
            )
            logger.info(f"User '{username}' created in users table.")

        # Insert into accounts_customuser table (for Django compatibility)
        cursor.execute("SELECT id FROM accounts_customuser WHERE username = %s", (username,))
        if cursor.fetchone():
            logger.info(f"User '{username}' already exists in accounts_customuser. Skipping creation.")
        else:
            hashed_password = pwd_context.hash(plain_password)
            cursor.execute(
                "INSERT INTO accounts_customuser (username, email, password, is_active, date_joined, role) VALUES (%s, %s, %s, %s, %s, %s);",
                (username, email, hashed_password, is_active, datetime.now(), role)
            )
            logger.info(f"Admin user '{username}' created in accounts_customuser.")
        
        connection.commit()
    except Exception as e:
        logger.error(f"Error creating admin user: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def insert_sample_user_data(username, plain_password, email, role="User", is_active=True):
    """Creates sample user in both users and accounts_customuser tables"""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return
        cursor = connection.cursor()

        # Insert into users table (for orders FK)
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        if not cursor.fetchone():
            hashed_password = pwd_context.hash(plain_password)
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s);",
                (username, email, hashed_password)
            )
            logger.info(f"Sample user '{username}' created in users table.")

        # Insert into accounts_customuser table (for Django compatibility)
        cursor.execute("SELECT id FROM accounts_customuser WHERE username = %s", (username,))
        if cursor.fetchone():
            logger.info(f"User '{username}' already exists in accounts_customuser. Skipping insertion.")
        else:
            hashed_password = pwd_context.hash(plain_password)
            cursor.execute(
                "INSERT INTO accounts_customuser (username, email, password, is_active, date_joined, role) VALUES (%s, %s, %s, %s, %s, %s);",
                (username, email, hashed_password, is_active, datetime.now(), role)
            )
            logger.info(f"Sample user '{username}' created in accounts_customuser.")
        
        connection.commit()
    except Exception as e:
        logger.error(f"Error inserting sample user data: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def insert_sample_products():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return
        cursor = connection.cursor()

        cursor.execute("SELECT COUNT(*) FROM products")
        if cursor.fetchone()[0] == 0:
            logger.info("Inserting sample products...")
            products_to_insert = [
                ('Electronics', 'Smartphones', 'SMARTPHONE001', 'Smartphone X', 'High-end smartphone with advanced features.', 999.99, 'https://placehold.co/100x100?text=Phone'),
                ('Electronics', 'Laptops', 'LAPTOP001', 'UltraBook Pro', 'Lightweight and powerful laptop for professionals.', 1499.99, 'https://placehold.co/100x100?text=Laptop'),
                ('Apparel', 'T-Shirts', 'TSHIRT001', 'Cotton T-Shirt', 'Comfortable cotton t-shirt for daily wear.', 19.99, 'https://placehold.co/100x100?text=T-Shirt'),
                ('Apparel', 'Jeans', 'JEANS001', 'Slim Fit Jeans', 'Stylish slim fit jeans for men and women.', 49.99, 'https://placehold.co/100x100?text=Jeans'),
                ('Books', 'Fiction', 'BOOKFIC001', 'The Great Novel', 'A captivating story of adventure and mystery.', 15.50, 'https://placehold.co/100x100?text=Book'),
                ('Home & Kitchen', 'Cookware', 'COOKWARE001', 'Non-Stick Pan Set', 'Set of 3 non-stick pans for everyday cooking.', 75.00, 'https://placehold.co/100x100?text=Pan')
            ]
            insert_query = """
            INSERT INTO products (main_category, sub_categories, item_code, product_title, product_description, price, large_image)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.executemany(insert_query, products_to_insert)
            connection.commit()
            logger.info("Sample products inserted successfully.")
        else:
            logger.info("Products table already has data. Skipping sample product insertion.")
    except Exception as e:
        logger.error(f"Error inserting sample products: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def create_orders_table():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return
        cursor = connection.cursor()
        # Drop table if it exists to ensure schema is always correct
        cursor.execute("DROP TABLE IF EXISTS orders CASCADE;")
        connection.commit()
        logger.info("Dropped existing 'orders' table.")

        create_table_query = '''
        CREATE TABLE orders (
            order_id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(50) DEFAULT 'Pending',
            total_amount DECIMAL(10, 2) NOT NULL,
            shipping_address TEXT,
            payment_method VARCHAR(50),
            payment_status VARCHAR(50) DEFAULT 'Unpaid',
            shipping_date TIMESTAMP,
            delivery_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        '''
        cursor.execute(create_table_query)
        connection.commit()
        logger.info("Table 'orders' created successfully")
    except Exception as e:
        logger.error(f"Error creating table: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_user_count():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return 0
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM accounts_customuser")
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"Error fetching user count: {e}")
        return 0
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_product_count():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return 0
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"Error fetching product count: {e}")
        return 0
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_total_sales():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return 0.0
        cursor = connection.cursor()
        # Sum of total_amount for completed orders
        cursor.execute("SELECT COALESCE(SUM(o.total_amount), 0) FROM orders o WHERE o.status = 'Completed'")
        total_sales = cursor.fetchone()[0]
        return float(total_sales)
    except Exception as e:
        logger.error(f"Error fetching total sales: {e}")
        return 0.0
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_pending_orders_count():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        if not connection:
            return 0
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending'")
        count = cursor.fetchone()[0]
        return count
    except Exception as e:
        logger.error(f"Error fetching pending orders count: {e}")
        return 0
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_recent_orders(limit=5):
    connection = None
    cursor = None
    recent_orders = []
    try:
        connection = get_db_connection()
        if not connection:
            return []
        cursor = connection.cursor()
        # Fetch order details and customer username
        cursor.execute("""
            SELECT
                o.order_id,
                u.username AS customer_name,
                o.status,
                o.order_date,
                o.total_amount
            FROM
                orders o
            JOIN
                users u ON o.user_id = u.user_id
            ORDER BY
                o.order_date DESC
            LIMIT %s;
        """, (limit,))
        for row in cursor.fetchall():
            recent_orders.append({
                "order_id": row[0],
                "customer_name": row[1],
                "status": row[2],
                "order_date": row[3],
                "total_amount": row[4]
            })
        return recent_orders
    except Exception as e:
        logger.error(f"Error fetching recent orders: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_product_category_counts():
    connection = None
    cursor = None
    category_counts = []
    try:
        connection = get_db_connection()
        if not connection:
            return []
        cursor = connection.cursor()
        cursor.execute("""
            SELECT main_category, COUNT(*) as count
            FROM products
            GROUP BY main_category
            ORDER BY count DESC;
        """)
        for row in cursor.fetchall():
            category_counts.append({
                "category": row[0],
                "count": row[1]
            })
        return category_counts
    except Exception as e:
        logger.error(f"Error fetching product category counts: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Drop all tables in correct order to handle foreign key dependencies
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS orders CASCADE;")
            cursor.execute("DROP TABLE IF EXISTS products CASCADE;")
            cursor.execute("DROP TABLE IF EXISTS punchout_responses CASCADE;")
            cursor.execute("DROP TABLE IF EXISTS users CASCADE;")
            cursor.execute("DROP TABLE IF EXISTS accounts_customuser CASCADE;")
            conn.commit()
            logger.info("Dropped all existing tables for a clean slate.")
        except Exception as e:
            logger.error(f"Error dropping tables: {e}")
        finally:
            if cursor: cursor.close()
            if conn: conn.close()

    # Recreate all tables
    create_users_table()  # Create users table first (required by orders FK)
    create_accounts_customuser_table()
    create_products_table()
    create_punchout_table()
    create_orders_table() # This will now be created cleanly after dependencies

    # Insert sample data
    create_admin_user("admin", "password123")
    insert_sample_user_data("testuser", "testpassword", "test@example.com", "User", True)
    insert_sample_products()
    
    # Insert some sample orders for dashboard data
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM orders")
            if cursor.fetchone()[0] == 0:
                logger.info("Inserting sample orders...")
                # Ensure user_id exists from sample data
                # Assuming admin (user_id 1) and testuser (user_id 2) exist
                cursor.execute("INSERT INTO orders (user_id, total_amount, status, order_date) VALUES (1, 1999.98, 'Completed', CURRENT_TIMESTAMP - INTERVAL '5 days');")
                cursor.execute("INSERT INTO orders (user_id, total_amount, status, order_date) VALUES (1, 1499.99, 'Pending', CURRENT_TIMESTAMP - INTERVAL '2 days');")
                cursor.execute("INSERT INTO orders (user_id, total_amount, status, order_date) VALUES (2, 99.95, 'Completed', CURRENT_TIMESTAMP - INTERVAL '10 days');")
                cursor.execute("INSERT INTO orders (user_id, total_amount, status, order_date) VALUES (2, 49.99, 'Pending', CURRENT_TIMESTAMP - INTERVAL '1 day');")
                cursor.execute("INSERT INTO orders (user_id, total_amount, status, order_date) VALUES (1, 15.50, 'Completed', CURRENT_TIMESTAMP - INTERVAL '3 days');")
                conn.commit()
                logger.info("Sample orders inserted.")
            else:
                logger.info("Orders table already has data. Skipping sample order insertion.")
        except Exception as e:
            logger.error(f"Error inserting sample orders: {e}")
        finally:
            if 'cursor' in locals() and cursor: cursor.close()
            if 'conn' in locals() and conn: conn.close()

    view_tables_and_data()