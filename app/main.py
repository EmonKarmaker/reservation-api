from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.chat.router import router as chat_router
from app.api.v1.voice.router import router as voice_router
from app.api.v1.admin.auth import router as admin_auth_router
from app.api.v1.admin.businesses import router as admin_businesses_router
from app.api.v1.admin.services import router as admin_services_router

app = FastAPI(
    title="AI Booking System",
    description="LangGraph-powered booking chatbot with voice support and admin dashboard",
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
app.include_router(chat_router, prefix="/api/v1", tags=["Chat"])
app.include_router(voice_router, prefix="/api/v1/voice", tags=["Voice"])
app.include_router(admin_auth_router, prefix="/api/v1/admin/auth", tags=["Admin Auth"])
app.include_router(admin_businesses_router, prefix="/api/v1/admin/businesses", tags=["Admin Businesses"])
app.include_router(admin_services_router, prefix="/api/v1/admin", tags=["Admin Services"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}