from flask import Flask, request, render_template_string, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import os
from werkzeug.utils import secure_filename
import tempfile

app = Flask(__name__)
CORS(app)

# Configuration for large files
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
ALLOWED_EXTENSIONS = {'csv'}

# Default ground truth file path
DEFAULT_GROUNDTRUTH_PATH = "truth_allah.csv"

# Increase timeout for large file processing
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# HTML template (updated for default ground truth)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>PBIAS Calculator - Large File Support</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .info {
            background-color: #e3f2fd;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            text-align: center;
        }
        .default-info {
            background-color: #fff3cd;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            border: 1px solid #ffeaa7;
        }
        .upload-section {
            margin: 20px 0;
            padding: 20px;
            border: 2px dashed #ccc;
            border-radius: 5px;
            background-color: #fafafa;
        }
        .optional-section {
            border-color: #90caf9;
            background-color: #f5f9ff;
        }
        label {
            display: block;
            margin-bottom: 10px;
            font-weight: bold;
            color: #555;
        }
        .optional-label {
            color: #1976d2;
        }
        input[type="file"] {
            margin-bottom: 10px;
            padding: 10px;
            width: 100%;
            box-sizing: border-box;
        }
        .checkbox-container {
            margin: 10px 0;
            display: flex;
            align-items: center;
        }
        input[type="checkbox"] {
            margin-right: 10px;
        }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
            margin-top: 10px;
        }
        button:hover {
            background-color: #45a049;
        }
        button:disabled {
            background-color: #cccccc;
            cursor: not-allowed;
        }
        .result {
            margin-top: 30px;
            padding: 20px;
            background-color: #e8f5e9;
            border-radius: 5px;
            display: none;
        }
        .error {
            background-color: #ffebee;
            color: #c62828;
            padding: 20px;
            border-radius: 5px;
            margin-top: 20px;
            display: none;
        }
        .error ul {
            margin: 10px 0;
            padding-left: 20px;
        }
        .loading {
            display: none;
            text-align: center;
            margin-top: 20px;
        }
        .progress {
            width: 100%;
            height: 20px;
            background-color: #f0f0f0;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-bar {
            height: 100%;
            background-color: #4CAF50;
            width: 0%;
            transition: width 0.3s ease;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #4CAF50;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .small-text {
            font-size: 0.9em;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>PBIAS Score Calculator</h1>
        <div class="info">
            <strong>Professional Calculator Service</strong><br>
            Maximum file size: 200MB per CSV<br>
            <small>Permanent URL: Save this link for future use!</small>
        </div>
        
        <div class="default-info">
            <strong>📌 Default Ground Truth:</strong> <span id="defaultStatus">Checking...</span><br>
            <span class="small-text">You can use the default ground truth file or upload your own below</span>
        </div>
        
        <form id="uploadForm">
            <div class="upload-section">
                <label for="submission">Upload Submission CSV: <span style="color: red;">*</span></label>
                <input type="file" id="submission" name="submission" accept=".csv" required>
            </div>
            
            <div class="upload-section optional-section">
                <label for="groundtruth" class="optional-label">Upload Ground Truth CSV (Optional):</label>
                <input type="file" id="groundtruth" name="groundtruth" accept=".csv">
                <div class="checkbox-container">
                    <input type="checkbox" id="useDefault" name="useDefault" checked>
                    <label for="useDefault" style="font-weight: normal; margin-bottom: 0;">Use default ground truth file</label>
                </div>
                <span class="small-text">Leave empty to use the default ground truth file</span>
            </div>
            
            <button type="submit">Calculate PBIAS Score</button>
        </form>
        
        <div class="loading">
            <div class="spinner"></div>
            <p>Processing large files...</p>
            <div class="progress">
                <div class="progress-bar" id="progressBar"></div>
            </div>
            <p><small>This may take up to a minute for 70MB+ files</small></p>
        </div>
        
        <div id="result" class="result"></div>
        <div id="error" class="error"></div>
    </div>

    <script>
        // Check default ground truth status on load
        window.addEventListener('load', async () => {
            try {
                const response = await fetch('/check_default_groundtruth');
                const data = await response.json();
                const statusElement = document.getElementById('defaultStatus');
                
                if (data.exists) {
                    statusElement.innerHTML = `<span style="color: green;">✓ Available (${data.shape[0]} rows × ${data.shape[1]} columns)</span>`;
                } else {
                    statusElement.innerHTML = '<span style="color: red;">✗ Not found - please upload a ground truth file</span>';
                    document.getElementById('useDefault').checked = false;
                    document.getElementById('useDefault').disabled = true;
                }
            } catch (error) {
                document.getElementById('defaultStatus').innerHTML = '<span style="color: orange;">⚠ Could not check status</span>';
            }
        });
        
        // Handle checkbox and file input interaction
        const groundtruthInput = document.getElementById('groundtruth');
        const useDefaultCheckbox = document.getElementById('useDefault');
        
        groundtruthInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                useDefaultCheckbox.checked = false;
            }
        });
        
        useDefaultCheckbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                groundtruthInput.value = '';
            }
        });
        
        // Increase timeout for large files
        const TIMEOUT = 5 * 60 * 1000; // 5 minutes
        
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData();
            const submissionFile = document.getElementById('submission').files[0];
            const groundtruthFile = document.getElementById('groundtruth').files[0];
            const useDefault = document.getElementById('useDefault').checked;
            
            if (!submissionFile) {
                showError('Please select a submission CSV file');
                return;
            }
            
            if (!useDefault && !groundtruthFile) {
                showError('Please either upload a ground truth file or check "Use default ground truth file"');
                return;
            }
            
            // Check file sizes
            let totalSize = submissionFile.size;
            let totalSizeMB = (totalSize / 1024 / 1024).toFixed(1);
            
            if (groundtruthFile) {
                totalSize += groundtruthFile.size;
                totalSizeMB = (totalSize / 1024 / 1024).toFixed(1);
            }
            
            if (totalSize > 200 * 1024 * 1024) {
                showError(`Total file size (${totalSizeMB}MB) exceeds 200MB limit`);
                return;
            }
            
            formData.append('submission', submissionFile);
            formData.append('use_default', useDefault);
            
            if (groundtruthFile) {
                formData.append('groundtruth', groundtruthFile);
            }
            
            // Show loading
            document.querySelector('.loading').style.display = 'block';
            document.getElementById('result').style.display = 'none';
            document.getElementById('error').style.display = 'none';
            document.querySelector('button[type="submit"]').disabled = true;
            
            // Simulate progress
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += Math.random() * 15;
                if (progress > 90) progress = 90;
                document.getElementById('progressBar').style.width = progress + '%';
            }, 500);
            
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), TIMEOUT);
                
                const response = await fetch('/calculate_pbias', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                clearInterval(progressInterval);
                document.getElementById('progressBar').style.width = '100%';
                
                const data = await response.json();
                
                if (response.ok) {
                    showResult(data);
                } else {
                    showError(data.error || 'An error occurred', data.details);
                }
            } catch (error) {
                clearInterval(progressInterval);
                if (error.name === 'AbortError') {
                    showError('Request timeout - file may be too large or connection too slow');
                } else {
                    showError('Network error: ' + error.message);
                }
            } finally {
                document.querySelector('.loading').style.display = 'none';
                document.querySelector('button[type="submit"]').disabled = false;
                document.getElementById('progressBar').style.width = '0%';
            }
        });
        
        function showResult(data) {
            const resultDiv = document.getElementById('result');
            const groundtruthSource = data.used_default ? 'Default ground truth' : 'Uploaded ground truth';
            
            resultDiv.innerHTML = `
                <h2>Results</h2>
                <p><strong>PBIAS Score:</strong> ${data.pbias_score.toFixed(4)}%</p>
                <p><strong>Ground Truth Used:</strong> ${groundtruthSource}</p>
                <p><strong>Submission shape:</strong> ${data.submission_shape[0]} rows × ${data.submission_shape[1]} columns</p>
                <p><strong>Ground truth shape:</strong> ${data.groundtruth_shape[0]} rows × ${data.groundtruth_shape[1]} columns</p>
                <p><strong>Data columns used:</strong> Columns ${data.start_column} to ${data.end_column}</p>
                <p><strong>Processing time:</strong> ${data.processing_time || 'N/A'} seconds</p>
                ${data.warnings ? '<p style="color: orange;"><strong>Warnings:</strong> ' + data.warnings + '</p>' : ''}
            `;
            resultDiv.style.display = 'block';
        }
        
        function showError(message, details) {
            const errorDiv = document.getElementById('error');
            let errorHTML = `<strong>Error:</strong> ${message}`;
            
            if (details && details.length > 0) {
                errorHTML += '<br><br><strong>Details:</strong><ul>';
                details.forEach(detail => {
                    errorHTML += `<li>${detail}</li>`;
                });
                errorHTML += '</ul>';
            }
            
            errorDiv.innerHTML = errorHTML;
            errorDiv.style.display = 'block';
        }
    </script>
</body>
</html>
'''

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def check_for_null_values(df, name):
    """Check for null values in dataframe and return detailed info"""
    null_info = []
    if df.isnull().any().any():
        null_counts = df.isnull().sum()
        null_cols = null_counts[null_counts > 0]
        for col, count in null_cols.items():
            null_info.append(f"{name}: Column '{col}' has {count} null values")
    return null_info

def pbias_abs(df_observe, df_predict):
    """Calculate absolute percent bias between observed and predicted dataframes"""
    diff_abs = (df_predict - df_observe).abs().values.flatten()
    obs_vals = df_observe.values.flatten()
    
    if obs_vals.sum() == 0:
        return np.nan
    
    pbias = 100 * (diff_abs.sum() / obs_vals.sum())
    return pbias

@app.route('/')
def index():
    """Render the main page"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/check_default_groundtruth')
def check_default_groundtruth():
    """Check if default ground truth file exists"""
    try:
        if os.path.exists(DEFAULT_GROUNDTRUTH_PATH):
            df = pd.read_csv(DEFAULT_GROUNDTRUTH_PATH)
            return jsonify({
                'exists': True,
                'shape': list(df.shape)
            })
        else:
            return jsonify({'exists': False})
    except Exception as e:
        return jsonify({
            'exists': False,
            'error': str(e)
        })

@app.route('/calculate_pbias', methods=['POST'])
def calculate_pbias():
    """API endpoint to calculate PBIAS score"""
    import time
    start_time = time.time()
    
    try:
        # Check if submission file is present
        if 'submission' not in request.files:
            return jsonify({'error': 'Submission CSV file is required'}), 400
        
        submission_file = request.files['submission']
        use_default = request.form.get('use_default', 'false').lower() == 'true'
        
        # Validate submission file
        if submission_file.filename == '':
            return jsonify({'error': 'No submission file selected'}), 400
        
        if not allowed_file(submission_file.filename):
            return jsonify({'error': 'Only CSV files are allowed'}), 400
        
        # Save submission file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_submission:
            submission_file.save(tmp_submission.name)
            submission_path = tmp_submission.name
        
        # Handle ground truth file
        groundtruth_path = None
        used_default = False
        
        try:
            if use_default:
                # Use default ground truth
                if not os.path.exists(DEFAULT_GROUNDTRUTH_PATH):
                    return jsonify({
                        'error': 'Default ground truth file not found',
                        'details': [f'Expected file at: {DEFAULT_GROUNDTRUTH_PATH}']
                    }), 400
                groundtruth_path = DEFAULT_GROUNDTRUTH_PATH
                used_default = True
            else:
                # Use uploaded ground truth
                if 'groundtruth' not in request.files:
                    return jsonify({'error': 'Ground truth file is required when not using default'}), 400
                
                groundtruth_file = request.files['groundtruth']
                if groundtruth_file.filename == '':
                    return jsonify({'error': 'No ground truth file selected'}), 400
                
                if not allowed_file(groundtruth_file.filename):
                    return jsonify({'error': 'Only CSV files are allowed for ground truth'}), 400
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_groundtruth:
                    groundtruth_file.save(tmp_groundtruth.name)
                    groundtruth_path = tmp_groundtruth.name
            
            # Read CSV files
            uploaded_data = pd.read_csv(submission_path)
            groundtruth_data = pd.read_csv(groundtruth_path)
            
            # Check for null values
            error_details = []
            submission_nulls = check_for_null_values(uploaded_data, "Submission file")
            groundtruth_nulls = check_for_null_values(groundtruth_data, "Ground truth file")
            
            if submission_nulls:
                error_details.extend(submission_nulls)
            if groundtruth_nulls:
                error_details.extend(groundtruth_nulls)
            
            # Validate data shapes
            if uploaded_data.shape != groundtruth_data.shape:
                error_details.append(
                    f'Data shape mismatch: Submission has {uploaded_data.shape[0]} rows × {uploaded_data.shape[1]} columns, '
                    f'Ground truth has {groundtruth_data.shape[0]} rows × {groundtruth_data.shape[1]} columns'
                )
            
            # Check if there are enough columns
            if uploaded_data.shape[1] < 6:
                error_details.append(
                    f'Not enough columns in submission file. Expected at least 6 columns, got {uploaded_data.shape[1]}'
                )
            
            if groundtruth_data.shape[1] < 6:
                error_details.append(
                    f'Not enough columns in ground truth file. Expected at least 6 columns, got {groundtruth_data.shape[1]}'
                )
            
            # If there are any errors, return them
            if error_details:
                return jsonify({
                    'error': 'Data validation failed',
                    'details': error_details
                }), 400
            
            # Calculate PBIAS using columns from index 5 onwards
            pbias_score = pbias_abs(groundtruth_data.iloc[:, 5:], uploaded_data.iloc[:, 5:])
            
            # Check for warnings
            warnings = []
            if np.isnan(pbias_score):
                warnings.append("PBIAS score is NaN (possibly due to zero values in ground truth)")
                pbias_score = 0.0  # Convert NaN to 0 for display
            
            # Calculate processing time
            processing_time = round(time.time() - start_time, 2)
            
            # Prepare response
            response = {
                'pbias_score': float(pbias_score),
                'submission_shape': list(uploaded_data.shape),
                'groundtruth_shape': list(groundtruth_data.shape),
                'start_column': 6,
                'end_column': uploaded_data.shape[1],
                'processing_time': processing_time,
                'used_default': used_default
            }
            
            if warnings:
                response['warnings'] = '; '.join(warnings)
            
            return jsonify(response), 200
            
        finally:
            # Clean up temporary files
            if os.path.exists(submission_path):
                os.unlink(submission_path)
            if groundtruth_path and not used_default and os.path.exists(groundtruth_path):
                os.unlink(groundtruth_path)
            
    except pd.errors.EmptyDataError:
        return jsonify({
            'error': 'One or both CSV files are empty',
            'details': ['Please ensure both files contain data']
        }), 400
    except pd.errors.ParserError as e:
        return jsonify({
            'error': 'Error parsing CSV files',
            'details': [f'Parser error: {str(e)}', 'Please check the file format and encoding']
        }), 400
    except MemoryError:
        return jsonify({
            'error': 'Files are too large to process',
            'details': ['Please try smaller files or split them into chunks']
        }), 500
    except Exception as e:
        return jsonify({
            'error': f'An unexpected error occurred: {str(e)}',
            'details': ['Please check your files and try again']
        }), 500

@app.errorhandler(413)
def request_entity_too_large(e):
    return jsonify({
        'error': 'File too large',
        'details': ['Maximum total file size is 200MB', 'Please use smaller files or compress them']
    }), 413

if __name__ == '__main__':
    # Run the Flask app
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)