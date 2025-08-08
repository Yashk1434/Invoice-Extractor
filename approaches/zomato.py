import os
import re
import pandas as pd
import camelot
import pdfplumber
from datetime import datetime

# ----------------------
# Zomato Invoice Extractor
# ----------------------

class ZomatoInvoiceExtractor:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.extracted_data = {}
        self.full_text = ""
        self.pages_text = []

    def _extract_text_from_pdf(self, pdf_path: str):
        """Extract combined and per-page text using pdfplumber."""
        full_text = ""
        pages_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
                    full_text += f"\n--- PAGE {i+1} ---\n{page_text}\n"
                else:
                    pages_text.append("")
        return full_text, pages_text

    def _extract_regex(self, pattern, text, flags=0):
        try:
            match = re.search(pattern, text, flags)
            if match and match.group(1):
                result = match.group(1).strip()
                result = re.sub(r'\s+', ' ', result)
                return result if result else "N/A"
            return "N/A"
        except Exception:
            return "N/A"

    def parse_page_1_header(self, text_content):
        # Parse header using regex patterns
        patterns = {
            "Legal Entity Name": [
                r"Legal Entity Name[:\s]*(.+?)(?:\n|Restaurant Name|$)",
                r"Legal Entity[:\s]*(.+?)(?:\n|Restaurant|$)"
            ],
            "Restaurant Name": [
                r"Restaurant Name[:\s]*(.+?)(?:\n|Restaurant Address|Address|$)",
                r"Restaurant[:\s]*(.+?)(?:\n|Address|$)"
            ],
            "Restaurant Address": [
                r"Restaurant Address[:\s]*(.+?)(?:\n|Restaurant GSTIN|GSTIN|$)",
                r"Address[:\s]*(.+?)(?:\n|GSTIN|$)"
            ],
            "Restaurant GSTIN": [
                r"Restaurant GSTIN[:\s]*([A-Z0-9]{15})",
                r"GSTIN[:\s]*([A-Z0-9]{15})"
            ],
            "Restaurant FSSAI": [
                r"Restaurant FSSAI[:\s]*(\d{14})",
                r"FSSAI[:\s]*(\d{14})"
            ],
            "Invoice No.": [
                r"Invoice No\.?[:\s]*([A-Z0-9\-/]+)",
                r"Invoice Number[:\s]*([A-Z0-9\-/]+)"
            ],
            "Invoice Date": [
                r"Invoice Date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
                r"Date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{4})"
            ],
            "Customer Name": [
                r"Customer Name[:\s]*(.+?)(?:\n|Delivery Address|Address|$)",
                r"Customer[:\s]*(.+?)(?:\n|Address|$)"
            ],
            "Order ID": [
                r"Order ID[:\s]*(\d+)",
                r"Order[:\s]*(\d+)"
            ],
            "HSN Code": [
                r"HSN Code[:\s]*(\d+)",
                r"HSN[:\s]*(\d+)"
            ]
        }
        info = {}
        for field, pats in patterns.items():
            for pat in pats:
                result = self._extract_regex(pat, text_content, re.IGNORECASE|re.DOTALL)
                if result != "N/A":
                    info[field] = result
                    break
            if field not in info:
                info[field] = "N/A"

        # Delivery address (multi-line)
        d_patterns = [
            r"Delivery Address[:\s]*(.+?)(?:\n.*?State|State name|$)",
            r"Address[:\s]*(.+?)(?:\n.*?State|$)"
        ]
        for p in d_patterns:
            m = re.search(p, text_content, re.IGNORECASE|re.DOTALL)
            if m:
                val = m.group(1).strip().replace('\n',' ')
                val = re.sub(r'\s+', ' ', val)
                if len(val) > 3:
                    info["Delivery Address"] = val
                    break
        if "Delivery Address" not in info:
            info["Delivery Address"] = "N/A"

        info["State name & Place of Supply"] = self._extract_regex(
            r"State name.*?Place of Supply[:\s]*(.+?)(?:\n|$)",
            text_content, re.IGNORECASE|re.DOTALL
        )
        info["Service Description"] = self._extract_regex(
            r"Service Description[:\s]*(.+?)(?:\n|Amount|$)",
            text_content, re.IGNORECASE|re.DOTALL
        )
        info["Amount (in words)"] = self._extract_regex(
            r"Amount.*?words[:\s]*(.+?)(?:\n|Order|$)",
            text_content, re.IGNORECASE|re.DOTALL
        )
        return info

    def parse_page_2_header(self, text_content):
        patterns = {
            "Zomato Limited Address": [
                r"Address[:\s]*[\"']?(.+?)[\"']?(?:\n.*?State|State|$)",
                r"Zomato.*?Address[:\s]*(.+?)(?:\n|State|$)"
            ],
            "Zomato Limited State": [
                r"State[:\s]*[\"']?(.+?)[\"']?(?:\n|Email|$)"
            ],
            "Zomato Limited Email ID": [
                r"Email ID[:\s]*[\"']?(.+?)[\"']?(?:\n|Invoice|$)"
            ],
            "Zomato Limited Invoice No": [
                r"Invoice No[:\s]*[\"']?(.+?)[\"']?(?:\n|PAN|$)"
            ],
            "Zomato Limited PAN": [
                r"PAN[:\s]*[\"']?([A-Z]{5}\d{4}[A-Z])[\"']?"
            ],
            "Zomato Limited CIN": [
                r"CIN[:\s]*[\"']?([A-Z]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})[\"']?"
            ],
            "Zomato Limited GSTIN": [
                r"GSTIN[:\s]*[\"']?([A-Z0-9]{15})[\"']?"
            ]
        }
        info = {}
        for field, pats in patterns.items():
            for pat in pats:
                result = self._extract_regex(pat, text_content, re.IGNORECASE|re.DOTALL)
                if result != "N/A":
                    info[field] = result
                    break
            if field not in info:
                info[field] = "N/A"
        return info

    def _clean_dataframe_columns(self, df):
        if df.empty: return df
        df = df.dropna(axis=1, how='all')
        # Handle duplicate columns
        cols, seen, new_cols = df.columns.tolist(), {}, []
        for col in cols:
            if col in seen:
                seen[col] += 1
                new_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0; new_cols.append(col)
        df.columns = new_cols
        return df

    def process_invoice(self):
        # Step 1: Text extraction
        self.full_text, self.pages_text = self._extract_text_from_pdf(self.pdf_path)
        if not self.full_text:
            print("[ZOMATO] No text found in PDF.")
            return {}

        page1_text = self.pages_text[0] if len(self.pages_text) > 0 else ""
        page2_text = self.pages_text[1] if len(self.pages_text) > 1 else ""

        self.extracted_data['restaurant_invoice_header'] = self.parse_page_1_header(page1_text)
        self.extracted_data['zomato_service_invoice_header'] = self.parse_page_2_header(page2_text)

        # Tables
        try:
            tables = camelot.read_pdf(self.pdf_path, pages='all', flavor='stream')
            # Restaurant (Page 1) items table
            if len(tables) > 0:
                df = tables[0].df
                df = self._clean_dataframe_columns(df)
                header_idx = -1
                for i, row in df.iterrows():
                    if 'particulars' in ' '.join(row.astype(str).values).lower() or 'item' in ' '.join(row.astype(str).values).lower():
                        header_idx = i; break
                if header_idx != -1:
                    df.columns = [str(col).replace('\n', ' ').strip() for col in df.iloc[header_idx]]
                    df = df[header_idx+1:].reset_index(drop=True)
                df = self._clean_dataframe_columns(df)
                df.dropna(how='all', inplace=True)
                self.extracted_data['restaurant_items_table'] = df.to_dict(orient='records')
            else:
                self.extracted_data['restaurant_items_table'] = []
            # Zomato service (Page 2) table
            if len(tables) > 1:
                df2 = tables[1].df
                df2 = self._clean_dataframe_columns(df2)
                header_idx2 = -1
                for i, row in df2.iterrows():
                    if 'particulars' in ' '.join(row.astype(str).values).lower() and ('cgst' in ' '.join(row.astype(str).values).lower() or 'tax' in ' '.join(row.astype(str).values).lower()):
                        header_idx2 = i; break
                if header_idx2 != -1:
                    df2.columns = [str(col).replace('\n', ' ').strip() for col in df2.iloc[header_idx2]]
                    df2 = df2[header_idx2+1:].reset_index(drop=True)
                df2 = self._clean_dataframe_columns(df2)
                df2.dropna(how='all', inplace=True)
                self.extracted_data['zomato_service_table'] = df2.to_dict(orient='records')
            else:
                self.extracted_data['zomato_service_table'] = []
        except Exception as e:
            print(f"[ZOMATO] Table extraction error: {e}")
            self.extracted_data['restaurant_items_table'] = []
            self.extracted_data['zomato_service_table'] = []

        return self.extracted_data

# ---- Backend-Orchestrator Compatible Entrypoint ----

def get_details(file_name):
    """
    Standard extractor API: receives file name (from uploads/).
    Returns dict with 'invoice_summary' (page 1 header), 'item_details' (page 1 table), and has_items
    """
    file_path = os.path.join("uploads", file_name)
    if not os.path.exists(file_path):
        print(f"[ZOMATO] File not found: {file_path}")
        return {
            "invoice_summary": pd.DataFrame(),
            "item_details": pd.DataFrame(),
            "has_items": False
        }
    extractor = ZomatoInvoiceExtractor(file_path)
    data = extractor.process_invoice()
    header = data.get("restaurant_invoice_header", {})
    items = data.get("restaurant_items_table", [])
    invoice_summary = pd.DataFrame([header]) if header else pd.DataFrame()
    item_details = pd.DataFrame(items) if items else pd.DataFrame()
    has_items = not item_details.empty
    return {
        "invoice_summary": invoice_summary,
        "item_details": item_details,
        "has_items": has_items
    }

# --- Optional Standalone Debug Test ---
# if __name__ == "__main__":
#     # This test block is for direct CLI usage and doesn't affect orchestrator use
#     test_file = "zomato1.pdf"
#     res = get_details(test_file)
#     print("Header:")
#     print(res["invoice_summary"])
#     print("Items:")
#     print(res["item_details"])
#     if res["has_items"]:
#         excel_file = f"zomato_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
#         with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
#             res["invoice_summary"].to_excel(writer, sheet_name="Invoice_Header", index=False)
#             res["item_details"].to_excel(writer, sheet_name="Items_Table", index=False)
#         print(f"Excel saved as: {excel_file}")
