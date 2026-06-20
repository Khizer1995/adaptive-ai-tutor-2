"""
Supabase Authentication Module
Handles user signup, login, and session management.
"""

from typing import Dict, Any, Optional
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()


class AuthManager:
    """
    Manages user authentication using Supabase.
    
    Usage:
    ------
    auth = AuthManager()
    
    # Sign up
    result = auth.signup("user@example.com", "password123")
    
    # Login
    result = auth.login("user@example.com", "password123")
    
    # Verify token
    user = auth.verify_token(token)
    """
    
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError(
                "Missing Supabase credentials. "
                "Please set SUPABASE_URL and SUPABASE_KEY in .env file"
            )
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
    
    def signup(self, email: str, password: str, name: str = None) -> Dict[str, Any]:
        """
        Create a new user account.
        
        Args:
            email: User's email address
            password: User's password (min 6 characters)
            name: Optional display name
        
        Returns:
            Dict with 'success', 'user_id', 'token', or 'error'
        """
        try:
            # Sign up the user
            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "data": {
                        "name": name or email.split("@")[0]
                    }
                }
            })
            
            if response.user:
                return {
                    "success": True,
                    "user_id": response.user.id,
                    "email": response.user.email,
                    "token": response.session.access_token if response.session else None,
                    "message": "Account created successfully"
                }
            else:
                return {
                    "success": False,
                    "error": "Signup failed"
                }
                
        except Exception as e:
            error_msg = str(e)
            
            # Handle common errors
            if "already registered" in error_msg.lower():
                return {
                    "success": False,
                    "error": "Email already registered"
                }
            elif "password" in error_msg.lower():
                return {
                    "success": False,
                    "error": "Password must be at least 6 characters"
                }
            else:
                return {
                    "success": False,
                    "error": f"Signup error: {error_msg}"
                }
    
    def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Login an existing user.
        
        Args:
            email: User's email address
            password: User's password
        
        Returns:
            Dict with 'success', 'user_id', 'token', or 'error'
        """
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user and response.session:
                return {
                    "success": True,
                    "user_id": response.user.id,
                    "email": response.user.email,
                    "token": response.session.access_token,
                    "name": response.user.user_metadata.get("name", email.split("@")[0]),
                    "message": "Login successful"
                }
            else:
                return {
                    "success": False,
                    "error": "Login failed"
                }
                
        except Exception as e:
            error_msg = str(e)
            
            # Handle common errors
            if "invalid" in error_msg.lower() or "credentials" in error_msg.lower():
                return {
                    "success": False,
                    "error": "Invalid email or password"
                }
            else:
                return {
                    "success": False,
                    "error": f"Login error: {error_msg}"
                }
    
    def logout(self, token: str) -> Dict[str, Any]:
        """
        Logout user and invalidate token.
        
        Args:
            token: User's access token
        
        Returns:
            Dict with 'success' or 'error'
        """
        try:
            self.supabase.auth.sign_out()
            return {
                "success": True,
                "message": "Logged out successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Logout error: {str(e)}"
            }
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a JWT token and get user info.
        
        Args:
            token: JWT access token
        
        Returns:
            User dict if valid, None if invalid
        """
        try:
            user = self.supabase.auth.get_user(token)
            if user:
                return {
                    "user_id": user.user.id,
                    "email": user.user.email,
                    "name": user.user.user_metadata.get("name")
                }
            return None
        except:
            return None
    
    def get_user_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get full user details by token.
        
        Args:
            token: JWT access token
        
        Returns:
            User dict with all details or None
        """
        return self.verify_token(token)
    
    def reset_password_request(self, email: str) -> Dict[str, Any]:
        """
        Send password reset email.
        
        Args:
            email: User's email address
        
        Returns:
            Dict with 'success' or 'error'
        """
        try:
            self.supabase.auth.reset_password_email(email)
            return {
                "success": True,
                "message": "Password reset email sent"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error: {str(e)}"
            }


# Quick test
if __name__ == "__main__":
    auth = AuthManager()
    print("✅ AuthManager initialized successfully")
    print(f"Connected to: {os.getenv('SUPABASE_URL')}")
