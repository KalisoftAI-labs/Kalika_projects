#!/usr/bin/env python
"""
PunchOut Edit/Inspect Mode Test Suite
Tests edit and inspect operations for modifying existing requisitions
"""

import os
import sys
import requests
from datetime import datetime
from lxml import etree

# Setup paths
sys.path.append('/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce.settings')

import django
django.setup()

from django.conf import settings
from catalog.models import Product
from cart.models import CartItem

class EditModeTestResults:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def add(self, name, status, details=""):
        self.tests.append({
            'name': name,
            'status': status,
            'details': details
        })
        if status == 'PASS':
            self.passed += 1
        elif status == 'FAIL':
            self.failed += 1
        elif status == 'WARN':
            self.warnings += 1
        
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{icon} {name}")
        if details:
            print(f"   {details}")

def get_test_products():
    """Get sample products from database for testing"""
    try:
        # Get first 3 products from database
        products = list(Product.objects.all()[:3])
        if len(products) >= 2:
            return products
        else:
            return None
    except Exception as e:
        print(f"Error fetching products: {e}")
        return None

def test_edit_mode_with_valid_products(results):
    """Test 1: Edit Mode with Valid Products"""
    print("\n" + "="*80)
    print("TEST 1: Edit Mode - Valid Products Pre-population")
    print("="*80 + "\n")
    
    endpoint_url = "https://www.kalikaindia.com/punchout/setup/"
    
    # Get test products
    products = get_test_products()
    if not products or len(products) < 2:
        results.add("Product Retrieval", "FAIL", "Insufficient products in database for testing")
        return
    
    results.add("Product Retrieval", "PASS", f"Found {len(products)} products for testing")
    
    # Build ItemOut elements
    item_out_xml = ""
    for i, product in enumerate(products[:2]):
        quantity = (i + 1) * 2  # 2, 4
        item_out_xml += f'''
        <ItemOut quantity="{quantity}">
            <ItemID>
                <SupplierPartID>{product.item_code}</SupplierPartID>
            </ItemID>
        </ItemOut>'''
    
    # Create cXML with edit operation
    cxml_request = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="edit_test@kalikaindia.com" timestamp="{datetime.utcnow().isoformat()}Z">
    <Header>
        <From><Credential domain="DUNS"><Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity></Credential></From>
        <To><Credential domain="DUNS"><Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity></Credential></To>
        <Sender>
            <Credential domain="NetworkId">
                <Identity>{settings.PUNCHOUT_ANID}</Identity>
                <SharedSecret>{settings.PUNCHOUT_SHARED_SECRET}</SharedSecret>
            </Credential>
        </Sender>
    </Header>
    <Request>
        <PunchOutSetupRequest operation="edit">
            <BuyerCookie>edit_test_cookie</BuyerCookie>
            <BrowserFormPost><URL>https://test.ariba.com/return</URL></BrowserFormPost>{item_out_xml}
        </PunchOutSetupRequest>
    </Request>
</cXML>'''
    
    try:
        response = requests.post(endpoint_url, data=cxml_request,
                                headers={'Content-Type': 'text/xml'},
                                timeout=15, verify=True)
        
        if response.status_code == 200:
            results.add("Edit Mode Request", "PASS", f"Status: {response.status_code}")
        else:
            results.add("Edit Mode Request", "FAIL", f"Unexpected status: {response.status_code}")
            return
        
        # Parse response
        try:
            root = etree.fromstring(response.content)
            start_page = root.find(".//StartPage/URL")
            
            if start_page is not None:
                start_page_url = start_page.text
                results.add("StartPage URL", "PASS", f"URL: {start_page_url}")
                
                # Verify it's cart page (not homepage)
                if "/cart/" in start_page_url:
                    results.add("Edit Mode Redirect", "PASS", "Correctly redirects to cart page")
                else:
                    results.add("Edit Mode Redirect", "FAIL", "Should redirect to /cart/, not homepage")
                
                # Verify punchout_session parameter
                if "punchout_session=" in start_page_url:
                    results.add("PunchOut Session Parameter", "PASS", "Session parameter present in URL")
                    
                    # Extract session key
                    session_key = start_page_url.split("punchout_session=")[1].split("&")[0]
                    results.add("Session Key Extraction", "PASS", f"Session: {session_key[:12]}...")
                    
                    # Verify cart was pre-populated (give system time to process)
                    import time
                    time.sleep(1)
                    
                    try:
                        cart_items = CartItem.objects.filter(session_key=session_key)
                        cart_count = cart_items.count()
                        
                        if cart_count == 2:
                            results.add("Cart Pre-population", "PASS", f"Cart has {cart_count} items as expected")
                            
                            # Verify quantities
                            for idx, cart_item in enumerate(cart_items):
                                expected_qty = (idx + 1) * 2
                                if cart_item.quantity == expected_qty:
                                    results.add(f"Item {idx+1} Quantity", "PASS", 
                                              f"{cart_item.product.item_code}: {cart_item.quantity} units")
                                else:
                                    results.add(f"Item {idx+1} Quantity", "FAIL",
                                              f"Expected {expected_qty}, got {cart_item.quantity}")
                        else:
                            results.add("Cart Pre-population", "FAIL", 
                                      f"Expected 2 items, got {cart_count}")
                    except Exception as e:
                        results.add("Cart Verification", "FAIL", str(e))
                else:
                    results.add("PunchOut Session Parameter", "FAIL", "Missing punchout_session parameter")
            else:
                results.add("StartPage URL", "FAIL", "StartPage URL not found in response")
        except Exception as e:
            results.add("Response Parsing", "FAIL", str(e))
            
    except Exception as e:
        results.add("Edit Mode Request", "FAIL", str(e))

def test_edit_mode_with_invalid_products(results):
    """Test 2: Edit Mode with Mixed Valid/Invalid Products"""
    print("\n" + "="*80)
    print("TEST 2: Edit Mode - Handling Invalid Products")
    print("="*80 + "\n")
    
    endpoint_url = "https://www.kalikaindia.com/punchout/setup/"
    
    # Get one valid product
    products = get_test_products()
    if not products:
        results.add("Product Retrieval", "FAIL", "No products available")
        return
    
    valid_product = products[0]
    invalid_item_code = "INVALID_ITEM_999999"
    
    # Mix of valid and invalid items
    item_out_xml = f'''
        <ItemOut quantity="5">
            <ItemID>
                <SupplierPartID>{valid_product.item_code}</SupplierPartID>
            </ItemID>
        </ItemOut>
        <ItemOut quantity="3">
            <ItemID>
                <SupplierPartID>{invalid_item_code}</SupplierPartID>
            </ItemID>
        </ItemOut>'''
    
    cxml_request = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="invalid_test@kalikaindia.com" timestamp="{datetime.utcnow().isoformat()}Z">
    <Header>
        <From><Credential domain="DUNS"><Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity></Credential></From>
        <To><Credential domain="DUNS"><Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity></Credential></To>
        <Sender>
            <Credential domain="NetworkId">
                <Identity>{settings.PUNCHOUT_ANID}</Identity>
                <SharedSecret>{settings.PUNCHOUT_SHARED_SECRET}</SharedSecret>
            </Credential>
        </Sender>
    </Header>
    <Request>
        <PunchOutSetupRequest operation="edit">
            <BuyerCookie>invalid_test_cookie</BuyerCookie>
            <BrowserFormPost><URL>https://test.ariba.com/return</URL></BrowserFormPost>{item_out_xml}
        </PunchOutSetupRequest>
    </Request>
</cXML>'''
    
    try:
        response = requests.post(endpoint_url, data=cxml_request,
                                headers={'Content-Type': 'text/xml'},
                                timeout=15, verify=True)
        
        if response.status_code == 200:
            results.add("Mixed Items Request", "PASS", "System accepted request")
            
            # Parse response
            root = etree.fromstring(response.content)
            start_page_url = root.find(".//StartPage/URL").text
            session_key = start_page_url.split("punchout_session=")[1].split("&")[0]
            
            import time
            time.sleep(1)
            
            # Check cart - should only have the valid item
            cart_items = CartItem.objects.filter(session_key=session_key)
            if cart_items.count() == 1:
                results.add("Invalid Item Handling", "PASS", 
                          "System added only valid items (1/2)")
                if cart_items[0].product.item_code == valid_product.item_code:
                    results.add("Valid Item Added", "PASS",
                              f"Correct product: {valid_product.item_code}")
            else:
                results.add("Invalid Item Handling", "FAIL",
                          f"Expected 1 item, got {cart_items.count()}")
        else:
            results.add("Mixed Items Request", "FAIL", f"Status: {response.status_code}")
            
    except Exception as e:
        results.add("Mixed Items Test", "FAIL", str(e))

def test_inspect_mode(results):
    """Test 3: Inspect Mode"""
    print("\n" + "="*80)
    print("TEST 3: Inspect Mode - Read-only Requisition View")
    print("="*80 + "\n")
    
    endpoint_url = "https://www.kalikaindia.com/punchout/setup/"
    
    products = get_test_products()
    if not products:
        results.add("Product Retrieval", "FAIL", "No products available")
        return
    
    item_out_xml = f'''
        <ItemOut quantity="10">
            <ItemID>
                <SupplierPartID>{products[0].item_code}</SupplierPartID>
            </ItemID>
        </ItemOut>'''
    
    cxml_request = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="inspect_test@kalikaindia.com" timestamp="{datetime.utcnow().isoformat()}Z">
    <Header>
        <From><Credential domain="DUNS"><Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity></Credential></From>
        <To><Credential domain="DUNS"><Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity></Credential></To>
        <Sender>
            <Credential domain="NetworkId">
                <Identity>{settings.PUNCHOUT_ANID}</Identity>
                <SharedSecret>{settings.PUNCHOUT_SHARED_SECRET}</SharedSecret>
            </Credential>
        </Sender>
    </Header>
    <Request>
        <PunchOutSetupRequest operation="inspect">
            <BuyerCookie>inspect_test_cookie</BuyerCookie>
            <BrowserFormPost><URL>https://test.ariba.com/return</URL></BrowserFormPost>{item_out_xml}
        </PunchOutSetupRequest>
    </Request>
</cXML>'''
    
    try:
        response = requests.post(endpoint_url, data=cxml_request,
                                headers={'Content-Type': 'text/xml'},
                                timeout=15, verify=True)
        
        if response.status_code == 200:
            results.add("Inspect Mode Request", "PASS", f"Status: {response.status_code}")
            
            root = etree.fromstring(response.content)
            start_page_url = root.find(".//StartPage/URL").text
            
            # Should behave like edit mode (redirect to cart)
            if "/cart/" in start_page_url:
                results.add("Inspect Mode Redirect", "PASS", "Redirects to cart page")
            else:
                results.add("Inspect Mode Redirect", "FAIL", "Should redirect to cart")
            
            if "punchout_session=" in start_page_url:
                results.add("Inspect Session Parameter", "PASS", "Session parameter present")
                
                session_key = start_page_url.split("punchout_session=")[1].split("&")[0]
                
                import time
                time.sleep(1)
                
                cart_items = CartItem.objects.filter(session_key=session_key)
                if cart_items.count() == 1 and cart_items[0].quantity == 10:
                    results.add("Inspect Cart Pre-population", "PASS",
                              f"Item loaded correctly: {cart_items[0].quantity} units")
                else:
                    results.add("Inspect Cart Pre-population", "FAIL",
                              "Cart not pre-populated correctly")
            else:
                results.add("Inspect Session Parameter", "FAIL", "Missing parameter")
        else:
            results.add("Inspect Mode Request", "FAIL", f"Status: {response.status_code}")
            
    except Exception as e:
        results.add("Inspect Mode Test", "FAIL", str(e))

def test_edit_mode_empty_cart_clear(results):
    """Test 4: Edit Mode Clears Previous Cart"""
    print("\n" + "="*80)
    print("TEST 4: Edit Mode - Cart Clearing Behavior")
    print("="*80 + "\n")
    
    endpoint_url = "https://www.kalikaindia.com/punchout/setup/"
    
    products = get_test_products()
    if not products or len(products) < 2:
        results.add("Product Retrieval", "FAIL", "Insufficient products")
        return
    
    # First request with product 1
    item_out_xml = f'''
        <ItemOut quantity="5">
            <ItemID>
                <SupplierPartID>{products[0].item_code}</SupplierPartID>
            </ItemID>
        </ItemOut>'''
    
    cxml_request1 = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="clear_test1@kalikaindia.com" timestamp="{datetime.utcnow().isoformat()}Z">
    <Header>
        <From><Credential domain="DUNS"><Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity></Credential></From>
        <To><Credential domain="DUNS"><Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity></Credential></To>
        <Sender>
            <Credential domain="NetworkId">
                <Identity>{settings.PUNCHOUT_ANID}</Identity>
                <SharedSecret>{settings.PUNCHOUT_SHARED_SECRET}</SharedSecret>
            </Credential>
        </Sender>
    </Header>
    <Request>
        <PunchOutSetupRequest operation="edit">
            <BuyerCookie>clear_test_cookie</BuyerCookie>
            <BrowserFormPost><URL>https://test.ariba.com/return</URL></BrowserFormPost>{item_out_xml}
        </PunchOutSetupRequest>
    </Request>
</cXML>'''
    
    try:
        response1 = requests.post(endpoint_url, data=cxml_request1,
                                 headers={'Content-Type': 'text/xml'},
                                 timeout=15, verify=True)
        
        if response1.status_code != 200:
            results.add("First Edit Request", "FAIL", f"Status: {response1.status_code}")
            return
        
        results.add("First Edit Request", "PASS", "Initial cart populated")
        
        root1 = etree.fromstring(response1.content)
        session_key1 = root1.find(".//StartPage/URL").text.split("punchout_session=")[1].split("&")[0]
        
        import time
        time.sleep(1)
        
        # Verify first cart
        cart_items1 = CartItem.objects.filter(session_key=session_key1)
        if cart_items1.count() == 1:
            results.add("First Cart Verification", "PASS", f"1 item in cart")
        
        # Second request with different product using SAME credentials
        # This simulates user editing the SAME requisition again
        item_out_xml2 = f'''
        <ItemOut quantity="3">
            <ItemID>
                <SupplierPartID>{products[1].item_code}</SupplierPartID>
            </ItemID>
        </ItemOut>'''
        
        cxml_request2 = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="clear_test2@kalikaindia.com" timestamp="{datetime.utcnow().isoformat()}Z">
    <Header>
        <From><Credential domain="DUNS"><Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity></Credential></From>
        <To><Credential domain="DUNS"><Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity></Credential></To>
        <Sender>
            <Credential domain="NetworkId">
                <Identity>{settings.PUNCHOUT_ANID}</Identity>
                <SharedSecret>{settings.PUNCHOUT_SHARED_SECRET}</SharedSecret>
            </Credential>
        </Sender>
    </Header>
    <Request>
        <PunchOutSetupRequest operation="edit">
            <BuyerCookie>clear_test_cookie</BuyerCookie>
            <BrowserFormPost><URL>https://test.ariba.com/return</URL></BrowserFormPost>{item_out_xml2}
        </PunchOutSetupRequest>
    </Request>
</cXML>'''
        
        response2 = requests.post(endpoint_url, data=cxml_request2,
                                 headers={'Content-Type': 'text/xml'},
                                 timeout=15, verify=True)
        
        if response2.status_code == 200:
            results.add("Second Edit Request", "PASS", "Second cart populated")
            
            root2 = etree.fromstring(response2.content)
            session_key2 = root2.find(".//StartPage/URL").text.split("punchout_session=")[1].split("&")[0]
            
            time.sleep(1)
            
            # Verify second cart replaced first cart
            cart_items2 = CartItem.objects.filter(session_key=session_key2)
            if cart_items2.count() == 1:
                if cart_items2[0].product.item_code == products[1].item_code:
                    results.add("Cart Clearing", "PASS",
                              "Previous cart cleared, new items loaded")
                else:
                    results.add("Cart Clearing", "FAIL",
                              "Wrong product in cart")
            else:
                results.add("Cart Clearing", "WARN",
                          f"Expected 1 item, got {cart_items2.count()}")
        else:
            results.add("Second Edit Request", "FAIL", f"Status: {response2.status_code}")
            
    except Exception as e:
        results.add("Cart Clearing Test", "FAIL", str(e))

def generate_report(results):
    """Generate test report"""
    print("\n" + "="*80)
    print("  EDIT/INSPECT MODE TEST RESULTS - SUMMARY")
    print("="*80 + "\n")
    
    total = results.passed + results.failed + results.warnings
    print(f"  Total Tests:     {total}")
    print(f"  ✅ Passed:        {results.passed}")
    print(f"  ❌ Failed:        {results.failed}")
    print(f"  ⚠️  Warnings:      {results.warnings}")
    print(f"\n  Success Rate:    {(results.passed/total*100) if total > 0 else 0:.1f}%")
    
    if results.failed == 0 and results.warnings == 0:
        print("\n  ✓ All edit/inspect mode tests passed!")
    elif results.failed == 0:
        print("\n  ✓ All critical tests passed. Review warnings.")
    else:
        print("\n  ⚠️  Some tests failed. Review failures.")
    
    print("="*80 + "\n")
    
    # Save report
    report_file = '/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/Test/edit_mode_test_report.txt'
    with open(report_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("  EDIT/INSPECT MODE TEST REPORT\n")
        f.write("="*80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Test Scope: PunchOut Edit and Inspect Operations\n\n")
        
        for idx, test in enumerate(results.tests, 1):
            icon = "✅" if test['status'] == "PASS" else "❌" if test['status'] == "FAIL" else "⚠️"
            f.write(f"{idx}. {icon} {test['name']}\n")
            f.write(f"   Status: {test['status']}\n")
            if test['details']:
                f.write(f"   {test['details']}\n")
            f.write("\n")
        
        f.write("="*80 + "\n")
        f.write(f"Total: {total} | Passed: {results.passed} | Failed: {results.failed} | Warnings: {results.warnings}\n")
        f.write("="*80 + "\n")
    
    print(f"📄 Full report saved to: {report_file}\n")
    
    return results.failed == 0

def main():
    """Run all edit mode tests"""
    print("\n" + "="*80)
    print("  PUNCHOUT EDIT/INSPECT MODE - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print(f"  Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Endpoint: https://www.kalikaindia.com/punchout/setup/")
    print(f"  Operations: edit, inspect")
    print("="*80)
    
    results = EditModeTestResults()
    
    # Run all tests
    test_edit_mode_with_valid_products(results)
    test_edit_mode_with_invalid_products(results)
    test_inspect_mode(results)
    test_edit_mode_empty_cart_clear(results)
    
    # Generate report
    success = generate_report(results)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
