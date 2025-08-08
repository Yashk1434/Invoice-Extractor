import os
import re
import pandas as pd
import pdfplumber
import camelot
import tabula

# --- Universal Patterns for Header Field Extraction ---
universal_patterns = {
    'invoice_number': [
        r'invoice\s*(?:no|number|#)[:\s]*([A-Z0-9\-/]+)',
        r'bill\s*(?:no|number)[:\s]*([A-Z0-9\-/]+)',
        r'receipt\s*(?:no|number)[:\s]*([A-Z0-9\-/]+)',
        r'(\d{10,})',  # Long numeric sequences
    ],
    'order_number': [
        r'order\s*(?:no|number|id)[:\s]*([A-Z0-9\-/]+)',
        r'order[:\s]*([A-Z0-9\-/]+)',
        r'ref(?:erence)?\s*(?:no|number)[:\s]*([A-Z0-9\-/]+)'
    ],
    'date': [
        r'date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'date[:\s]*(\d{4}-\d{2}-\d{2})',
        r'(\d{1,2}\s+[A-Za-z]+\s+\d{4})',
        r'(\d{2}\.\d{2}\.\d{4})'
    ],
    'amount': [
        r'total[:\s]*₹?\s*([0-9,]+\.?\d*)',
        r'amount[:\s]*₹?\s*([0-9,]+\.?\d*)',
        r'₹\s*([0-9,]+\.?\d*)',
        r'rs\.?\s*([0-9,]+\.?\d*)',
        r'inr\s*([0-9,]+\.?\d*)'
    ],
    'customer': [
        r'(?:customer|bill\s*to|ship\s*to|sold\s*to)[:\s]*([A-Za-z\s]+)',
        r'name[:\s]*([A-Za-z\s]+)',
    ],
    'gst': [
        r'gst(?:in)?[:\s]*([A-Z0-9]{15})',
        r'tax\s*id[:\s]*([A-Z0-9]{15})',
        r'([A-Z0-9]{2}[A-Z0-9]{10}[A-Z0-9]{3})'  # GST format pattern
    ],
    'seller': [
        r'(?:sold\s*by|seller|vendor)[:\s]*([A-Za-z\s&.,()]+)',
        r'(?:from|by)[:\s]*([A-Za-z\s&.,()]+)'
    ],
    'address': [
        r'address[:\s]*([A-Za-z0-9\s,.-]+)',
        r'([A-Za-z\s,.-]+\d{6})',  # Address ending with pincode
    ]
}

def extract_universal_header(text, filename=""):
    """Extracts header fields using broad regexes from universal_patterns."""
    from datetime import datetime
    extracted_data = {
        'filename': filename,
        'extraction_method': 'universal2',
        'extraction_timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    for field_type, patterns in universal_patterns.items():
        found_value = ""
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match[0] else (match[1] if len(match)>1 else "")
                    if match and len(str(match).strip()) > 2:
                        found_value = str(match).strip()
                        break
                if found_value: break
        extracted_data[field_type] = found_value
    # Try to get a probable company
    company_patterns = [
        r'([A-Z][A-Za-z\s&]+(?:LTD|LIMITED|PRIVATE|PVT|COMPANY|CORP|INC))',
        r'([A-Z][A-Za-z]+\.com)',
        r'([A-Z][A-Za-z\s]+(?:STORE|MART|SHOP|PHARMACY))'
    ]
    for pattern in company_patterns:
        matches = re.findall(pattern, text)
        if matches:
            extracted_data['detected_company'] = matches[0]
            break
    else:
        extracted_data['detected_company'] = ""
    return extracted_data

def extract_items_universal(text):
    """Extracts probable item lines from text as a fallback for unknown formats."""
    items = []
    item_patterns = [
        r'(\d+)\s+([A-Za-z][^0-9\n]{10,50}?)\s+₹?\s*([0-9,]+\.?\d*)',
        r'([A-Za-z][^0-9\n]{10,50}?)\s+(\d+)\s+₹?\s*([0-9,]+\.?\d*)',
        r'([A-Za-z][^0-9\n]{15,}?)\s+₹?\s*([0-9,]+\.?\d*)'
    ]
    for pattern in item_patterns:
        matches = re.finditer(pattern, text, re.MULTILINE)
        for match in matches:
            groups = match.groups()
            if len(groups) == 3:
                if groups[0].isdigit():
                    item = {
                        'quantity': groups[0],
                        'description': groups[1].strip(),
                        'amount': groups[2]
                    }
                else:
                    item = {
                        'description': groups[0].strip(),
                        'quantity': groups[1] if groups[1].isdigit() else '1',
                        'amount': groups[2]
                    }
            elif len(groups) == 2:
                item = {
                    'description': groups[0].strip(),
                    'quantity': '1',
                    'amount': groups[1]
                }
            else:
                continue
            if len(item['description']) > 5 and not item['description'].isdigit():
                items.append(item)
    # Remove duplicates
    seen = set()
    unique_items = []
    for item in items:
        item_key = (item['description'], item['amount'])
        if item_key not in seen:
            seen.add(item_key)
            unique_items.append(item)
    return unique_items[:10]

def extract_table_with_fallback(pdf_path):
    """Try Camelot, fallback to Tabula for table extraction from PDF."""
    tables = []
    try:
        camelot_tables = camelot.read_pdf(str(pdf_path), pages='all', flavor='lattice')
        tables = [table.df for table in camelot_tables if not table.df.empty and table.df.shape[0] > 1]
        if tables:
            return tables
    except Exception:
        pass
    try:
        tabula_tables = tabula.read_pdf(str(pdf_path), pages='all', multiple_tables=True)
        tabula_tables = [df for df in tabula_tables if isinstance(df, pd.DataFrame) and not df.empty]
        return tabula_tables
    except Exception:
        return []
        
def keep_only_nonempty_columns(df):
    if df.empty:
        return df
    df = df.dropna(axis=1, how='all')
    # Remove columns if (after NaN removal), all values are empty/whitespace string
    df = df.loc[:, ~(
        df.applymap(lambda x: (isinstance(x, float) and pd.isnull(x)) or (isinstance(x, str) and x.strip() == '')).all()
    )]
    return df

# ---------------------------- Orchestrator-compatible Entrypoint ----------------------------

def get_details(file_name):
    """
    Universal invoice extractor (universal2): for *any* PDF, field and table extraction.
    Args:
        file_name: name of a PDF file in the 'uploads/' directory.
    Returns:
        {
            'invoice_summary': DataFrame for header fields,
            'item_details': DataFrame for items (from tables or fallback lines),
            'has_items': bool
        }
    """
    uploads_dir = "uploads"
    file_path = os.path.join(uploads_dir, file_name)
    if not os.path.isfile(file_path):
        print(f"[UNIVERSAL2] File not found: {file_path}")
        return {
            "invoice_summary": pd.DataFrame(),
            "item_details": pd.DataFrame(),
            "has_items": False
        }
    # -- Step 1: Extract PDF text --
    try:
        with pdfplumber.open(file_path) as pdf:
            full_text = ''
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text += page_text + '\n'
    except Exception as e:
        print(f"[UNIVERSAL2] Text extraction error: {e}")
        return {
            "invoice_summary": pd.DataFrame(),
            "item_details": pd.DataFrame(),
            "has_items": False
        }

    # -- Step 2: Header field extraction --
    header_data = extract_universal_header(full_text, filename=file_name)
    invoice_summary_df = pd.DataFrame([header_data])
    invoice_summary_df = keep_only_nonempty_columns(invoice_summary_df)

    # -- Step 3: Try table extraction --
    tables = extract_table_with_fallback(file_path)
    if tables:
        # Merge all tables into one if possible
        merged_df = pd.concat(tables, ignore_index=True)
        item_details_df = keep_only_nonempty_columns(merged_df)
    else:
        # If table extraction fails, fallback to line/regex item extraction
        items = extract_items_universal(full_text)
        item_details_df = pd.DataFrame(items)
        item_details_df = keep_only_nonempty_columns(item_details_df)

    has_items = not item_details_df.empty
    return {
        "invoice_summary": invoice_summary_df,
        "item_details": item_details_df,
        "has_items": has_items
    }

# # -- Optional standalone usage for offline test --
# if __name__ == "__main__":
#     test_pdf = "sample_invoice.pdf"
#     res = get_details(test_pdf)
#     print(res["invoice_summary"])
#     print(res["item_details"])
#     print("Has items:", res["has_items"])
