#!/usr/bin/env python
"""
Comprehensive End-to-End PunchOut System Test
SAP Ariba Default Authentication Validation
"""

import os
import sys
import django
import requests
import json
from datetime import datetime
from lxml import etree

# Setup Django environment
sys.path.append('/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce.settings')
django.setup()

from django.conf import settings
from django.contrib.sessions.models import Session
from accounts.models import CustomUser
from punchout.models import PunchOutSession
from cart.models import CartItem
from catalog.models import Product

class PunchOutTester:
    def __init__(self):
        self.base_url = "https://www.kalikaindia.com"
        self.results = []
        self.session_key = None
        self.test_identity = f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
    def log_result(self, category, test_name, status, details="", data=None):
        """Log test result"""
        result = {
            "category": category,
            "test": test_name,
            "status": status,
            "details": details,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{icon} [{category}] {test_name}: {status}")
        if details:
            print(f"   Details: {details}")
    
    def test_configuration(self):
        """Test 1: Configuration Validation"""
        print("\n" + "="*80)
        print("TEST 1: CONFIGURATION VALIDATION")
        print("="*80)
        
        # Check required settings
        config_tests = [
            ("PUNCHOUT_ANID", settings.PUNCHOUT_ANID),
            ("PUNCHOUT_SHARED_SECRET", settings.PUNCHOUT_SHARED_SECRET),
            ("PUNCHOUT_SUPPLIER_DUNS", settings.PUNCHOUT_SUPPLIER_DUNS),
            ("SESSION_COOKIE_SAMESITE", settings.SESSION_COOKIE_SAMESITE),
            ("SESSION_SAVE_EVERY_REQUEST", settings.SESSION_SAVE_EVERY_REQUEST),
            ("X_FRAME_OPTIONS", settings.X_FRAME_OPTIONS),
            ("CSRF_COOKIE_SAMESITE", settings.CSRF_COOKIE_SAMESITE),
        ]
        
        for setting_name, value in config_tests:
            if value or value == '':  # Empty string is valid for X_FRAME_OPTIONS
                self.log_result("Config", f"{setting_name}", "PASS", f"Value: {value if setting_name != 'PUNCHOUT_SHARED_SECRET' else '***'}")
            else:
                self.log_result("Config", f"{setting_name}", "FAIL", "Not configured")
        
        # Validate specific settings
        if settings.SESSION_COOKIE_SAMESITE == 'None':
            self.log_result("Config", "SameSite Cookie Setting", "PASS", "Configured for iframe support")
        else:
            self.log_result("Config", "SameSite Cookie Setting", "FAIL", f"Should be 'None', got '{settings.SESSION_COOKIE_SAMESITE}'")
    
    def test_punchout_setup_request(self):
        """Test 2: PunchOut Setup Request/Response"""
        print("\n" + "="*80)
        print("TEST 2: PUNCHOUT SETUP REQUEST/RESPONSE")
        print("="*80)
        
        # Create cXML PunchOutSetupRequest
        cxml_request = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="{self.test_identity}@test.com" timestamp="{datetime.utcnow().isoformat()}Z" xml:lang="en-US">
    <Header>
        <From>
            <Credential domain="DUNS">
                <Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity>
            </Credential>
        </From>
        <To>
            <Credential domain="DUNS">
                <Identity>{settings.PUNCHOUT_SUPPLIER_DUNS}</Identity>
            </Credential>
        </To>
        <Sender>
            <Credential domain="NetworkId">
                <Identity>{settings.PUNCHOUT_ANID}</Identity>
                <SharedSecret>{settings.PUNCHOUT_SHARED_SECRET}</SharedSecret>
            </Credential>
            <UserAgent>PunchOut Test Suite</UserAgent>
        </Sender>
    </Header>
    <Request>
        <PunchOutSetupRequest operation="create">
            <BuyerCookie>TEST_BUYER_COOKIE_{datetime.now().strftime('%Y%m%d%H%M%S')}</BuyerCookie>
            <BrowserFormPost>
                <URL>https://test.ariba.com/Buyer/Main/ad/punchoutReturn/testReturnURL</URL>
            </BrowserFormPost>
        </PunchOutSetupRequest>
    </Request>
</cXML>'''
        
        try:
            response = requests.post(
                f"{self.base_url}/punchout/setup/",
                data=cxml_request,
                headers={"Content-Type": "text/xml"},
                timeout=30,
                verify=True
            )
            
            if response.status_code == 200:
                self.log_result("PunchOut Setup", "HTTP Status", "PASS", f"Status: {response.status_code}")
                
                # Parse response
                try:
                    root = etree.fromstring(response.content)
                    
                    # Check cXML structure
                    if root.tag == "cXML":
                        self.log_result("PunchOut Setup", "cXML Structure", "PASS", "Valid cXML root element")
                    else:
                        self.log_result("PunchOut Setup", "cXML Structure", "FAIL", f"Unexpected root: {root.tag}")
                    
                    # Check Status
                    status = root.find(".//Status")
                    if status is not None:
                        status_code = status.get("code")
                        status_text = status.get("text")
                        if status_code == "200":
                            self.log_result("PunchOut Setup", "Status Code", "PASS", f"200 - {status_text}")
                        else:
                            self.log_result("PunchOut Setup", "Status Code", "FAIL", f"{status_code} - {status_text}")
                    
                    # Extract StartPage URL
                    start_page_url = root.find(".//StartPage/URL")
                    if start_page_url is not None and start_page_url.text:
                        url = start_page_url.text
                        self.log_result("PunchOut Setup", "StartPage URL", "PASS", url)
                        
                        # Extract session key from URL
                        if "punchout_session=" in url:
                            self.session_key = url.split("punchout_session=")[1].split("&")[0]
                            self.log_result("PunchOut Setup", "Session Key Extraction", "PASS", f"Session: {self.session_key[:20]}...")
                        else:
                            self.log_result("PunchOut Setup", "Session Key Extraction", "FAIL", "No punchout_session parameter in URL")
                        
                        # Validate URL format
                        if url.startswith("https://www.kalikaindia.com"):
                            self.log_result("PunchOut Setup", "URL Format", "PASS", "Uses www subdomain")
                        elif url.startswith("https://kalikaindia.com"):
                            self.log_result("PunchOut Setup", "URL Format", "WARN", "Missing www subdomain")
                        else:
                            self.log_result("PunchOut Setup", "URL Format", "FAIL", f"Unexpected domain: {url}")
                    else:
                        self.log_result("PunchOut Setup", "StartPage URL", "FAIL", "No StartPage URL in response")
                    
                except Exception as e:
                    self.log_result("PunchOut Setup", "Response Parsing", "FAIL", str(e))
            else:
                self.log_result("PunchOut Setup", "HTTP Status", "FAIL", f"Status: {response.status_code}")
                self.log_result("PunchOut Setup", "Response Body", "INFO", response.text[:500])
                
        except Exception as e:
            self.log_result("PunchOut Setup", "Request Execution", "FAIL", str(e))
    
    def test_session_persistence(self):
        """Test 3: Session Persistence"""
        print("\n" + "="*80)
        print("TEST 3: SESSION PERSISTENCE")
        print("="*80)
        
        if not self.session_key:
            self.log_result("Session", "Session Key Available", "FAIL", "No session key from previous test")
            return
        
        # Check Django session
        try:
            django_session = Session.objects.filter(session_key=self.session_key).first()
            if django_session:
                self.log_result("Session", "Django Session Exists", "PASS", f"Session key: {self.session_key[:20]}...")
                
                # Decode session data
                session_data = django_session.get_decoded()
                
                # Check is_punchout flag
                if session_data.get('is_punchout'):
                    self.log_result("Session", "is_punchout Flag", "PASS", "Set to True")
                else:
                    self.log_result("Session", "is_punchout Flag", "FAIL", "Not set or False")
                
                # Check authentication
                if session_data.get('_auth_user_id'):
                    self.log_result("Session", "User Authentication", "PASS", f"User ID: {session_data.get('_auth_user_id')}")
                    
                    # Check user exists
                    try:
                        user = CustomUser.objects.get(pk=session_data.get('_auth_user_id'))
                        self.log_result("Session", "User Object", "PASS", f"Username: {user.username}")
                        
                        if user.buyer_identifier:
                            self.log_result("Session", "Buyer Identifier", "PASS", f"Identifier: {user.buyer_identifier}")
                        else:
                            self.log_result("Session", "Buyer Identifier", "WARN", "No buyer_identifier set")
                    except CustomUser.DoesNotExist:
                        self.log_result("Session", "User Object", "FAIL", "User not found in database")
                else:
                    self.log_result("Session", "User Authentication", "FAIL", "No _auth_user_id in session")
                
                # Check return URL
                if session_data.get('punchout_return_url'):
                    self.log_result("Session", "Return URL", "PASS", session_data.get('punchout_return_url')[:50] + "...")
                else:
                    self.log_result("Session", "Return URL", "FAIL", "No punchout_return_url in session")
                
                # Check buyer cookie
                if session_data.get('punchout_buyer_cookie'):
                    self.log_result("Session", "Buyer Cookie", "PASS", session_data.get('punchout_buyer_cookie'))
                else:
                    self.log_result("Session", "Buyer Cookie", "FAIL", "No punchout_buyer_cookie in session")
            else:
                self.log_result("Session", "Django Session Exists", "FAIL", "Session not found in database")
        except Exception as e:
            self.log_result("Session", "Session Check", "FAIL", str(e))
        
        # Check PunchOutSession model
        try:
            punchout_session = PunchOutSession.objects.filter(session_key=self.session_key).first()
            if punchout_session:
                self.log_result("Session", "PunchOut Session DB", "PASS", f"Identity: {punchout_session.from_identity}")
            else:
                self.log_result("Session", "PunchOut Session DB", "FAIL", "No PunchOutSession record")
        except Exception as e:
            self.log_result("Session", "PunchOut Session DB", "FAIL", str(e))
    
    def test_startpage_accessibility(self):
        """Test 4: StartPage URL Accessibility"""
        print("\n" + "="*80)
        print("TEST 4: STARTPAGE URL ACCESSIBILITY")
        print("="*80)
        
        if not self.session_key:
            self.log_result("StartPage", "Session Key Available", "FAIL", "No session key from previous test")
            return
        
        start_page_url = f"{self.base_url}/?punchout_session={self.session_key}"
        
        try:
            response = requests.get(start_page_url, timeout=30, verify=True)
            
            if response.status_code == 200:
                self.log_result("StartPage", "HTTP Status", "PASS", f"Status: {response.status_code}")
                
                # Check content type
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type:
                    self.log_result("StartPage", "Content Type", "PASS", content_type)
                else:
                    self.log_result("StartPage", "Content Type", "WARN", f"Unexpected: {content_type}")
                
                # Check for key elements
                html = response.text
                checks = [
                    ("DOCTYPE", "<!DOCTYPE html>" in html or "<!doctype html>" in html),
                    ("Title Tag", "<title>" in html),
                    ("Body Tag", "<body>" in html or "<body " in html),
                ]
                
                for check_name, check_result in checks:
                    if check_result:
                        self.log_result("StartPage", f"HTML {check_name}", "PASS", "Present")
                    else:
                        self.log_result("StartPage", f"HTML {check_name}", "WARN", "Not found")
            else:
                self.log_result("StartPage", "HTTP Status", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("StartPage", "Request", "FAIL", str(e))
    
    def test_security_headers(self):
        """Test 5: Security Headers"""
        print("\n" + "="*80)
        print("TEST 5: SECURITY HEADERS")
        print("="*80)
        
        try:
            response = requests.head(self.base_url, timeout=30, verify=True)
            headers = response.headers
            
            # Check CSP header
            csp = headers.get('Content-Security-Policy', '')
            if 'frame-ancestors' in csp:
                self.log_result("Security", "Content-Security-Policy", "PASS", "frame-ancestors configured")
                
                # Check for Ariba domains
                if 'ariba.com' in csp:
                    self.log_result("Security", "CSP Ariba Domains", "PASS", "Includes ariba.com")
                else:
                    self.log_result("Security", "CSP Ariba Domains", "FAIL", "Missing ariba.com")
            else:
                self.log_result("Security", "Content-Security-Policy", "FAIL", "frame-ancestors not configured")
            
            # Check X-Frame-Options
            xfo = headers.get('X-Frame-Options', '')
            if xfo == '' or xfo is None:
                self.log_result("Security", "X-Frame-Options", "PASS", "Empty (allows iframe)")
            else:
                self.log_result("Security", "X-Frame-Options", "WARN", f"Set to: {xfo}")
            
            # Check HSTS
            hsts = headers.get('Strict-Transport-Security', '')
            if 'max-age' in hsts.lower():
                self.log_result("Security", "HSTS Header", "PASS", hsts[:50] + "...")
            else:
                self.log_result("Security", "HSTS Header", "FAIL", "Not configured")
            
            # Check SSL
            if response.url.startswith('https://'):
                self.log_result("Security", "HTTPS Enabled", "PASS", "Site uses HTTPS")
            else:
                self.log_result("Security", "HTTPS Enabled", "FAIL", "Not using HTTPS")
                
        except Exception as e:
            self.log_result("Security", "Header Check", "FAIL", str(e))
    
    def test_cart_functionality(self):
        """Test 6: Cart Functionality"""
        print("\n" + "="*80)
        print("TEST 6: CART FUNCTIONALITY")
        print("="*80)
        
        if not self.session_key:
            self.log_result("Cart", "Session Key Available", "FAIL", "No session key from previous test")
            return
        
        # Check if cart can be accessed
        cart_url = f"{self.base_url}/cart/?punchout_session={self.session_key}"
        
        try:
            response = requests.get(cart_url, timeout=30, verify=True)
            if response.status_code == 200:
                self.log_result("Cart", "Cart Page Access", "PASS", "Successfully accessed cart")
            else:
                self.log_result("Cart", "Cart Page Access", "FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.log_result("Cart", "Cart Page Access", "FAIL", str(e))
        
        # Check cart items in database
        try:
            cart_items = CartItem.objects.filter(session_key=self.session_key)
            count = cart_items.count()
            self.log_result("Cart", "Cart Items in DB", "INFO", f"{count} items found")
        except Exception as e:
            self.log_result("Cart", "Cart Items in DB", "FAIL", str(e))
    
    def test_product_catalog(self):
        """Test 7: Product Catalog"""
        print("\n" + "="*80)
        print("TEST 7: PRODUCT CATALOG")
        print("="*80)
        
        # Check if products exist
        try:
            product_count = Product.objects.count()
            if product_count > 0:
                self.log_result("Catalog", "Products Available", "PASS", f"{product_count} products in catalog")
                
                # Get sample product
                sample_product = Product.objects.first()
                if sample_product:
                    fields = []
                    if sample_product.item_code:
                        fields.append("item_code")
                    if sample_product.product_title:
                        fields.append("product_title")
                    if sample_product.price:
                        fields.append("price")
                    if sample_product.unit_of_measure:
                        fields.append("unit_of_measure")
                    
                    self.log_result("Catalog", "Sample Product Fields", "PASS", f"Fields: {', '.join(fields)}")
            else:
                self.log_result("Catalog", "Products Available", "FAIL", "No products in catalog")
        except Exception as e:
            self.log_result("Catalog", "Product Check", "FAIL", str(e))
    
    def test_authentication_security(self):
        """Test 8: Authentication Security"""
        print("\n" + "="*80)
        print("TEST 8: AUTHENTICATION SECURITY")
        print("="*80)
        
        # Test with invalid credentials
        invalid_cxml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="invalid@test.com" timestamp="{datetime.utcnow().isoformat()}Z">
    <Header>
        <Sender>
            <Credential domain="NetworkId">
                <Identity>INVALID_ANID</Identity>
                <SharedSecret>invalid_secret</SharedSecret>
            </Credential>
        </Sender>
    </Header>
    <Request>
        <PunchOutSetupRequest operation="create">
            <BuyerCookie>test</BuyerCookie>
            <BrowserFormPost><URL>https://test.com</URL></BrowserFormPost>
        </PunchOutSetupRequest>
    </Request>
</cXML>'''
        
        try:
            response = requests.post(
                f"{self.base_url}/punchout/setup/",
                data=invalid_cxml,
                headers={"Content-Type": "text/xml"},
                timeout=30,
                verify=True
            )
            
            if response.status_code in [401, 403]:
                self.log_result("Authentication", "Invalid Credentials Rejected", "PASS", f"Status: {response.status_code}")
            elif response.status_code == 200:
                # Check if response contains error
                if '401' in response.text or 'Unauthorized' in response.text:
                    self.log_result("Authentication", "Invalid Credentials Rejected", "PASS", "Returns cXML error 401")
                else:
                    self.log_result("Authentication", "Invalid Credentials Rejected", "FAIL", "Accepted invalid credentials")
            else:
                self.log_result("Authentication", "Invalid Credentials Rejected", "WARN", f"Unexpected status: {response.status_code}")
        except Exception as e:
            self.log_result("Authentication", "Security Test", "FAIL", str(e))
    
    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*80)
        print("GENERATING COMPREHENSIVE REPORT")
        print("="*80)
        
        # Calculate statistics
        total = len(self.results)
        passed = sum(1 for r in self.results if r['status'] == 'PASS')
        failed = sum(1 for r in self.results if r['status'] == 'FAIL')
        warnings = sum(1 for r in self.results if r['status'] == 'WARN')
        
        # Generate report content
        report = []
        report.append("="*80)
        report.append("COMPREHENSIVE PUNCHOUT SYSTEM TEST REPORT")
        report.append("SAP Ariba Default Authentication - End-to-End Validation")
        report.append("="*80)
        report.append(f"\nTest Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Base URL: {self.base_url}")
        report.append(f"Test Identity: {self.test_identity}")
        report.append("\n" + "="*80)
        report.append("EXECUTIVE SUMMARY")
        report.append("="*80)
        report.append(f"\nTotal Tests: {total}")
        report.append(f"✅ Passed: {passed}")
        report.append(f"❌ Failed: {failed}")
        report.append(f"⚠️  Warnings: {warnings}")
        report.append(f"\nSuccess Rate: {(passed/total*100) if total > 0 else 0:.1f}%")
        
        # Overall status
        if failed == 0 and warnings == 0:
            report.append("\n🟢 STATUS: READY FOR PRODUCTION")
        elif failed == 0:
            report.append("\n🟡 STATUS: READY WITH MINOR WARNINGS")
        elif failed <= 2:
            report.append("\n🟠 STATUS: REQUIRES ATTENTION")
        else:
            report.append("\n🔴 STATUS: NOT READY - CRITICAL ISSUES")
        
        # Detailed results by category
        report.append("\n" + "="*80)
        report.append("DETAILED TEST RESULTS")
        report.append("="*80)
        
        categories = {}
        for result in self.results:
            cat = result['category']
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(result)
        
        for category, tests in categories.items():
            report.append(f"\n{category.upper()}")
            report.append("-" * 80)
            
            for test in tests:
                icon = "✅" if test['status'] == "PASS" else "❌" if test['status'] == "FAIL" else "⚠️" if test['status'] == "WARN" else "ℹ️"
                report.append(f"\n{icon} {test['test']}: {test['status']}")
                if test['details']:
                    report.append(f"   {test['details']}")
                if test['data']:
                    report.append(f"   Data: {test['data']}")
        
        # Recommendations
        report.append("\n" + "="*80)
        report.append("RECOMMENDATIONS")
        report.append("="*80)
        
        if failed > 0:
            report.append("\n⚠️  CRITICAL ACTIONS REQUIRED:")
            for result in self.results:
                if result['status'] == 'FAIL':
                    report.append(f"  - Fix: {result['category']} - {result['test']}")
                    if result['details']:
                        report.append(f"    Reason: {result['details']}")
        
        if warnings > 0:
            report.append("\n💡 SUGGESTED IMPROVEMENTS:")
            for result in self.results:
                if result['status'] == 'WARN':
                    report.append(f"  - Review: {result['category']} - {result['test']}")
                    if result['details']:
                        report.append(f"    Note: {result['details']}")
        
        if failed == 0:
            report.append("\n✅ SYSTEM VALIDATION:")
            report.append("  - All critical tests passed")
            report.append("  - PunchOut Setup Request/Response: Working")
            report.append("  - Session Management: Operational")
            report.append("  - Security Headers: Configured")
            report.append("  - Authentication: Validated")
            report.append("\n✅ READY FOR SAP ARIBA PRODUCTION TESTING")
        
        # Configuration details
        report.append("\n" + "="*80)
        report.append("SYSTEM CONFIGURATION")
        report.append("="*80)
        report.append(f"\nPunchOut ANID: {settings.PUNCHOUT_ANID}")
        report.append(f"Supplier DUNS: {settings.PUNCHOUT_SUPPLIER_DUNS}")
        report.append(f"Session Cookie SameSite: {settings.SESSION_COOKIE_SAMESITE}")
        report.append(f"X-Frame-Options: '{settings.X_FRAME_OPTIONS}' (empty = allows iframe)")
        report.append(f"Session Save Every Request: {settings.SESSION_SAVE_EVERY_REQUEST}")
        
        # Save report
        report_text = "\n".join(report)
        report_file = "/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/Test/COMPREHENSIVE_TEST_REPORT.txt"
        
        with open(report_file, 'w') as f:
            f.write(report_text)
        
        print(report_text)
        print(f"\n📄 Report saved to: {report_file}")
        
        # also save JSON version
        json_file = "/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/Test/test_results.json"
        with open(json_file, 'w') as f:
            json.dump({
                "summary": {
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "warnings": warnings,
                    "success_rate": (passed/total*100) if total > 0 else 0,
                    "timestamp": datetime.now().isoformat(),
                    "test_identity": self.test_identity
                },
                "results": self.results
            }, f, indent=2)
        
        print(f"📊 JSON report saved to: {json_file}")
        
        return failed == 0

def main():
    """Run comprehensive PunchOut system tests"""
    print("\n" + "="*80)
    print("INITIALIZING COMPREHENSIVE PUNCHOUT SYSTEM TEST")
    print("="*80)
    print("\nThis test will validate:")
    print("  1. Configuration")
    print("  2. PunchOut Setup Request/Response")
    print("  3. Session Persistence")
    print("  4. StartPage URL Accessibility")
    print("  5. Security Headers")
    print("  6. Cart Functionality")
    print("  7. Product Catalog")
    print("  8. Authentication Security")
    print("\n" + "="*80)
    
    tester = PunchOutTester()
    
    # Run all tests
    tester.test_configuration()
    tester.test_punchout_setup_request()
    tester.test_session_persistence()
    tester.test_startpage_accessibility()
    tester.test_security_headers()
    tester.test_cart_functionality()
    tester.test_product_catalog()
    tester.test_authentication_security()
    
    # Generate report
    success = tester.generate_report()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
