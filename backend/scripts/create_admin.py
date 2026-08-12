import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pharma_management.db import SessionLocal
from pharma_management.models import User, UserRole
from pharma_management.security import hash_password


if __name__ == "__main__":
    email = input("Admin email: ").strip()
    name = input("Admin name: ").strip()
    password = input("Admin password (12+ chars): ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    with SessionLocal() as db:
        if db.query(User).filter(User.email == email).first():
            raise SystemExit("User already exists")
        db.add(User(email=email, full_name=name, password_hash=hash_password(password), role=UserRole.SUPER_ADMIN))
        db.commit()
    print("Super-admin created.")
