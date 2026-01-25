import time
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from .models import Product
from django.db.models import Q
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
import logging
from cart.models import CartItem
from urllib.parse import unquote
from django.db.models import Q, Count
from django.conf import settings

logger = logging.getLogger(__name__)

# This is the master list of main categories that will appear in your menu.
DEFINED_MAIN_CATEGORIES = [
    "Safety", "Janitorial", "Packaging", "Facility Maintenance",
    "Chemicals & Lubricants", "Abrasives", "Adhesives, Sealants & Tape",
    "Hand & Power Tools", "Pneumatics", "Cutting Tools", "Welding Tools",
    "Measuring Instruments & Tools", "Mechanical Power Transmission",
    "ACCESSORIES", "STATIONERY", "Appliances And Utilities", "WAVE PROJECT",
    "Plastic Bags", "PTFE HOSE CTCI",
]

# This is a blocklist to filter out unwanted sub-category names.
SUB_CATEGORY_BLOCKLIST = ["home", "system", "menu1", "shop", ""]

def build_category_context():
    """
    Builds the nested dictionary for the header menu, including products for each subcategory.
    Uses efficient database queries to fetch main categories, subcategories, and up to 5 products per subcategory.
    """
    category_structure = {main_cat: {'subcategories': {}, 'product_count': 0} for main_cat in DEFINED_MAIN_CATEGORIES}

    # Count products per main category and build subcategory structure with products
    for main_cat in DEFINED_MAIN_CATEGORIES:
        category_structure[main_cat]['product_count'] = Product.objects.filter(main_category=main_cat).count()
        
        # CORRECTED: Changed lookups to use double underscores (e.g., __isnull)
        subcategories = Product.objects.filter(main_category=main_cat).exclude(
            Q(sub_categories__isnull=True) | Q(sub_categories__exact='') | Q(sub_categories__in=SUB_CATEGORY_BLOCKLIST)
        ).values('sub_categories').distinct()
        
        for sub_cat in subcategories:
            sub_cat_name = sub_cat['sub_categories']
            product_count = Product.objects.filter(main_category=main_cat, sub_categories=sub_cat_name).count()
            
            # Fetch up to 5 products for the subcategory
            products = Product.objects.filter(
                main_category=main_cat,
                sub_categories=sub_cat_name
            ).exclude(
                sub_categories__in=SUB_CATEGORY_BLOCKLIST
            ).values('item_id', 'product_title')[:5]
            
            category_structure[main_cat]['subcategories'][sub_cat_name] = {
                'name': sub_cat_name,
                'product_count': product_count,
                'products': list(products)
            }

    # Convert to final format
    final_categories_data = {}
    for main_cat in DEFINED_MAIN_CATEGORIES:
        if main_cat in category_structure:
            subcategories_list = sorted([
                sub_data for sub_key, sub_data in category_structure[main_cat]['subcategories'].items()
            ], key=lambda x: x['name'])
            final_categories_data[main_cat] = {
                'subcategories': subcategories_list,
                'product_count': category_structure[main_cat]['product_count']
            }

    # Limit to first 10 main categories for dropdown
    limited_categories = dict(list(final_categories_data.items())[:10])
    return limited_categories

def get_s3_presigned_url(bucket_name, object_key, expiration=3600):
    try:
        object_key = object_key.lstrip('/')
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        return s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expiration
        )
    except ClientError as e:
        logger.error(f"Error generating pre-signed URL for {object_key}: {e}")
        return None

def add_s3_urls_to_products(products):
    """
    Optimized version with caching to prevent excessive S3 API calls.
    Caches S3 URLs for 1 hour per product.
    """
    from django.core.cache import caches
    
    # Use dedicated product_images cache
    image_cache = caches['product_images']
    default_image_url = f"{settings.STATIC_URL}images/noimage.jpg"

    for product in products:
        # Generate cache key based on product ID and image path
        cache_key = f"s3_url_{product.item_id}_{hash(product.large_image or '')}"
        
        # Try to get cached URL first
        cached_url = image_cache.get(cache_key)
        if cached_url:
            product.s3_image_url = cached_url
            continue  # Skip S3 API call, use cached URL
        
        # If not cached, generate S3 URL
        if product.large_image and 'noimage.jpg' not in product.large_image:
            image_key = product.large_image.lstrip('/')
            
            # Try to generate the secure S3 URL
            presigned_url = get_s3_presigned_url(
                settings.AWS_S3_BUCKET_NAME,
                image_key
            )

            if presigned_url:
                product.s3_image_url = presigned_url
                # Cache the successful URL for 1 hour
                image_cache.set(cache_key, presigned_url, timeout=3600)
            else:
                product.s3_image_url = default_image_url
                # Cache default image for shorter time (5 minutes)
                image_cache.set(cache_key, default_image_url, timeout=300)
        else:
            product.s3_image_url = default_image_url
            # Cache default image
            image_cache.set(cache_key, default_image_url, timeout=300)
        
    return products

def home(request):
    """
    Optimized home view with efficient batch product fetching.
    Instead of calling add_s3_urls_to_products 15+ times, we call it once.
    """
    from django.core.cache import cache
    
    # Try to get cached homepage products (cache for 5 minutes)
    cache_key = 'homepage_products_v2'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        products_by_category = cached_data
    else:
        # Fetch products for various categories dynamically
        products_by_category = {}
        current_minute = int(time.time() // 60)
        
        # Collect all products in one go to minimize queries
        all_products_list = []
        category_products_map = {}
        
        for category in DEFINED_MAIN_CATEGORIES:
            all_products = Product.objects.filter(
                main_category__icontains=category.split(" ")[0]
            ).exclude(large_image__icontains='noimage.jpg')
            
            total = all_products.count()
            offset = ((current_minute // 9) * 9) % max(1, total)
            
            if total <= 10:
                products = list(all_products)
            else:
                end = offset + 10
                if end <= total:
                    products = list(all_products[offset:end])
                else:
                    products = list(all_products[offset:]) + list(all_products[:end - total])
            
            category_products_map[category] = products
            all_products_list.extend(products)
        
        # Call add_s3_urls_to_products ONCE for all products
        add_s3_urls_to_products(all_products_list)
        
        # Now assign processed products back to categories
        products_by_category = category_products_map
        
        # Cache for 5 minutes (300 seconds)
        cache.set(cache_key, products_by_category, timeout=300)

    # Generate presigned URL for the video (cache this too)
    video_cache_key = 'homepage_video_url'
    video_url = cache.get(video_cache_key)
    
    if not video_url:
        video_key = '/kalika-images/kalika-ad1.mp4'
        video_url = get_s3_presigned_url(
            bucket_name=settings.AWS_S3_BUCKET_NAME,
            object_key=video_key,
            expiration=3600  # URL valid for 1 hour
        )
        # Cache video URL for 50 minutes (slightly less than expiration)
        cache.set(video_cache_key, video_url, timeout=3000)

    context = {
        'products_by_category': products_by_category,
        'featured_products': products_by_category.get("Hand & Power Tools", [])[:10],
        'categories': build_category_context(),
        'hero_video_url': video_url,
    }
    return render(request, 'catalog/home.html', context)

def product_list(request):
    products = Product.objects.all()
    products_with_urls = add_s3_urls_to_products(products)

    context = {
        'products': products_with_urls,
        'categories': build_category_context()
    }
    return render(request, 'catalog/product_list.html', context)

def product_detail(request, item_id):
    product = get_object_or_404(Product, item_id=item_id)
    if product.large_image:
        product.s3_image_url = get_s3_presigned_url(settings.AWS_S3_BUCKET_NAME, product.large_image.lstrip('/'))
    else:
        product.s3_image_url = None

    context = {
        'product': product,
        'categories': build_category_context()
    }
    return render(request, 'catalog/product_detail.html', context)

def products_by_category(request, main_category_name):
    # Get all products for the main category
    products = Product.objects.filter(main_category=main_category_name)
    products_with_urls = add_s3_urls_to_products(products)

    # CORRECTED: Use .annotate() to dynamically count products for each subcategory
    subcategories_qs = Product.objects.filter(
        main_category=main_category_name
    ).exclude(
        Q(sub_categories__isnull=True) | Q(sub_categories__exact='')
    ).values('sub_categories').annotate(
        product_count=Count('item_id')
    ).order_by('sub_categories')

    # Convert the queryset to the list format the template expects
    subcategories_list = [
        {'name': item['sub_categories'], 'product_count': item['product_count']}
        for item in subcategories_qs
    ]

    context = {
        'main_category': main_category_name,
        'products': products_with_urls,
        'subcategories_list': subcategories_list,  # Pass the correctly formatted list
        'categories': build_category_context()    # For the main header menu
    }
    return render(request, 'catalog/products_by_category.html', context)

def products_by_subcategory(request, main_category_name, sub_category_name):
    # Decode URL-encoded subcategory name
    decoded_sub_category = unquote(sub_category_name)
    logger.debug(f"Fetching products for main_category: {main_category_name}, raw sub_categories: {sub_category_name}, decoded sub_categories: {decoded_sub_category}")
    
    # Filter products with case-insensitive exact match, excluding blocklisted subcategories
    products = Product.objects.filter(
        main_category__iexact=main_category_name,
        sub_categories__iexact=decoded_sub_category
    ).exclude(sub_categories__in=SUB_CATEGORY_BLOCKLIST)
    
    if not products.exists():
        logger.warning(f"No products found for main_category: {main_category_name}, sub_categories: {decoded_sub_category}")
        messages.warning(request, f"No products found for {decoded_sub_category} in {main_category_name}.")
    
    products_with_urls = add_s3_urls_to_products(products)

    context = {
        'main_category': main_category_name,
        'sub_category': decoded_sub_category,
        'products': products_with_urls,
        'categories': build_category_context()
    }
    return render(request, 'catalog/products_by_subcategory.html', context)

def all_categories(request):
    categories_data = {}
    main_categories_queryset = (
        Product.objects
        .values_list('main_category', flat=True)
        .distinct()
        .exclude(main_category__isnull=True)
        .exclude(main_category__exact='')
        .order_by('main_category')
    )

    for main_cat in main_categories_queryset:
        subcategories_queryset = (
            Product.objects
            .filter(main_category=main_cat)
            .values_list('sub_categories', flat=True)
            .distinct()
            .exclude(sub_categories__isnull=True)
            .exclude(sub_categories__exact='')
            .exclude(sub_categories__in=SUB_CATEGORY_BLOCKLIST)
            .order_by('sub_categories')
        )
        subcategories_list = [{'name': sub_cat_name} for sub_cat_name in subcategories_queryset]
        if subcategories_list:
            categories_data[main_cat] = {'subcategories': subcategories_list}
    context = {
        'categories': categories_data,
        'categories_menu': build_category_context()
    }
    return render(request, 'catalog/all_categories.html', context)

def search_products(request):
    query = request.GET.get('query', '').strip()
    products = []
    if query:  # Only perform query if non-empty
        products = Product.objects.filter(
            Q(product_title__icontains=query) |
            Q(main_category__icontains=query) |
            Q(sub_categories__icontains=query)
        ).exclude(
            Q(sub_categories__in=SUB_CATEGORY_BLOCKLIST) |
            Q(main_category__isnull=True) |
            Q(main_category__exact='')
        ).distinct()[:12]
    products_with_urls = add_s3_urls_to_products(products)

    context = {
        'products': products_with_urls,
        'query': query,
        'categories': build_category_context()
    }
    return render(request, 'catalog/search_results.html', context)