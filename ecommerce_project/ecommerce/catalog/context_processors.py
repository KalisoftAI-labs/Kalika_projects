from .models import Product
from cart.models import CartItem
from django.db.models import Q

# Define main categories and blocklist as in old module
DEFINED_MAIN_CATEGORIES = [
    "Safety", "Janitorial", "Packaging", "Facility Maintenance",
    "Chemicals & Lubricants", "Abrasives", "Adhesives, Sealants & Tape",
    "Hand & Power Tools", "Pneumatics", "Cutting Tools", "Welding Tools",
    "Measuring Instruments & Tools", "Mechanical Power Transmission",
    "ACCESSORIES", "STATIONERY", "Appliances And Utilities", "WAVE PROJECT",
    "Plastic Bags", "PTFE HOSE CTCI",
]
SUB_CATEGORY_BLOCKLIST = ["home", "system", "menu1", "shop", ""]

def categories(request):
    category_structure = {main_cat: {'subcategories': {}, 'product_count': 0} for main_cat in DEFINED_MAIN_CATEGORIES}

    # Fetch all relevant product fields in a single query
    products_for_categories = Product.objects.filter(
        main_category__in=DEFINED_MAIN_CATEGORIES
    ).exclude(
        Q(sub_categories__isnull=True) | Q(sub_categories__exact='') | Q(sub_categories__in=SUB_CATEGORY_BLOCKLIST)
    ).values('main_category', 'sub_categories').distinct().order_by('main_category', 'sub_categories')

    # Count products per main category and subcategory
    for main_cat in DEFINED_MAIN_CATEGORIES:
        category_structure[main_cat]['product_count'] = Product.objects.filter(main_category=main_cat).count()
        subcategories = Product.objects.filter(main_category=main_cat).exclude(
            Q(sub_categories__isnull=True) | Q(sub_categories__exact='') | Q(sub_categories__in=SUB_CATEGORY_BLOCKLIST)
        ).values('sub_categories').distinct()
        for sub_cat in subcategories:
            sub_cat_name = sub_cat['sub_categories']
            product_count = Product.objects.filter(main_category=main_cat, sub_categories=sub_cat_name).count()
            category_structure[main_cat]['subcategories'][sub_cat_name] = {'name': sub_cat_name, 'product_count': product_count}

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
    return {'categories': limited_categories}

def cart_item_count(request):
    if not request.session.session_key:
        request.session.create()
    cart_items = CartItem.objects.filter(session_key=request.session.session_key)
    total_quantity = sum(item.quantity for item in cart_items)
    return {'cart_item_count': total_quantity}

def punchout_context(request):
    """Add punchout session info to all templates for preserving session across navigation."""
    punchout_session = request.GET.get('punchout_session')
    is_punchout = request.session.get('is_punchout', False) or bool(punchout_session)
    
    return {
        'punchout_session': punchout_session or (request.session.session_key if is_punchout else None),
        'is_punchout': is_punchout,
    }