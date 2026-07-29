

-----
# 🛒 E-commerce PunchOut Catalog (Django)

This project is a Django-based PunchOut Catalog system designed for B2B e-procurement. It enables suppliers to receive and process PunchOut orders from enterprise procurement systems using cXML. The system is built with a PostgreSQL backend, making it a robust solution for production environments.

<p align="center">
  <img src="architecture.gif" alt="Architecture Diagram">
</p>



-----

## 🚀 Features

  - **Django Backend**: A high-level Python web framework for rapid and secure development.
  - **PostgreSQL Database**: A powerful, open-source object-relational database system.
  - **cXML PunchOut Support**: Captures and stores PunchOut orders directly from procurement platforms.
  - **Session-Based Order Tracking**: Manages cXML orders using Django's session framework.
  - **Deployment Ready**: Includes `collectstatic` for streamlined static file management in production.

-----

## 📦 Local Project Setup

Follow these steps to get the project running on your local machine for development and testing.

### 1\. Clone the Repository

First, clone the project from its GitHub repository to your local machine.

```bash
git clone https://github.com/your-username/ecom-punchout-catalog.git
cd ecom-punchout-catalog
```

### 2\. Create and Activate a Virtual Environment

It's a best practice to use a virtual environment to manage project-specific dependencies.

```bash
# Create the virtual environment
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on macOS/Linux
source venv/bin/activate
```

### 3\. Install Requirements

Install all the necessary Python packages listed in the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 4\. Configure PostgreSQL

This project uses PostgreSQL as its database.

#### **Download and Install PostgreSQL**

If you don't have it installed, download it from the official site:
[PostgreSQL Downloads](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads)

#### **Create the Database and User**

Connect to PostgreSQL and run the following SQL commands to set up the database and a dedicated user.

```sql
-- Create the database
CREATE DATABASE ecom_prod_catalog;

-- Create a user with a secure password
CREATE USER vikas WITH PASSWORD 'kalika1667';

-- Grant all privileges on the database to the new user
GRANT ALL PRIVILEGES ON DATABASE ecom_prod_catalog TO vikas;
```

#### **Create the `punchout_orders` Table**

This table will store the incoming PunchOut cXML data.

```sql
-- Connect to the newly created database before running this
\c ecom_prod_catalog

-- Create the table
CREATE TABLE punchout_orders (
    id BIGSERIAL PRIMARY KEY,
    session_key VARCHAR(40) NOT NULL,
    cxml_data TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    supplier_id VARCHAR(255),
    punchout_request_url VARCHAR(500),
    punchout_response_url VARCHAR(500),
    total_amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR'
);

-- Grant table access to the user
GRANT ALL PRIVILEGES ON TABLE punchout_orders TO vikas;
```

### 5\. Load Product Data into the Database

A script is provided to load product data from a CSV file into your database.

1.  **Locate the Script**: Open the `dbtest2.py` file in your project.

2.  **Update File Path**: Change the placeholder for the CSV file path to the actual path of your `kalika_catalog_products_s31.csv` file.

3.  **Run the Script**:

    ```bash
    python dbtest2.py
    ```

### 6\. Run Django Migrations and Server

With the database configured, apply Django's migrations and start the development server.

```bash
# Create and apply database migrations
python manage.py makemigrations
python manage.py migrate

# Collect static files (for deployment, but good practice)
python manage.py collectstatic

# Start the development server
python manage.py runserver
```

You can now access the application at `http://127.0.0.1:8000/`.

**Important Note**: Before committing and pushing your code, ensure that your `.env` file (containing sensitive credentials) is listed in your `.gitignore` file to prevent it from being exposed.

-----

# ☁️ Deploying on AWS EC2

This guide outlines the process for deploying your Django project to a production environment on an AWS EC2 instance using Gunicorn as the application server and Nginx as a reverse proxy.

## Prerequisites

  - An active AWS account with permission to manage EC2 instances.
  - Your EC2 SSH key pair (`.pem` file) for secure access.
  - A domain name that you can point to your EC2 instance's IP address.
  - Basic familiarity with the Linux command line.

### 1\. Launch and Connect to EC2

1.  From the AWS Management Console, launch a new **Ubuntu** EC2 instance.

2.  Once the instance is running, select it and click **Connect**.

3.  Use the provided SSH command to connect.

    ```bash
    # Replace with your actual .pem file and public DNS
    ssh -i "your-key.pem" ubuntu@ec2-public-dns.compute-1.amazonaws.com
    ```

### 2\. (Optional) Fix PEM File Permissions on Windows

If you encounter a "public key" error on Windows, open PowerShell as an Administrator and run these commands to reset permissions.

```powershell
icacls.exe your-key.pem /reset
icacls.exe your-key.pem /grant:r "$($env:username):(R)"
icacls.exe your-key.pem /inheritance:r
```

### 3\. Install and Configure PostgreSQL on EC2

Update the server's package list and install PostgreSQL.

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y postgresql postgresql-contrib
```

Switch to the `postgres` user to configure the database.

```bash
sudo -i -u postgres
psql
```

Inside the `psql` shell, execute the following commands.

```sql
-- Set a password for the default postgres user
\password postgres -- (e.g., enter 'kalika1667')

-- Create the application database and user
CREATE DATABASE ecom_prod_catalog;
CREATE USER vikas WITH PASSWORD 'kalika1667';

-- Grant connection privileges
GRANT CONNECT ON DATABASE ecom_prod_catalog TO vikas;

-- Connect to the new database to grant further permissions
\c ecom_prod_catalog

-- Grant all privileges on future tables and sequences in the public schema
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO vikas;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO vikas;

-- Exit psql and the postgres user session
\q
exit
```

### 4\. Clone Your Project

Clone your project repository onto the EC2 instance.

```bash
git clone --branch Kalika_project_Django https://github.com/KalisoftAI/Kalika_projects.git
cd Kalika_projects/
```

### 5\. Set Up Python Environment

Install `pip` and `venv`, then create and activate a virtual environment.

```bash
sudo apt install python3-pip python3.12-venv -y
python3 -m venv env
source env/bin/activate
```

### 6\. Install Project Dependencies

Install the required Python packages into your virtual environment.

```bash
pip install -r requirements.txt
```

### 7\. Configure Django and Run Migrations

1.  **Environment Variables**: Create a `.env` file and add your database URL and other secrets. Make sure your `settings.py` is configured to read these variables.
2.  **Run Migrations**: Apply migrations to set up your schema in the PostgreSQL database.
    ```bash
    cd ecommerce_project/ecommerce # Navigate to the directory with manage.py
    python manage.py migrate
    ```
3.  **Collect Static Files**: Gather all static files into a single directory for Nginx to serve.
    ```bash
    python manage.py collectstatic
    ```

### 8\. Install and Configure Gunicorn

Gunicorn will serve as the WSGI HTTP server for your Django application.

```bash
pip install gunicorn
```

Create a `systemd` service file to manage the Gunicorn process.

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Paste the following configuration, **updating the paths** to match your project structure.

```ini
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce
ExecStart=/home/ubuntu/Kalika_projects/env/bin/gunicorn --workers 3 --bind unix:/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/ecommerce.sock ecommerce.wsgi:application

[Install]
WantedBy=multi-user.target
```

Start and enable the Gunicorn service.

```bash
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```

### 9\. Install and Configure Nginx

Nginx will act as a reverse proxy, forwarding client requests to Gunicorn and serving static files.

```bash
sudo apt install nginx -y
```

#### **Copy SSL Certificates**

From your **local machine**, securely copy your SSL certificate and private key to the EC2 instance.

```powershell
# Replace paths and IP with your own
scp -i "your-key.pem" "path/to/your_domain.crt" ubuntu@your-ec2-ip:~/
scp -i "your-key.pem" "path/to/your_domain.key" ubuntu@your-ec2-ip:~/
```

On the **EC2 instance**, move the certificates to the Nginx directory and set secure permissions.

```bash
sudo mkdir -p /etc/nginx/ssl
sudo mv your_domain.crt /etc/nginx/ssl/
sudo mv your_domain.key /etc/nginx/ssl/
sudo chown -R root:root /etc/nginx/ssl
sudo chmod 600 /etc/nginx/ssl/your_domain.key
sudo chmod 644 /etc/nginx/ssl/your_domain.crt
```

#### **Create Nginx Server Block**

Edit the default Nginx configuration file.

```bash
sudo nano /etc/nginx/sites-available/default
```

Replace its content with the following server block, **adjusting server\_name, SSL paths, and file paths**.

```nginx
server {
    listen 80;
    server_name your_domain.com www.your_domain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your_domain.com www.your_domain.com;

    ssl_certificate /etc/nginx/ssl/your_domain.crt;
    ssl_certificate_key /etc/nginx/ssl/your_domain.key;

    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location /static/ {
        alias /home/ubuntu/Kalika_projects/staticfiles/;
    }

    location /media/ {
        alias /home/ubuntu/Kalika_projects/mediafiles/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/ecommerce.sock;
    }
}
```

Test the Nginx configuration and restart the service.

```bash
sudo nginx -t
sudo systemctl restart nginx
```

### 10\. Final Verification

1.  **Check Service Status**: Ensure PostgreSQL, Gunicorn, and Nginx are all active and running without errors.
    ```bash
    sudo systemctl status postgresql
    sudo systemctl status gunicorn
    sudo systemctl status nginx
    ```
2.  **Adjust Security Group**: In your AWS EC2 console, ensure your instance's security group allows inbound traffic on port 80 (HTTP) and port 443 (HTTPS).
3.  **Visit Your Domain**: Open your browser and navigate to `https://your_domain.com`.

Congratulations\! Your Django project is now successfully deployed and running in a production environment.


