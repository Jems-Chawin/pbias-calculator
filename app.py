from flask import Flask, request, render_template_string, jsonify
from flask_cors import CORS
import csv
import os
from werkzeug.utils import secure_filename
import tempfile
import logging

app = Flask(__name__)
CORS(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'csv'}

# HTML template (same as before)
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>PBIAS Calculator</title>
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
        .note {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 20px;
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
        <p class="note">Note: This lightweight version works with CSV files efficiently</p>
        
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
            <p>Calculating PBIAS score...</p>
        </div>
        
        <div id="result" class="result"></div>
        <div id="error" class="error"></div>
    </div>

    <script>
        document.getElementById('uploadForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData();
            const submissionFile = document.getElementById('submission').files[0];
            const groundtruthFile = document.getElementById('groundtruth').files[0];
            
            if (!submissionFile || !groundtruthFile) {
                showError('Please select both CSV files');
                return;
            }
            
            formData.append('submission', submissionFile);
            formData.append('groundtruth', groundtruthFile);
            
            document.querySelector('.loading').style.display = 'block';
            document.getElementById('result').style.display = 'none';
            document.getElementById('error').style.display = 'none';
            document.querySelector('button[type="submit"]').disabled = true;
            
            try {
                const response = await fetch('/calculate_pbias', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showResult(data);
                } else {
                    showError(data.error || 'An error occurred');
                }
            } catch (error) {
                showError('Network error: ' + error.message);
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
                <p><strong>Submission rows:</strong> ${data.submission_rows}</p>
                <p><strong>Ground truth rows:</strong> ${data.groundtruth_rows}</p>
                <p><strong>Columns processed:</strong> ${data.columns_processed}</p>
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

def calculate_pbias_from_csv(submission_path, groundtruth_path):
    """Calculate PBIAS without loading entire dataset into memory"""
    sum_diff_abs = 0.0
    sum_obs = 0.0
    rows_processed = 0
    columns_processed = 0
    
    with open(submission_path, 'r') as sub_file, open(groundtruth_path, 'r') as gt_file:
        sub_reader = csv.reader(sub_file)
        gt_reader = csv.reader(gt_file)
        
        # Skip headers if any
        sub_header = next(sub_reader, None)
        gt_header = next(gt_reader, None)
        
        # Process row by row
        for sub_row, gt_row in zip(sub_reader, gt_reader):
            if len(sub_row) != len(gt_row):
                raise ValueError(f"Row {rows_processed + 1}: Column count mismatch")
            
            # Process columns from index 5 onwards
            if len(sub_row) > 5:
                columns_processed = len(sub_row) - 5
                for i in range(5, len(sub_row)):
                    try:
                        sub_val = float(sub_row[i])
                        gt_val = float(gt_row[i])
                        sum_diff_abs += abs(sub_val - gt_val)
                        sum_obs += abs(gt_val)
                    except (ValueError, IndexError):
                        continue
            
            rows_processed += 1
    
    if sum_obs == 0:
        return 0.0, rows_processed, columns_processed
    
    pbias = 100 * (sum_diff_abs / sum_obs)
    return pbias, rows_processed, columns_processed

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/calculate_pbias', methods=['POST'])
def calculate_pbias():
    try:
        logger.info("Received PBIAS calculation request")
        
        if 'submission' not in request.files or 'groundtruth' not in request.files:
            logger.error("Missing files in request")
            return jsonify({'error': 'Both CSV files are required'}), 400
        
        submission_file = request.files['submission']
        groundtruth_file = request.files['groundtruth']
        
        logger.info(f"Files received: {submission_file.filename}, {groundtruth_file.filename}")
        
        if submission_file.filename == '' or groundtruth_file.filename == '':
            return jsonify({'error': 'No files selected'}), 400
        
        if not (allowed_file(submission_file.filename) and allowed_file(groundtruth_file.filename)):
            return jsonify({'error': 'Only CSV files are allowed'}), 400
        
        # Save temporary files
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_submission:
                submission_file.save(tmp_submission.name)
                submission_path = tmp_submission.name
                logger.info(f"Saved submission to: {submission_path}")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_groundtruth:
                groundtruth_file.save(tmp_groundtruth.name)
                groundtruth_path = tmp_groundtruth.name
                logger.info(f"Saved groundtruth to: {groundtruth_path}")
        except Exception as e:
            logger.error(f"Error saving files: {str(e)}")
            return jsonify({'error': f'Error saving files: {str(e)}'}), 500
        
        try:
            # Calculate PBIAS
            logger.info("Starting PBIAS calculation")
            pbias_score, rows, cols = calculate_pbias_from_csv(submission_path, groundtruth_path)
            logger.info(f"PBIAS calculated: {pbias_score}, rows: {rows}, cols: {cols}")
            
            response = {
                'pbias_score': float(pbias_score),
                'submission_rows': rows,
                'groundtruth_rows': rows,
                'columns_processed': cols
            }
            
            return jsonify(response), 200
            
        except Exception as calc_error:
            logger.error(f"Error in PBIAS calculation: {str(calc_error)}")
            raise
        finally:
            try:
                os.unlink(submission_path)
                os.unlink(groundtruth_path)
                logger.info("Cleaned up temporary files")
            except Exception as e:
                logger.error(f"Error cleaning up files: {str(e)}")
            
    except ValueError as e:
        logger.error(f"ValueError: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)