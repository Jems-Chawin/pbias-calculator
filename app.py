from flask import Flask, request, render_template, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
import numpy as np
import os
from werkzeug.utils import secure_filename
import tempfile
from sklearn.model_selection import train_test_split
import time

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


def calculate_split_pbias_sklearn(df_observe, df_predict, split_ratio=0.5, random_seed=42):
    """Calculate PBIAS and position stats for public/private splits"""
    
    # Create indices
    indices = np.arange(len(df_observe))
    
    # Random split
    public_idx, private_idx = train_test_split(
        indices, 
        test_size=(1 - split_ratio), 
        random_state=random_seed,
        shuffle=True
    )
    
    # Split the data
    public_observe = df_observe.iloc[public_idx]
    public_predict = df_predict.iloc[public_idx]
    
    private_observe = df_observe.iloc[private_idx]
    private_predict = df_predict.iloc[private_idx]
    
    # Calculate PBIAS for each split
    overall_pbias = pbias_abs(df_observe, df_predict)
    public_pbias = pbias_abs(public_observe, public_predict)
    private_pbias = pbias_abs(private_observe, private_predict)
    
    # Calculate position stats for overall
    overall_positions = calculate_position_matches(df_observe, df_predict)
    
    # Calculate position stats for public split
    public_positions = calculate_position_matches(public_observe, public_predict)
    
    # Calculate position stats for private split
    private_positions = calculate_position_matches(private_observe, private_predict)
    
    return {
        'overall': overall_pbias,
        'public': public_pbias,
        'private': private_pbias,
        'public_rows': len(public_idx),
        'private_rows': len(private_idx),
        'position_stats': overall_positions,
        'public_position_stats': public_positions,
        'private_position_stats': private_positions
    }


def calculate_position_matches(df_observe, df_predict):
    """Calculate position matches based on zero and non-zero values
    
    Following the friend's suggestion:
    1. Total positions
    2. Both are zero
    3. Both are non-zero  
    4. Submission non-zero but ground truth zero
    5. Submission zero but ground truth non-zero
    """
    # Get boolean masks
    obs_zero = df_observe == 0
    pred_zero = df_predict == 0
    obs_nonzero = df_observe != 0
    pred_nonzero = df_predict != 0
    
    # Calculate all cases
    both_zero = (obs_zero & pred_zero).sum().sum()
    both_nonzero = (obs_nonzero & pred_nonzero).sum().sum()
    pred_nonzero_obs_zero = (pred_nonzero & obs_zero).sum().sum()
    pred_zero_obs_nonzero = (pred_zero & obs_nonzero).sum().sum()
    
    total_positions = df_observe.size
    
    # IMPORTANT: Keep the old keys for backward compatibility
    # AND add the new keys
    return {
        # Old keys (for compatibility)
        'matches': int(both_nonzero),
        'mismatches': int(pred_nonzero_obs_zero + pred_zero_obs_nonzero),
        'only_groundtruth_positive': int(pred_zero_obs_nonzero),
        'only_submission_positive': int(pred_nonzero_obs_zero),
        'total_positions': int(total_positions),
        # New keys for the updated display
        'both_zero': int(both_zero),
        'both_nonzero': int(both_nonzero),
        'submission_nonzero_truth_zero': int(pred_nonzero_obs_zero),
        'submission_zero_truth_nonzero': int(pred_zero_obs_nonzero)
    }


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
    return render_template('index.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)


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
            pbias_results = calculate_split_pbias_sklearn(
                groundtruth_data.iloc[:, 5:], 
                uploaded_data.iloc[:, 5:],
                split_ratio=0.5,
                random_seed=69420
            )

            # Calculate position matches
            position_stats = calculate_position_matches(
                groundtruth_data.iloc[:, 5:], 
                uploaded_data.iloc[:, 5:]
            )
            
            # Check for warnings
            warnings = []
            if np.isnan(pbias_results['overall']):
                warnings.append("PBIAS score is NaN (possibly due to zero values in ground truth)")
                pbias_results['overall'] = 0.0  # Convert NaN to 0 for display

            # Also handle NaN for public and private scores
            if np.isnan(pbias_results['public']):
                pbias_results['public'] = 0.0
            if np.isnan(pbias_results['private']):
                pbias_results['private'] = 0.0
            
            # Calculate processing time
            processing_time = round(time.time() - start_time, 2)
            
            # Prepare response
            response = {
                'pbias_score': float(pbias_results['overall']),
                'pbias_public': float(pbias_results['public']),
                'pbias_private': float(pbias_results['private']),
                'public_rows': pbias_results['public_rows'],
                'private_rows': pbias_results['private_rows'],
                'submission_shape': list(uploaded_data.shape),
                'groundtruth_shape': list(groundtruth_data.shape),
                'start_column': 6,
                'end_column': uploaded_data.shape[1],
                'processing_time': processing_time,
                'used_default': used_default,
                'position_stats': pbias_results['position_stats'],
                'public_position_stats': pbias_results['public_position_stats'],
                'private_position_stats': pbias_results['private_position_stats']
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
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)