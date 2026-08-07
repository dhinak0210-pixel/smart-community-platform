#!/usr/bin/env python3
"""
Seed Smart Community Platform with demo data.
Use for: development, demos, testing UI.
DO NOT run in production.

Usage: python scripts/seed_data.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.database import SessionLocal
from backend.models.user import User, UserRole
from backend.models.issue import (
    Issue, IssueCategory, IssueStatus, IssuePriority,
    Comment, CommentType, Vote, VoteType
)
from backend.utils.auth import hash_password
from datetime import datetime, timedelta
import random

DEMO_PASSWORD = "DemoPass123!"


def seed_users(db) -> dict:
    """Create demo users of each role idempotently"""
    from sqlalchemy import select
    users = {}

    for i in range(5):
        email = f"citizen{i+1}@demo.com"
        if not db.execute(select(User).where(User.email == email)).scalar_one_or_none():
            user = User(
                name=f"Citizen User {i+1}",
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                role=UserRole.CITIZEN,
                is_active=True,
                is_verified=True,
                location_city="Riyadh",
                location_area=random.choice(["Downtown", "North", "South", "East", "West"]),
                reputation_score=random.uniform(10, 100),
                total_issues_reported=random.randint(1, 10)
            )
            db.add(user)

    for dept in ["Roads", "Waste", "Safety", "Utilities"]:
        email = f"{dept.lower()}@municipality.demo"
        if not db.execute(select(User).where(User.email == email)).scalar_one_or_none():
            user = User(
                name=f"{dept} Authority",
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                role=UserRole.AUTHORITY,
                is_active=True,
                is_verified=True,
                location_city="Riyadh"
            )
            db.add(user)

    if not db.execute(select(User).where(User.email == "admin@demo.com")).scalar_one_or_none():
        admin = User(
            name="Platform Admin",
            email="admin@demo.com",
            password_hash=hash_password(DEMO_PASSWORD),
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True
        )
        db.add(admin)

    if not db.execute(select(User).where(User.email == "volunteer@demo.com")).scalar_one_or_none():
        volunteer = User(
            name="Active Volunteer",
            email="volunteer@demo.com",
            password_hash=hash_password(DEMO_PASSWORD),
            role=UserRole.VOLUNTEER,
            is_active=True,
            is_verified=True,
            location_city="Riyadh",
            location_area="Downtown"
        )
        db.add(volunteer)

    db.commit()
    print(f"✅ Verified / Created demo users (password: {DEMO_PASSWORD})")
    return users


DEMO_ISSUES = [
    {
        "title": "Large pothole on King Fahd Road",
        "description": "There is a very large and deep pothole on King Fahd Road near the Al Olaya exit. It has been there for 3 weeks and has already damaged multiple vehicles. Urgent attention required from road maintenance.",
        "category": IssueCategory.INFRASTRUCTURE,
        "status": IssueStatus.IN_PROGRESS,
        "priority": IssuePriority.HIGH,
        "lat": 24.6877,
        "lng": 46.7219,
        "city": "Riyadh",
        "area": "Olaya",
        "votes": 23,
        "address": "King Fahd Road, Al Olaya"
    },
    {
        "title": "Illegal garbage dumping near park",
        "description": "Someone has been dumping large bags of garbage and construction waste near the community park entrance. The smell is terrible and it is attracting flies and rodents. Children play in this area.",
        "category": IssueCategory.WASTE,
        "status": IssueStatus.REPORTED,
        "priority": IssuePriority.MEDIUM,
        "lat": 24.7136,
        "lng": 46.6753,
        "city": "Riyadh",
        "area": "Downtown",
        "votes": 15,
        "address": "Central Park, Downtown Riyadh"
    },
    {
        "title": "Street flooding after rain",
        "description": "The main intersection at Abdullah Al Sudairi Street floods every time it rains. The drainage system appears to be blocked. Last week the water was knee-deep and several cars got stuck.",
        "category": IssueCategory.FLOODING,
        "status": IssueStatus.ACKNOWLEDGED,
        "priority": IssuePriority.CRITICAL,
        "lat": 24.7500,
        "lng": 46.6500,
        "city": "Riyadh",
        "area": "North",
        "votes": 45,
        "address": "Abdullah Al Sudairi Street"
    },
    {
        "title": "Broken traffic signal at busy junction",
        "description": "The traffic light at the junction of Prince Mohammed bin Abdulaziz Road and Tahlia Street has been broken for 4 days. Traffic is chaotic and there have been 2 minor accidents already.",
        "category": IssueCategory.TRAFFIC,
        "status": IssueStatus.ASSIGNED,
        "priority": IssuePriority.CRITICAL,
        "lat": 24.7000,
        "lng": 46.7000,
        "city": "Riyadh",
        "area": "Tahlia",
        "votes": 67,
        "address": "Prince Mohammed Rd & Tahlia St Junction"
    },
    {
        "title": "Street lights out on residential street",
        "description": "All 6 street lights on Al Imam Abdullah Ibn Saud Ibn Abdulaziz Road are not working. The street is completely dark from 7pm. This is a residential area with families and children.",
        "category": IssueCategory.UTILITIES,
        "status": IssueStatus.RESOLVED,
        "priority": IssuePriority.MEDIUM,
        "lat": 24.6500,
        "lng": 46.7100,
        "city": "Riyadh",
        "area": "South",
        "votes": 12,
        "address": "Al Imam Abdullah Ibn Saud Road"
    },
    {
        "title": "Tree blocking road after storm",
        "description": "A large tree has fallen across Al Urubah Road blocking half of the road after last night's storm. Emergency vehicles cannot pass properly. Needs immediate removal by municipality.",
        "category": IssueCategory.ENVIRONMENT,
        "status": IssueStatus.IN_PROGRESS,
        "priority": IssuePriority.HIGH,
        "lat": 24.7300,
        "lng": 46.6800,
        "city": "Riyadh",
        "area": "East",
        "votes": 31,
        "address": "Al Urubah Road, Eastern District"
    },
    {
        "title": "Construction noise at night",
        "description": "The construction site on Olaya Street has been working until 3am every night for the past 2 weeks. The noise is unbearable and is affecting the entire neighborhood's sleep and wellbeing.",
        "category": IssueCategory.NOISE,
        "status": IssueStatus.UNDER_REVIEW,
        "priority": IssuePriority.MEDIUM,
        "lat": 24.6900,
        "lng": 46.6900,
        "city": "Riyadh",
        "area": "Olaya",
        "votes": 8,
        "address": "Olaya Street Construction Site"
    },
    {
        "title": "Dangerous abandoned building",
        "description": "There is an abandoned multi-story building on Prince Sultan Road with broken windows and exposed electrical wires. Children have been seen playing near it. The structure looks unstable and dangerous.",
        "category": IssueCategory.SAFETY,
        "status": IssueStatus.ACKNOWLEDGED,
        "priority": IssuePriority.CRITICAL,
        "lat": 24.7200,
        "lng": 46.6600,
        "city": "Riyadh",
        "area": "West",
        "votes": 52,
        "address": "Prince Sultan Road, West District"
    }
]


def seed_issues(db) -> list:
    """Create demo issues"""
    from sqlalchemy import select
    citizen = db.execute(
        select(User).where(User.email == "citizen1@demo.com")
    ).scalar_one()

    created_issues = []
    for issue_data in DEMO_ISSUES:
        days_ago = random.randint(1, 30)
        issue = Issue(
            title=issue_data["title"],
            description=issue_data["description"],
            short_description=issue_data["description"][:300],
            category=issue_data["category"],
            status=issue_data["status"],
            priority=issue_data["priority"],
            location_lat=issue_data["lat"],
            location_lng=issue_data["lng"],
            location_address=issue_data["address"],
            location_city=issue_data["city"],
            location_area=issue_data["area"],
            reporter_id=citizen.id,
            ai_processed=True,
            vote_count=issue_data["votes"],
            comment_count=random.randint(1, 8),
            view_count=random.randint(50, 500),
            created_at=datetime.utcnow() - timedelta(days=days_ago),
            ai_tags=[issue_data["category"].value, issue_data["area"].lower()]
        )
        db.add(issue)
        created_issues.append(issue)

    db.commit()
    print(f"✅ Created {len(created_issues)} demo issues")
    return created_issues


def seed_comments(db, issues: list):
    """Add demo comments to issues"""
    from sqlalchemy import select
    citizen = db.execute(
        select(User).where(User.email == "citizen1@demo.com")
    ).scalar_one()
    authority = db.execute(
        select(User).where(User.email == "roads@municipality.demo")
    ).scalar_one()

    for issue in issues[:5]:
        citizen_comment = Comment(
            issue_id=issue.id,
            user_id=citizen.id,
            content=f"I can confirm this issue. Seen it myself near {issue.location_area}. Hope it gets resolved soon.",
            comment_type=CommentType.CITIZEN_COMMENT,
            created_at=issue.created_at + timedelta(hours=2)
        )
        db.add(citizen_comment)

        if issue.status != IssueStatus.REPORTED:
            auth_comment = Comment(
                issue_id=issue.id,
                user_id=authority.id,
                content="Our team has assessed the situation and is taking appropriate action. We appreciate your patience and civic engagement.",
                comment_type=CommentType.AUTHORITY_UPDATE,
                is_pinned=True,
                created_at=issue.created_at + timedelta(days=1)
            )
            db.add(auth_comment)

    db.commit()
    print("✅ Created demo comments")


def main():
    print("\n════════════════════════════════════════")
    print("  Smart Community Platform - Seed Data")
    print("  WARNING: Only for development/demo!")
    print("════════════════════════════════════════\n")

    confirm = input("Continue? This will add demo data. (yes/no): ")
    if confirm.lower() != "yes":
        print("Aborted.")
        sys.exit(0)

    db = SessionLocal()
    try:
        seed_users(db)
        issues = seed_issues(db)
        seed_comments(db, issues)

        print("\n✅ Seed data created successfully!")
        print("\nDemo accounts (password: DemoPass123!):")
        print("  citizen1@demo.com → Citizen")
        print("  roads@municipality.demo → Authority")
        print("  admin@demo.com → Admin")
        print("  volunteer@demo.com → Volunteer")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
