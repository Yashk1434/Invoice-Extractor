import pandas as pd
import os

def get_details(file_name):
    """
    Extract details from PDF using myntra approach
    Args:
        file_name (str): Name of the PDF file to process
    Returns:
        pandas.DataFrame: Extracted data
    """
    # Dummy implementation - replace with actual extraction logic
    file_path = os.path.join("uploads", file_name)

    # Return dummy DataFrame for now
    dummy_data = {
        'Invoice_Number': ['INV-001', 'INV-002'],
        'Date': ['2024-01-01', '2024-01-02'],
        'Amount': [1000, 2000],
        'Vendor': ['myntra Vendor 1', 'myntra Vendor 2'],
        'Description': ['Item 1 from myntra', 'Item 2 from myntra']
    }

    df = pd.DataFrame(dummy_data)
    print(f"[MYNTRA] Processed {file_name} - Found {len(df)} records")
    return df
