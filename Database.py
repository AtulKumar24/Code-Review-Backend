from bson import ObjectId
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import bcrypt
import os
import datetime
import base64
import pytz
from Models import User , CodeReviewResult, UserOut


load_dotenv()

uri = os.getenv("MONGODB_URI")
client = MongoClient(uri, server_api=ServerApi('1'))

try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)
    

db = client['User_Data']
users_collection = db['users']
code_reviews_collection = db['code_reviews']
refresh_tokens = db["refresh_tokens"]
otp_collection = db["otps"]

def create_user(user_data : dict):
    hashed_password = bcrypt.hashpw(user_data["password"].encode(), bcrypt.gensalt()).decode()
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.datetime.now(ist)
    
    user_data["password"] =  hashed_password
    user_data["created_at"] = now_ist
    photo = user_data.get("photo")
    
    if not photo:
        user_data["photo"] = None
        
    user = User(**user_data)
    
    result = users_collection.insert_one(user.dict())
    print("User created with id:", result.inserted_id)
    return str(result.inserted_id)

def update_user(email: str, update_data: dict):
    data = {}


    if "photo" in update_data and update_data["photo"] is not None:
        data["photo"] = update_data["photo"]

    if "username" in update_data:
        data["username"] = update_data["username"]
        
    if not data:
        return 0 

    # Always update timestamp
    ist = pytz.timezone("Asia/Kolkata")
    data["updated_at"] = datetime.datetime.now(ist)

    result = users_collection.update_one(
        {"email": email},
        {"$set": data}
    )

    return result.modified_count


def delete_user(email):
    result = users_collection.delete_one({"email": email})
    return result.deleted_count

def get_user(email):
    email = normalize_email(email)
    user = users_collection.find_one({"email": email})
    if user:
        # Convert MongoDB ObjectId to string
        if "_id" in user and isinstance(user["_id"], ObjectId):
            user["_id"] = str(user["_id"])
        if not user.get("photo"):
            user["photo"] = None

        return User(**user)
    return None

def change_user_password(email: str, new_password: str):
    result = users_collection.update_one(
        {"email": email},
        {"$set": {"password": new_password,
                  "updated_at": datetime.datetime.utcnow()}}
    )
    return result.modified_count

def store_review(code_review_data: dict):
    # Validate using correct output model
    review = CodeReviewResult(**code_review_data)

    # Prepare mongo-safe dict
    review_dict = review.dict()

    result = code_reviews_collection.insert_one(review_dict)
    print("Code review stored with id:", result.inserted_id)

    return str(result.inserted_id)
    
def store_img_review(metadata: dict):
    final_dict = CodeReviewResult(**metadata)
    data = final_dict.dict()
    result = db['images'].insert_one(data)
    print("Image stored with id:", result.inserted_id)
    return str(result.inserted_id)

def get_all_users():
    users_cursor = users_collection.find()
    users_list = []
    
    for user in users_cursor:
        # Convert ObjectId to string
        if "_id" in user and isinstance(user["_id"], ObjectId):
            user["_id"] = str(user["_id"])
        
        # Decode photo if exists
        if not user.get("photo"):
            user["photo"] = None

        try:
            users_list.append(User(**user))
        except Exception as e:
            print(f"Skipping a user due to validation error: {e}")
    
    return users_list

def store_refresh_token(email: str, token: str):
    
    refresh_tokens.insert_one({
        "email": email,
        "token": token,
        "created_at": datetime.datetime.utcnow(),
        "expires_at": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    })

def is_valid_refresh_token(email: str, token: str) -> bool:
    token_entry = refresh_tokens.find_one({
        "email": email,
        "token": token,
        "expires_at": {"$gt": datetime.datetime.utcnow()}
    })
    return token_entry is not None

def delete_refresh_token(email: str):
    result = refresh_tokens.delete_one({
        "email": email,
    })
    return result.deleted_count

def delete_all_refresh_tokens(email: str):
    email = normalize_email(email)
    refresh_tokens.delete_many({"email": email})
    
def upsert_refresh_token(email: str, token: str):
    email = normalize_email(email)
    refresh_tokens.update_one(
        {"email": email},
        {"$set": {
            "email": email,
            "token": token,
            "created_at": datetime.datetime.utcnow(),
            "expires_at": datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }},
        upsert=True
    )

def store_otp(email: str, otp: str):
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.datetime.now(ist)
    expiry_time = now_ist + datetime.timedelta(minutes=10)
    email = normalize_email(email)

    otp_collection.update_one(
        {"email": email},
        {"$set": {
            "email": email,
            "otp": otp,
            'attempt': 0,
            "expires_at": expiry_time
    }}
    , upsert=True
    )

def verify_otp(email: str, otp: str) -> bool:
    email = normalize_email(email)
    record = otp_collection.find_one({"email": email})
    if not record:
        return False
    if record["expires_at"] < datetime.datetime.now(pytz.timezone('Asia/Kolkata')):
        return False
    if record["attempt"] >= 5:
        return False
    if not bcrypt.checkpw(otp.encode(), record["otp"].encode()):
        otp_collection.update_one(
            {"email": email},
            {"$inc": {"attempt": 1}}
        )
        return False
    return True

def delete_otp(email: str):
    result = otp_collection.delete_one({
        "email": email,
    })
    return result.deleted_count

def normalize_email(email: str) -> str:
    return email.strip().lower()