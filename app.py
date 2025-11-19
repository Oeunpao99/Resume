# mains.py - Main FastAPI application (pure Python version)
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

# Import PDF library (pure Python)
try:
    from pdfminer.high_level import extract_text
    PDFMINER_AVAILABLE = True
except ImportError as e:
    print(f"PDFMiner import error: {e}")
    PDFMINER_AVAILABLE = False

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

def extract_personal_info(text: str) -> Dict[str, str]:
    """Extract personal information from resume text"""
    info = {
        'name': 'Not found',
        'email': 'Not found', 
        'phone': 'Not found'
    }
    
    # Extract email
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    if email_match:
        info['email'] = email_match.group()
    
    # Extract phone
    phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
    if phone_match:
        info['phone'] = phone_match.group()
    
    # Simple name extraction (look for lines that might be names)
    lines = text.split('\n')
    for line in lines[:10]:  # Check first 10 lines
        line = line.strip()
        if (len(line) > 2 and len(line) < 50 and 
            not any(word in line.lower() for word in ['resume', 'cv', 'curriculum', 'vitae', 'email', 'phone']) and
            re.match(r'^[A-Za-z\s\.]+$', line)):
            info['name'] = line
            break
    
    return info

def extract_skills(text: str) -> List[str]:
    """Extract skills using keyword matching"""
    skill_keywords = [
        'python', 'java', 'javascript', 'c++', 'c#', 'php', 'ruby', 'go', 'rust',
        'html', 'css', 'react', 'angular', 'vue', 'django', 'flask', 'node', 'express',
        'sql', 'mysql', 'postgresql', 'mongodb', 'redis',
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins',
        'machine learning', 'data analysis', 'artificial intelligence', 'ai',
        'tensorflow', 'pytorch', 'pandas', 'numpy', 'scikit-learn',
        'git', 'linux', 'windows', 'macos'
    ]
    
    found_skills = []
    text_lower = text.lower()
    
    for skill in skill_keywords:
        if skill in text_lower:
            found_skills.append(skill.title())
    
    return list(set(found_skills))  # Remove duplicates

def analyze_resume_sections(text: str) -> Dict[str, Any]:
    """Analyze resume structure and completeness"""
    sections = {
        'contact_info': bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)),
        'summary': any(keyword in text.lower() for keyword in ['summary', 'objective', 'profile']),
        'education': any(keyword in text.lower() for keyword in ['education', 'academic', 'university', 'college']),
        'experience': any(keyword in text.lower() for keyword in ['experience', 'work', 'employment', 'professional']),
        'skills': any(keyword in text.lower() for keyword in ['skills', 'technical', 'technologies']),
        'projects': any(keyword in text.lower() for keyword in ['projects', 'personal projects', 'portfolio'])
    }
    
    score = sum(15 for section in sections.values() if section)
    
    feedback = []
    for section, found in sections.items():
        if found:
            feedback.append(f"✓ {section.replace('_', ' ').title()} found")
        else:
            feedback.append(f"✗ {section.replace('_', ' ').title()} missing")
    
    return {
        'score': min(score, 100),
        'sections_found': sections,
        'feedback': feedback,
        'grade': 'Excellent' if score >= 80 else 'Good' if score >= 60 else 'Needs Improvement'
    }

def extract_education(text: str) -> List[Dict[str, str]]:
    """Extract education information"""
    education = []
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in ['bachelor', 'master', 'phd', 'degree', 'university', 'college']):
            edu = {'institution': line.strip()}
            
            # Look for degree type
            if 'bachelor' in line_lower or 'b.s.' in line_lower or 'b.a.' in line_lower:
                edu['degree'] = 'Bachelor'
            elif 'master' in line_lower or 'm.s.' in line_lower or 'm.a.' in line_lower:
                edu['degree'] = 'Master'
            elif 'phd' in line_lower or 'doctorate' in line_lower:
                edu['degree'] = 'PhD'
            
            # Look for year
            year_match = re.search(r'(19|20)\d{2}', line)
            if year_match:
                edu['year'] = year_match.group()
            
            education.append(edu)
    
    return education

@app.post("/analyze-resume", response_model=ResumeAnalysisResponse)
async def analyze_resume(file: UploadFile = File(...)):
    """
    Analyze uploaded resume PDF using pure Python
    """
    temp_path = None
    try:
        print(f"🔍 Starting analysis for: {file.filename}")
        
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Validate file size (5MB max for Render free tier)
        max_size = 5 * 1024 * 1024
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > max_size:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 5MB")
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Extract text from PDF
        if not PDFMINER_AVAILABLE:
            raise HTTPException(status_code=500, detail="PDF processing not available")
        
        resume_text = extract_text(temp_path)
        
        if not resume_text.strip():
            raise HTTPException(status_code=400, detail="No text could be extracted from PDF")
        
        # Analyze resume content
        personal_info = extract_personal_info(resume_text)
        skills = extract_skills(resume_text)
        quality_analysis = analyze_resume_sections(resume_text)
        education = extract_education(resume_text)
        
        # Determine experience level based on content length
        text_length = len(resume_text)
        if text_length < 1000:
            experience_level = "Fresher"
        elif text_length < 3000:
            experience_level = "Intermediate"
        else:
            experience_level = "Experienced"
        
        # Prepare analysis result
        analysis_result = {
            'personal_information': personal_info,
            'skills_analysis': {
                'detected_skills': skills,
                'total_skills': len(skills),
                'skill_categories': {
                    'programming': [s for s in skills if any(kw in s.lower() for kw in ['python', 'java', 'javascript', 'c++', 'c#'])],
                    'web': [s for s in skills if any(kw in s.lower() for kw in ['html', 'css', 'react', 'angular', 'vue'])],
                    'data': [s for s in skills if any(kw in s.lower() for kw in ['sql', 'database', 'data', 'analysis'])],
                    'tools': [s for s in skills if any(kw in s.lower() for kw in ['git', 'docker', 'aws', 'linux'])]
                }
            },
            'education': education,
            'resume_quality': quality_analysis,
            'experience_level': experience_level,
            'metadata': {
                'filename': file.filename,
                'file_size': file_size,
                'analysis_timestamp': datetime.now().isoformat(),
                'text_length': text_length,
                'processing_engine': 'Pure Python (No external NLP)'
            }
        }
        
        print(f"✅ Analysis completed for: {file.filename}")
        print(f"📊 Found {len(skills)} skills, Score: {quality_analysis['score']}")
        
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
        "engine": "Pure Python (No Rust dependencies)",
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
            "pdfminer": PDFMINER_AVAILABLE
        }
    }

@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify API is working"""
    return {
        "message": "API is working!",
        "engine": "Pure Python - No Rust dependencies",
        "timestamp": datetime.now().isoformat()
    }

# This allows running with: python mains.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
