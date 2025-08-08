import os
import re
import fitz  # PyMuPDF
import numpy as np
import pandas as pd
import camelot
import tabula

def load_vectorizer_and_classifier():
    # These should be set to correct absolute/relative paths as per your deployment
    from joblib import load
    vectorizer = load("vectorizer.pkl")
    header_model = load("classifier.pkl")
    return vectorizer, header_model

def load_yolo_model():
    from ultralytics import YOLO
    return YOLO("best.pt")

# ------- Universal table & field extractor for invoices -------

target_fields = [
    "Invoice Number", "Invoice Date", "PAN Number", "Vendor", "Order Number", "Order Date",
    "Quantity", "Seller Details", "Billing Address", "Product Description", "Net Amount",
    "GST Amount", "Tax Rate", "Taxable Value", "Shipping Charge", "Total Amount", "Total Amount (in words)"
]

def mask_tables_in_pdf(input_pdf_path, output_pdf_path, model):
    doc = fitz.open(input_pdf_path)
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_width, page_height = page.rect.width, page.rect.height
        zoom = 300 / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        results = model.predict(source=img, conf=0.3, iou=0.5)
        boxes_px = results[0].boxes.xyxy.cpu().numpy() if results else []
        x_scale = page_width / pix.width
        y_scale = page_height / pix.height
        for box in boxes_px:
            x0, y0, x1, y1 = box
            rect = fitz.Rect(
                x0 * x_scale,
                page_height - y1 * y_scale,
                x1 * x_scale,
                page_height - y0 * y_scale,
            )
            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
    doc.save(output_pdf_path)

def extract_text_from_masked_pdf(pdf_path):
    text_lines = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text_lines.append(page.get_text())
    return " ".join(text_lines)

def extract_tables_with_fallback(pdf_path):
    try:
        camelot_tables = camelot.read_pdf(pdf_path, pages='all', flavor='lattice')
        tables = [table.df for table in camelot_tables]
        fallback_needed = False
        if not tables:
            fallback_needed = True
        else:
            for df in tables:
                if df.empty or df.isnull().values.any():
                    fallback_needed = True
                    break
        if not fallback_needed:
            return tables
    except Exception:
        pass
    try:
        tabula_tables = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
        tabula_dfs = [df for df in tabula_tables if isinstance(df, pd.DataFrame) and not df.empty]
        return tabula_dfs
    except Exception:
        return []

def extract_fields(text):
    field_data = dict.fromkeys(target_fields, "")
    patterns = {
        "Invoice Number": r"(?:Invoice\s*(?:No|Number)\s*[:\-]?\s*)([\w\-]+)",
        "Invoice Date": r"(?:Invoice\s*Date\s*[:\-]?\s*)([\d\/\-\.,]+)",
        "Order Number": r"(?:Order\s*(?:No|Number)\s*[:\-]?\s*)([\w\-]+)",
        "Order Date": r"(?:Order\s*Date\s*[:\-]?\s*)([\d\/\-\.,]+)",
        "PAN Number": r"(?:PAN\s*No\s*[:\-]?\s*)([A-Z]{5}\d{4}[A-Z])",
        "Vendor": r"(?:Vendor|Seller|Supplier)\s*(?:Name)?\s*[:\-]?\s*([\w\s&.,-]+)",
        "Seller Details": r"(?:Seller\s*Details\s*[:\-]?\s*)([\w\s&.,\-/]+)",
        "Billing Address": r"(?:Billing\s*Address\s*[:\-]?\s*)([\w\s&.,\-/]+)",
        "Product Description": r"(?:Product\s*Description[s]?\s*[:\-]?\s*)([\w\s&.,\-]+)",
        "Quantity": r"(?:Quantity\s*[:\-]?\s*)(\d+)",
        "Net Amount": r"(?:Net\s*Amount\s*[:\-]?\s*₹?\s*)([\d,\.]+)",
        "GST Amount": r"(?:GST\s*Amount\s*[:\-]?\s*₹?\s*)([\d,\.]+)",
        "Tax Rate": r"(\d{1,2}%\s*(?:SGST|CGST|IGST)?)",
        "Taxable Value": r"(?:Taxable\s*Value\s*[:\-]?\s*₹?\s*)([\d,\.]+)",
        "Shipping Charge": r"(?:Shipping\s*Charge\s*[:\-]?\s*₹?\s*)([\d,\.]+)",
        "Total Amount": r"(?:Total\s*Amount\s*[:\-]?\s*₹?\s*)([\d,\.]+)",
        "Total Amount (in words)": r"Total\s*Amount\s*\(?in\s*words\)?\s*[:\-]?\s*(.+?)(?:\s+E\.?&?O\.?E\.?|$)"
    }
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            value = match.group(1).strip()
            value = re.sub(r'\s+', ' ', value)
            field_data[field] = value
    return field_data

def keep_only_nonempty_columns(df):
    df = df.dropna(axis=1, how='all')
    df = df.loc[:, ~(
        df.applymap(lambda x: (isinstance(x, float) and pd.isnull(x)) or (isinstance(x, str) and x.strip() == '')).all()
    )]
    return df

# ========== Orchestrator-compatible entrypoint ==========

def get_details(file_name):
    """
    Universal invoice extractor.
    Args:
        file_name: name of a PDF file in 'uploads/' directory.

    Returns:
        {
            'invoice_summary': DataFrame of key fields,
            'item_details': DataFrame from item table(s), or empty if none,
            'has_items': bool
        }
    """
    uploads_dir = "uploads"
    file_path = os.path.join(uploads_dir, file_name)
    if not os.path.isfile(file_path):
        print(f"[UNIVERSAL1] File not found: {file_path}")
        return {
            "invoice_summary": pd.DataFrame(),
            "item_details": pd.DataFrame(),
            "has_items": False
        }
    # Load heavy models (so only done if called)
    vectorizer, header_model = load_vectorizer_and_classifier()
    yolo_model = load_yolo_model()

    # Step 1: Mask tables on PDF (so text extraction doesn't grab tabular data)
    masked_path = os.path.join("masked", file_name)
    os.makedirs("masked", exist_ok=True)
    mask_tables_in_pdf(file_path, masked_path, yolo_model)

    # Step 2: Extract text from masked PDF (so only field text remains)
    text = extract_text_from_masked_pdf(masked_path)
    fields = extract_fields(text)

    # Step 3: Extract table(s) from original file, using fallback logic
    tables = extract_tables_with_fallback(file_path)
    item_details_df = pd.DataFrame()
    if tables:
        merged_df = pd.concat(tables, ignore_index=True)
        item_details_df = keep_only_nonempty_columns(merged_df)

    invoice_summary_df = pd.DataFrame([fields])
    invoice_summary_df = keep_only_nonempty_columns(invoice_summary_df)
    has_items = not item_details_df.empty

    return {
        "invoice_summary": invoice_summary_df,
        "item_details": item_details_df,
        "has_items": has_items
    }

# ---- Debugging main block (Optional, for direct CLI test) ----
# if __name__ == "__main__":
#     test_pdf = "sample_invoice.pdf"
#     res = get_details(test_pdf)
#     print("Invoice Summary:")
#     print(res["invoice_summary"])
#     print("Item Table(s):")
#     print(res["item_details"])
#     print("Has items:", res["has_items"])
