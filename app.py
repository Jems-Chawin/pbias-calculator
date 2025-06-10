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

# Increase timeout for large file processing
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# HTML template (updated for large files)
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
        .upload-section {
            margin: 20px 0;
            padding: 20px;
            border: 2px dashed #ccc;
            border-radius: 5px;
            background-color: #fafafa;
        }
        label {
            display: block;
            margin-bottom: 10px;
            font-weight: bold;
            color: #555;
        }
        input[type="file"] {
            margin-bottom: 20px;
            padding: 10px;
            width: 100%;
            box-sizing: border-box;
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
    </style>
</head>
<body>
    <div class="container">
        <h1>PBIAS Score Calculator</h1>
        <div class="info">
            <strong>Large File Support Enabled</strong><br>
            Maximum file size: 200MB per CSV<br>
            <small>Processing may take a moment for files over 50MB</small>
        </div>
        
        <form id="uploadForm">
            <div class="upload-section">
                <label for="submission">Upload Submission CSV:</label>
                <input type="file" id="submission" name="submission" accept=".csv" required>
            </div>
            
            <div class="upload-section">
                <label for="groundtruth">Upload Ground Truth CSV:</label>
                <input type="file" id="groundtruth" name="groundtruth" accept=".csv" required>
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
        // Increase timeout for large files
        const TIMEOUT = 5 * 60 * 1000; // 5 minutes
        
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData();
            const submissionFile = document.getElementById('submission').files[0];
            const groundtruthFile = document.getElementById('groundtruth').files[0];
            
            if (!submissionFile || !groundtruthFile) {
                showError('Please select both CSV files');
                return;
            }
            
            // Check file sizes
            const totalSize = submissionFile.size + groundtruthFile.size;
            const totalSizeMB = (totalSize / 1024 / 1024).toFixed(1);
            
            if (totalSize > 200 * 1024 * 1024) {
                showError(`Total file size (${totalSizeMB}MB) exceeds 200MB limit`);
                return;
            }
            
            formData.append('submission', submissionFile);
            formData.append('groundtruth', groundtruthFile);
            
            // Show loading
            document.querySelector('.loading').style.display = 'block';
            document.getElementById('result').style.display = 'none';
            document.getElementById('error').style.display = 'none';
            document.querySelector('button[type="submit"]').disabled = true;
            
            // Simulate progress (since we can't track actual upload progress easily)
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
                    showError(data.error || 'An error occurred');
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
            }
        });
        
        function showResult(data) {
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = `
                <h2>Results</h2>
                <p><strong>PBIAS Score:</strong> ${data.pbias_score.toFixed(4)}%</p>
                <p><strong>Submission shape:</strong> ${data.submission_shape[0]} rows × ${data.submission_shape[1]} columns</p>
                <p><strong>Ground truth shape:</strong> ${data.groundtruth_shape[0]} rows × ${data.groundtruth_shape[1]} columns</p>
                <p><strong>Data columns used:</strong> Columns ${data.start_column} to ${data.end_column}</p>
                <p><strong>Processing time:</strong> ${data.processing_time || 'N/A'} seconds</p>
            `;
            resultDiv.style.display = 'block';
        }
        
        function showError(message) {
            const errorDiv = document.getElementById('error');
            errorDiv.innerHTML = `<strong>Error:</strong> ${message}`;
            errorDiv.style.display = 'block';
        }
    </script>
</body>
</html>
'''

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

@app.route('/calculate_pbias', methods=['POST'])
def calculate_pbias():
    """API endpoint to calculate PBIAS score"""
    import time
    start_time = time.time()
    
    try:
        # Check if files are present
        if 'submission' not in request.files or 'groundtruth' not in request.files:
            return jsonify({'error': 'Both CSV files are required'}), 400
        
        submission_file = request.files['submission']
        groundtruth_file = request.files['groundtruth']
        
        # Validate file names
        if submission_file.filename == '' or groundtruth_file.filename == '':
            return jsonify({'error': 'No files selected'}), 400
        
        # Validate file extensions
        if not (allowed_file(submission_file.filename) and allowed_file(groundtruth_file.filename)):
            return jsonify({'error': 'Only CSV files are allowed'}), 400
        
        # Save temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_submission:
            submission_file.save(tmp_submission.name)
            submission_path = tmp_submission.name
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_groundtruth:
            groundtruth_file.save(tmp_groundtruth.name)
            groundtruth_path = tmp_groundtruth.name
        
        try:
            # Read CSV files - use chunks for very large files
            uploaded_data = pd.read_csv(submission_path)
            groundtruth_data = pd.read_csv(groundtruth_path)
            
            # Validate data shapes
            if uploaded_data.shape != groundtruth_data.shape:
                return jsonify({
                    'error': f'Data shape mismatch. Submission: {uploaded_data.shape}, Ground truth: {groundtruth_data.shape}'
                }), 400
            
            # Check if there are enough columns
            if uploaded_data.shape[1] < 6:
                return jsonify({
                    'error': f'Not enough columns. Expected at least 6 columns, got {uploaded_data.shape[1]}'
                }), 400
            
            # Calculate PBIAS using columns from index 5 onwards
            pbias_score = pbias_abs(groundtruth_data.iloc[:, 5:], uploaded_data.iloc[:, 5:])
            
            # Calculate processing time
            processing_time = round(time.time() - start_time, 2)
            
            # Prepare response
            response = {
                'pbias_score': float(pbias_score),
                'submission_shape': list(uploaded_data.shape),
                'groundtruth_shape': list(groundtruth_data.shape),
                'start_column': 6,
                'end_column': uploaded_data.shape[1],
                'processing_time': processing_time
            }
            
            return jsonify(response), 200
            
        finally:
            # Clean up temporary files
            if os.path.exists(submission_path):
                os.unlink(submission_path)
            if os.path.exists(groundtruth_path):
                os.unlink(groundtruth_path)
            
    except pd.errors.EmptyDataError:
        return jsonify({'error': 'One or both CSV files are empty'}), 400
    except pd.errors.ParserError:
        return jsonify({'error': 'Error parsing CSV files. Please check the file format'}), 400
    except MemoryError:
        return jsonify({'error': 'Files are too large to process. Please try smaller files or split them.'}), 500
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

@app.errorhandler(413)
def request_entity_too_large(e):
    return jsonify({'error': 'File too large. Maximum total size is 200MB'}), 413

if __name__ == '__main__':
    # Run the Flask app
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)