from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
import os
import pandas as pd
from datetime import datetime
from back import process_files

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['EXCEL_FOLDER'] = 'extracted_excels'
app.secret_key = 'supersecret'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['EXCEL_FOLDER'], exist_ok=True)


def get_file_list():
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        size = os.path.getsize(filepath)
        timestamp = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%b %d, %Y')
        files.append({
            'name': filename,
            'size': f"{size / 1024:.2f} KB",
            'timestamp': timestamp
        })
    return sorted(files, key=lambda x: x['timestamp'], reverse=True)


def get_excel_list():
    files = []
    if os.path.exists(app.config['EXCEL_FOLDER']):
        for filename in os.listdir(app.config['EXCEL_FOLDER']):
            filepath = os.path.join(app.config['EXCEL_FOLDER'], filename)
            size = os.path.getsize(filepath)
            timestamp = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%b %d, %Y')

            try:
                excel_file = pd.ExcelFile(filepath)
                sheet_count = len(excel_file.sheet_names)
                sheet_names = excel_file.sheet_names
                sheets = f"{sheet_count} Sheet{'s' if sheet_count != 1 else ''}"
            except:
                sheets = "1 Sheet"
                sheet_names = ["Sheet1"]

            files.append({
                'name': filename,
                'size': f"{size / 1024:.2f} KB",
                'timestamp': timestamp,
                'sheets': sheets,
                'sheet_names': sheet_names
            })
    return sorted(files, key=lambda x: x['timestamp'], reverse=True)


# Dashboard Routes
@app.route('/')
def dashboard():
    uploaded_files = get_file_list()
    excel_files = get_excel_list()

    # Calculate statistics
    stats = {
        'total_uploads': len(uploaded_files),
        'total_extractions': len(excel_files),
        'success_rate': round((len(excel_files) / len(uploaded_files) * 100) if uploaded_files else 0, 1),
        'recent_files': uploaded_files[:5]  # Last 5 files
    }

    return render_template("dashboard.html", stats=stats)


@app.route('/extraction')
def extraction():
    uploaded_files = get_file_list()
    excel_files = get_excel_list()
    return render_template("extraction.html", uploaded_files=uploaded_files, excel_files=excel_files)


@app.route('/visualization')
def visualization():
    excel_files = get_excel_list()
    return render_template("visualization.html", excel_files=excel_files)


# File upload route
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    if file and file.filename:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        flash(f"File {file.filename} uploaded successfully!")
    return redirect(url_for('extraction'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/excel/<filename>')
def excel_file(filename):
    return send_from_directory(app.config['EXCEL_FOLDER'], filename)


@app.route('/preview_excel/<filename>')
def preview_excel(filename):
    filepath = os.path.join(app.config['EXCEL_FOLDER'], filename)

    try:
        import openpyxl
        workbook = openpyxl.load_workbook(filepath)
        sheet_names = workbook.sheetnames

        sheet_data = {}
        for sheet_name in sheet_names:
            try:
                worksheet = workbook[sheet_name]
                data = []
                headers = []

                first_row = True
                for row in worksheet.iter_rows():
                    row_data = []
                    for cell in row:
                        cell_value = cell.value if cell.value is not None else ""
                        row_data.append(str(cell_value))

                    if first_row:
                        headers = row_data
                        first_row = False
                    else:
                        if any(cell.strip() for cell in row_data if cell):
                            data.append(row_data)

                if data:
                    df = pd.DataFrame(data, columns=headers)
                else:
                    df = pd.DataFrame(columns=headers)

                sheet_data[sheet_name] = df

            except Exception as sheet_error:
                print(f"Error reading sheet {sheet_name}: {sheet_error}")
                sheet_data[sheet_name] = pd.DataFrame({
                    'Error': [f'Could not read sheet {sheet_name}: {str(sheet_error)}']
                })

        workbook.close()

        return render_template("excel_preview.html",
                               filename=filename,
                               sheet_data=sheet_data,
                               sheet_names=sheet_names)

    except Exception as e:
        print(f"Error in preview_excel: {e}")
        return render_template("excel_preview.html",
                               filename=filename,
                               error=f"Could not load Excel file: {str(e)}")


@app.route('/api/excel_sheet/<filename>/<sheet_name>')
def get_excel_sheet_data(filename, sheet_name):
    try:
        filepath = os.path.join(app.config['EXCEL_FOLDER'], filename)
        import openpyxl
        workbook = openpyxl.load_workbook(filepath, data_only=True)

        if sheet_name in workbook.sheetnames:
            worksheet = workbook[sheet_name]
            data = []
            headers = []

            first_row = True
            for row in worksheet.iter_rows():
                row_data = []
                for cell in row:
                    cell_value = cell.value if cell.value is not None else ""
                    row_data.append(str(cell_value))

                if first_row:
                    headers = row_data
                    first_row = False
                else:
                    if any(cell.strip() for cell in row_data if cell):
                        data.append(row_data)

            if data:
                df = pd.DataFrame(data, columns=headers)
            else:
                df = pd.DataFrame(columns=headers)

            workbook.close()

            html_table = df.to_html(classes='excel-table', table_id='sheet-table', escape=False, index=False)

            return jsonify({
                'success': True,
                'html': html_table,
                'records': len(df),
                'columns': len(df.columns)
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Sheet {sheet_name} not found'
            })

    except Exception as e:
        print(f"Error in get_excel_sheet_data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/delete_upload/<filename>', methods=['POST'])
def delete_upload(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f"File {filename} deleted successfully!")
    return redirect(url_for('extraction'))


@app.route('/delete_excel/<filename>', methods=['POST'])
def delete_excel(filename):
    filepath = os.path.join(app.config['EXCEL_FOLDER'], filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f"Excel file {filename} deleted successfully!")
    return redirect(url_for('extraction'))


@app.route('/process/<method>/<filename>', methods=['POST'])
def process_file(method, filename):
    result = process_files([filename], method)
    if result[filename]['status'] == 'success':
        flash(f"Successfully processed {filename} using {method}")
    else:
        flash(f"Failed to process {filename} with {method}")
    return redirect(url_for('extraction'))


if __name__ == '__main__':
    app.run(debug=True)
