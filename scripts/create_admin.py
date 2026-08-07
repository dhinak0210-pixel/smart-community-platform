#!/usr/bin/env python3
"""
Create the first admin user for Smart Community Platform.
Run this ONCE after first deployment.

Usage:
  python scripts/create_admin.py
  
Or with arguments:
  python scripts/create_admin.py --email admin@city.gov --name "City Admin"
"""

import sys
import os
import argparse
from getpass import getpass

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.database import SessionLocal
from backend.models.user import User, UserRole
from backend.utils.auth import hash_password, validate_password_strength
from datetime import datetime


def create_admin_user(name: str, email: str, password: str) -> User:
    """Create admin user in database"""

    db = SessionLocal()
    try:
        from sqlalchemy import select
        existing = db.execute(
            select(User).where(User.email == email.lower())
        ).scalar_one_or_none()

        if existing:
            if existing.role == UserRole.ADMIN or existing.role == UserRole.ADMIN.value:
                print(f"✅ Admin user already exists: {email}")
                return existing
            else:
                print(f"⚠️  User exists with role '{existing.role}'")
                upgrade = input("Upgrade to admin? (yes/no): ")
                if upgrade.lower() == "yes":
                    existing.role = UserRole.ADMIN
                    db.commit()
                    print(f"✅ User upgraded to admin: {email}")
                    return existing
                else:
                    print("Aborted.")
                    sys.exit(0)

        admin = User(
            name=name,
            email=email.lower(),
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
            created_at=datetime.utcnow()
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(f"\n✅ Admin user created successfully!")
        print(f"   Name: {admin.name}")
        print(f"   Email: {admin.email}")
        print(f"   UUID: {admin.uuid}")
        print(f"   Role: {admin.role.value if hasattr(admin.role, 'value') else admin.role}")
        print(f"\n   Login at: /api/auth/login")
        print(f"   Dashboard: /dashboard.html\n")

        return admin

    except Exception as e:
        db.rollback()
        print(f"\n❌ Failed to create admin: {e}")
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Create admin user for Smart Community Platform"
    )
    parser.add_argument("--name", help="Admin user full name")
    parser.add_argument("--email", help="Admin user email")
    parser.add_argument("--password", help="Admin password (or prompted)")
    args = parser.parse_args()

    print("\n════════════════════════════════════════")
    print("  Smart Community Platform - Create Admin")
    print("════════════════════════════════════════\n")

    name = args.name or input("Admin full name: ").strip()
    if not name:
        print("❌ Name is required")
        sys.exit(1)

    email = args.email or input("Admin email: ").strip()
    if not email or "@" not in email:
        print("❌ Valid email is required")
        sys.exit(1)

    if args.password:
        password = args.password
    else:
        password = getpass("Admin password: ")
        confirm = getpass("Confirm password: ")
        if password != confirm:
            print("❌ Passwords do not match")
            sys.exit(1)

    strength = validate_password_strength(password)
    if not strength["valid"]:
        print(f"❌ Weak password: {', '.join(strength['errors'])}")
        sys.exit(1)

    create_admin_user(name, email, password)


if __name__ == "__main__":
    main()
