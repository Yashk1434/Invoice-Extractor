import torch
import os
import pandas as pd
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
from langchain_community.document_loaders import PyPDFLoader

FLAN_MODEL = "google/flan-t5-base"
UPLOAD_FOLDER = "uploads"
EXCEL_FOLDER = "extracted_excels"
os.makedirs(EXCEL_FOLDER, exist_ok=True)

# Fields to extract:
FIELDS = [
    "Invoice Number", "Invoice Date", "PAN Number", "Vendor", "Order Number", "Order Date",
    "Quantity", "Seller Details", "Billing Address", "Product Description", "Net Amount", "GST Amount",
    "Tax Rate", "Taxable Value", "Shipping Charge", "Total Amount", "Total Amount (in words)"
]

# Truncate input to avoid sequence length/model errors (approx 512-700 tokens, safe for FLAN)
MAX_CHARS = 2000

def load_flan_pipe():
    tokenizer = AutoTokenizer.from_pretrained(FLAN_MODEL)
    model = AutoModelForSeq2SeqLM.from_pretrained(FLAN_MODEL)
    return pipeline(
        "text2text-generation", model=model, tokenizer=tokenizer,
        max_new_tokens=70, device=0 if torch.cuda.is_available() else -1
    )

def clean_answer(ans, field=None):
    """Returns only the first line, strips, and tries to remove field echoes."""
    ans = ans.strip().split("\n")[0]
    if field:
        ans = ans.replace(f"{field}:", "").replace(f"{field}", "").strip()
    # Remove generic echoes if present
    for f in FIELDS:
        ans = ans.replace(f"{f}:", "").replace(f"{f}", "").strip()
    # Remove leading punctuation and unnecessary remnants
    ans = ans.lstrip(":.-– \t").rstrip(" .\t")
    return ans

# def extract_with_flan(pdf_filename):
#     try:
#         path = os.path.join(UPLOAD_FOLDER, pdf_filename)
#         loader = PyPDFLoader(path)
#         docs = loader.load()
#         # Concatenate and truncate
#         fulltext = " ".join(doc.page_content for doc in docs)
#         text = fulltext[:MAX_CHARS]

#         flan = load_flan_pipe()
#         result_row = {}
#         for field in FIELDS:
#             prompt = (
#                 f"Extract the {field} from the following invoice. "
#                 f"Only return the value for {field}, nothing else. "
#                 f"If not found, say '[Not found]'.\n\n"
#                 f"Invoice Text:\n{text}\nAnswer:"
#             )
#             # Sometimes FLAN hallucininates multiple lines, so just take the first returned sequence
#             output = flan(prompt, num_return_sequences=1, do_sample=False)[0]["generated_text"]
#             value = clean_answer(output, field)
#             result_row[field] = value if value else "[Not found]"
#         # Save to Excel
#         outpath = os.path.join(EXCEL_FOLDER, os.path.splitext(pdf_filename)[0] + "_flan.xlsx")
#         pd.DataFrame([result_row]).to_excel(outpath, index=False)
#         return {"status": "success", "output": outpath}
#     except Exception as e:
#         print(f"[FLAN Extraction ERROR] {e}")
#         return {"status": "error", "error": str(e)}
def extract_with_flan(pdf_filename):
    try:
        path = os.path.join(UPLOAD_FOLDER, pdf_filename)
        loader = PyPDFLoader(path)
        docs = loader.load()
        # Combine all pages
        fulltext = " ".join(doc.page_content for doc in docs)
        # ---- ADD THESE LINES HERE ----
        max_chars = 2000
        text = fulltext[:max_chars]
        # ------------------------------

        flan = load_flan_pipe()
        result_row = {}
        for field in FIELDS:
            prompt = (
                f"Extract the {field} from the following invoice. "
                f"Only return the value for {field}, nothing else. "
                f"If not found, say '[Not found]'.\n\n"
                f"Invoice Text:\n{text}\nAnswer:"
            )
            output = flan(prompt, num_return_sequences=1, do_sample=False)[0]["generated_text"]
            value = clean_answer(output, field)
            result_row[field] = value if value else "[Not found]"
        outpath = os.path.join(EXCEL_FOLDER, os.path.splitext(pdf_filename)[0] + "_flan.xlsx")
        pd.DataFrame([result_row]).to_excel(outpath, index=False)
        return {"status": "success", "output": outpath}
    except Exception as e:
        print(f"[FLAN Extraction ERROR] {e}")
        return {"status": "error", "error": str(e)}


# Optionally: for testing from CLI
if __name__ == "__main__":
    import sys
    fname = sys.argv[1]
    print(extract_with_flan(fname))
