import pandas as pd  # Add this missing import
from create_excel import convert_df_to_xlsx

# Manual Based Methods
from approaches.mandal import get_details as mandal_extractor
from approaches.myntra import get_details as myntra_extractor
from approaches.spella import get_details as spella_extractor
from approaches.reliance_digital import get_details as reliance_digital
from approaches.flipkart import get_details as flipkart_extractor
from approaches.onemg import get_details as onemg_extractor
from approaches.swiggy import get_details as swiggy_extractor
# AI Based Methods
from approaches.amazon import get_details as amazon_extractor

MANUAL_METHODS = {
    "mandal": mandal_extractor,
    "myntra": myntra_extractor,
    "spella": spella_extractor,
    "reliance_digital": reliance_digital,
    "flipkart": flipkart_extractor,
    "onemg": onemg_extractor,
    "swiggy": swiggy_extractor
}

AI_METHODS = {
    "amazon": amazon_extractor
}

ALL_METHODS = {**MANUAL_METHODS, **AI_METHODS}


def extract_details(file_name, method):
    print(f"Processing {file_name} with {method}")
    extractor = ALL_METHODS.get(method)

    if not extractor:
        print(f"[!] {method} extractor not found")
        return {
            "model_used": method,
            "status": "failed",
            "data": None,
            "error": "Extractor not found"
        }

    try:
        result = extractor(file_name)

        # Handle different return types
        has_data = False
        if isinstance(result, dict):
            # For 1mg-style extractors that return dict with multiple sheets
            has_data = (not result.get('invoice_summary', pd.DataFrame()).empty or
                        not result.get('item_details', pd.DataFrame()).empty)
        elif isinstance(result, pd.DataFrame):
            # For regular extractors that return single DataFrame
            has_data = not result.empty

        if has_data:
            print(f"[✓] Data extracted using {method}")
            convert_df_to_xlsx(result, file_name, method)
            return {
                "model_used": method,
                "status": "success",
                "data": result
            }
        else:
            print(f"[x] No data extracted with {method}")
            return {
                "model_used": method,
                "status": "failed",
                "data": None,
                "error": "No data extracted"
            }
    except Exception as e:
        print(f"[!] Error with {method}: {e}")
        return {
            "model_used": method,
            "status": "failed",
            "data": None,
            "error": str(e)
        }


def process_files(file_list, method):
    results = {}
    for file_name in file_list:
        results[file_name] = extract_details(file_name, method)
    return results
