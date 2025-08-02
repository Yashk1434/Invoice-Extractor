import pandas as pd
import os

def get_details(file_name):
    """
    Extract details from PDF using amazon AI approach
    Args:
        file_name (str): Name of the PDF file to process
    Returns:
        pandas.DataFrame: Extracted data using AI
    """
    # Dummy AI implementation - replace with actual AI extraction logic
    file_path = os.path.join("uploads", file_name)

    # Return dummy DataFrame for now
    dummy_data = {
        'Invoice_Number': ['AI-001', 'AI-002', 'AI-003'],
        'Date': ['2024-01-01', '2024-01-02', '2024-01-03'],
        'Amount': [1500, 2500, 3500],
        'Vendor': ['amazon AI Vendor 1', 'amazon AI Vendor 2', 'amazon AI Vendor 3'],
        'Description': ['AI Item 1 from amazon', 'AI Item 2 from amazon', 'AI Item 3 from amazon'],
        'Confidence': [0.95, 0.87, 0.92]
    }

    df = pd.DataFrame(dummy_data)
    print(f"[AMAZON AI] Processed {file_name} - Found {len(df)} records")
    return df
