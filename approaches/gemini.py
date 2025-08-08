import os
import pandas as pd
import google.generativeai as genai
from langchain_community.document_loaders import PyPDFLoader

# ----- Configuration -----
API_KEY = 'AIzaSyDymP6gj8KCkP5LsUSwezh-C9CYp9Lc8Aw'
UPLOAD_FOLDER = "uploads"
EXCEL_FOLDER = "extracted_excels"
os.makedirs(EXCEL_FOLDER, exist_ok=True)

FIELDS = [
    "Invoice Number", "Invoice Date", "PAN Number", "Vendor", "Order Number", "Order Date",
    "Quantity", "Seller Details", "Billing Address", "Product Description", "Net Amount", "GST Amount",
    "Tax Rate", "Taxable Value", "Shipping Charge", "Total Amount", "Total Amount (in words)"
]
MAX_CHARS = 2000

# ----- Gemini Client Setup -----
def configure_gemini():
    genai.configure(api_key=API_KEY)

def clean_answer(ans, field=None):
    ans = ans.strip().split("\n")[0]
    if field:
        ans = ans.replace(f"{field}:", "").replace(f"{field}", "").strip()
    for f in FIELDS:
        ans = ans.replace(f"{f}:", "").replace(f"{f}", "").strip()
    ans = ans.lstrip(":.-– \t").rstrip(" .\t")
    return ans

# def extract_with_gemini(pdf_filename):
#     try:
#         path = os.path.join(UPLOAD_FOLDER, pdf_filename)
#         loader = PyPDFLoader(path)
#         docs = loader.load()
#         fulltext = " ".join(doc.page_content for doc in docs)
#         text = fulltext[:MAX_CHARS]
#         configure_gemini()

#         result_row = {}
#         model = genai.GenerativeModel("gemini-2.5-flash")
#         for field in FIELDS:
#             prompt = (
#                 f"Extract the {field} from the following invoice. "
#                 f"Only return the value for {field}, nothing else. "
#                 f"If not found, say '[Not found]'.\n\n"
#                 f"Invoice Text:\n{text}\nAnswer:"
#             )
#             response = model.generate_content(prompt)
#             value = clean_answer(response.text, field)
#             result_row[field] = value if value else "[Not found]"

#         outpath = os.path.join(EXCEL_FOLDER, os.path.splitext(pdf_filename)[0] + "_gemini.xlsx")
#         pd.DataFrame([result_row]).to_excel(outpath, index=False)
#         return {"status": "success", "output": outpath}
#     except Exception as e:
#         print(f"[GEMINI Extraction ERROR] {e}")
#         return {"status": "error", "error": str(e)}
def extract_with_gemini(pdf_filename):
    try:
        path = os.path.join(UPLOAD_FOLDER, pdf_filename)
        loader = PyPDFLoader(path)
        docs = loader.load()
        fulltext = " ".join(doc.page_content for doc in docs)
        text = fulltext[:MAX_CHARS]
        configure_gemini()

        result_row = {}
        model = genai.GenerativeModel("gemini-2.5-flash")
        for field in FIELDS:
            prompt = (
                f"Extract the {field} from the following invoice. "
                f"Only return the value for {field}, nothing else. "
                f"If not found, say '[Not found]'.\n\n"
                f"Invoice Text:\n{text}\nAnswer:"
            )
            response = model.generate_content(prompt)
            value = clean_answer(response.text, field)
            result_row[field] = value if value else "[Not found]"

        # Return directly as DataFrame:
        return pd.DataFrame([result_row])
    except Exception as e:
        print(f"[GEMINI Extraction ERROR] {e}")
        return pd.DataFrame()

# # Optionally: for testing from CLI
# if __name__ == "__main__":
#     import sys
#     fname = sys.argv[1]
#     print(extract_with_gemini(fname))
