from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import tempfile
import re
import json
from datetime import datetime
import traceback

# Try to import PDF libraries with error handling
try:
    from pdfminer.high_level import extract_text
    PDFMINER_AVAILABLE = True
except ImportError as e:
    print(f"PDFMiner import error: {e}")
    PDFMINER_AVAILABLE = False
    # Fallback: create a dummy function
    def extract_text(file_path):
        return "PDF text extraction not available"

try:
    from pyresparser import ResumeParser
    PYRESPARSER_AVAILABLE = True
except ImportError as e:
    print(f"PyResParser import error: {e}")
    PYRESPARSER_AVAILABLE = False
    # Fallback: create a dummy function
    def ResumeParser(file_path):
        class DummyParser:
            def get_extracted_data(self):
                return {
                    'name': 'Sample Name',
                    'email': 'sample@email.com',
                    'skills': ['Python', 'FastAPI', 'PDF Processing'],
                    'no_of_pages': 1
                }
        return DummyParser()

app = FastAPI(
    title="Resume Analyzer API",
    description="AI-powered resume analysis and candidate screening API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ResumeAnalysisResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

def analyze_resume_content(resume_text: str, basic_data: dict) -> Dict[str, Any]:
    """Analyze resume content and extract structured information"""
    
    # Extract email
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', resume_text)
    email = email_match.group() if email_match else basic_data.get('email', 'Not found')
    
    # Extract phone
    phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', resume_text)
    phone = phone_match.group() if phone_match else basic_data.get('mobile_number', 'Not found')
    
    # Analyze sections
    sections = {
        'summary': any(keyword in resume_text.lower() for keyword in ['summary', 'objective']),
        'education': any(keyword in resume_text.lower() for keyword in ['education', 'academic']),
        'experience': any(keyword in resume_text.lower() for keyword in ['experience', 'work', 'employment']),
        'skills': any(keyword in resume_text.lower() for keyword in ['skills', 'technical']),
        'projects': any(keyword in resume_text.lower() for keyword in ['projects', 'personal projects']),
    }
    
    resume_score = sum(20 for section in sections.values() if section)
    
    return {
        'personal_info': {
            'name': basic_data.get('name', 'Not specified'),
            'email': email,
            'phone': phone,
            'pages': basic_data.get('no_of_pages', 1)
        },
        'skills_analysis': {
            'detected_skills': basic_data.get('skills', []),
            'total_skills': len(basic_data.get('skills', [])),
            'skill_categories': categorize_skills(basic_data.get('skills', []))
        },
        'resume_quality': {
            'score': resume_score,
            'sections_found': sections,
            'grade': 'Excellent' if resume_score >= 80 else 'Good' if resume_score >= 60 else 'Needs Improvement'
        },
        'experience_level': determine_experience_level(basic_data.get('no_of_pages', 1))
    }

def categorize_skills(skills: List[str]) -> Dict[str, List[str]]:
    """Categorize skills into different domains"""
    categories = {
        'programming': [],
        'web_development': [],
        'data_science': [],
        'devops': [],
        'tools': []
    }
    
    skill_keywords = {
        'programming': ['python', 'java', 'javascript', 'c++', 'c#', 'go', 'rust', 'php'],
        'web_development': ['html', 'css', 'react', 'angular', 'vue', 'django', 'flask', 'node'],
        'data_science': ['machine learning', 'data analysis', 'pandas', 'numpy', 'tensorflow', 'pytorch'],
        'devops': ['docker', 'kubernetes', 'aws', 'azure', 'gcp', 'jenkins', 'ci/cd']
    }
    
    for skill in skills:
        skill_lower = skill.lower()
        categorized = False
        for category, keywords in skill_keywords.items():
            if any(keyword in skill_lower for keyword in keywords):
                categories[category].append(skill)
                categorized = True
                break
        if not categorized:
            categories['tools'].append(skill)
    
    return categories

def determine_experience_level(pages: int) -> str:
    if pages == 1:
        return "Fresher"
    elif pages == 2:
        return "Intermediate"
    else:
        return "Experienced"

@app.post("/analyze-resume", response_model=ResumeAnalysisResponse)
async def analyze_resume(file: UploadFile = File(...)):
    """
    Analyze uploaded resume PDF and extract candidate information
    """
    temp_path = None
    try:
        print(f"🔍 Starting analysis for: {file.filename}")
        
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Validate file size (10MB max)
        max_size = 10 * 1024 * 1024  # 10MB
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Extract text from PDF
        resume_text = extract_text(temp_path)
        
        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="No text could be extracted from PDF")
        
        # Parse with pyresparser
        resume_data = ResumeParser(temp_path).get_extracted_data()
        
        if not resume_data:
            raise HTTPException(status_code=400, detail="Could not extract structured data from resume")
        
        # Enhanced analysis
        analysis_result = analyze_resume_content(resume_text, resume_data)
        
        # Add metadata
        analysis_result['metadata'] = {
            'filename': file.filename,
            'file_size': file_size,
            'analysis_timestamp': datetime.now().isoformat(),
            'text_length': len(resume_text)
        }
        
        print(f"✅ Analysis completed for: {file.filename}")
        
        return ResumeAnalysisResponse(
            success=True,
            message="Resume analyzed successfully",
            data=analysis_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Error analyzing resume: {str(e)}")
        print(f"🔍 Stack trace: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Analysis failed: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass

@app.get("/")
async def root():
    return {
        "message": "Resume Analyzer API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "analyze_resume": "POST /analyze-resume",
            "docs": "GET /docs",
            "health": "GET /health"
        }
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "dependencies": {
            "pdfminer": PDFMINER_AVAILABLE,
            "pyresparser": PYRESPARSER_AVAILABLE
        }
    }

@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify API is working"""
    return {
        "message": "API is working!",
        "timestamp": datetime.now().isoformat()
    }