#!/usr/bin/env python
"""
PunchOut System Test - Production Catalog Validation
Tests the corrected catalog file for SAP Ariba compliance
"""

import os
import sys
import requests
import pandas as pd
from datetime import datetime

# Setup paths
sys.path.append('/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce.settings')

import django
django.setup()

from django.conf import settings

class TestResults:
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

def test_catalog_file_format(results):
    """Test 1: Catalog File Format Validation"""
    print("\n" + "="*80)
    print("TEST 1: Catalog File Format Validation - CORRECTED FILE")
    print("="*80 + "\n")
    
    catalog_file = '/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/Test/KALIKA_ENTERPRISES_PUNCHOUT_CORRECTED.xlsx'
    
    try:
        # Read the catalog file
        df = pd.read_excel(catalog_file, header=None)
        results.add("File Read - KALIKA_ENTERPRISES_PUNCHOUT_CORRECTED.xlsx", "PASS", 
                   f"Successfully read {len(df)} rows")
        
        # Check CIF version
        if df.iloc[0, 0] == 'CIF_I_V3.0':
            results.add("CIF Version", "PASS", "Valid CIF_I_V3.0 format")
        else:
            results.add("CIF Version", "FAIL", f"Unexpected version: {df.iloc[0, 0]}")
        
        # Check LOADMODE
        if 'LOADMODE:' in str(df.iloc[1, 0]) and df.iloc[1, 1] == 'F':
            results.add("Load Mode", "PASS", "Full load mode configured (F)")
        
        # Check CODEFORMAT
        if 'CODEFORMAT:' in str(df.iloc[2, 0]):
            results.add("Code Format", "PASS", f"Code format: {df.iloc[2, 1]}")
        
        # Check CURRENCY
        if 'CURRENCY:' in str(df.iloc[3, 0]) and df.iloc[3, 1] == 'INR':
            results.add("Currency", "PASS", "Currency set to INR")
        
        # Check field count (row 9 has field names)
        field_names_row = df.iloc[9].tolist()
        field_count = sum(1 for x in field_names_row if pd.notna(x))
        if field_count == 13:
            results.add("Field Count", "PASS", f"All 13 fields defined")
        else:
            results.add("Field Count", "WARN", f"Expected 13 fields, got {field_count}")
        
        # Check data completeness (row 11 has data)
        data_row = df.iloc[11].tolist()
        non_empty_count = sum(1 for x in data_row if pd.notna(x))
        if non_empty_count >= 10:
            results.add("Data Completeness", "PASS", 
                       f"{non_empty_count}/13 data fields populated")
        elif non_empty_count >= 8:
            results.add("Data Completeness", "WARN", 
                       f"Only {non_empty_count}/13 data fields populated")
        else:
            results.add("Data Completeness", "FAIL", 
                       f"Only {non_empty_count}/13 data fields populated")
        
        # Check critical fields are present in data
        supplier_id = df.iloc[11, 0]
        part_id = df.iloc[11, 1]
        description = df.iloc[11, 3]
        
        if pd.notna(supplier_id) and pd.notna(part_id) and pd.notna(description):
            results.add("Critical Fields", "PASS", 
                       f"Supplier ID={supplier_id}, Part ID={part_id}")
        else:
            results.add("Critical Fields", "FAIL", "Missing critical field values")
        
    except Exception as e:
        results.add("File Read", "FAIL", f"Error: {str(e)}")

def test_configuration(results):
    """Test 2: Configuration Validation"""
    print("\n" + "="*80)
    print("TEST 2: Configuration Validation")
    print("="*80 + "\n")
    
    # Check PUNCHOUT_ANID
    if settings.PUNCHOUT_ANID:
        results.add("Config: Supplier Network ID", "PASS", 
                   f"Configured: {settings.PUNCHOUT_ANID}")
    else:
        results.add("Config: Supplier Network ID", "FAIL", "Not configured")
    
    # Check PUNCHOUT_SHARED_SECRET
    if settings.PUNCHOUT_SHARED_SECRET:
        masked = settings.PUNCHOUT_SHARED_SECRET[:4] + '*' * (len(settings.PUNCHOUT_SHARED_SECRET) - 4)
        results.add("Config: Shared Secret", "PASS", f"Configured: {masked}")
    else:
        results.add("Config: Shared Secret", "WARN", "Not configured (optional for default auth)")
    
    # Check PUNCHOUT_SUPPLIER_DUNS
    if settings.PUNCHOUT_SUPPLIER_DUNS:
        results.add("Config: DUNS Number", "PASS", 
                   f"Configured: {settings.PUNCHOUT_SUPPLIER_DUNS}")
    else:
        results.add("Config: DUNS Number", "FAIL", "Not configured")
    
    # Check catalog vs environment consistency
    try:
        df = pd.read_excel('/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/Test/KALIKA_ENTERPRISES_PUNCHOUT_CORRECTED.xlsx', header=None)
        catalog_supplier_id = str(df.iloc[11, 0])  # Row 11 is the data row, column 0 is Supplier ID
        
        if catalog_supplier_id == settings.PUNCHOUT_ANID:
            results.add("Credential Consistency", "PASS", 
                       "Catalog Supplier ID matches environment config")
        else:
            results.add("Credential Consistency", "FAIL", 
                       f"Mismatch: Catalog={catalog_supplier_id}, Config={settings.PUNCHOUT_ANID}")
    except Exception as e:
        results.add("Credential Consistency", "FAIL", f"Error: {str(e)}")

def test_punchout_endpoint(results):
    """Test 3: PunchOut Endpoint Testing"""
    print("\n" + "="*80)
    print("TEST 3: PunchOut Endpoint Testing")
    print("="*80 + "\n")
    
    endpoint_url = "https://www.kalikaindia.com/punchout/setup/"
    
    # Test server reachability
    try:
        response = requests.get("https://www.kalikaindia.com", timeout=10, verify=True)
        if response.status_code == 200:
            results.add("Server Reachability", "PASS", 
                       f"Server is accessible (Status: {response.status_code})")
        else:
            results.add("Server Reachability", "FAIL", 
                       f"Unexpected status: {response.status_code}")
    except Exception as e:
        results.add("Server Reachability", "FAIL", str(e))
    
    # Test SSL certificate
    try:
        import ssl
        import socket
        context = ssl.create_default_context()
        with socket.create_connection(("www.kalikaindia.com", 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname="www.kalikaindia.com") as ssock:
                cert = ssock.getpeercert()
                results.add("SSL Certificate", "PASS", "Valid SSL certificate")
    except Exception as e:
        results.add("SSL Certificate", "FAIL", str(e))
    
    # Test authentication security (invalid credentials)
    test_cxml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="test@test.com" timestamp="{datetime.utcnow().isoformat()}Z">
    <Header>
        <Sender>
            <Credential domain="NetworkId">
                <Identity>INVALID</Identity>
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
        response = requests.post(endpoint_url, data=test_cxml, 
                                headers={'Content-Type': 'text/xml'}, 
                                timeout=10, verify=True)
        if response.status_code == 401 or '401' in response.text:
            results.add("Authentication Security", "PASS", 
                       "System correctly rejects invalid credentials (401)")
        elif response.status_code == 200:
            results.add("Authentication Security", "FAIL", 
                       "System accepted invalid credentials")
        else:
            results.add("Authentication Security", "WARN", 
                       f"Unexpected response: {response.status_code}")
    except Exception as e:
        results.add("Authentication Security", "FAIL", str(e))
    
    # Test valid credentials flow
    valid_cxml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.014/cXML.dtd">
<cXML payloadID="test@kalikaindia.com" timestamp="{datetime.utcnow().isoformat()}Z">
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
        <PunchOutSetupRequest operation="create">
            <BuyerCookie>test_cookie</BuyerCookie>
            <BrowserFormPost><URL>https://test.ariba.com/return</URL></BrowserFormPost>
        </PunchOutSetupRequest>
    </Request>
</cXML>'''
    
    try:
        response = requests.post(endpoint_url, data=valid_cxml, 
                                headers={'Content-Type': 'text/xml'}, 
                                timeout=10, verify=True)
        if response.status_code == 200 and '<StartPage>' in response.text:
            results.add("Valid Credentials Flow", "PASS", 
                       "System accepts valid credentials and returns proper cXML")
        else:
            results.add("Valid Credentials Flow", "FAIL", 
                       f"Status: {response.status_code}")
    except Exception as e:
        results.add("Valid Credentials Flow", "FAIL", str(e))

def test_catalog_data_integrity(results):
    """Test 4: Catalog Data Integrity"""
    print("\n" + "="*80)
    print("TEST 4: Catalog Data Integrity")
    print("="*80 + "\n")
    
    try:
        df = pd.read_excel('/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/Test/KALIKA_ENTERPRISES_PUNCHOUT_CORRECTED.xlsx', header=None)
        data_row = df.iloc[11]  # Row 11 is the data row
        
        # Check Supplier URL (column 9)
        supplier_url = str(data_row[9]) if pd.notna(data_row[9]) else ""
        if "kalikaindia.com" in supplier_url:
            results.add("Supplier URL", "PASS", f"Valid URL: {supplier_url}")
        else:
            results.add("Supplier URL", "WARN", f"URL: {supplier_url}")
        
        # Check PunchOut Enabled Flag (column 12)
        enabled_flag = str(data_row[12]) if pd.notna(data_row[12]) else ""
        if enabled_flag.upper() == "TRUE" or enabled_flag.upper() == "Y" or enabled_flag == "1":
            results.add("PunchOut Enabled Flag", "PASS", f"Enabled: {enabled_flag}")
        else:
            results.add("PunchOut Enabled Flag", "WARN", f"Flag value: {enabled_flag}")
        
        # Check Unit Price (column 5)
        price = data_row[5] if pd.notna(data_row[5]) else None
        if price is not None:
            try:
                float(price)
                results.add("Unit Price", "PASS", f"Valid price: {price} INR")
            except:
                results.add("Unit Price", "FAIL", f"Invalid price: {price}")
        else:
            results.add("Unit Price", "FAIL", "Price not specified")
        
        # Check SPSC Code (column 4)
        spsc = str(int(data_row[4])) if pd.notna(data_row[4]) else ""
        if spsc.isdigit() and len(spsc) >= 4:
            results.add("SPSC Code", "PASS", f"Valid SPSC: {spsc}")
        else:
            results.add("SPSC Code", "WARN", f"SPSC: {spsc}")
        
        # Check Unit of Measure (column 6)
        uom = str(data_row[6]) if pd.notna(data_row[6]) else ""
        if uom:
            results.add("Unit of Measure", "PASS", f"UOM: {uom}")
        else:
            results.add("Unit of Measure", "WARN", "UOM not specified")
        
        # Check Manufacturer Name (column 8)
        manufacturer = str(data_row[8]) if pd.notna(data_row[8]) else ""
        if manufacturer:
            results.add("Manufacturer Name", "PASS", f"Manufacturer: {manufacturer}")
        else:
            results.add("Manufacturer Name", "WARN", "Manufacturer not specified")
            
    except Exception as e:
        results.add("Catalog Data Integrity", "FAIL", str(e))

def generate_report(results):
    """Generate test report"""
    print("\n" + "="*80)
    print("  PUNCHOUT SYSTEM TEST RESULTS - SUMMARY")
    print("="*80 + "\n")
    
    total = results.passed + results.failed + results.warnings
    print(f"  Total Tests:     {total}")
    print(f"  ✅ Passed:        {results.passed}")
    print(f"  ❌ Failed:        {results.failed}")
    print(f"  ⚠️  Warnings:      {results.warnings}")
    print(f"\n  Success Rate:    {(results.passed/total*100) if total > 0 else 0:.1f}%")
    
    if results.failed == 0 and results.warnings == 0:
        print("\n  ✓ All tests passed. System is production ready.")
    elif results.failed == 0:
        print("\n  ✓ All critical tests passed. Review warnings.")
    else:
        print("\n  ⚠️  Some tests failed. Review failures before deployment.")
    
    print("="*80 + "\n")
    
    # Save detailed report
    report_file = '/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/Test/test_report.txt'
    with open(report_file, 'w') as f:
        f.write("="*80 + "\n")
        f.write("  PUNCHOUT SYSTEM TEST REPORT\n")
        f.write("="*80 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Catalog File: KALIKA_ENTERPRISES_PUNCHOUT_CORRECTED.xlsx\n\n")
        
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
    """Run all tests"""
    print("\n" + "="*80)
    print("  KALIKA ENTERPRISES PUNCHOUT SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print(f"  Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Location: /home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/Test")
    print(f"  Catalog: KALIKA_ENTERPRISES_PUNCHOUT_CORRECTED.xlsx")
    print("="*80)
    
    results = TestResults()
    
    # Run all tests
    test_catalog_file_format(results)
    test_configuration(results)
    test_punchout_endpoint(results)
    test_catalog_data_integrity(results)
    
    # Generate report
    success = generate_report(results)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
