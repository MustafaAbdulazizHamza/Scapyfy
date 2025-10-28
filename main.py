from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import get_db, engine
from models import Base, User
from hashing import hash_password
from routers import user, login, crafter

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI application
app = FastAPI(
    title="Scapyfy",
    description="Secure LLM agent that does the packet crafting tasks on behalf of you.",
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

# Include routers
app.include_router(login.router)
app.include_router(user.router)
app.include_router(crafter.router)

@app.on_event("startup")
async def startup_event():
    """Initialize admin user"""
    db = next(get_db())
    try:
        # Check if admin user exists
        admin_user = db.query(User).filter(User.id == 0).first()
        if not admin_user:
            # Create admin user with ID 0
            admin_user = User(
                id=0,
                username="root",
                email="root@email.local",
                hashed_password=hash_password("root"),
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print("✅ Admin user created:")
            print("   Username: root")
            print("   Password: root")
            print("⚠️  SECURITY: Change password immediately!")
        else:
            print("ℹ️  Admin user already exists")
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
    finally:
        db.close()

@app.get("/")
def root():
    """API root endpoint"""
    return {
        "message": "Scapyfy - AI-Powered Packet Crafter",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)