# data_validator.py

def validate_data(data):
    required_fields = ["invoice_no", "date", "total"]

    if not data or not isinstance(data, dict):
        return False

    # Check all required fields are present and non-empty
    for field in required_fields:
        if not data.get(field):
            return False

    return True
