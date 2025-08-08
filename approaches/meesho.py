import os
import re
import pandas as pd
import pdfplumber

# ------------------- Utility Functions -------------------

def extract_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ''
        for page in pdf.pages:
            page_text = page.extract_text()
            full_text += (page_text or '') + '\n'
    return full_text

def extract_header(text):
    header = {}
    # Extract fields
    bill_to_match = re.search(r'Bill To\s*(.*?)\s*Ship To', text, re.DOTALL)
    header['Bill To'] = bill_to_match.group(1).strip().replace('\n', ' ') if bill_to_match else "N/A"

    ship_to_match = re.search(r'Ship To\s*(.*?)\s*Invoice Number', text, re.DOTALL)
    header['Ship To'] = ship_to_match.group(1).strip().replace('\n', ' ') if ship_to_match else "N/A"

    invoice_number_match = re.search(r'Invoice Number\s*(\S+)', text)
    header['Invoice Number'] = invoice_number_match.group(1) if invoice_number_match else "N/A"

    order_number_match = re.search(r'Order Number\s*(\S+)', text)
    header['Order Number'] = order_number_match.group(1) if order_number_match else "N/A"

    invoice_date_match = re.search(r'Invoice Date\s*(.*)', text)
    header['Invoice Date'] = invoice_date_match.group(1).strip() if invoice_date_match else "N/A"

    order_date_match = re.search(r'Order Date\s*(.*)', text)
    header['Order Date'] = order_date_match.group(1).strip() if order_date_match else "N/A"

    place_of_supply_match = re.search(r'Place of Supply\s*:\s*(.*)', text)
    header['Place of Supply'] = place_of_supply_match.group(1).strip() if place_of_supply_match else "N/A"

    seller_name_match = re.search(r'Sold by:\s*(.*?)\n', text)
    header['Seller Name'] = seller_name_match.group(1).strip() if seller_name_match else "N/A"

    seller_address_match = re.search(r'Sold by:[\s\S]*?(\d{6})', text)
    header['Seller Address'] = seller_address_match.group(0).strip().replace('\n', ' ') if seller_address_match else "N/A"

    seller_gstin_match = re.search(r'(\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d[Z]{1}[A-Z\d])', text)
    header['Seller GSTIN'] = seller_gstin_match.group(1) if seller_gstin_match else "N/A"

    # Other Meesho-specific fields can be extracted here if needed

    return pd.DataFrame(list(header.items()), columns=['Field', 'Value'])

def extract_items(text):
    # Regex for extracting line-item rows
    pattern = re.compile(
        r'(?P<SN>\d+)\s+'
        r'(?P<Description>[^\d]+?)\s+'
        r'(?P<HSN>\d{6})\s+'
        r'(?P<Qty>\S+)\s+'
        r'Rs\.(?P<Gross>\d+\.\d{2})\s+'
        r'Rs\.(?P<Discount>\d+\.\d{2})\s+'
        r'Rs\.(?P<Taxable>\d+\.\d{2})\s+'
        r'IGST\s+@[\d.]+% :Rs\.(?P<Taxes>\d+\.\d{2})\s+'
        r'Rs\.(?P<Total>\d+\.\d{2})',
        re.MULTILINE
    )

    items = []
    for match in pattern.finditer(text):
        item = {
            'SN': match.group('SN'),
            'Description': match.group('Description').strip().replace('\n', ' '),
            'HSN': match.group('HSN'),
            'Qty': match.group('Qty'),
            'Gross Amount': match.group('Gross'),
            'Discount': match.group('Discount'),
            'Taxable Value': match.group('Taxable'),
            'Taxes': match.group('Taxes'),
            'Total': match.group('Total')
        }
        items.append(item)

    return pd.DataFrame(items)

def create_empty_result():
    return {
        "invoice_summary": pd.DataFrame(),
        "item_details": pd.DataFrame(),
        "has_items": False
    }

# ------------------- Main Entry Point -------------------

def get_details(file_name):
    """
    Extracts header and item details from a Meesho PDF invoice from uploads/.
    Returns a dict suitable for your backend/Excel creator.
    """
    file_path = os.path.join("uploads", file_name)
    if not os.path.exists(file_path):
        print(f"[MEESHO] File not found: {file_path}")
        return create_empty_result()

    try:
        text = extract_text(file_path)
        header_df = extract_header(text)
        items_df = extract_items(text)

        print(f"[MEESHO] Extracted: Header fields {len(header_df)}, Items {len(items_df)}")

        return {
            "invoice_summary": header_df,
            "item_details": items_df,
            "has_items": not items_df.empty
        }
    except Exception as e:
        print(f"[MEESHO] Extraction error: {e}")
        return create_empty_result()

# ----------------- For Direct Debug/Test -----------------
# if __name__ == "__main__":
#     # Test using a PDF in the local directory
#     pdf_path = "meesho3.pdf"   # Change as appropriate
#     file_name = os.path.basename(pdf_path)
#     res = get_details(file_name)
#     if not res["invoice_summary"].empty and not res["item_details"].empty:
#         print("[MEESHO] Extraction successful! Saving Excel...")
#         excel_path = "meesho_invoice_extracted.xlsx"
#         with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
#             res["invoice_summary"].to_excel(writer, sheet_name="Invoice_Header", index=False)
#             res["item_details"].to_excel(writer, sheet_name="Items_Table", index=False)
#         print(f"Saved as: {excel_path}")
#     else:
#         print("[MEESHO] No data extracted.")
