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
        Mount('/fastapi-admin', app=fastapi_app),
        # Mount('/admin', app=fastapi_app),  # FastAPI admin at /admin
        Mount('/static', app=StaticFiles(directory=str(settings.STATIC_ROOT)), name='static'),  # Static files
        Mount('/', app=django_app),        # Django at root (must be last)
    ],
    middleware=[
        Middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
    ]
)

