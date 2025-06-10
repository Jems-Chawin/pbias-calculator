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
    
    // Calculate percentage for position stats
    const matchPercentage = ((data.position_stats.matches / data.position_stats.total_positions) * 100).toFixed(2);
    const mismatchPercentage = ((data.position_stats.mismatches / data.position_stats.total_positions) * 100).toFixed(2);
    
    // Check if this is a perfect match (likely testing with identical files)
    const isPerfectMatch = data.pbias_score === 0 && data.position_stats.mismatches === 0;

    // Check if we have the new stats format
    const hasNewStats = data.position_stats.both_zero !== undefined;
    
    // Helper function to create position stats display
    function createPositionStatsDisplay(stats, title, color) {
        return `
        <div style="background-color: ${color}15; padding: 15px; border-radius: 8px; border-left: 4px solid ${color};">
            <h4 style="margin: 0 0 10px 0; color: ${color};">${title}</h4>
            <div style="font-size: 0.9em; line-height: 1.6;">
                <p style="margin: 5px 0;"><strong>1. Total positions analyzed:</strong> ${stats.total_positions.toLocaleString()}</p>
                <p style="margin: 5px 0;"><strong>2. จำนวนช่องที่ = 0 ในที่ส่งไป และ = 0 ใน ground truth:</strong> ${stats.both_zero.toLocaleString()}</p>
                <p style="margin: 5px 0;"><strong>3. จำนวนช่องที่ != 0 ในที่ส่งไป และ != 0 ใน ground truth:</strong> <span style="color: #4CAF50; font-weight: bold;">${stats.both_nonzero.toLocaleString()}</span></p>
                <p style="margin: 5px 0;"><strong>4. จำนวนช่องที่ != 0 ในที่ส่งไป แต่ = 0 ใน ground truth:</strong> <span style="color: #ff9800;">${stats.submission_nonzero_truth_zero.toLocaleString()}</span></p>
                <p style="margin: 5px 0;"><strong>5. จำนวนช่องที่ = 0 ในที่ส่งไป แต่ != 0 ใน ground truth:</strong> <span style="color: #f44336;">${stats.submission_zero_truth_nonzero.toLocaleString()}</span></p>
            </div>
        </div>
        `;
    }
    
    // Create status message based on results
    let statusMessage = '';
    
    if (isPerfectMatch) {
        statusMessage = `
            <div style="background-color: #4CAF50; color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; text-align: center;">
                <strong>⚠️ PERFECT MATCH DETECTED</strong><br>
                <span style="font-size: 0.9em;">The submission is identical to the ground truth file</span><br>
                <span style="font-size: 0.8em; opacity: 0.9;">This typically indicates you're testing with the same file</span>
            </div>
        `;
    } else if (data.pbias_score < 10) {
        statusMessage = `
            <div style="background-color: #4CAF50; color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; text-align: center;">
                <strong>✅ EXCELLENT RESULT</strong><br>
                <span style="font-size: 0.9em;">Your PBIAS score indicates very low bias</span>
            </div>
        `;
    } else if (data.pbias_score < 25) {
        statusMessage = `
            <div style="background-color: #ff9800; color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; text-align: center;">
                <strong>⚡ MODERATE RESULT</strong><br>
                <span style="font-size: 0.9em;">Your PBIAS score indicates moderate bias</span>
            </div>
        `;
    } else {
        statusMessage = `
            <div style="background-color: #f44336; color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; text-align: center;">
                <strong>⚠️ HIGH BIAS DETECTED</strong><br>
                <span style="font-size: 0.9em;">Your PBIAS score indicates significant bias</span>
            </div>
        `;
    }
    
    // Build the complete result HTML
    let resultHTML = `
        <h2>Results</h2>
        ${statusMessage}
        
        <p><strong>PBIAS Score:</strong> <span style="font-size: 1.2em; font-weight: bold; color: ${data.pbias_score === 0 ? '#4CAF50' : '#333'};">${data.pbias_score.toFixed(4)}%</span></p>
        <p><strong>Ground Truth Used:</strong> ${groundtruthSource}</p>
        <p><strong>Submission shape:</strong> ${data.submission_shape[0]} rows × ${data.submission_shape[1]} columns</p>
        <p><strong>Ground truth shape:</strong> ${data.groundtruth_shape[0]} rows × ${data.groundtruth_shape[1]} columns</p>
        <p><strong>Data columns used:</strong> Columns ${data.start_column} to ${data.end_column}</p>
    `;

    // Add Competition-Style Evaluation if we have public/private data
    if (data.pbias_public !== undefined && data.pbias_private !== undefined) {
        resultHTML += `
        <h3>Competition-Style Evaluation</h3>
        <div style="background-color: #f0f4f8; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <!-- PBIAS Scores Row -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; border-left: 4px solid #2196f3;">
                    <h4 style="margin: 0 0 10px 0; color: #1976d2;">📊 Public Score (50%)</h4>
                    <p style="font-size: 1.8em; font-weight: bold; margin: 5px 0; color: #1565c0;">
                        ${data.pbias_public.toFixed(4)}%
                    </p>
                    <p style="margin: 0; color: #666; font-size: 0.9em;">
                        Based on ${data.public_rows.toLocaleString()} random rows
                    </p>
                </div>
                
                <div style="background-color: #fce4ec; padding: 15px; border-radius: 5px; border-left: 4px solid #e91e63;">
                    <h4 style="margin: 0 0 10px 0; color: #c2185b;">🔒 Private Score (50%)</h4>
                    <p style="font-size: 1.8em; font-weight: bold; margin: 5px 0; color: #880e4f;">
                        ${data.pbias_private.toFixed(4)}%
                    </p>
                    <p style="margin: 0; color: #666; font-size: 0.9em;">
                        Based on ${data.private_rows.toLocaleString()} random rows
                    </p>
                </div>
            </div>
            
            <!-- Position Analysis Row -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                ${data.public_position_stats ? createPositionStatsDisplay(data.public_position_stats, "Public Split Position Analysis", "#2196f3") : ''}
                ${data.private_position_stats ? createPositionStatsDisplay(data.private_position_stats, "Private Split Position Analysis", "#e91e63") : ''}
            </div>
            
            <!-- Overall Score -->
            <div style="margin-top: 15px; padding: 10px; background-color: #fff; border-radius: 5px;">
                <p style="margin: 0; text-align: center;">
                    <strong>Overall PBIAS Score:</strong> 
                    <span style="font-size: 1.3em; color: ${data.pbias_score < 10 ? '#4caf50' : data.pbias_score < 25 ? '#ff9800' : '#f44336'};">
                        ${data.pbias_score.toFixed(4)}%
                    </span>
                </p>
            </div>
        </div>
        `;
    }

    // Add Overall Position Analysis
    resultHTML += `
        <h3>Overall Position Analysis</h3>
        ${hasNewStats ? createPositionStatsDisplay(data.position_stats, "All Data", "#9c27b0") : `
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 15px;">
            <p><strong>✓ Matching positions:</strong> ${data.position_stats.matches.toLocaleString()} positions (${matchPercentage}%)</p>
            <p><strong>✗ Non-matching positions:</strong> <span style="color: ${data.position_stats.mismatches === 0 ? '#4CAF50' : '#f44336'};">${data.position_stats.mismatches.toLocaleString()}</span> positions (${mismatchPercentage}%)</p>
            <p style="margin-left: 20px; font-size: 0.9em;">
                • Only ground truth > 0: ${data.position_stats.only_groundtruth_positive.toLocaleString()} positions<br>
                • Only submission > 0: ${data.position_stats.only_submission_positive.toLocaleString()} positions
            </p>
            <p><strong>Total positions analyzed:</strong> ${data.position_stats.total_positions.toLocaleString()}</p>
        </div>
        `}
    `;
    
    // Add processing time and warnings
    resultHTML += `
        <p style="margin-top: 20px;"><strong>Processing time:</strong> ${data.processing_time || 'N/A'} seconds</p>
        ${data.warnings ? '<p style="color: orange;"><strong>Warnings:</strong> ' + data.warnings + '</p>' : ''}
        ${isPerfectMatch ? '<p style="text-align: center; margin-top: 20px; font-style: italic; color: #666;">💡 Tip: Try testing with a different submission file to see actual bias calculations</p>' : ''}
    `;
    
    resultDiv.innerHTML = resultHTML;
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