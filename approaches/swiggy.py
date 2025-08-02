import pandas as pd
import os
import pdfplumber
import camelot
import re


def get_details(file_name):
    """
    Extract details from Swiggy invoice PDF using camelot and pdfplumber
    Args:
        file_name (str): Name of the PDF file to process
    Returns:
        dict: Contains both invoice summary and item details DataFrames
    """
    try:
        file_path = os.path.join("uploads", file_name)

        if not os.path.exists(file_path):
            print(f"[SWIGGY] File not found: {file_path}")
            return create_empty_result()

        # === STEP 1: Extract Header Details (same logic as original) ===
        header_details = extract_swiggy_header(file_path)

        # === STEP 2: Extract Items Table (same logic as original) ===
        items_table = extract_swiggy_items(file_path)

        # === STEP 3: Create Two DataFrames ===
        # Invoice Summary DataFrame - convert header dict to DataFrame
        invoice_summary = pd.DataFrame([header_details])

        # Item Details DataFrame - use the extracted items table as-is
        item_details = items_table

        # Add source file to items if not empty
        if not item_details.empty:
            item_details["Source_File"] = os.path.basename(file_path)

        print(f"[SWIGGY] Successfully processed {file_name} - Invoice summary: 1 record, Item details: {len(item_details)} items")

        return {
            "invoice_summary": invoice_summary,
            "item_details": item_details,
            "has_items": not item_details.empty
        }

    except Exception as e:
        print(f"[SWIGGY] Error processing {file_name}: {e}")
        return create_empty_result()


def create_empty_result():
    """Create empty result structure"""
    return {
        "invoice_summary": pd.DataFrame(),
        "item_details": pd.DataFrame(),
        "has_items": False
    }


def extract_swiggy_header(pdf_path):
    """Extract header details - EXACT SAME LOGIC as original"""
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    details = {}

    buyer_match = re.search(r"Invoice To:\s*(.+?)\s*Invoice issued by", text, re.DOTALL)
    if buyer_match:
        details["Buyer Name"] = buyer_match.group(1).strip()

    address_match = re.search(r"Customer Address:\s*(.+?)\s+Restaurant GSTIN", text, re.DOTALL)
    if address_match:
        details["Buyer Address"] = address_match.group(1).replace("\n", ", ").strip()

    restaurant_match = re.search(r"Restaurant Name:\s*(.+)", text)
    if restaurant_match:
        details["Restaurant Name"] = restaurant_match.group(1).strip()

    rest_gstin_match = re.search(r"Restaurant GSTIN:\s*([A-Z0-9]+)", text)
    if rest_gstin_match:
        details["Restaurant GSTIN"] = rest_gstin_match.group(1)

    order_id_match = re.search(r"Order ID:\s*(\d+)", text)
    if order_id_match:
        details["Order ID"] = order_id_match.group(1)

    invoice_no_match = re.search(r"Invoice No:\s*(\S+)", text)
    if invoice_no_match:
        details["Invoice Number"] = invoice_no_match.group(1)

    invoice_date_match = re.search(r"Date of Invoice:\s*(\d{2}-\d{2}-\d{4})", text)
    if invoice_date_match:
        details["Invoice Date"] = invoice_date_match.group(1)

    total_amount_match = re.search(r"Invoice Total\s+([\d\.]+)", text)
    if total_amount_match:
        details["Invoice Total"] = total_amount_match.group(1)

    total_words_match = re.search(r"Invoice total in words\s+(.+?)\s+Authorized Signature", text, re.DOTALL)
    if total_words_match:
        details["Invoice Total (Words)"] = total_words_match.group(1).strip()

    return details


def extract_swiggy_items(pdf_path):
    """Extract items table - EXACT SAME LOGIC as original"""
    # Try camelot first
    try:
        tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream', strip_text='\n')
        for table in tables:
            df = table.df
            if any("Description" in str(cell) for cell in df.iloc[0]):
                df.columns = df.iloc[0]
                df = df[1:].reset_index(drop=True)
                return df
    except Exception as e:
        print("Camelot failed:", e)

    # Fallback: Manual parsing via pdfplumber
    item_rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            lines = page.extract_text().split('\n')
            for line in lines:
                if re.match(r"\d+\.\s+.+\s+OTH\s+\d+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+", line):
                    parts = re.split(r'\s{2,}', line.strip())
                    if len(parts) == 1:  # handle single-spacing fallback
                        parts = re.findall(r"[^\s]+\s|[^\s]+$", line.strip())
                        parts = [''.join(parts).strip()]

                    raw = re.findall(r"(.*?)\s+OTH\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", line)
                    if raw:
                        desc, qty, unit_price, amount, discount, net = raw[0]
                        item_rows.append({
                            "Description": desc.strip(),
                            "Unit": "OTH",
                            "Quantity": qty,
                            "Unit Price": unit_price,
                            "Amount": amount,
                            "Discount": discount,
                            "Net Value": net
                        })

    return pd.DataFrame(item_rows)
