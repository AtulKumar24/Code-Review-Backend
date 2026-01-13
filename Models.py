from symtable import Class
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from bson import ObjectId
from pydantic import ConfigDict

class User(BaseModel):
    id : Optional[str] = Field(None, alias="_id")
    username: str
    password: str
    email: EmailStr
    photo: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={ObjectId: str}
        )

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    
    

class UserOut(BaseModel):
    id: str
    username: str
    email: EmailStr
    photo: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None

class CodeReviewRequest(BaseModel):
    code: str
    language: str | None = None

class Issue(BaseModel):
    id: str
    line: int
    severity: str
    category: str
    title: str
    explanation: str
    suggestedFix: str

class Summary(BaseModel):
    issueCount: int
    criticalCount: int
    warningCount: int

class CodeReviewResult(BaseModel):
    summary: Summary
    issues: List[Issue]
    codeLength: int
    codeLanguage: str
    suggestions: List[str]
    issues_found: int = Field(..., alias="issuesFound")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    raw_code: str
    user_id: str
    improved_code: Optional[str] = None
    
    model_config = ConfigDict(
        populate_by_name=True, # This allows you to pass 'issues_found' or 'issuesFound'
        from_attributes=True
    )

class ImageReview(BaseModel):
    image_path: str
    review: CodeReviewResult | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ImageCodeReviewRequest(BaseModel):
    img_path: str   
    
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserUpdate(BaseModel):
    username: Optional[str] = None
    photo: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email : str
    otp: str
    new_password: str

class RefreshRequest(BaseModel):
    refresh_token: str
    
class Example(BaseModel):
    input: CodeReviewRequest
    output: CodeReviewResult