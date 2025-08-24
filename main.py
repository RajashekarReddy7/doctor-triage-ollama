from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt
import motor.motor_asyncio
import os, time
from datetime import datetime, timedelta

from doctor_agent import doctor_reply
from symptom_extractor import extract_structured
from triage_engine import evaluate_triage
from guideline_verifier import verify
from utils import log_session, APP_PORT

# ---------------------------
# Setup
# ---------------------------
app = FastAPI()
SESSIONS = {}
app.mount("/static", StaticFiles(directory="static"), name="static")

# Load .env file
from dotenv import load_dotenv
load_dotenv()

# MongoDB Atlas connection
MONGO_URL = os.getenv("MONGO_URL")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client["carecompanion"]
users = db["users"]


# JWT + Password hashing
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await users.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------------------------
# Models
# ---------------------------
class User(BaseModel):
    email: str
    password: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

# ---------------------------
# Routes
# ---------------------------
@app.post("/register")
async def register(user: User):
    if await users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_pw = hash_password(user.password)
    await users.insert_one({"email": user.email, "password": hashed_pw})
    return {"message": "User registered successfully"}

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await users.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user["email"]})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/")
def serve_home():
    return FileResponse(os.path.join("static", "login.html"))  # redirect to login first

@app.get("/chat")
def serve_chat():
    return FileResponse(os.path.join("static", "index.html"))

@app.post("/api/chat")
async def chat(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    # same chatbot logic you already have
    sid = req.session_id
    if sid not in SESSIONS:
        SESSIONS[sid] = []
    SESSIONS[sid].append({"role": "user", "content": req.message})

    # Doctor agent reply
    reply = doctor_reply(SESSIONS[sid])
    SESSIONS[sid].append({"role": "assistant", "content": reply})

    # Extract structured data
    conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in SESSIONS[sid]])
    structured = extract_structured(conv_text)
    raw_triage = evaluate_triage(structured)

    top_diagnoses = []  
    verified = verify(raw_triage, top_diagnoses)

    # Urgent/Emergency handling
    if verified["level"] in ("Emergency", "Urgent"):
        context = (
            f"{verified['level']} — {verified['reason']}. Recommended action: "
            f"{'go to the nearest emergency department immediately' if verified['level']=='Emergency' else 'seek urgent medical attention'}."
        )
        final = doctor_reply(SESSIONS[sid], triage_context=context)
        SESSIONS[sid].append({"role": "assistant", "content": final})
        out_reply = final
    else:
        out_reply = reply

    # Log session
    log_session(sid, {
        "session": SESSIONS[sid],
        "structured": structured,
        "triage": verified,
        "ts": time.time()
    })

    return {"reply": out_reply, "triage": verified, "structured": structured}
