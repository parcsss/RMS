import pandas as pd
from flask import Flask, request, render_template_string, send_file, redirect, url_for, session, flash
import io
import os
from werkzeug.utils import secure_filename # Used to sanitize filenames

app = Flask(__name__)
# IMPORTANT: Sessions require a secret key
app.secret_key = 'your_super_secret_key_here' 
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# Global variable to temporarily store generated data in memory 
download_data = {}


def process_data(df_imported, df_basis):
    
    df_imported.rename(columns={
        'Category Name': 'Category Name (Old)',
        'Rate': 'Rate (Original)'
    }, inplace=True)


    df_processed = df_imported[['Item Name', 'Category Name (Old)', 'Rate (Original)']].copy()

    # --- Remove Duplicated Item Names ---
    df_processed.drop_duplicates(subset=['Item Name'], keep='first', inplace=True)
    
    # --- Prepare Basis Data ---
    df_basis_map = df_basis[[
        'Pos Product Name', 
        'Product Id', 
        'Pos Categories'
    ]].copy()
    
    df_basis_map.rename(columns={
        'Pos Product Name': 'Item Name',
        'Pos Categories': 'Category Name (New)'
    }, inplace=True)
    
    df_basis_map.drop_duplicates(subset=['Item Name'], keep='first', inplace=True)
    
    # --- Merge Data ---
    df_processed = pd.merge(
        df_processed, 
        df_basis_map, 
        on='Item Name', 
        how='left'
    )
 
    
    # Check for items that will become 'UNCATEGORIZED' before filling NaNs.
    has_uncategorized_items = df_processed['Category Name (New)'].isnull().any()
    
    df_processed['Category Name (New)'].fillna('UNCATEGORIZED', inplace=True) 
    
    
    # --- Rate and Final Column Setup ---
    df_processed['Rate (Base Price)'] = (df_processed['Rate (Original)'] / 1.12).round(2)
    
    df_processed.sort_values(by='Product Id', inplace=True, na_position='last')
    
    df_processed['Featured Product'] = 'N'
    df_processed['Pos Point Short Name'] = 'RMS'
    df_processed['Unit Short Name'] = 'Unit'
    df_processed['Status'] = 'A'

    
    remaining_placeholder_cols = [
        'Description', 'Taxes Short Name', 'Pos Attributes', 
        'NC value(%)', 'Kitchen Code'
    ]
    for col in remaining_placeholder_cols:
        df_processed[col] = ''
    
 
    df_final = df_processed[[
        'Featured Product', 'Pos Point Short Name', 'Item Name', 'Product Id', 
        'Description', 'Category Name (New)', 'Taxes Short Name', 'Pos Attributes', 
        'Rate (Base Price)', 'NC value(%)', 'Unit Short Name', 'Kitchen Code', 'Status'
    ]].copy()

    df_final.rename(columns={
        'Item Name': 'Pos Product Name',         
        'Category Name (New)': 'Pos Categories', 
        'Rate (Base Price)': 'Price'              
    }, inplace=True)

    # Return the final DataFrame AND the status of UNCATEGORIZED items
    return df_final, has_uncategorized_items

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "Error: No file part", 400
        
        file = request.files['file']
        
        if file.filename == '':
            return "Error: No selected file", 400
        
        if file and file.filename.endswith(('.xlsx', '.xls')):
            try:
                # --- NEW FILENAME LOGIC ---
                uploaded_filename = secure_filename(file.filename)
                
                # 1. Strip the extension (e.g., '.xlsx')
                base_name = os.path.splitext(uploaded_filename)[0]
                
                # 2. Define the new filename (basename + '.csv')
                generated_filename = base_name + '.csv'
                
                # --- End NEW FILENAME LOGIC ---
                
                df_imported = pd.read_excel(file)

                basis_file_name = 'basis_data.csv' 
                if not os.path.exists(basis_file_name):
                    return f"Error: Basis file '{basis_file_name}' not found. Please save 'PosProductDetails-RMS (1).csv' as 'basis_data.csv' in the same folder as 'app.py'.", 500
                
                df_basis = pd.read_csv(basis_file_name)
                
                # Unpack both the DataFrame and the status
                df_exported, has_uncategorized = process_data(df_imported, df_basis)
                
                # 1. Convert DataFrame to CSV string
                output = io.StringIO()
                df_exported.to_csv(output, index=False)
                output.seek(0)
                csv_data = output.getvalue().encode('utf-8')

                # 2. Store the CSV data and filename globally 
                download_id = os.urandom(16).hex()
                session['download_id'] = download_id
                
                # Store both data and the desired filename
                download_data[download_id] = {
                    'data': csv_data, 
                    'filename': generated_filename
                }
                
                # 3. Use Flash to store the uncategorized status
                if has_uncategorized:
                    flash('uncategorized_warning', 'warning')
                else:
                    flash('success_message', 'success')

                # 4. Redirect immediately to the GET route
                return redirect(url_for('index', success='true'))

            except Exception as e:
                return f"An error occurred during file processing: {e}", 500

    # GET Request Logic (Template Rendering)
    success_message = request.args.get('success')
    
    # Check for flashed messages
    messages = session.pop('_flashes', [])
    uncategorized_message = False
    
    for category, message in messages:
        if message == 'uncategorized_warning':
            uncategorized_message = True
            break

    # Conditional message for UNCATEGORIZED items
    uncategorized_warning_html = ""
    if uncategorized_message:
        uncategorized_warning_html = """
            <div class="warning-prompt">
                ⚠️ **The generated template has item that is uncategorized. Please review the template first before importing in HLX.**
            </div>
        """
        
    # Get the generated filename from the stored data for display/download link
    current_download_data = download_data.get(session.get('download_id'), {})
    download_filename = current_download_data.get('filename', 'monggoloid.csv')
    download_link = url_for('download_template') if session.get('download_id') else '#'


    html_template = f"""
    <!doctype html>
    <title> Branch POS template </title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 50px; background-color: #f4f4f9; color: #333; }}
        .container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 600px; margin: auto; }}
        
        h1 {{ 
            color: #007bff; 
            border-bottom: 2px solid #eee; 
            padding-bottom: 10px; 
            text-align: center; 
        }}
        
        form {{ display: flex; flex-direction: column; }} 
        
        input[type="file"] {{ 
            border: 1px solid #ccc; 
            padding: 10px; 
            border-radius: 4px; 
            margin-bottom: 20px; 
        }}
        
        .download-button {{ 
            background-color: #007bff; 
            color: white; 
            padding: 12px 20px; 
            border: none; 
            border-radius: 4px; 
            cursor: pointer; 
            font-size: 16px; 
            text-align: center;
            text-decoration: none;
            display: block;
            margin: 10px 0;
            transition: background-color 0.3s;
        }}
        .download-button:hover {{ background-color: #0056b3; }}
        
        .success-prompt {{
            background-color: #d4edda;
            color: #155724;
            padding: 15px;
            margin-bottom: 20px;
            border: 1px solid #c3e6cb;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
        }}
        
        .warning-prompt {{
            background-color: #fff3cd; 
            color: #856404;
            padding: 15px;
            margin-bottom: 20px;
            border: 1px solid #ffeeba;
            border-radius: 5px;
            text-align: center;
            font-weight: bold;
        }}
        
        #success-view {{
            display: flex;
            flex-direction: column;
            align-items: center; 
        }}
        .reset-button {{
            background-color: #28a745; 
            width: auto; 
            margin-top: 10px; 
        }}
        .reset-button:hover {{
            background-color: #218838; 
        }}
        
        button {{ 
            background-color: #28a745; 
            color: white; 
            padding: 12px 20px; 
            border: none; 
            border-radius: 4px; 
            cursor: pointer; 
            font-size: 16px; 
            transition: background-color 0.3s; 
        }}
        button:hover {{ background-color: #218838; }}

        .note {{ background-color: #fff3cd; color: #856404; padding: 10px; border: 1px solid #ffeeba; border-radius: 4px; margin-top: 15px; }}
        
    </style>
    <div class="container">
        <h1>POS Template Generator</h1>
        
        <div id="success-view" style="display: {'block' if success_message == 'true' else 'none'};">
            {uncategorized_warning_html}
            <div class="success-prompt">
                ✅ File successfully generated!
            </div>
            
            <a href="{download_link}" class="download-button" download="{download_filename}" id="download-btn">
                Download Generated CSV: <strong>{download_filename}</strong>
            </a>

            <button class="reset-button" onclick="window.location.href = window.location.pathname;">
                Generate New Template
            </button>
        </div>

        <form id="upload-form" method="POST" enctype="multipart/form-data" action="/" style="display: {'none' if success_message == 'true' else 'flex'};">
            <input type="file" name="file" required>
            
            <button type="submit">Proceed and Generate New CSV File</button>
        </form>
        
        <div class="note">
            <strong>Generated template note:</strong> The generated CSV file automatically put values on those required columns for importing POS products in HLX. Please double check generated file and modify columns if needed.
        </div>
    </div>
    <script>
        document.querySelector('#upload-form').onsubmit = function() {{
            const fileInput = document.querySelector('input[type="file"]');
            if (fileInput.files.length > 0) {{
                // Disable button and show a loading state
                const button = document.querySelector('#upload-form button[type="submit"]');
                button.disabled = true;
                button.textContent = 'Processing... Please wait.';
            }}
            return true;
        }};

        const isSuccess = '{{ success_message }}' === 'true';
        if (isSuccess) {{
            window.scrollTo(0, 0);
        }}
    </script>
    """
    return render_template_string(html_template)

# ----------------------------------------------------------------------

@app.route('/download', methods=['GET'])
def download_template():
    """Handles the dedicated file download request."""
    download_id = session.get('download_id')
    
    if not download_id or download_id not in download_data:
        # If the file data isn't found, redirect back
        return redirect(url_for('index'))

    
    file_info = download_data[download_id]
    csv_data = file_info['data']
    filename = file_info['filename']
    
    
    del download_data[download_id]
    session.pop('download_id', None)
    
    return send_file(
        io.BytesIO(csv_data), 
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename 
    )

# ----------------------------------------------------------------------

if __name__ == '__main__':
    print("Running Flask app. Open your browser to http://127.0.0.1:5000/")
    app.run(debug=True)