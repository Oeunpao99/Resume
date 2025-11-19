# main.py - Render entry point
from app import app

# This file is needed for Render to detect the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
