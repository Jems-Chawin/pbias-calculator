#!/bin/bash

# Configuration
NGROK_DOMAIN="pbias-calculator.ngrok.app"  # Replace with your domain
PORT=8080

echo "Starting PBIAS Calculator Server..."
echo "========================================="

# Start the Flask server in the background
echo "Starting Flask server on port $PORT..."
python run.py &
FLASK_PID=$!

# Wait for Flask to fully start
sleep 5

# Start ngrok with custom domain
echo "Starting ngrok with domain: $NGROK_DOMAIN"
./ngrok http $PORT --domain=$NGROK_DOMAIN &
NGROK_PID=$!

# Wait for ngrok to initialize
sleep 3

echo ""
echo "========================================="
echo "✅ PBIAS Calculator is ready!"
echo "========================================="
echo ""
echo "🌐 Permanent URL: https://$NGROK_DOMAIN"
echo ""
echo "Share this URL with your friends - it never changes!"
echo ""
echo "📊 Ngrok Inspector: http://localhost:4040"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================="

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $FLASK_PID 2>/dev/null
    kill $NGROK_PID 2>/dev/null
    echo "Server stopped."
    exit 0
}

# Set trap for Ctrl+C
trap cleanup INT

# Keep script running
wait