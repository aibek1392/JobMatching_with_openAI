from app.db.session import init_db
from app.db.base import Base
from app.models import models  # This imports all models to ensure they're registered with Base

def init():
    print("Creating database tables...")
    init_db()
    print("Database tables created successfully!")

if __name__ == "__main__":
    init()
