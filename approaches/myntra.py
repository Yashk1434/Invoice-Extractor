import os
import re
import pandas as pd
import pdfplumber
from datetime import datetime
try:
    import pytesseract
    from pdf2image import convert_from_path
except ImportError:
    pytesseract = None
    convert_from_path = None

# -------------------- UTILITY FUNCTIONS --------------------

def extract_text(pdf_path):
    """Extract text from PDF using pdfplumber, with OCR fallback if needed."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text_parts = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            text = "\n".join(text_parts)
    except Exception as e:
        print(f"[MYNTRA] PDF extraction failed: {e}")
        text = ""
    
    # Fallback to OCR if nothing extracted and pytesseract is available
    if not text.strip() and pytesseract and convert_from_path:
        print("[MYNTRA] No text extracted, trying OCR fallback...")
        try:
            images = convert_from_path(pdf_path)
            ocr_texts = []
            for img in images:
                ocr_text = pytesseract.image_to_string(img, config="--psm 6")
                ocr_texts.append(ocr_text)
            text = "\n".join(ocr_texts)
        except Exception as ocr_e:
            print(f"[MYNTRA] OCR extraction failed: {ocr_e}")
            text = ""
    return text

def clean_text(text):
    return re.sub(r'\s+', ' ', text.strip()) if text else ""

def extract_order_number(text):
    for pat in [r"Order Number:\s*(\S+)", r"Order Number\s*(\S+)"]:
        match = re.search(pat, text)
        if match:
            return clean_text(match.group(1))
    return "Not found"

def extract_invoice_numbers(text):
    matches = re.findall(r"Invoice Number:\s*(\S+)", text)
    return [clean_text(m) for m in matches] if matches else ["Not found"]

def extract_packet_id(text):
    match = re.search(r"PacketID:\s*(\S+)", text)
    return clean_text(match.group(1)) if match else "Not found"

def extract_dates(text):
    date_info = {}
    for pat in [
        r"Invoice Date:\s*(\d{1,2}\s+\w+\s+\d{4})",
        r"Date:\s*(\d{1,2}\s+\w+\s+\d{4})",
        r"Invoice Date:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})"
    ]:
        match = re.search(pat, text)
        if match:
            date_info['invoice_date'] = clean_text(match.group(1))
            break
    order_match = re.search(r"Order Date:\s*(\d{1,2}\s+\w+\s+\d{4})", text)
    if order_match:
        date_info['order_date'] = clean_text(order_match.group(1))
    return date_info

def extract_transaction_details(text):
    details = {}
    nm = re.search(r"Nature of Transaction:\s*([^\n]+)", text)
    if nm: details['nature_of_transaction'] = clean_text(nm.group(1))
    pl = re.search(r"Place of Supply:\s*([^\n]+)", text)
    if pl: details['place_of_supply'] = clean_text(pl.group(1))
    ns = re.search(r"Nature of Supply:\s*([^\n]+)", text)
    if ns: details['nature_of_supply'] = clean_text(ns.group(1))
    return details

def extract_customer_details(text):
    info = {}
    try:
        m = re.search(r"Bill to / Ship to:\s*(.*?)Customer Type:", text, re.DOTALL)
        if m:
            block = m.group(1).strip()
            lines = [line for line in block.splitlines() if line.strip()]
            if lines:
                info['customer_name'] = clean_text(lines[0])
                if len(lines) > 1:
                    addr = ' '.join(lines[1:])
                    info['full_address'] = clean_text(addr)
                    pin_match = re.search(r'(\d{6})', addr)
                    if pin_match: info['pincode'] = pin_match.group(1)
                    st_match = re.search(r'([A-Z]{2}),?\s*India', addr)
                    if st_match: info['state'] = st_match.group(1)
        ty = re.search(r"Customer Type:\s*([^\n]+)", text)
        if ty:
            info['customer_type'] = clean_text(ty.group(1))
    except Exception as e:
        info['error'] = f"Error extracting customer details: {e}"
    return info

def extract_seller_details(text):
    sellers = []
    try:
        bill_froms = re.findall(r"Bill From:\s*(.*?)(?=Ship From:|GSTIN Number:|$)", text, re.DOTALL)
        for b in bill_froms:
            lines = [line.strip() for line in b.strip().splitlines() if line.strip()]
            seller = {}
            if lines:
                seller['company_name'] = clean_text(lines[0])
                if len(lines) > 1:
                    seller['address'] = clean_text(' '.join(lines[1:]))
            sellers.append(seller)
        gstins = re.findall(r"GSTIN Number:\s*([A-Z0-9]+)", text)
        for i, gstin in enumerate(gstins):
            if i < len(sellers):
                sellers[i]['gstin'] = clean_text(gstin)
        cins = re.findall(r"CIN:\s*([A-Z0-9]+)", text)
        for i, cin in enumerate(cins):
            if i < len(sellers):
                sellers[i]['cin'] = clean_text(cin)
    except Exception as e:
        sellers.append({"error": f"Error extracting seller details: {e}"})
    return sellers

def extract_detailed_items(text):
    items = []
    invoice_sections = re.split(r"Tax Invoice", text)
    for section in invoice_sections:
        if not section.strip():
            continue
        # Main Regex patterns for product lines and platform fee
        patterns = [
            r"([A-Z0-9]+ - [^H]+?)\s+HSN:\s*(\d+),\s*([\d.]+)%\s*(IGST|CGST|SGST).*?(\d+)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)",
            r"(Platform Fee)\s+HSN:\s*(\d+),\s*([\d.]+)%\s*(IGST|CGST|SGST).*?(\d+)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)"
        ]
        for pat in patterns:
            matches = re.findall(pat, section, re.DOTALL)
            for m in matches:
                if len(m) >= 11:
                    desc = m[0]
                    hsn = m[1]
                    rate = float(m[2])
                    tax_type = m[3]
                    qty = int(m[4])
                    gross_amt = float(m[5].replace(',', ''))
                    disc_amt = float(m[6].replace(',', ''))
                    other_amt = float(m[7].replace(',', ''))
                    taxable_amt = float(m[8].replace(',', ''))
                    tax_amt = float(m[9].replace(',', ''))
                    total_amt = float(m[10].replace(',', ''))
                    # Tax breakdown
                    if tax_type == 'IGST':
                        igst_amount, cgst_amount, sgst_amount = tax_amt, 0.0, 0.0
                    else:
                        cgst_amount = tax_amt / 2
                        sgst_amount = tax_amt / 2
                        igst_amount = 0.0
                    items.append({
                        'product_description': clean_text(desc),
                        'hsn_code': clean_text(hsn),
                        'tax_rate': rate,
                        'tax_type': clean_text(tax_type),
                        'quantity': qty,
                        'gross_amount': gross_amt,
                        'discount': disc_amt,
                        'other_charges': other_amt,
                        'taxable_amount': taxable_amt,
                        'cgst_amount': cgst_amount,
                        'sgst_ugst_amount': sgst_amount,
                        'igst_amount': igst_amount,
                        'cess_amount': 0.0,
                        'total_amount': total_amt
                    })
    return items

def extract_financial_summary(text):
    financial_data = {}
    total_matches = re.findall(r"TOTAL\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)\s+Rs\s+([\d,]+\.?\d*)", text)
    if total_matches:
        t = lambda i: sum(float(match[i].replace(',', '')) for match in total_matches)
        financial_data = {
            'total_gross_amount': t(0),
            'total_discount': t(1),
            'total_other_charges': t(2),
            'total_taxable_amount': t(3),
            'total_tax_amount': t(4),
            'grand_total': t(5),
            'net_savings': t(1),
            'effective_tax_rate': round((t(4)/t(3)*100) if t(3) else 0, 2)
        }
    return financial_data

def create_empty_result():
    return {
        "invoice_summary": pd.DataFrame(),
        "item_details": pd.DataFrame(),
        "has_items": False
    }

# ------------------- MAIN ENTRY POINT -------------------

def get_details(file_name):
    """Extracts header and detailed items from a Myntra invoice in uploads/."""
    file_path = os.path.join("uploads", file_name)
    if not os.path.exists(file_path):
        print(f"[MYNTRA] File not found: {file_path}")
        return create_empty_result()
    try:
        text = extract_text(file_path)
        if not text.strip():
            print("[MYNTRA] No extractable text in file, even with OCR fallback.")
            return create_empty_result()
        # --- Extraction ---
        invoice_row = {
            'order_number': extract_order_number(text),
            'invoice_numbers': ', '.join(extract_invoice_numbers(text)),
            'packet_id': extract_packet_id(text),
            **extract_dates(text),
            **extract_transaction_details(text)
        }
        customer_details = extract_customer_details(text)
        for k in ['customer_name', 'full_address', 'pincode', 'state', 'customer_type']:
            invoice_row[k] = customer_details.get(k, "")
        sellers = extract_seller_details(text)
        if sellers and isinstance(sellers, list):
            for i, seller in enumerate(sellers):
                pref = f'seller_{i+1}_' if len(sellers) > 1 else 'seller_'
                invoice_row.update({f'{pref}company_name': seller.get('company_name', ''),
                                    f'{pref}address': seller.get('address',''),
                                    f'{pref}gstin': seller.get('gstin',''),
                                    f'{pref}cin': seller.get('cin','')})
        fs = extract_financial_summary(text)
        if fs:
            invoice_row.update(fs)
        # DataFrames
        invoice_df = pd.DataFrame([invoice_row])
        items = extract_detailed_items(text)
        items_df = pd.DataFrame(items) if items else pd.DataFrame()
        print(f"[MYNTRA] Extracted: Invoice fields {len(invoice_df.columns)}, Items {len(items_df)}")
        return {
            "invoice_summary": invoice_df,
            "item_details": items_df,
            "has_items": not items_df.empty
        }
    except Exception as e:
        print(f"[MYNTRA] Error: {e}")
        return create_empty_result()

# ----------------- Optional: Standalone test -----------------
if __name__ == "__main__":
    pdf_file = "itemInvoiceDownload-5.pdf"
    res = get_details(pdf_file)
    if not res["invoice_summary"].empty and not res["item_details"].empty:
        print("[MYNTRA] Extraction successful! Saving Excel...")
        excel_path = "itemInvoiceDownload-5_extracted.xlsx"
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            res["invoice_summary"].to_excel(writer, sheet_name="Invoice_Details", index=False)
            res["item_details"].to_excel(writer, sheet_name="Item_Details", index=False)
        print(f"Saved as: {excel_path}")
    else:
        print("[MYNTRA] No data extracted.")

