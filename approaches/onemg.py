import pandas as pd
import os
import pdfplumber
import re


def get_details(file_name):
    """
    Extract details from 1mg invoice PDF using pdfplumber
    Args:
        file_name (str): Name of the PDF file to process
    Returns:
        dict: Contains both invoice summary and item details DataFrames
    """
    try:
        file_path = os.path.join("uploads", file_name)

        if not os.path.exists(file_path):
            print(f"[1MG] File not found: {file_path}")
            return create_empty_result()

        # === STEP 1: Extract Metadata ===
        metadata = extract_metadata_1mg(file_path)

        # === STEP 2: Extract Item Details ===
        item_details = extract_items_1mg(file_path)

        # === STEP 3: Create Two DataFrames ===
        # Invoice Summary DataFrame
        invoice_summary = pd.DataFrame([metadata])

        # Item Details DataFrame (with metadata columns added)
        if not item_details.empty:
            # Add key metadata to each item row
            for key, value in metadata.items():
                if key not in ["Source_File"]:  # Don't duplicate source file
                    item_details[key] = value

        print(
            f"[1MG] Successfully processed {file_name} - Invoice summary: 1 record, Item details: {len(item_details)} items")

        return {
            "invoice_summary": invoice_summary,
            "item_details": item_details,
            "has_items": not item_details.empty
        }

    except Exception as e:
        print(f"[1MG] Error processing {file_name}: {e}")
        return create_empty_result()


def create_empty_result():
    """Create empty result structure"""
    return {
        "invoice_summary": pd.DataFrame(),
        "item_details": pd.DataFrame(),
        "has_items": False
    }


def extract_metadata_1mg(file_path):
    """Extract metadata from 1mg invoice PDF"""
    metadata = {
        "Invoice_Number": "",
        "Date": "",
        "Vendor": "1mg",
        "Amount": "",
        "Description": "1mg Invoice",
        "Order_ID": "",
        "Patient_Name": "",
        "Contact": "",
        "Place_of_Supply": "",
        "GST_Number": "",
        "Source_File": os.path.basename(file_path)
    }

    try:
        with pdfplumber.open(file_path) as pdf:
            full_text = "\n".join([page.extract_text() or "" for page in pdf.pages])

        # Define patterns specific to 1mg invoices
        patterns = {
            "Invoice_Number": r"Invoice\s*no\.\:?\s*([A-Z0-9]+)",
            "Date": r"Date\s*:\s*([\d\-\/]+)",
            "Order_ID": r"Order ID\s*:\s*([A-Z0-9]+)",
            "Patient_Name": r"Patient Name\s*:\s*([^\n]+)",
            "Contact": r"Contact\s*:\s*(\d+)",
            "Place_of_Supply": r"Place of supply\s*:\s*([A-Za-z\s]+)",
            "Amount": r"(?:BILL AMOUNT|PAYABLE AMOUNT)\s*:\s*₹?([\d\.]+)",
            "GST_Number": r"GST\s*:\s*([A-Z0-9]+)"
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                metadata[key] = match.group(1).strip()

        print(f"[1MG] Extracted metadata: Invoice {metadata['Invoice_Number']}, Amount {metadata['Amount']}")

    except Exception as e:
        print(f"[1MG] Error extracting metadata: {e}")

    return metadata


def extract_items_1mg(file_path):
    """Extract item details from 1mg invoice PDF using pdfplumber"""

    def is_serial(cell):
        return isinstance(cell, str) and cell.strip().isdigit()

    cleaned_rows = []
    filename = os.path.basename(file_path)

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                for table in page_tables:
                    if len(table) < 5 or len(table[0]) < 5:
                        continue

                    df = pd.DataFrame(table)
                    if len(df.columns) >= 8:  # Ensure enough columns
                        df.columns = df.iloc[0]
                        df = df.drop(0).reset_index(drop=True)
                        cleaned_rows.extend(process_table_rows(df, filename, is_serial))

        print(f"[1MG] pdfplumber extracted {len(cleaned_rows)} items")

        # === Convert to DataFrame ===
        if cleaned_rows:
            final_df = pd.DataFrame(cleaned_rows)

            # Standard column mapping for 1mg invoices
            expected_columns = [
                "Sr No", "Product Name", "Manufacturer", "Batch No", "Expiry Date",
                "Quantity", "UOM", "Pack Size", "MRP", "Discount", "Taxable Amount",
                "HSN", "GST Rate (%)", "GST Amount", "Total Amount", "Source File", "Custom Sr No"
            ]

            # Adjust columns to match available data
            final_df.columns = expected_columns[:len(final_df.columns)]

            # Clean and filter valid rows (basic filtering only)
            final_df = final_df[
                final_df["Product Name"].notna() &
                final_df["Product Name"].astype(str).str.strip().ne("")
                ].reset_index(drop=True)

            return final_df

        else:
            print(f"[1MG] No valid items extracted from {filename}")
            return pd.DataFrame()

    except Exception as e:
        print(f"[1MG] Error in item extraction: {e}")
        return pd.DataFrame()


def process_table_rows(df, filename, is_serial_func):
    """Process table rows and handle multi-line entries"""
    cleaned_rows = []
    current_row = None
    row_serial = 1

    for _, row in df.iterrows():
        first_cell = str(row.iloc[0]).strip()

        if is_serial_func(first_cell):
            # Save previous row if exists
            if current_row is not None:
                cleaned_rows.append(current_row)

            # Start new row
            current_row = row.copy()
            current_row["Source File"] = filename
            current_row["Custom Sr No"] = f"1mg.{row_serial}"
            row_serial += 1

        elif current_row is not None:
            # Append to current row (multi-line handling)
            for col in df.columns:
                val = str(row[col]).strip()
                if val and val != 'nan':
                    current_val = str(current_row.get(col, '')).strip()
                    current_row[col] = f"{current_val} {val}".strip()

    # Don't forget the last row
    if current_row is not None:
        cleaned_rows.append(current_row)

    return cleaned_rows
