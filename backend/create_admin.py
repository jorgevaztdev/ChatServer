"""One-shot script: create or promote a user to admin."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.models.base import SessionLocal, init_db
from src.models.user import User
from src.services.auth import hash_password


def create_or_promote(email: str, username: str, password: str) -> None:
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.is_admin = True
            print(f"Promoted existing user '{user.username}' ({email}) to admin.")
        else:
            user = User(
                email=email,
                username=username,
                password_hash=hash_password(password),
                is_admin=True,
            )
            db.add(user)
            print(f"Created admin user '{username}' ({email}).")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    create_or_promote(
        email="glitch@test.com",
        username="glitch",
        password="test1234",
    )
