from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from .forms import CustomUserCreationForm
import logging

logger = logging.getLogger(__name__)

def login_view(request):
    if request.session.get('is_punchout', False):
        logger.info("PunchOut session detected, redirecting to catalog")
        return redirect('catalog:home')

    if request.user.is_authenticated:
        logger.info(f"Authenticated user {request.user.username} redirected to catalog")
        return redirect('catalog:home')

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            logger.info(f"User {username} logged in successfully")
            return redirect('catalog:home')
        else:
            logger.warning(f"Failed login attempt for username: {username}")
            messages.error(request, 'Invalid username or password.')
    return render(request, 'accounts/login.html')

def register_view(request):
    if request.session.get('is_punchout', False):
        logger.info("PunchOut session detected, redirecting to catalog")
        return redirect('catalog:home')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful. Please log in.')
            logger.info(f"New user registered: {form.cleaned_data['username']}")
            return redirect('accounts:login')
        else:
            logger.warning("Registration form errors: %s", form.errors)
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
        form.helper = FormHelper()
        form.helper.add_input(Submit('submit', 'Register'))
    
    return render(request, 'accounts/register.html', {'form': form})

def logout_view(request):
    logger.info(f"User {request.user.username} logged out")
    logout(request)
    return redirect('catalog:home')