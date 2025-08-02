import pandas as pd
import os

def get_details(file_name):
    """
    Extract details from PDF using flipkart approach
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
        'Vendor': ['flipkart Vendor 1', 'flipkart Vendor 2'],
        'Description': ['Item 1 from flipkart', 'Item 2 from flipkart']
    }

    df = pd.DataFrame(dummy_data)
    print(f"[FLIPKART] Processed {file_name} - Found {len(df)} records")
    return df
