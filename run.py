from waitress import serve
from app import app

if __name__ == '__main__':
    print("Starting production server...")
    print("Server running on http://0.0.0.0:8080")
    serve(app, host='0.0.0.0', port=8080)