import pandas as pd
import os


def convert_df_to_xlsx(data, file_name, model_used):
    """
    Convert data to Excel with multiple sheets support
    Args:
        data: Can be DataFrame or dict with DataFrames
        file_name: Original file name
        model_used: Model/approach used
    """
    base_name = os.path.splitext(os.path.basename(file_name))[0]
    out_dir = "extracted_excels"
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, f"{base_name}_{model_used}.xlsx")

    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:  # Changed to openpyxl
            if isinstance(data, dict):
                # Handle multiple sheets (for 1mg and similar extractors)
                if 'invoice_summary' in data and 'item_details' in data:
                    # Write invoice summary
                    if not data['invoice_summary'].empty:
                        data['invoice_summary'].to_excel(writer, sheet_name='Invoice Summary', index=False)
                        print(f"[✓] Invoice Summary sheet created with {len(data['invoice_summary'])} records")

                    # Write item details
                    if not data['item_details'].empty:
                        data['item_details'].to_excel(writer, sheet_name='Item Details', index=False)
                        print(f"[✓] Item Details sheet created with {len(data['item_details'])} records")
                    else:
                        # Create empty item details sheet if no items
                        pd.DataFrame({'Message': ['No item details found']}).to_excel(writer, sheet_name='Item Details',
                                                                                      index=False)
                        print(f"[!] Empty Item Details sheet created")
                else:
                    # Handle other dict formats
                    for sheet_name, df in data.items():
                        if isinstance(df, pd.DataFrame):
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                # Handle single DataFrame (for other extractors)
                data.to_excel(writer, sheet_name='Data', index=False)

        print(f"[✓] Excel saved: {output_path}")

    except Exception as e:
        print(f"[!] Error saving Excel: {e}")
        # Fallback to single sheet
        try:
            if isinstance(data, dict) and 'invoice_summary' in data:
                data['invoice_summary'].to_excel(output_path, index=False)
                print(f"[✓] Fallback: Saved invoice summary only")
            elif isinstance(data, pd.DataFrame):
                data.to_excel(output_path, index=False)
                print(f"[✓] Fallback: Saved as single sheet")
        except Exception as fallback_error:
            print(f"[!] Fallback also failed: {fallback_error}")
