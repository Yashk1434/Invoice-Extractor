import pandas as pd
import os
import pdfplumber
import camelot
import re


def get_details(file_name):
    """
    Extract details from Reliance Digital invoice PDF using camelot and pdfplumber
    Args:
        file_name (str): Name of the PDF file to process
    Returns:
        dict: Contains both invoice summary and item details DataFrames
    """
    try:
        file_path = os.path.join("uploads", file_name)

        if not os.path.exists(file_path):
            print(f"[RELIANCE_DIGITAL] File not found: {file_path}")
            return create_empty_result()

        # === STEP 1: Extract Header Details - EXACT SAME LOGIC ===
        header_details = extract_header_details(file_path)

        # === STEP 2: Extract Items Table - EXACT SAME LOGIC ===
        items_table = extract_items_table(file_path)

        # === STEP 3: Create Two DataFrames ===
        invoice_summary = pd.DataFrame([header_details])
        item_details = items_table

        if not item_details.empty:
            item_details["Source_File"] = os.path.basename(file_path)

        print(f"[RELIANCE_DIGITAL] Successfully processed {file_name} - Invoice summary: 1 record, Item details: {len(item_details)} items")

        return {
            "invoice_summary": invoice_summary,
            "item_details": item_details,
            "has_items": not item_details.empty
        }

    except Exception as e:
        print(f"[RELIANCE_DIGITAL] Error processing {file_name}: {e}")
        return create_empty_result()


def create_empty_result():
    """Create empty result structure"""
    return {
        "invoice_summary": pd.DataFrame(),
        "item_details": pd.DataFrame(),
        "has_items": False
    }


def extract_header_details(pdf_path):
    """EXACT SAME FUNCTION from your working Colab code - NO CHANGES"""
    with pdfplumber.open(pdf_path) as pdf:
        first_page = pdf.pages[0]
        text = first_page.extract_text()

    details = {}

    # Tax Invoice No
    invoice_no_match = re.search(r'Tax Invoice No:\s*(D\d+[A-Z0-9]*)', text)
    if invoice_no_match:
        details["Invoice Number"] = invoice_no_match.group(1)

    # Invoice Date
    date_match = re.search(r'Dated:\s*(\d{2}-\d{2}-\d{4})', text)
    if date_match:
        details["Invoice Date"] = date_match.group(1)

    # Seller Info
    seller_match = re.search(r'Seller/Consignor:\s*(.*?)\s*Tax Invoice No', text, re.DOTALL)
    if seller_match:
        details["Seller"] = seller_match.group(1).strip().replace("\n", ", ")

    # Buyer Name and Address
    recipient_match = re.search(r'Recipient Address:\s*(.*?)\n(.*?)\n', text)
    if recipient_match:
        details["Buyer Name"] = recipient_match.group(1).strip()
        details["Buyer Address"] = recipient_match.group(2).strip()

    # Mobile Number
    mobile_match = re.search(r'Mobile\s*:\s*(\d+)', text)
    if mobile_match:
        details["Buyer Mobile"] = mobile_match.group(1)

    # Total Invoice Value
    total_match = re.search(r'Total Invoice Value[\s\S]*?([\d,]+\.\d+)', text)
    if not total_match:
        total_match = re.search(r'Total in Words\s*:.*?\n.*?([\d,]+\.\d+)', text)
    if total_match:
        details["Total Amount"] = total_match.group(1)

    return details


def extract_items_table(pdf_path):
    """EXACT SAME FUNCTION from your working Colab code - NO CHANGES"""
    tables = camelot.read_pdf(pdf_path, pages='1', strip_text='\n', flavor='lattice')
    if tables:
        df = tables[0].df
        df.columns = df.iloc[0]
        df = df[1:]  # remove header row
        df.reset_index(drop=True, inplace=True)
        return df
    return pd.DataFrame()
