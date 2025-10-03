import pandas as pd
from flask import Flask, request, render_template_string, send_file, redirect, url_for
import io
import os

# --- Configuration (Unchanged) ---
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 Megabytes

# --- Helper Function for Data Processing (UPDATED DEFAULT STRINGS) ---
def process_data(df_imported, df_basis):
    """
    Analyzes the imported DataFrame, performs transformations, and prepares for export.
    Outputs columns matching the target POS template structure with specific default values.
    """
    
    # 1. Standardize column names from the uploaded file
    df_imported.rename(columns={
        'Category Name': 'Category Name (Old)',
        'Rate': 'Rate (Original)'
    }, inplace=True)

    # Select the required columns from the uploaded file
    df_processed = df_imported[['Item Name', 'Category Name (Old)', 'Rate (Original)']].copy()

    # --- Remove Duplicated Item Names ---
    df_processed.drop_duplicates(subset=['Item Name'], keep='first', inplace=True)
    
    
    # 2. Prepare the mapping data from the basis file
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
    
    
    # 3. Merge the uploaded data with the basis map
    df_processed = pd.merge(
        df_processed, 
        df_basis_map, 
        on='Item Name', 
        how='left'
    )
    
    # 4. Apply Fallback and Calculation
    
    # Use 'UNCATEGORIZED' for unmatched items
    df_processed['Category Name (New)'].fillna('UNCATEGORIZED', inplace=True) 
    
    # Calculate the Base Price (Rate / 1.12).
    df_processed['Rate (Base Price)'] = df_processed['Rate (Original)'] / 1.12
    
    # Round the calculated price to two decimal places
    df_processed['Rate (Base Price)'] = df_processed['Rate (Base Price)'].round(2)
    
    df_processed.sort_values(by='Product Id', inplace=True, na_position='last')
    
    
    # --- UPDATED: Set Specific String Values for Requested Columns ---
    df_processed['Featured Product'] = 'N'
    df_processed['Pos Point Short Name'] = 'RMS'
    df_processed['Unit Short Name'] = 'Unit'
    df_processed['Status'] = 'A'

    # Set remaining placeholder columns to empty string
    remaining_placeholder_cols = [
        'Description', 'Taxes Short Name', 'Pos Attributes', 
        'NC value(%)', 'Kitchen Code'
    ]
    for col in remaining_placeholder_cols:
        df_processed[col] = ''
    
    
    # 5. Finalize columns for export in the desired POS template order
    df_final = df_processed[[
        'Featured Product',
        'Pos Point Short Name',
        'Item Name',              # To be renamed to Pos Product Name
        'Product Id', 
        'Description',
        'Category Name (New)',    # To be renamed to Pos Categories
        'Taxes Short Name',
        'Pos Attributes',
        'Rate (Base Price)',      # To be renamed to Price
        'NC value(%)',
        'Unit Short Name',
        'Kitchen Code',
        'Status'
    ]].copy()
    
    # --- FINAL MAPPING TO TARGET POS TEMPLATE COLUMNS ---
    df_final.rename(columns={
        'Item Name': 'Pos Product Name',        
        'Category Name (New)': 'Pos Categories', 
        'Rate (Base Price)': 'Price'             
    }, inplace=True)

    return df_final

# --- Flask Routes (Unchanged Logic) ---
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
                df_imported = pd.read_excel(file)
                
                # Load the basis file
                basis_file_name = 'basis_data.csv' 
                if not os.path.exists(basis_file_name):
                    return f"Error: Basis file '{basis_file_name}' not found. Please save 'PosProductDetails-RMS (1).csv' as 'basis_data.csv' in the same folder as 'app.py'.", 500
                
                df_basis = pd.read_csv(basis_file_name)
                
                df_exported = process_data(df_imported, df_basis)
                
                # Generate downloadable CSV file
                output = io.StringIO()
                df_exported.to_csv(output, index=False)
                output.seek(0)
                output_bytes = io.BytesIO(output.getvalue().encode('utf-8'))
                
                response = send_file(
                    output_bytes, 
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name='monggoloid.csv' 
                )
                
                return response
                
            except Exception as e:
                return f"An error occurred during file processing: {e}", 500

    # HTML Interface for file upload (GET request)
    success_message = request.args.get('success')
    
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
        
        #success-view {{
            display: flex;
            flex-direction: column;
            align-items: center; 
        }}
        .reset-button {{
            background-color: #007bff; 
            width: auto; 
            margin-top: 10px; 
        }}
        .reset-button:hover {{
            background-color: #0056b3; 
        }}
        
        button:hover {{ background-color: #218838; }}
        .note {{ background-color: #fff3cd; color: #856404; padding: 10px; border: 1px solid #ffeeba; border-radius: 4px; margin-top: 15px; }}
        
    </style>
    <div class="container">
        <h1>POS Template shit</h1>
        
        <div id="success-view" style="display: {'block' if success_message == 'true' else 'none'};">
            <div class="success-prompt">
                ✅ File successfully processed and download initiated!
            </div>
            <button class="reset-button" onclick="window.location.href = window.location.pathname;">
                Generate New File
            </button>
        </div>

        <form id="upload-form" method="POST" enctype="multipart/form-data" action="/" style="display: {'none' if success_message == 'true' else 'flex'};">
            <input type="file" name="file" required>
            
            <button type="submit">Proceed and Generate New CSV File</button>
        </form>
        
        <div class="note">
            <strong>Generated template note:</strong> The generated CSV file automatically put values on those required columns for importing POS products in HLX. Modify columns if needed.
        </div>
    </div>
    <script>
        const isSuccess = '{{ success_message }}' === 'true';

        document.querySelector('#upload-form').onsubmit = function() {{
            const fileInput = document.querySelector('input[type="file"]');
            if (fileInput.files.length > 0) {{
                document.querySelector('#upload-form button[type="submit"]').disabled = true;
                
                setTimeout(() => {{
                    window.location.href = window.location.pathname + '?success=true';
                }}, 2000); 
            }}
            return true;
        }};

        if (isSuccess) {{
            window.scrollTo(0, 0);
        }}
    </script>
    """
    return render_template_string(html_template)

# --- Main Execution (Unchanged) ---
if __name__ == '__main__':
    print("Running Flask app. Open your browser to http://127.0.0.1:5000/")
    app.run(debug=True)