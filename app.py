import streamlit as st
import pywhatkit
from datetime import timedelta, datetime
import time
import imaplib
import email
from email.header import decode_header
import PyPDF2
import re
import io
import threading
from PO_s3store import process_po_emails

# Secrets for email and WhatsApp group link
EMAIL = st.secrets["gmail_uname"]
PASSWORD = st.secrets["gmail_pwd"]
IMAP_SERVER = "imap.gmail.com"
WHATSAPP_GROUP_LINK = st.secrets["WHATSAPP_GROUP_LINK"]

# Session state for WhatsApp message counter
if "whatsapp_sent_counter" not in st.session_state:
    st.session_state["whatsapp_sent_counter"] = 0

# Helper: Extract text from PDF
def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        return "".join(page.extract_text() for page in pdf_reader.pages)
    except Exception as e:
        st.error(f"Error extracting text from PDF: {str(e)}")
        return ""

# Helper: Parse order details
def parse_order_details(text):
    patterns = {
        "Product Name": r"Product(?: Name)?:?\s*(.+)",
        "Category": r"Category:?\s*(.+)",
        "Price": r"Price:?\s*[₹$]?\s*(\d+\.?\d*)",
        "Quantity": r"Quantity:?\s*(\d+)",
        "Order Date": r"Order Date:?\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})",
        "Delivery Date": r"(?:Expected )?Delivery(?: Date)?:?\s*(\d{4}-\d{2}-\d{2})",
        "Customer Name": r"Customer(?: Name)?:?\s*(.+)",
        "Phone": r"Phone:?\s*(\+?\d{10,13})",
        "Email": r"Email:?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        "Address": r"Address:?\s*(.+)",
        "Payment Method": r"Payment(?: Method)?:?\s*(COD|Credit Card|UPI|Bank Transfer)",
        "Payment Status": r"Payment Status:?\s*(Paid|Unpaid)",
        "Order Status": r"(?:Order )?Status:?\s*(Pending|Processing|Shipped|Delivered)"
    }
    order_details = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        order_details[key] = match.group(1).strip() if match else "Not found"
    return order_details

# Helper: Fetch unseen email PDFs
def fetch_email_pdfs():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL, PASSWORD)
        mail.select("inbox")
        status, messages = mail.search(None, '(UNSEEN SUBJECT "PO Dump")')
        if status != "OK" or not messages[0]:
            return []
        mail_ids = messages[0].split()
        pdf_files = []
        for mail_id in mail_ids:
            status, msg_data = mail.fetch(mail_id, '(RFC822)')
            if status != "OK":
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            for part in msg.walk():
                if part.get_content_type() == "application/pdf":
                    pdf_data = part.get_payload(decode=True)
                    if pdf_data:
                        pdf_files.append(pdf_data)
        mail.logout()
        return pdf_files
    except Exception as e:
        st.error(f"Error fetching emails: {str(e)}")
        return []

# Helper: Send WhatsApp message
def send_whatsapp(message):
    try:
        now = datetime.now()
        send_time = now + timedelta(minutes=1)
        pywhatkit.sendwhatmsg_to_group(
            group_id=WHATSAPP_GROUP_LINK,
            message=message,
            time_hour=send_time.hour,
            time_min=send_time.minute,
            wait_time=10,
            tab_close=True
        )
        st.session_state.whatsapp_sent_counter += 1
        time.sleep(60)
    except Exception as e:
        st.error(f"Error sending WhatsApp message: {str(e)}")

def send_whatsapp_in_thread(message):
    thread = threading.Thread(target=send_whatsapp, args=(message,))
    thread.start()

# Streamlit App Layout 
st.set_page_config(page_title="PO Order Manager", layout="wide")
st.title("PO Order Management Dashboard")

tab1, tab2 = st.tabs([" Email PO Summary", " Manual PO + WhatsApp"])

# Tab 1: Show extracted PO count (without extraction button)
with tab1:
    st.subheader(" Incoming PO Emails Summary")

    # Automatically process and get count
    with st.spinner("Checking for new PO emails..."):
        extracted_count = process_po_emails()  # This should return number of new PDFs processed
        time.sleep(1)  

    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric(label="New PO PDFs Extracted", value=extracted_count)
    with col2:
        st.caption("This count reflects new 'PO Dump' emails processed and uploaded to S3.")
# Tab 2: Manual Order + WhatsApp
with tab2:
    st.subheader("Manual Order Form and Notifications")

    with st.expander(" Add New Manual PO Order"):
        with st.form("manual_order"):
            st.markdown("##### Enter Order Details")
            col1, col2 = st.columns(2)
            with col1:
                product_name = st.text_input("Product Name")
                category = st.text_input("Category")
                price = st.number_input("Price", min_value=0.0, step=0.01)
                quantity = st.number_input("Quantity", min_value=1, step=1)
                order_date = st.date_input("Order Date")
                order_time = st.time_input("Order Time")
            with col2:
                delivery_date = st.date_input("Delivery Date")
                customer_name = st.text_input("Customer Name")
                phone = st.text_input("Phone")
                email = st.text_input("Email")
                address = st.text_area("Address")
                payment_method = st.selectbox("Payment Method", ["COD", "Credit Card", "UPI", "Bank Transfer"])
                payment_status = st.selectbox("Payment Status", ["Paid", "Unpaid"])
                order_status = st.selectbox("Order Status", ["Pending", "Processing", "Shipped", "Delivered"])

            submit_button = st.form_submit_button("Submit Order")

            if submit_button:
                if not all([product_name, category, price, quantity, order_date, order_time, delivery_date, customer_name, phone, email, address, payment_method, payment_status, order_status]):
                    st.error("All fields are required.")
                else:
                    order_datetime = datetime.combine(order_date, order_time)
                    message = f"""New PO Order Manually Entered

Product: {product_name}
Category: {category}
Price: ₹{price}
Quantity: {quantity}
Order Date: {order_datetime.strftime('%Y-%m-%d %H:%M')}
Expected Delivery: {delivery_date.strftime('%Y-%m-%d')}
Customer: {customer_name}
Phone: {phone}
Email: {email}
Address: {address}
Payment: {payment_method} ({payment_status})
Status: {order_status}"""
                    send_whatsapp_in_thread(message)
                    st.success("Order submitted and WhatsApp message scheduled.")

    st.divider()

    st.markdown("###  Email Orders to WhatsApp")
    st.caption("Automatically reads PO Dump emails and sends order summaries to your WhatsApp group.")

    if st.button("Check New PO Emails and Send WhatsApp Alerts"):
        pdf_files = fetch_email_pdfs()
        if pdf_files:
            for pdf_data in pdf_files:
                pdf_file = io.BytesIO(pdf_data)
                text = extract_text_from_pdf(pdf_file)
                if text:
                    order_details = parse_order_details(text)
                    message = f"""New PO Order Received via Email

Product: {order_details['Product Name']}
Category: {order_details['Category']}
Price: ₹{order_details['Price']}
Quantity: {order_details['Quantity']}
Order Date: {order_details['Order Date']}
Expected Delivery: {order_details['Delivery Date']}
Customer: {order_details['Customer Name']}
Phone: {order_details['Phone']}
Email: {order_details['Email']}
Address: {order_details['Address']}
Payment: {order_details['Payment Method']} ({order_details['Payment Status']})
Status: {order_details['Order Status']}"""
                    send_whatsapp_in_thread(message)
            st.success(f"Processed {len(pdf_files)} email orders and scheduled WhatsApp messages.")
        else:
            st.info("No new PO Dump emails found.")

    st.markdown(f"**Total WhatsApp messages sent this session:** `{st.session_state.whatsapp_sent_counter}`")
