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
        "title": "Severe Pothole & Road Damage on Anna Salai (Mount Road)",
        "description": "Deep road erosion and pothole near Mount Road Metro station causing severe traffic bottlenecks and safety risk for two-wheelers. Immediate repair required from Greater Chennai Corporation.",
        "category": IssueCategory.INFRASTRUCTURE,
        "status": IssueStatus.IN_PROGRESS,
        "priority": IssuePriority.HIGH,
        "lat": 13.0604,
        "lng": 80.2496,
        "city": "Chennai",
        "area": "Anna Salai",
        "votes": 43,
        "address": "Anna Salai, Mount Road, Chennai"
    },
    {
        "title": "Stormwater Drain Waterlogging in T. Nagar",
        "description": "Monsoon rainwater accumulation on Usman Road near Ranganathan Street due to clogged stormwater drains. Pedestrians unable to cross shop fronts.",
        "category": IssueCategory.FLOODING,
        "status": IssueStatus.REPORTED,
        "priority": IssuePriority.HIGH,
        "lat": 13.0418,
        "lng": 80.2341,
        "city": "Chennai",
        "area": "T. Nagar",
        "votes": 35,
        "address": "Usman Road, T. Nagar, Chennai"
    },
    {
        "title": "Broken Streetlights on OMR IT Corridor (Kandanchavadi)",
        "description": "All 12 streetlights from Kandanchavadi junction to Perungudi on Rajiv Gandhi Salai (OMR) are inactive after nightfall, creating unsafe conditions for night shift workers.",
        "category": IssueCategory.UTILITIES,
        "status": IssueStatus.ACKNOWLEDGED,
        "priority": IssuePriority.MEDIUM,
        "lat": 12.9642,
        "lng": 80.2471,
        "city": "Chennai",
        "area": "OMR Corridor",
        "votes": 28,
        "address": "Kandanchavadi, OMR Road, Chennai"
    },
    {
        "title": "Traffic Light Malfunction on Avinashi Road",
        "description": "The automated traffic signal at Lakshmi Mills junction on Avinashi Road, Coimbatore is stuck on amber, causing chaotic traffic jams during peak morning hours.",
        "category": IssueCategory.TRAFFIC,
        "status": IssueStatus.ASSIGNED,
        "priority": IssuePriority.CRITICAL,
        "lat": 11.0168,
        "lng": 76.9558,
        "city": "Coimbatore",
        "area": "Peelamedu",
        "votes": 67,
        "address": "Lakshmi Mills Junction, Avinashi Road, Coimbatore"
    },
    {
        "title": "Garbage Dumping near Koyambedu Bus Terminus",
        "description": "Huge accumulation of commercial organic waste dumped on the perimeter road near CMBT Koyambedu. Odor and stray animal safety concern.",
        "category": IssueCategory.WASTE,
        "status": IssueStatus.RESOLVED,
        "priority": IssuePriority.MEDIUM,
        "lat": 13.0694,
        "lng": 80.1948,
        "city": "Chennai",
        "area": "Koyambedu",
        "votes": 19,
        "address": "CMBT Outer Ring Road, Koyambedu, Chennai"
    },
    {
        "title": "Waste Dump near Meenakshi Amman Temple Perimeter",
        "description": "Plastic and paper waste piling up along East Chitrai Street near Madurai Meenakshi Temple. Sanitation team needed for daily clearance.",
        "category": IssueCategory.WASTE,
        "status": IssueStatus.IN_PROGRESS,
        "priority": IssuePriority.HIGH,
        "lat": 9.9195,
        "lng": 78.1193,
        "city": "Madurai",
        "area": "Town Hall",
        "votes": 51,
        "address": "East Chitrai Street, Madurai"
    },
    {
        "title": "Open Canal & Damaged Footpath near Chathiram Bus Stand",
        "description": "Concrete slab covering the drainage canal broke near Chathiram Bus Stand in Tiruchirappalli. High risk of pedestrian falls at night.",
        "category": IssueCategory.SAFETY,
        "status": IssueStatus.UNDER_REVIEW,
        "priority": IssuePriority.CRITICAL,
        "lat": 10.8272,
        "lng": 78.6946,
        "city": "Tiruchirappalli",
        "area": "Chathiram",
        "votes": 38,
        "address": "Chathiram Bus Stand Rd, Trichy"
    },
    {
        "title": "Fallen Tree Branch at Five Roads Junction",
        "description": "A heavy banyan tree branch fell across Five Roads intersection in Salem following heavy thunderstorm winds, blocking one lane of vehicular traffic.",
        "category": IssueCategory.ENVIRONMENT,
        "status": IssueStatus.ACKNOWLEDGED,
        "priority": IssuePriority.HIGH,
        "lat": 11.6643,
        "lng": 78.1460,
        "city": "Salem",
        "area": "Five Roads",
        "votes": 22,
        "address": "Five Roads Junction, Salem"
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
