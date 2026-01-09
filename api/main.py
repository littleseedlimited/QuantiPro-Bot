"""
QuantiProBot API - FastAPI Backend for Mini App
Provides REST endpoints for all bot functionality.
"""
import os
import sys
import json
import hashlib
import hmac
from urllib.parse import parse_qs
from datetime import datetime
from typing import Optional, List, Dict, Any
import numpy as np

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.db_manager import DatabaseManager
from src.core.file_manager import FileManager
from src.core.analyzer import Analyzer
from src.core.visualizer import Visualizer
from src.core.sampler import Sampler
from src.writing.generator import ManuscriptGenerator
from openai import AsyncOpenAI
import asyncio

# Initialize FastAPI
app = FastAPI(
    title="QuantiProBot API",
    description="REST API for QuantiProBot Mini App",
    version="1.0.0"
)

# CORS for Telegram Mini App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Telegram uses various domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve Mini App static files - MOVED TO END
MINIAPP_DIR = os.path.join(os.path.dirname(__file__), "..", "miniapp")
# if os.path.exists(MINIAPP_DIR):
#    app.mount("/app", StaticFiles(directory=MINIAPP_DIR, html=True), name="miniapp")

DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


# ==================== MODELS ====================

class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None

class AnalysisRequest(BaseModel):
    file_id: str
    analysis_type: str
    variables: Optional[List[str]] = None
    options: Optional[Dict[str, Any]] = None

class ProjectCreate(BaseModel):
    title: str
    file_path: Optional[str] = None
    context_data: Optional[Dict[str, Any]] = None

class SamplingRequest(BaseModel):
    method: str
    confidence_level: float = 0.95
    margin_of_error: float = 0.05
    population_size: Optional[int] = None
    expected_proportion: float = 0.5

class AIChatRequest(BaseModel):
    message: str
    file_id: Optional[str] = None

class ReportRequest(BaseModel):
    title: str = "Analysis Report"
    file_id: Optional[str] = None
    sections: Optional[Dict[str, str]] = None


# ==================== AUTH ====================

def verify_telegram_data(init_data: str) -> Optional[TelegramUser]:
    """Verify Telegram Web App initData and extract user."""
    if not BOT_TOKEN:
        # Dev mode - return mock user
        print("DEBUG: No BOT_TOKEN, using dev mode")
        return TelegramUser(id=12345, first_name="Dev", username="developer")
    
    try:
        parsed = parse_qs(init_data)
        print(f"DEBUG: Parsed init_data keys: {list(parsed.keys())}")
        
        data_check_string = "\n".join(
            f"{k}={v[0]}" for k, v in sorted(parsed.items()) if k != "hash"
        )
        
        secret_key = hmac.new(
            b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
        ).digest()
        
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()
        
        received_hash = parsed.get("hash", [""])[0]
        print(f"DEBUG: Hash match: {calculated_hash == received_hash}")
        
        if calculated_hash == received_hash:
            user_data = json.loads(parsed.get("user", ["{}"])[0])
            print(f"DEBUG: Extracted user_id: {user_data.get('id')}")
            return TelegramUser(**user_data)
        else:
            print(f"DEBUG: Hash mismatch - received: {received_hash[:20]}... calculated: {calculated_hash[:20]}...")
    except Exception as e:
        print(f"Auth error: {e}")
    
    return None


async def get_current_user(x_telegram_init_data: str = Header(None)) -> TelegramUser:
    """Dependency to get authenticated user from Telegram initData."""
    print(f"DEBUG: Received init_data header: {x_telegram_init_data[:100] if x_telegram_init_data else 'None'}...")
    
    if not x_telegram_init_data:
        # Allow dev access without auth
        print("DEBUG: No auth header, using dev user 12345")
        return TelegramUser(id=12345, first_name="Dev", username="developer")
    
    user = verify_telegram_data(x_telegram_init_data)
    if user:
        print(f"DEBUG: Authenticated user: {user.id} - {user.first_name}")
        return user
    else:
        print("DEBUG: Auth verification failed, falling back to dev user")
        # Fallback to dev user instead of raising error during development
        return TelegramUser(id=12345, first_name="Dev", username="developer")


# ==================== ROUTES ====================

@app.get("/")
async def root():
    """Redirect to Mini App."""
    return FileResponse(os.path.join(MINIAPP_DIR, "index.html"))


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/user")
async def get_user_info(user: TelegramUser = Depends(get_current_user)):
    """Get current user info and plan details."""
    db = DatabaseManager()
    db_user = db.get_user(user.id)
    
    if not db_user:
        return {
            "id": user.id,
            "name": user.first_name,
            "plan": "Free",
            "is_new": True
        }
    
    return {
        "id": user.id,
        "name": db_user.full_name or user.first_name,
        "email": db_user.email,
        "plan": db_user.plan.name if db_user.plan else "Free",
        "is_new": False
    }


@app.get("/api/session/active")
async def get_active_session_info(user: TelegramUser = Depends(get_current_user)):
    """Retrieve the user's active session data (mirrored from bot)."""
    db = DatabaseManager()
    session_data = db.get_active_session(user.id)
    
    if not session_data:
        return {"active": False}
        
    # If session exists, load file info to return full state to frontend
    try:
        file_path = session_data['file_path']
        if not os.path.exists(file_path):
            return {"active": False, "error": "File not found"}
            
        df, _ = FileManager.load_file(file_path)
        
        # Determine file_id from path
        file_id = os.path.basename(file_path)
        
        # Get column info
        columns = list(df.columns)
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=['number']).columns.tolist()
        
        return {
            "active": True,
            "file_id": file_id,
            "file_path": file_path,
            "rows": len(df),
            "columns": columns,
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "preview": df.head(5).replace({np.nan: None}).to_dict(orient="records")
        }
    except Exception as e:
        print(f"Session retrieval error: {e}")
        return {"active": False, "error": str(e)}


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: TelegramUser = Depends(get_current_user)
):
    """Upload a data file for analysis."""
    try:
        # Save file
        file_path = os.path.join(DATA_DIR, f"{user.id}_{file.filename}")
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Load and validate
        df, meta = FileManager.load_file(file_path)
        df = FileManager.clean_data(df)
        
        # Get column info
        columns = list(df.columns)
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=['number']).columns.tolist()
        
        return {
            "file_id": f"{user.id}_{file.filename}",
            "file_path": file_path,
            "rows": len(df),
            "columns": columns,
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "preview": df.head(5).replace({np.nan: None}).to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/analyze/descriptive")
async def analyze_descriptive(
    request: AnalysisRequest,
    user: TelegramUser = Depends(get_current_user)
):
    """Run descriptive statistics analysis."""
    try:
        file_path = os.path.join(DATA_DIR, request.file_id)
        df, _ = FileManager.load_file(file_path)
        
        stats = Analyzer.get_descriptive_stats(df, request.variables)
        
        # Generate image
        img_path = Visualizer.create_stats_table_image(stats)
        
        return {
            "success": True,
            "data": stats.to_dict(),
            "image_path": img_path,
            "formatted": stats.round(3).to_html()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/analyze/correlation")
async def analyze_correlation(
    request: AnalysisRequest,
    user: TelegramUser = Depends(get_current_user)
):
    """Run correlation analysis."""
    try:
        file_path = os.path.join(DATA_DIR, request.file_id)
        df, _ = FileManager.load_file(file_path)
        
        result = Analyzer.get_correlation(df, request.variables)
        
        # Generate heatmap
        # img_path = Visualizer.create_correlation_heatmap(df, request.variables)
        img_path = None # Disable for now until implemented
        
        return {
            "success": True,
            "data": result,
            "image_path": img_path
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/analyze/hypothesis")
async def analyze_hypothesis(
    request: AnalysisRequest,
    user: TelegramUser = Depends(get_current_user)
):
    """Run hypothesis test."""
    try:
        file_path = os.path.join(DATA_DIR, request.file_id)
        df, _ = FileManager.load_file(file_path)
        
        test_type = request.options.get("test_type", "t_test") if request.options else "t_test"
        
        if test_type == "t_test":
            result = Analyzer.run_ttest(df, request.variables[0], request.variables[1])
        elif test_type == "anova":
            result = Analyzer.run_anova(df, request.variables[0], request.variables[1])
        elif test_type == "chi_square":
            result = Analyzer.run_chi2(df, request.variables[0], request.variables[1])
        else:
            raise ValueError(f"Unknown test type: {test_type}")
        
        return {
            "success": True,
            "test_type": test_type,
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/analyze/crosstab")
async def analyze_crosstab(
    request: AnalysisRequest,
    user: TelegramUser = Depends(get_current_user)
):
    """Run Crosstab analysis."""
    try:
        file_path = os.path.join(DATA_DIR, request.file_id)
        df, _ = FileManager.load_file(file_path)
        
        result = Analyzer.crosstab(df, request.variables[0], request.variables[1])
        formatted = Analyzer.format_crosstab_mobile(result)
        
        # Convert DataFrames to dicts for JSON serialization
        json_safe_result = {}
        for key, val in result.items():
            if hasattr(val, 'to_dict'):
                 json_safe_result[key] = val.fillna(0).to_dict()
            else:
                 json_safe_result[key] = val
        
        return {
            "success": True,
            "data": json_safe_result,
            "formatted": formatted
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/analyze/regression")
async def analyze_regression(
    request: AnalysisRequest,
    user: TelegramUser = Depends(get_current_user)
):
    """Run Regression analysis."""
    try:
        file_path = os.path.join(DATA_DIR, request.file_id)
        df, _ = FileManager.load_file(file_path)
        
        if len(request.variables) < 2:
             raise ValueError("Regression requires at least 2 variables.")

        y_col = request.variables[0]
        x_cols = request.variables[1:]

        result = Analyzer.run_regression(df, x_cols, y_col)
        
        html_result = str(result).replace('\n', '<br>').replace(' ', '&nbsp;')

        return {
            "success": True,
            "data": str(result),
            "formatted": f"<div style='font-family: monospace; overflow-x: auto;'>{html_result}</div>"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/analyze/visual")
async def analyze_visual(
    request: AnalysisRequest,
    user: TelegramUser = Depends(get_current_user)
):
    """Generate visualization."""
    try:
        file_path = os.path.join(DATA_DIR, request.file_id)
        df, _ = FileManager.load_file(file_path)
        
        chart_type = request.options.get("chart_type", "histogram")
        
        # TODO: Implement proper visualizer calls based on type
        # Placeholder for now
        img_path = None
        
        return {
            "success": True,
            "image_path": img_path
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sampling/calculate")
async def calculate_sample_size(
    request: SamplingRequest,
    user: TelegramUser = Depends(get_current_user)
):
    """Calculate required sample size."""
    try:
        result = Sampler.calculate_sample_size(
            method=request.method,
            confidence_level=request.confidence_level,
            margin_of_error=request.margin_of_error,
            population_size=request.population_size,
            expected_proportion=request.expected_proportion
        )
        
        return {
            "success": True,
            "sample_size": result.get("sample_size"),
            "details": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== AI & REPORTS ====================

@app.post("/api/ai/chat")
async def ai_chat(
    request: AIChatRequest,
    user: TelegramUser = Depends(get_current_user)
):
    """Chat with AI about the dataset."""
    try:
        data_summary = "No dataset loaded."
        
        if request.file_id:
            file_path = os.path.join(DATA_DIR, request.file_id)
            if os.path.exists(file_path):
                df, _ = FileManager.load_file(file_path)
                data_summary = f"Dataset: {len(df)} rows, {len(df.columns)} columns\n"
                data_summary += f"Columns: {', '.join(df.columns.tolist())}\n"
                num_cols = df.select_dtypes(include='number').columns.tolist()
                data_summary += f"Numeric: {', '.join(num_cols[:50])}"

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"response": "Error: OpenAI API Key not configured."}

        client = AsyncOpenAI(api_key=api_key)
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": f"You are a statistical analyst. The user has a dataset with these details:\n{data_summary}\n\nAnswer their question about the data. Be concise and clear. Do NOT use asterisks or markdown formatting. Use plain text only."},
                    {"role": "user", "content": request.message}
                ],
                max_tokens=300,
                timeout=60.0
            )
            answer = response.choices[0].message.content
            return {"response": answer}
            
        except asyncio.TimeoutError:
            return {"response": "AI Request Timed Out."}
            
    except Exception as e:
        print(f"AI Chat Error: {e}")
        return {"response": "Sorry, I couldn't process that request."}


@app.post("/api/reports/generate")
async def generate_report(
    request: ReportRequest,
    user: TelegramUser = Depends(get_current_user)
):
    """Generate a downloadable report."""
    try:
        generator = ManuscriptGenerator()
        
        # Prepare content (basic implementation)
        filename = f"report_{user.id}_{int(datetime.now().timestamp())}.docx"
        output_path = os.path.join(DATA_DIR, filename)
        
        # Determine authors
        authors = [f"{user.first_name} {user.last_name or ''}".strip()]
        
        # Generate with default sections if not provided
        generator.generate(
            filename=output_path,
            title=request.title,
            authors=authors,
            abstract=request.sections.get('abstract', "Auto-generated analysis report."),
            introduction_text=request.sections.get('intro', ""),
            methods_text=request.sections.get('methods', "Data was analyzed using QuantiProBot."),
            stats_results=[request.sections.get('results', "See attached figures.")],
            discussion_text=request.sections.get('discussion', ""),
            conclusion_text=request.sections.get('conclusion', "")
        )
        
        return {
            "success": True,
            "filename": filename,
            "download_url": f"/api/reports/download/{filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/reports/download/{filename}")
async def download_report(filename: str):
    """Download a generated report."""
    file_path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )

# ==================== PROJECTS ====================

@app.get("/api/projects")
async def list_projects(user: TelegramUser = Depends(get_current_user)):
    """List user's saved projects."""
    db = DatabaseManager()
    tasks = db.get_user_tasks(user.id, limit=20)
    return {"projects": tasks}


@app.post("/api/projects")
async def create_project(
    project: ProjectCreate,
    user: TelegramUser = Depends(get_current_user)
):
    """Create a new project."""
    db = DatabaseManager()
    task_id = db.save_task(
        user_id=user.id,
        title=project.title,
        file_path=project.file_path or "",
        context_data=project.context_data or {},
        status="saved"
    )
    return {"id": task_id, "message": "Project saved"}


@app.get("/api/projects/{project_id}")
async def get_project(
    project_id: int,
    user: TelegramUser = Depends(get_current_user)
):
    """Get a specific project."""
    db = DatabaseManager()
    task = db.get_task(project_id)
    if not task:
        raise HTTPException(status_code=404, detail="Project not found")
    return task


@app.delete("/api/projects/{project_id}")
async def delete_project(
    project_id: int,
    user: TelegramUser = Depends(get_current_user)
):
    """Delete a project."""
    db = DatabaseManager()
    success = db.delete_task(project_id, user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"message": "Project deleted"}


# ==================== ADMIN ROUTES ====================

@app.get("/api/admin/users")
async def admin_list_users(user: TelegramUser = Depends(get_current_user)):
    """List all users (Admin only)."""
    db = DatabaseManager()
    
    # Check admin status (DB flag OR Super Admin whitelist)
    is_super = False
    
    # Check Username
    if user.username and user.username.lower() == "origichidiah":
        is_super = True
    
    # Check Env Var
    super_id = os.getenv("SUPER_ADMIN_ID")
    if super_id and str(user.id) == str(super_id):
        is_super = True
        
    # Check Hardcoded ID (The user's specific ID)
    if str(user.id) == "1241907317":
        is_super = True
        
    admin_user = db.get_user(user.id)
    if not is_super and (not admin_user or not admin_user.is_admin):
        # Return detail to help debug
        raise HTTPException(status_code=403, detail=f"Access Denied for user: {user.username} ({user.id}). Bot Token configured? {bool(BOT_TOKEN)}")
        
    users = db.get_all_users()
    return {"users": users}

@app.get("/api/admin/stats")
async def admin_stats(user: TelegramUser = Depends(get_current_user)):
    """Get system stats (Admin only)."""
    db = DatabaseManager()
    
    # Check admin status
    is_super = False
    if user.username and user.username.lower() == "origichidiah":
        is_super = True
        
    super_id = os.getenv("SUPER_ADMIN_ID")
    if super_id and str(user.id) == str(super_id):
        is_super = True

    if str(user.id) == "1241907317":
        is_super = True

    admin_user = db.get_user(user.id)
    if not is_super and (not admin_user or not admin_user.is_admin):
        raise HTTPException(status_code=403, detail=f"Access Denied for user: {user.username} ({user.id})")
        
    # Basic stats
    users = db.get_all_users()
    total_users = len(users)
    verified_users = sum(1 for u in users if u.get('verified'))
    
    return {
        "total_users": total_users,
        "verified_users": verified_users,
        "active_today": 0 # Placeholder
    }


# ==================== HOSTING OPTIONS ====================
"""
HOSTING RECOMMENDATIONS:

1. **Fly.io** (Recommended - you already have fly.toml)
   - Add API to existing Dockerfile
   - Run both bot and API on same instance
   - Free tier available

2. **Railway**
   - Easy Python deployment
   - Automatic HTTPS
   - Free tier: 500 hours/month

3. **Render**
   - Free static site hosting for Mini App
   - Free web service tier
   - Auto-deploy from GitHub

4. **Vercel + Railway combo**
   - Vercel for static Mini App (free)
   - Railway for API backend

5. **Self-hosted VPS** (DigitalOcean, Linode)
   - Full control
   - $4-6/month for basic VPS
"""


# ==================== STATIC SERVING ====================

# Mount /app for specific access
if os.path.exists(MINIAPP_DIR):
    app.mount("/app", StaticFiles(directory=MINIAPP_DIR, html=True), name="miniapp_app")

# Mount root "/" as catch-all for static files (MUST BE LAST)
# This allows serving /admin.html, /styles.css directly
if os.path.exists(MINIAPP_DIR):
    app.mount("/", StaticFiles(directory=MINIAPP_DIR, html=True), name="miniapp_root")

if __name__ == "__main__":
    import uvicorn
    # Debug paths
    print(f"DEBUG: MINIAPP_DIR = {os.path.abspath(MINIAPP_DIR)}")
    print(f"DEBUG: Files in MINIAPP_DIR: {os.listdir(MINIAPP_DIR) if os.path.exists(MINIAPP_DIR) else 'Not Found'}")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
