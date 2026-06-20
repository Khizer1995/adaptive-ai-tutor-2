"""
Authentication API Endpoints
Add these to your api_server.py to enable auth functionality.

Copy the code below and paste it into api_server.py
"""

from fastapi import Header, HTTPException
from pydantic import BaseModel
from core.auth import AuthManager
from core.profile_manager import ProfileManager

# Initialize auth manager (add this near top of api_server.py with other initializations)
auth_manager = AuthManager()

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SignupRequest(BaseModel):
    email: str
    password: str
    name: str = None

class LoginRequest(BaseModel):
    email: str
    password: str

class LogoutRequest(BaseModel):
    token: str

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/auth/signup")
async def signup(request: SignupRequest):
    """
    Create a new user account.
    
    Request body:
    {
        "email": "user@example.com",
        "password": "password123",
        "name": "John Doe"  // optional
    }
    
    Response:
    {
        "success": true,
        "user_id": "abc123...",
        "student_id": "USER-abc12345",
        "token": "eyJhbGci...",
        "message": "Account created successfully"
    }
    """
    # Create Supabase user
    result = auth_manager.signup(
        email=request.email,
        password=request.password,
        name=request.name
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # Create student profile linked to user
    user_id = result["user_id"]
    student_id = f"USER-{user_id[:8]}"
    name = request.name or request.email.split("@")[0]
    
    try:
        # Create profile if it doesn't exist
        if student_id not in pm.list_profiles():
            pm.create_profile(
                student_id=student_id,
                name=name,
                level="beginner",
                learning_style="balanced"
            )
        
        result["student_id"] = student_id
        return result
        
    except Exception as e:
        # If profile creation fails, still return success for auth
        # (profile can be created later)
        result["student_id"] = student_id
        result["profile_warning"] = f"Profile creation delayed: {str(e)}"
        return result


@app.post("/auth/login")
async def login(request: LoginRequest):
    """
    Login an existing user.
    
    Request body:
    {
        "email": "user@example.com",
        "password": "password123"
    }
    
    Response:
    {
        "success": true,
        "user_id": "abc123...",
        "student_id": "USER-abc12345",
        "token": "eyJhbGci...",
        "name": "John Doe",
        "message": "Login successful"
    }
    """
    result = auth_manager.login(
        email=request.email,
        password=request.password
    )
    
    if not result["success"]:
        raise HTTPException(status_code=401, detail=result["error"])
    
    # Add student_id to response
    user_id = result["user_id"]
    student_id = f"USER-{user_id[:8]}"
    result["student_id"] = student_id
    
    # Ensure profile exists
    if student_id not in pm.list_profiles():
        pm.create_profile(
            student_id=student_id,
            name=result["name"],
            level="beginner",
            learning_style="balanced"
        )
    
    return result


@app.post("/auth/logout")
async def logout(request: LogoutRequest):
    """
    Logout user and invalidate token.
    
    Request body:
    {
        "token": "eyJhbGci..."
    }
    
    Response:
    {
        "success": true,
        "message": "Logged out successfully"
    }
    """
    result = auth_manager.logout(request.token)
    return result


@app.get("/auth/me")
async def get_current_user(authorization: str = Header(None)):
    """
    Get current logged-in user info.
    
    Headers:
    Authorization: Bearer <token>
    
    Response:
    {
        "user_id": "abc123...",
        "email": "user@example.com",
        "name": "John Doe",
        "student_id": "USER-abc12345"
    }
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    user = auth_manager.verify_token(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Add student_id
    user["student_id"] = f"USER-{user['user_id'][:8]}"
    
    return user


# ============================================================================
# HELPER FUNCTION - Token Verification (use this to protect endpoints)
# ============================================================================

def require_auth(authorization: str = Header(None)) -> Dict[str, Any]:
    """
    Helper function to protect endpoints.
    Use this in any endpoint that requires authentication.
    
    Example usage:
    @app.get("/protected-endpoint")
    async def protected_route(user: Dict = Depends(require_auth)):
        # user contains user_id, email, name
        return {"message": f"Hello {user['name']}"}
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please login first."
        )
    
    token = authorization.replace("Bearer ", "")
    user = auth_manager.verify_token(token)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token. Please login again."
        )
    
    # Add student_id for convenience
    user["student_id"] = f"USER-{user['user_id'][:8]}"
    
    return user


# ============================================================================
# EXAMPLE: PROTECTED ENDPOINT
# ============================================================================

"""
Here's how to protect your existing endpoints:

BEFORE (no auth):
@app.get("/student/state")
async def get_state():
    state = get_student_state()
    return state

AFTER (with auth):
@app.get("/student/state")
async def get_state(user: Dict = Depends(require_auth)):
    # Now only authenticated users can access this
    # user["student_id"] contains their student profile ID
    state = pm.load(user["student_id"])
    return state
"""

# ============================================================================
# INSTRUCTIONS
# ============================================================================

"""
TO ADD THIS TO YOUR API_SERVER.PY:

1. Add this import at the top:
   from fastapi import Header, Depends

2. Add auth_manager initialization:
   auth_manager = AuthManager()

3. Copy all the @app.post and @app.get functions above

4. Add Depends to protect existing endpoints:
   @app.get("/student/state")
   async def get_state(user: Dict = Depends(require_auth)):
       student_id = user["student_id"]
       state = pm.load(student_id)
       return state

5. Test with:
   - POST /auth/signup - Create account
   - POST /auth/login - Get token
   - Use token in headers: Authorization: Bearer <token>
"""
