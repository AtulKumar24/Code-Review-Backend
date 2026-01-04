import base64
import datetime
from argon2 import hash_password
import bcrypt
from bson import ObjectId
from fastapi import Depends, FastAPI, HTTPException, BackgroundTasks, File , UploadFile , Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from Database import change_user_password, create_user, delete_all_refresh_tokens, delete_otp, get_user, store_otp, store_review, update_user, delete_user, upsert_refresh_token,users_collection, get_all_users, refresh_tokens , is_valid_refresh_token , store_refresh_token, delete_refresh_token, verify_otp
from auth import create_access_token, create_otp, create_refresh_token, get_current_user, hash_OTP, normalize_email, verify_password, decode_refresh_token
import Image_LLM
from Models import CodeReviewRequest, ImageCodeReviewRequest, ImageReview, RefreshRequest, User, CodeReviewResult , LoginRequest, TokenResponse, UserCreate, UserCreate, UserOut, UserUpdate , ForgotPasswordRequest , ResetPasswordRequest
import uvicorn
from LLM import code_review
from email_service import send_email
import uuid, os, shutil



app = FastAPI(
    title="Code Review",
    description="Backend API for Code Review managing users and issues.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get('/')
async def root():
    return {"message": "Welcome to the CodeReview Backend API"}

@app.get("/endpoints")
async def get_endpoints():
    return {
        "endpoints": {
            "/" : "Root endpoint",
            "/endpoints" : "List all endpoints",
            "/test" : "Test endpoint",
            "/auth/register" : "Register a new user",
            "/auth/login" : "Login a user",
            "/auth/refresh" : "Refresh access token",
            "/auth/profile" : "View user profile",
            "/auth/logout" : "Logout a user",
            "/users" : "List all users",
            "/users/changedata" : "Update user data",
            "/users/delete" : "Delete a user"
        }
    }

@app.get("/test")
async def test():
    return {"message": "API is working!"}


@app.post("/auth/register", response_model=UserOut , status_code=201)
async def create_new_user(username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    photo: UploadFile | None = File(None),):
    
    email = email.strip().lower()
    print("PHOTO RECEIVED:", photo)
    print("FILENAME:", photo.filename if photo else None)
    print(f"DEBUG: Processing {email}, photo included: {photo is not None}")
    
    if get_user(email):
        raise HTTPException(status_code=409, detail="User with this email already exists")
    
    photo_url = None
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "heic"}
    ALLOWED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/heic",
        "image/heif",
    }
    
    if photo:
        # 1️⃣ filename must exist
        if not photo.filename:
            raise HTTPException(status_code=400, detail="Invalid file")

        # 2️⃣ validate extension (PRIMARY)
        ext = photo.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Invalid image format")

        # 3️⃣ validate mime type (SECONDARY, only if provided)
        if photo.content_type and photo.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=400, detail="Invalid image format")

        # 4️⃣ save file
        filename = f"{uuid.uuid4()}.{ext}"
        upload_dir = "uploads/profile"
        os.makedirs(upload_dir, exist_ok=True)

        with open(os.path.join(upload_dir, filename), "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)

        photo_url = f"/uploads/profile/{filename}"
        

    user_data = {
        "username": username,
        "email": email,
        "password": password,
        "photo": photo_url,  # can be None
    }

    create_user(user_data)

    created_user = get_user(email)
    if created_user:
        return created_user

    raise HTTPException(status_code=400, detail="User creation failed")
    
@app.post('/auth/login',response_model=TokenResponse, status_code=200)
async def login_user(login_request: LoginRequest):
    email = login_request.email.strip().lower()
    user = get_user(email)
    if not user or not verify_password(login_request.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(
        {"sub": user.email},
        expires_minutes= 15
    )

    refresh_token = create_refresh_token(
        {"sub": user.email},
        expires_days=7
    )
    upsert_refresh_token(user.email, refresh_token)
    return {
    "access_token": access_token,
    "refresh_token": refresh_token,
    "token_type": "bearer"
    }

@app.post("/auth/refresh")
async def refresh_access_token(data: RefreshRequest):

    # 1️⃣ Decode & validate refresh token 
    unemail = decode_refresh_token(data.refresh_token)
    email = normalize_email(unemail)
    
    # 2️⃣ Check token exists in DB (not revoked)
    if not is_valid_refresh_token(email, data.refresh_token):
        raise HTTPException(status_code=401, detail="Token revoked")

    # 3️⃣ Issue new access token
    new_access_token = create_access_token(
        {"sub": email},
        expires_minutes=15
    )
    new_refresh_token = create_refresh_token(
        {"sub": email},
        expires_days=7
    )
    
    upsert_refresh_token(email, new_refresh_token)

    return {
        "access_token": new_access_token,
         "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }


@app.get('/auth/profile', response_model=UserOut)
async def read_user_profile(current_user = Depends(get_current_user)):
    return current_user

@app.post("/auth/logout")
async def logout(current_user = Depends(get_current_user)):
    refresh_tokens.delete_many({"email": normalize_email(current_user.email)})
    return {"message": "Logged out successfully"}


@app.get("/users", response_model=list[User])
async def read_users():
    return get_all_users()

@app.put("/users/changedata", response_model=UserOut)
async def update_profile(
    updates: UserUpdate,
    current_user = Depends(get_current_user)
):
    updated = update_user(normalize_email(current_user.email), updates.dict(exclude_unset=True))

    if updated == 0:
        raise HTTPException(status_code=400, detail="Nothing updated")
    user = get_user(normalize_email(current_user.email))
    return user

@app.put("/users/forgot-password", status_code=200)
async def forget_password(data : ForgotPasswordRequest):
    email = normalize_email(data.email)
    user = get_user(email)
    
    if not user:
        return {"message": "If email exists, OTP sent"}
    
    reset_otp = create_otp()
    
    delete_otp(data.email)
    
    hash_otp = hash_OTP(reset_otp)
    
    store_otp(user.email, hash_otp)
    
    sent = send_email(user.email, reset_otp)
    
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send reset email")
    
    return {"message": "If email exists, OTP sent"}

@app.put("/users/reset-password", status_code=200)
async def reset_password(data : ResetPasswordRequest):
    
    email = normalize_email(data.email)
    
    record = verify_otp(email, data.otp)
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    hashed_password = bcrypt.hashpw(
        data.new_password.encode(),
        bcrypt.gensalt()
    ).decode()
    
    change_user_password(email, hashed_password)
    
    delete_otp(email)
    
    delete_all_refresh_tokens(email)
    
    return "Password reset successfully"

@app.delete("/users/delete", status_code=200)
async def delete_existing_user(current_user = Depends(get_current_user)):

    deleted_count = delete_user(current_user.email)
    delete_all_refresh_tokens(current_user.email)

    if deleted_count:
        return {
            "message": f"User with email '{current_user.email}' deleted successfully",
            "deleted_count": deleted_count
        }

    raise HTTPException(status_code=404, detail=f"User with email '{current_user.email}' not found")

@app.delete("/users/delete-photo", response_model=UserOut)
async def delete_profile_photo(current_user = Depends(get_current_user)):
    if current_user.photo:
        path = current_user.photo.lstrip("/")
        if os.path.exists(path):
            os.remove(path)

    update_user(current_user.email, {"photo": None})
    return get_user(current_user.email)

@app.put("/users/update-photo", response_model=UserOut)
async def update_profile_photo(
    photo: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "heic"}
    ALLOWED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/heic",
        "image/heif",
    }

    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

    contents = await photo.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="Image too large")

    photo.file.seek(0)
    
    # 1️⃣ filename must exist
    if not photo.filename:
        raise HTTPException(status_code=400, detail="Invalid file")

    # 2️⃣ validate extension (PRIMARY)
    ext = photo.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid image format")

    # 3️⃣ validate mime type (SECONDARY, only if provided)
    if photo.content_type and photo.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid image format")

    # 4️⃣ save file
    filename = f"{uuid.uuid4()}.{ext}"
    upload_dir = "uploads/profile"
    os.makedirs(upload_dir, exist_ok=True)

    with open(os.path.join(upload_dir, filename), "wb") as buffer:
        shutil.copyfileobj(photo.file, buffer)

    photo_url = f"/uploads/profile/{filename}"

    updated = update_user(
        normalize_email(current_user.email),
        {"photo": photo_url}
    )

    if updated == 0:
        raise HTTPException(status_code=400, detail="Photo not updated")

    user = get_user(normalize_email(current_user.email))
    return user


@app.post("/code-review/" , response_model=CodeReviewResult)
async def code_review_endpoint(payload: CodeReviewRequest , background_tasks: BackgroundTasks , current_user = Depends(get_current_user)):
    try:
        uid = str(current_user.id)
        review_result = code_review(
            user_id=uid,
            code=payload.code,
            language=payload.language,
        )
        background_tasks.add_task(store_review, review_result)
        return review_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/image-code-review/",response_model=CodeReviewResult)
async def image_code_review_endpoint(
    background_tasks : BackgroundTasks , 
    current_user  = Depends(get_current_user),
    photo : UploadFile = File(...),
):


    photo_url = None
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "heic"}
    ALLOWED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/heic",
        "image/heif",
    }
    
    try:
        if photo:
            # 1️⃣ filename must exist
            if not photo.filename:
                raise HTTPException(status_code=400, detail="Invalid file")

            # 2️⃣ validate extension (PRIMARY)
            ext = photo.filename.rsplit(".", 1)[-1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=400, detail="Invalid image format")

            # 3️⃣ validate mime type (SECONDARY, only if provided)
            if photo.content_type and photo.content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(status_code=400, detail="Invalid image format")

            # 4️⃣ save file
            filename = f"{uuid.uuid4()}.{ext}"
            upload_dir = "uploads/codereview"
            os.makedirs(upload_dir, exist_ok=True)

            with open(os.path.join(upload_dir, filename), "wb") as buffer:
                shutil.copyfileobj(photo.file, buffer)

            photo_url = f"/uploads/codereview/{filename}"
            image_result = Image_LLM.img_code(user_id=str(current_user.id), img_path=photo_url)  # returns ImageReview dict
            # store only the review (not the whole ImageReview) because store_review expects CodeReviewResult
            review_only = image_result.get("review")
            if isinstance(review_only, dict):  # Ensure review_only is a dictionary
                background_tasks.add_task(store_review, review_only)
            return image_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/uploads/")
async def get_uploaded_file():
    return {"message": "Use /uploads/<file_path> to access files."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=5600,
        reload=True,
        log_level="info"
    )
        

