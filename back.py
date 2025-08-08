import pandas as pd  # Required for DataFrame checks
from create_excel import convert_df_to_xlsx

# Manual Based Methods (Import your get_details for each vendor)
from approaches.mandal import get_details as mandal_extractor
from approaches.myntra import get_details as myntra_extractor
from approaches.spella import get_details as spella_extractor
from approaches.reliance_digital import get_details as reliance_digital
from approaches.flipkart import get_details as flipkart_extractor
from approaches.meesho import get_details as meesho_extractor
from approaches.onemg import get_details as onemg_extractor
from approaches.swiggy import get_details as swiggy_extractor
from approaches.zomato import get_details as zomato_extractor
from approaches.instamart import get_details as instamart_extractor
from approaches.universal1 import get_details as universal_extractor1
from approaches.universal2 import get_details as universal_extractor2
from approaches.gemini import extract_with_gemini


# AI Based Methods
from approaches.amazon import get_details as amazon_extractor

# --- Register extractors in method dictionary ---
MANUAL_METHODS = {
    "mandal": mandal_extractor,
    "myntra": myntra_extractor,
    "spella": spella_extractor,
    "reliance_digital": reliance_digital,
    "flipkart": flipkart_extractor,
    "onemg": onemg_extractor,
    "swiggy": swiggy_extractor,
    "meesho": meesho_extractor,
    "zomato":zomato_extractor,
    "instamart":instamart_extractor,
    "universal1":universal_extractor1,
    "universal2":universal_extractor2
}

AI_METHODS = {
    "amazon": amazon_extractor,
    "gemini": extract_with_gemini,
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
            "error": "Extractor not found",
        }

    try:
        result = extractor(file_name)  # This calls the correct get_details()

        # Flexibly check if data was extracted
        has_data = False
        if isinstance(result, dict):
            # For extractors returning a dict with multiple DataFrames
            has_data = (not result.get('invoice_summary', pd.DataFrame()).empty or
                        not result.get('item_details', pd.DataFrame()).empty)
        elif isinstance(result, pd.DataFrame):
            # For legacy/single-DF extractors
            has_data = not result.empty

        if has_data:
            print(f"[✓] Data extracted using {method}")
            # Save to Excel: result is dict or DataFrame
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
