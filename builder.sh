#!/bin/bash
echo "Installing dependencies for Resume Analyzer API..."
pip install -r requirements.txt

# Download NLTK data
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt')"

echo "Build completed successfully!"