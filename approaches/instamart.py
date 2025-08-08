import os
import pdfplumber
import pandas as pd
import re

def extract_instamart_invoice(pdf_path):
    def extract_header(text):
        patterns = {
            'Order Id': r'Order Id:\s*([A-Z0-9]+)',
            'Order Date': r'Order Date:\s*([0-9\-:, PM AM]+)',
            'Invoice No': r'Invoice No:\s*([A-Z0-9]+)', 
            'Invoice Date': r'Invoice Date:\s*([0-9\-:, PM AM]+)',
            'GSTIN': r'GSTIN:\s*([A-Z0-9]+)',
            'PAN': r'PAN:\s*([A-Z0-9]+)',
            'Sold By': r'Sold By\s*(.*?)(?=Shipping ADDRESS|Billing Address)',
            'Seller GST': r'GST:\s*([A-Z0-9]+)',
            'Billing Address': r'Billing Address\s*(.*?)(?=Gross Taxable|Product Description)',
            'Shipping Address': r'Shipping ADDRESS\s*(.*?)(?=Gross Taxable|Product Description)',
            'Seller Registered Address': r'Seller Registered Address:\s*(.*?)(?=Declaration)',
            'Total Qty': r'TOTAL QTY:\s*([0-9]+)',
            'Total Price': r'TOTAL PRICE:\s*([0-9.]+)',
        }
        header_data = {}
        for key, pat in patterns.items():
            match = re.search(pat, text, re.DOTALL)
            if match:
                val = match.group(1).strip().replace('\n', ' ')
                val = re.sub(r'\s+', ' ', val)
                header_data[key] = val
            else:
                header_data[key] = ""
        return header_data

    def extract_items_table_fixed(text):
        lines = text.split('\n')
        items_data = []
        # Protect against index errors
        try:
            if len(lines) > 13:
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
                        'HSN/Tax Info': hsn_info,
                        'Qty': numbers[-6],
                        'Gross Amount': numbers[-5],
                        'Discount': numbers[-4], 
                        'Taxable Value': numbers[-3],
                        'IGST Amount': numbers[-2],
                        'Total': numbers[-1]
                    })
            if len(lines) > 16:
                shipping_desc = lines[14] + " " + lines[16]
                shipping_numbers = re.findall(r'\d+\.\d+|\d+', lines[15])
                if len(shipping_numbers) >= 6:
                    items_data.append({
                        'Description': shipping_desc,
                        'HSN/Tax Info': '',
                        'Qty': shipping_numbers[0],
                        'Gross Amount': shipping_numbers[1],
                        'Discount': shipping_numbers[2],
                        'Taxable Value': shipping_numbers[3], 
                        'IGST Amount': shipping_numbers[4],
                        'Total': shipping_numbers[5]
                    })
        except Exception as e:
            print(f"[INSTAMART] Error processing lines: {e}")
        return pd.DataFrame(items_data)

    # Main extraction process
    with pdfplumber.open(pdf_path) as pdf:
        full_text = pdf.pages[0].extract_text()

    # Extract both header and items data
    header_data = extract_header(full_text)
    header_df = pd.DataFrame(list(header_data.items()), columns=['Field', 'Value'])
    items_df = extract_items_table_fixed(full_text)

    return header_df, items_df

def get_details(file_name):
    # Entry point for orchestrator: looks for file in uploads/
    file_path = os.path.join("uploads", file_name)
    if not os.path.exists(file_path):
        print(f"[INSTAMART] File not found: {file_path}")
        return {
            "invoice_summary": pd.DataFrame(),
            "item_details": pd.DataFrame(),
            "has_items": False
        }
    header_df, items_df = extract_instamart_invoice(file_path)
    has_items = not items_df.empty
    return {
        "invoice_summary": header_df,
        "item_details": items_df,
        "has_items": has_items
    }

# Optional standalone test
# if __name__ == "__main__":
#     # For offline testing only
#     pdf_file = "instamart_invoice_sample.pdf"
#     header_df, items_df = extract_instamart_invoice(pdf_file)
#     print("Header:\n", header_df)
#     print("Items:\n", items_df)
#     if not items_df.empty:
#         header_df.to_excel("instamart_invoice_extracted.xlsx", sheet_name="Invoice_Header", index=False)
#         items_df.to_excel("instamart_invoice_extracted.xlsx", sheet_name="Items_Table", index=False)
#         print("Excel saved.")
