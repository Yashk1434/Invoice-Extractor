import pandas as pd
import os
import pdfplumber
import re

def get_details(file_name):
    """
    Extract details from Flipkart invoice PDF using pdfplumber.
    Args:
        file_name (str): Name of the PDF file to process (should be in 'uploads' folder)
    Returns:
        dict: Contains both invoice summary and item details DataFrames
    """
    try:
        file_path = os.path.join("uploads", file_name)

        if not os.path.exists(file_path):
            print(f"[FLIPKART] File not found: {file_path}")
            return create_empty_result()

        # === Step 1: Extract Metadata ===
        metadata = extract_metadata_flipkart(file_path)

        # === Step 2: Extract Item Details ===
        item_details = extract_items_flipkart(file_path)

        # === Step 3: Build DataFrames ===
        invoice_summary = pd.DataFrame([metadata])

        # Add metadata columns to each item row (for context)
        if not item_details.empty:
            for key, value in metadata.items():
                if key not in ["Source_File"]:
                    item_details[key] = value

        print(
            f"[FLIPKART] Successfully processed {file_name} - Invoice summary: 1 record, Item details: {len(item_details)} items")

        return {
            "invoice_summary": invoice_summary,
            "item_details": item_details,
            "has_items": not item_details.empty
        }

    except Exception as e:
        print(f"[FLIPKART] Error processing {file_name}: {e}")
        return create_empty_result()


def create_empty_result():
    """Create empty result structure for Flipkart extractor"""
    return {
        "invoice_summary": pd.DataFrame(),
        "item_details": pd.DataFrame(),
        "has_items": False
    }


def extract_metadata_flipkart(file_path):
    """Extract metadata (header fields) from Flipkart invoice PDF"""
    # Set up default metadata fields (only add more as needed)
    metadata = {
        "Order_Id": "",
        "Order_Date": "",
        "Invoice_No": "",
        "Invoice_Date": "",
        "GSTIN": "",
        "PAN": "",
        "Seller_Name": "",
        "Seller_GST": "",
        "Billing_Address": "",
        "Shipping_Address": "",
        "Seller_Registered_Address": "",
        "Total_Qty": "",
        "Total_Price": "",
        "Vendor": "Flipkart",
        "Description": "Flipkart Invoice",
        "Source_File": os.path.basename(file_path)
    }

    try:
        with pdfplumber.open(file_path) as pdf:
            text = pdf.pages[0].extract_text()

        patterns = {
            'Order_Id': r'Order Id:\s*([A-Z0-9]+)',
            'Order_Date': r'Order Date:\s*([\d\-\:, PMAM]+)',
            'Invoice_No': r'Invoice No:\s*([A-Z0-9]+)',
            'Invoice_Date': r'Invoice Date:\s*([\d\-\:, PMAM]+)',
            'GSTIN': r'GSTIN:\s*([A-Z0-9]+)',
            'PAN': r'PAN:\s*([A-Z0-9]+)',
            'Seller_Name': r'Sold By\s*(.*?)(?=Shipping ADDRESS|Billing Address)',
            'Seller_GST': r'GST:\s*([A-Z0-9]+)',
            'Billing_Address': r'Billing Address\s*(.*?)(?=Gross Taxable|Product Description)',
            'Shipping_Address': r'Shipping ADDRESS\s*(.*?)(?=Gross Taxable|Product Description)',
            'Seller_Registered_Address': r'Seller Registered Address:\s*(.*?)(?=Declaration)',
            'Total_Qty': r'TOTAL QTY:\s*([\d]+)',
            'Total_Price': r'TOTAL PRICE:\s*([\d\.]+)',
        }

        for key, pat in patterns.items():
            match = re.search(pat, text, re.DOTALL)
            if match:
                val = match.group(1).strip().replace('\n', ' ')
                val = re.sub(r'\s+', ' ', val)
                metadata[key] = val

        print(f"[FLIPKART] Extracted metadata: Order {metadata['Order_Id']}, Invoice {metadata['Invoice_No']}")

    except Exception as e:
        print(f"[FLIPKART] Error extracting metadata: {e}")

    return metadata


def extract_items_flipkart(file_path):
    """Extract item details from Flipkart invoice PDF using pdfplumber."""

    try:
        with pdfplumber.open(file_path) as pdf:
            text = pdf.pages[0].extract_text()

        lines = text.split('\n')
        items_data = []

        # Adjust this part as per real Flipkart invoice slicing logic:
        if len(lines) > 13:
            try:
                product_name = lines[11] + " " + lines[12].split('HSN:')[0] + lines[13]
                product_name = product_name.replace('|', '').strip()
                numbers_line = lines[12]
                hsn_match = re.search(r'HSN: (\d+)', numbers_line)
                tax_match = re.search(r'IGST: (\d+%)', numbers_line)
                hsn_info = f"HSN: {hsn_match.group(1) if hsn_match else 'N/A'} | IGST: {tax_match.group(1) if tax_match else 'N/A'}"
                numbers = re.findall(r'\d+\.\d+|\d+', numbers_line)
                if len(numbers) >= 6:
                    items_data.append({
                        'Description': product_name,
                        'HSN/Tax_Info': hsn_info,
                        'Qty': numbers[-6],
                        'Gross_Amount': numbers[-5],
                        'Discount': numbers[-4],
                        'Taxable_Value': numbers[-3],
                        'IGST_Amount': numbers[-2],
                        'Total': numbers[-1]
                    })
            except Exception as e:
                print(f"[FLIPKART] Error extracting main product: {e}")

        # Shipping charges
        if len(lines) > 16:
            try:
                shipping_desc = lines[14] + " " + lines[16]
                shipping_numbers = re.findall(r'\d+\.\d+|\d+', lines[15])
                if len(shipping_numbers) >= 6:
                    items_data.append({
                        'Description': shipping_desc,
                        'HSN/Tax_Info': '',
                        'Qty': shipping_numbers[0],
                        'Gross_Amount': shipping_numbers[1],
                        'Discount': shipping_numbers[2],
                        'Taxable_Value': shipping_numbers[3],
                        'IGST_Amount': shipping_numbers[4],
                        'Total': shipping_numbers[5]
                    })
            except Exception as e:
                print(f"[FLIPKART] Error extracting shipping: {e}")

        # If more sophisticated table extraction is needed, add it here.

        if items_data:
            df = pd.DataFrame(items_data)
            # Add Source File column for traceability
            df["Source_File"] = os.path.basename(file_path)
            # Optional: Standard column names mapping
            return df
        else:
            print(f"[FLIPKART] No item rows found.")
            return pd.DataFrame()

    except Exception as e:
        print(f"[FLIPKART] Error extracting items: {e}")
        return pd.DataFrame()
