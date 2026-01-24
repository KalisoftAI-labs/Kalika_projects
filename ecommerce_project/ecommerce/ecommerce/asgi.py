import os
from django.core.asgi import get_asgi_application
from django.conf import settings
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

# Set the settings module for Django BEFORE importing Django app
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce.settings')

# Initialize Django
django_app = get_asgi_application()

# Import the FastAPI app AFTER Django initialization
from fastapi_app.app import app as fastapi_app

# Create the main application with proper routing
application = Starlette(
    routes=[
        Mount('/admin', app=fastapi_app),  # FastAPI admin at /admin
        Mount('/static', app=StaticFiles(directory=str(settings.STATIC_ROOT)), name='static'),  # Static files
        Mount('/', app=django_app),        # Django at root (must be last)
    ],
    middleware=[
        Middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
    ]
)

# import os
# from django.core.asgi import get_asgi_application
# from fastapi.staticfiles import StaticFiles
# # Make sure the import path is correct for your project structure
# # import sys

# # # Add your project base directory to sys.path
# # BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# # PARENT_DIR = os.path.dirname(BASE_DIR)
# # if PARENT_DIR not in sys.path:
# #     sys.path.insert(0, PARENT_DIR)

# from fastapi_app.main import app as fastapi_app

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce.settings')

# # This is the standard Django ASGI application
# django_app = get_asgi_application()

# # This is your FastAPI app instance
# # Mount the FastAPI app at the /admin path.
# # IMPORTANT: This line makes all FastAPI routes available under /admin
# application = fastapi_app
# application.mount("/admin", django_app)

# # This line is for serving FastAPI's own static files if needed
# # The path "/admin-static" must match what's in your FastAPI app.mount()
# application.mount("/admin-static", StaticFiles(directory="fastapi_app/static"), name="admin-static")