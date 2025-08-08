"""
Enhanced Amazon Invoice Extractor (APPROACH 1 STYLE)

• Scans a single Amazon invoice PDF
• Pulls all header fields using robust regexes
• Extracts every tabular block with pdfplumber
• Saves Excel (header sheet + one per table)
• Returns a structured result dictionary
• Enhanced error handling and logging
• Configurable output paths and easily usable in orchestration/backend
"""

from __future__ import annotations
import os
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import pdfplumber
import PyPDF2

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AmazonInvoiceExtractor:
    """Amazon invoice extraction with clean error handling."""
    
    def __init__(self, output_base_dir: Optional[str] = None):
        self.output_base_dir = Path(output_base_dir) if output_base_dir else None
        
        # Amazon India GST Invoice field patterns (add/modify for your variants)
        self.field_patterns = {
            "invoice_type": r"(Tax Invoice/Bill of Supply/Cash Memo)",
            "order_number": r"Order Number\s*[:\-]?\s*([A-Z0-9\-]+)",
            "invoice_number": r"Invoice Number\s*[:\-]?\s*([A-Z0-9\-]+)",
            "order_date": r"Order Date\s*[:\-]?\s*(\d{2}.\d{2}.\d{4})",
            "invoice_date": r"Invoice Date\s*[:\-]?\s*(\d{2}.\d{2}.\d{4})",
            "seller_name": r"Sold By\s*[:\-]?\s*([^\n]+)",
            "seller_gst": r"GST Registration No[\.:]?\s*([A-Z0-9]+)",
            "billing_address": r"Billing Address\s*[:\-]?\s*(.*?)State/UT Code",
            "shipping_address": r"Shipping Address\s*[:\-]?\s*(.*?)State/UT Code",
            "place_of_supply": r"Place of supply\s*[:\-]?\s*([^\n]+)",
            "place_of_delivery": r"Place of delivery\s*[:\-]?\s*([^\n]+)",
            "fssai_license": r"FSSAI License No\.\s*([0-9]+)",
            "pan": r"PAN No\s*[:\-]?\s*([A-Z0-9]+)",
            "total_tax": r"Total Tax Amount\s*[:\-]?\s*₹?\s*([\d,\.]+)",
            "total_amount": r"Total Amount\s*[:\-]?\s*₹?\s*([\d,\.]+)",
            "amount_in_words": r"Amount in Words\s*[:\-]?\s*(.+)",
        }

    def _safe_search(self, pattern, text, default=""):
        try:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            return match.group(1).strip() if match else default
        except Exception as e:
            logger.warning(f"Regex search failed for pattern '{pattern}': {e}")
            return default

    def _clean_text(self, text):
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract concatenated text from a (multi-page) PDF using PyPDF2 for reliability."""
        try:
            with open(pdf_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                text_parts = []
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_parts.append(page_text)
                return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise

    def extract_invoice_header(self, pdf_path: Path) -> Dict[str, str]:
        """Extract structured header info from an Amazon invoice PDF."""
        try:
            text = self._extract_pdf_text(pdf_path)
            header_info = {}
            for field, pattern in self.field_patterns.items():
                val = self._safe_search(pattern, text)
                header_info[field] = self._clean_text(val)
            header_info["vendor"] = "Amazon"
            header_info["source_file"] = os.path.basename(pdf_path)
            return header_info
        except Exception as e:
            logger.error(f"Failed extracting Amazon header: {e}")
            return {}

    def extract_tables(self, pdf_path: Path) -> List[pd.DataFrame]:
        """Extract every table using pdfplumber (multiple per invoice are supported)."""
        tables = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_tables = page.extract_tables()
                    for table_num, table in enumerate(page_tables):
                        if not table or len(table) < 2:
                            continue
                        try:
                            df = pd.DataFrame(table[1:], columns=table[0])
                            df.columns = [self._clean_text(col) for col in df.columns]
                            df.dropna(axis=0, how="all", inplace=True)
                            if not df.empty:
                                tables.append(df)
                        except Exception as e:
                            logger.warning(f"Table parse failed on page {page_num+1} table {table_num+1}: {e}")
            return tables
        except Exception as e:
            logger.error(f"Failed to extract tables from Amazon invoice: {e}")
            raise

    def generate_output_path(self, pdf_path: Path, invoice_number: Optional[str] = None) -> Path:
        """Generate output Excel file path for this invoice."""
        output_dir = self.output_base_dir or pdf_path.parent
        output_dir.mkdir(exist_ok=True, parents=True)
        if invoice_number:
            safe_invoice = re.sub(r'[^A-Za-z0-9_-]', '_', invoice_number)
            filename = f"amazon_invoice_{safe_invoice}.xlsx"
        else:
            filename = f"{pdf_path.stem}_amazon.xlsx"
        return output_dir / filename

    def save_to_excel(self, header_data: Dict[str, str], tables: List[pd.DataFrame], output_path: Path):
        """Save the extracted header/table info to an Excel file."""
        try:
            header_df = pd.DataFrame(list(header_data.items()), columns=["Field", "Value"])
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                header_df.to_excel(writer, sheet_name="Invoice_Header", index=False)
                for idx, df in enumerate(tables):
                    df.to_excel(writer, sheet_name=f"Table_{idx+1}"[:31], index=False)
            logger.info(f"Amazon invoice Excel saved: {output_path}")
        except Exception as e:
            logger.error(f"Could not write Excel: {e}")
            raise

    def extract_invoice(self, pdf_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Extract all info from this invoice PDF and write Excel."""
        try:
            pdf_file = Path(pdf_path)
            if not pdf_file.exists():
                raise FileNotFoundError(f"PDF not found: {pdf_path}")
            if pdf_file.suffix.lower() != ".pdf":
                raise ValueError("File is not a PDF.")

            logger.info(f"Extracting Amazon invoice: {pdf_file.name}")
            header = self.extract_invoice_header(pdf_file)
            tables = self.extract_tables(pdf_file)
            if output_path:
                excel_path = Path(output_path)
            else:
                excel_path = self.generate_output_path(pdf_file, header.get("invoice_number"))
            self.save_to_excel(header, tables, excel_path)
            summary = {
                "filename": pdf_file.name,
                "invoice_number": header.get("invoice_number", "-"),
                "invoice_date": header.get("invoice_date", "-"),
                "total_amount": header.get("total_amount", "-"),
                "seller_name": header.get("seller_name", "-"),
                "tables_extracted": len(tables),
                "excel_file": excel_path.name,
                "excel_path": str(excel_path),
            }
            return {
                "success": True,
                "message": f"Amazon invoice extraction OK: {pdf_file.name}",
                "summary": summary,
                "header_data": header,
                "tables_count": len(tables),
                "output_file": str(excel_path),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Amazon invoice extraction failed: {e}")
            return {
                "success": False,
                "message": "Amazon invoice extraction failed",
                "error": str(e),
                "pdf_path": pdf_path,
                "timestamp": datetime.now().isoformat(),
            }

# ──────────────────────────────────────────────────────────────
# Simple high-level and Flask-compatible usage
# ──────────────────────────────────────────────────────────────

def extract_invoice_from_path(pdf_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
    extractor = AmazonInvoiceExtractor(output_base_dir=output_dir)
    return extractor.extract_invoice(pdf_path)

def batch_extract_invoices(pdf_paths: List[str], output_dir: Optional[str] = None) -> Dict[str, Any]:
    extractor = AmazonInvoiceExtractor(output_base_dir=output_dir)
    results = []
    successful = 0
    failed = 0
    for pdf_path in pdf_paths:
        result = extractor.extract_invoice(pdf_path)
        results.append(result)
        successful += int(result["success"])
        failed += int(not result["success"])
    return {
        "success": successful > 0,
        "message": f"Processed {len(pdf_paths)}: {successful} success, {failed} failed",
        "results": results,
        "summary": {
            "total_files": len(pdf_paths),
            "successful": successful,
            "failed": failed,
            "success_rate": f"{successful}/{len(pdf_paths)}",
            "timestamp": datetime.now().isoformat(),
        }
    }

def get_details(file_name: str) -> Dict[str, Any]:
    """
    Flask/backend-compatible entry point: expects just the PDF filename in uploads directory.
    """
    file_path = os.path.join("uploads", file_name)
    result = extract_invoice_from_path(file_path, output_dir="extracted_excels")
    # Adapt to "invoice_summary"/"item_details" style if needed by backend
    # For full genericity, you could parse first table of tables as "item_details"
    tables = result.get("tables_count", 0)
    header_dict = result["header_data"] if result["success"] else {}
    item_details = []
    if result["success"]:
        # Optionally, return first data table as item_details, if one exists
        output_file = result["output_file"]
        # Try to load first table quickly for compatibility
        try:
            xls = pd.ExcelFile(output_file)
            sheets = xls.sheet_names
            for name in sheets:
                if name.lower().startswith("table"):
                    item_details = xls.parse(name)
                    break
        except Exception as e:
            item_details = pd.DataFrame()
    return {
        "invoice_summary": pd.DataFrame([header_dict]) if header_dict else pd.DataFrame(),
        "item_details": item_details if isinstance(item_details, pd.DataFrame) else pd.DataFrame(),
        "has_items": (tables > 0),
    }

# ────────────────
# MAIN TEST BLOCK
# ────────────────
# if __name__ == "__main__":
#     # Single file test
#     PDF_PATH = r"F:\Internship\approaches\input\sample_amazon_invoice.pdf"
#     result = extract_invoice_from_path(PDF_PATH)
#     if result["success"]:
#         print(f"✅ Extracted: {result['output_file']}")
#     else:
#         print(f"❌ Error: {result.get('error', result['message'])}")

    # Batch test example:
    # pdf_files = ["invoice1.pdf", "invoice2.pdf"]
    # batch_result = batch_extract_invoices(pdf_files)
    # print(batch_result)
