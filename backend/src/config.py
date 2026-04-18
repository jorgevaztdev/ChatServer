import os

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:////data/chat.db")
MEDIA_DIR: str = os.getenv("MEDIA_DIR", "/media")
JWT_SECRET: str = os.getenv("JWT_SECRET", "changeme-in-production")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
