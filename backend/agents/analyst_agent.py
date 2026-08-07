"""Smart Community Platform - Analyst Agent (Data Scientist)."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy import select, func, and_

from backend.config import settings
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    """The Data Scientist Agent.
    
    Runs every Sunday at 2am and:
    1. WEEKLY STATISTICS: Collects all stats from the past week
    2. TREND ANALYSIS: Compares this week to last 4 weeks
    3. HOTSPOT PREDICTION: Runs hotspot_predictor on historical data
    4. MODEL RETRAINING: Retrains Random Forest priority model with real resolved data
    5. CHROMA DB SYNC: Ensures all active issues are indexed in vector DB
    6. WEEKLY REPORT GENERATION: Writes narrative summary & emails report to authorities
    """

    agent_name = "analyst"
    agent_description = "Weekly analytics, model retraining, and report generation"

    def __init__(self, groq_api_key: str = None):
        super().__init__()
        self.api_key = groq_api_key or settings.GROQ_API_KEY

    def compile_civic_report(self, total_issues: int, resolved_count: int, top_category: str) -> Dict[str, Any]:
        """Compile executive summary report of community issues."""
        rate = round((resolved_count / total_issues * 100), 1) if total_issues > 0 else 0.0

        if rate >= 80.0:
            health_status = "Excellent"
            recommendation = "Maintain current maintenance schedules and reward responsive municipal teams."
        elif rate >= 50.0:
            health_status = "Moderate"
            recommendation = f"Allocate additional crew resources to '{top_category}' repairs to improve response velocity."
        else:
            health_status = "Needs Urgent Attention"
            recommendation = f"Critical backlog detected in '{top_category}'. Convene emergency municipal taskforce."

        return {
            "civic_health_status": health_status,
            "total_issues": total_issues,
            "resolved_issues": resolved_count,
            "resolution_rate_percent": rate,
            "primary_concern_category": top_category,
            "key_recommendation": recommendation,
            "agent": "AnalystAgent",
        }

    async def execute(self, db) -> None:
        """Run weekly analysis."""
        self.logger.info("Analyst Agent starting weekly analysis...")

        weekly_stats = await self._collect_weekly_stats(db)
        self.details["weekly_stats"] = weekly_stats

        trends = await self._analyze_trends(db)
        self.details["trends"] = trends

        hotspots = await self._update_hotspot_predictions(db)
        self.details["hotspots"] = hotspots

        retrain_result = await self._retrain_priority_model(db)
        self.details["model_retrain"] = retrain_result

        sync_result = await self._sync_chroma_db(db)
        self.details["chroma_sync"] = sync_result

        await self._generate_and_send_report(
            db=db,
            stats=weekly_stats,
            trends=trends,
            hotspots=hotspots
        )

        self.logger.info("Analyst Agent weekly analysis complete")

    async def _collect_weekly_stats(self, db) -> dict:
        """Collect comprehensive weekly statistics."""
        from backend.models.issue import Issue, IssueStatus

        week_start = datetime.utcnow() - timedelta(days=7)
        prev_week_start = week_start - timedelta(days=7)

        this_week = db.execute(
            select(func.count(Issue.id))
            .where(
                and_(
                    Issue.created_at >= week_start,
                    Issue.deleted_at.is_(None)
                )
            )
        ).scalar() or 0

        last_week = db.execute(
            select(func.count(Issue.id))
            .where(
                and_(
                    Issue.created_at >= prev_week_start,
                    Issue.created_at < week_start,
                    Issue.deleted_at.is_(None)
                )
            )
        ).scalar() or 0

        resolved_this_week = db.execute(
            select(func.count(Issue.id))
            .where(
                and_(
                    Issue.resolved_at >= week_start,
                    Issue.deleted_at.is_(None)
                )
            )
        ).scalar() or 0

        total_open = db.execute(
            select(func.count(Issue.id))
            .where(
                and_(
                    Issue.status.notin_([
                        IssueStatus.RESOLVED,
                        IssueStatus.REJECTED,
                        IssueStatus.DUPLICATE
                    ]),
                    Issue.deleted_at.is_(None)
                )
            )
        ).scalar() or 0

        cat_counts = db.execute(
            select(Issue.category, func.count(Issue.id).label("count"))
            .where(
                and_(
                    Issue.created_at >= week_start,
                    Issue.deleted_at.is_(None)
                )
            )
            .group_by(Issue.category)
        ).all()

        avg_resolution = db.execute(
            select(
                func.avg(
                    func.extract('epoch', Issue.resolved_at - Issue.created_at) / 86400
                )
            )
            .where(
                and_(
                    Issue.resolved_at.isnot(None),
                    Issue.created_at >= week_start,
                    Issue.deleted_at.is_(None)
                )
            )
        ).scalar()

        weekly_change = 0.0
        if last_week > 0:
            weekly_change = ((this_week - last_week) / last_week) * 100

        stats = {
            "period": "last_7_days",
            "reported": this_week,
            "resolved": resolved_this_week,
            "total_open": total_open,
            "last_week_reported": last_week,
            "weekly_change_percent": round(weekly_change, 1),
            "avg_resolution_days": round(float(avg_resolution or 0), 1),
            "resolution_rate": round((resolved_this_week / max(1, this_week)) * 100, 1),
            "by_category": {
                row.category.value: row.count
                for row in cat_counts
            }
        }

        self.issues_processed += this_week
        return stats

    async def _analyze_trends(self, db) -> dict:
        """Compare current week to previous weeks for trend detection."""
        from backend.models.issue import Issue, IssueCategory

        trends = {
            "increasing_categories": [],
            "decreasing_categories": [],
            "stable_categories": []
        }

        for category in IssueCategory:
            this_week_count = db.execute(
                select(func.count(Issue.id))
                .where(
                    and_(
                        Issue.category == category,
                        Issue.created_at >= datetime.utcnow() - timedelta(days=7),
                        Issue.deleted_at.is_(None)
                    )
                )
            ).scalar() or 0

            last_4_weeks = db.execute(
                select(func.count(Issue.id))
                .where(
                    and_(
                        Issue.category == category,
                        Issue.created_at >= datetime.utcnow() - timedelta(days=28),
                        Issue.created_at < datetime.utcnow() - timedelta(days=7),
                        Issue.deleted_at.is_(None)
                    )
                )
            ).scalar() or 0

            last_4_weeks_avg = last_4_weeks / 3.0

            if last_4_weeks_avg > 0:
                change = ((this_week_count - last_4_weeks_avg) / last_4_weeks_avg) * 100
                if change > 20:
                    trends["increasing_categories"].append({
                        "category": category.value,
                        "this_week": this_week_count,
                        "avg_prev_weeks": round(last_4_weeks_avg, 1),
                        "change_percent": round(change, 1)
                    })
                elif change < -20:
                    trends["decreasing_categories"].append({
                        "category": category.value,
                        "change_percent": round(change, 1)
                    })
                else:
                    trends["stable_categories"].append(category.value)

        self.record_action(
            "Trend analysis completed",
            {
                "increasing": len(trends["increasing_categories"]),
                "decreasing": len(trends["decreasing_categories"])
            }
        )

        return trends

    async def _update_hotspot_predictions(self, db) -> dict:
        """Run hotspot predictor and cache results."""
        try:
            from backend.ml.hotspot_predictor import predict_hotspots
            hotspots = await predict_hotspots(db, days_history=90)

            self.record_action(
                "Hotspot predictions updated",
                {"risk_areas_found": len(hotspots.get("high_risk_areas", []))}
            )

            return hotspots
        except Exception as e:
            self.record_error(f"Hotspot prediction failed: {e}")
            return {"error": str(e)}

    async def _retrain_priority_model(self, db) -> dict:
        """Collect training data and retrain priority model."""
        from backend.models.issue import Issue, IssueStatus

        training_issues = db.execute(
            select(Issue)
            .where(
                and_(
                    Issue.status == IssueStatus.RESOLVED,
                    Issue.created_at >= datetime.utcnow() - timedelta(days=90),
                    Issue.deleted_at.is_(None),
                    Issue.priority.isnot(None)
                )
            )
            .limit(500)
        ).scalars().all()

        if len(training_issues) < 20:
            result = {
                "retrained": False,
                "reason": f"Not enough data: {len(training_issues)} samples (need 20+)"
            }
            self.logger.info(result["reason"])
            return result

        training_data = []
        for issue in training_issues:
            training_data.append({
                "category": issue.category.value,
                "title": issue.title,
                "description": issue.description,
                "vote_count": issue.vote_count,
                "has_image": bool(issue.image_url),
                "priority": issue.priority.value
            })

        try:
            from backend.ml.model_manager import model_manager
            success = model_manager.retrain_priority_model(training_data)
        except Exception as e:
            self.logger.warning(f"Retrain model call failed: {e}")
            success = False

        result = {
            "retrained": success,
            "training_samples": len(training_data),
            "timestamp": datetime.utcnow().isoformat()
        }

        if success:
            self.record_action(
                "Priority model retrained",
                {"samples": len(training_data)}
            )

        return result

    async def _sync_chroma_db(self, db) -> dict:
        """Ensure all active issues are indexed in ChromaDB."""
        from backend.models.issue import Issue, IssueStatus
        from backend.ml.similarity_engine import index_issue_in_chroma

        try:
            from backend.ml.model_manager import model_manager
            collection = model_manager.get("issues_collection")
        except Exception:
            collection = None

        if not collection:
            return {"synced": False, "reason": "ChromaDB not available"}

        try:
            existing = collection.get(include=[])
            existing_ids = set(existing.get("ids", []))
        except Exception:
            existing_ids = set()

        active_issues = db.execute(
            select(Issue.uuid, Issue.title, Issue.description, Issue.category, Issue.location_city)
            .where(
                and_(
                    Issue.status.notin_([IssueStatus.REJECTED, IssueStatus.DUPLICATE]),
                    Issue.deleted_at.is_(None)
                )
            )
        ).all()

        unindexed = [i for i in active_issues if str(i.uuid) not in existing_ids]

        indexed_count = 0
        for issue in unindexed[:100]:
            try:
                await index_issue_in_chroma(
                    issue_uuid=str(issue.uuid),
                    title=issue.title,
                    description=issue.description,
                    category=issue.category.value if hasattr(issue.category, "value") else str(issue.category),
                    location_city=issue.location_city or ""
                )
                indexed_count += 1
            except Exception as e:
                self.record_error(f"ChromaDB index failed: {e}")

        if indexed_count > 0:
            self.record_action(
                f"ChromaDB sync: indexed {indexed_count} issues",
                {"indexed": indexed_count, "total_unindexed": len(unindexed)}
            )

        return {
            "synced": True,
            "existing_in_chroma": len(existing_ids),
            "newly_indexed": indexed_count,
            "total_active": len(active_issues)
        }

    async def _generate_and_send_report(
        self,
        db,
        stats: dict,
        trends: dict,
        hotspots: dict
    ):
        """Generate weekly report and email to all authorities."""
        from backend.models.user import User, UserRole
        from backend.utils.email import send_email
        from backend.ml.groq_llm import generate_weekly_report_summary

        top_issues_list = [
            {"category": cat, "count": count}
            for cat, count in stats.get("by_category", {}).items()
        ]
        top_issues_list.sort(key=lambda x: x.get("count", 0), reverse=True)

        try:
            narrative = await generate_weekly_report_summary(
                stats=stats,
                top_issues=top_issues_list[:5],
                resolved_this_week=stats.get("resolved", 0),
                total_open=stats.get("total_open", 0)
            )
        except Exception as e:
            self.logger.warning(f"Failed to generate LLM report narrative: {e}")
            narrative = (
                f"Weekly Community Performance Summary: {stats.get('reported', 0)} issues reported, "
                f"{stats.get('resolved', 0)} issues resolved. Overall resolution rate is {stats.get('resolution_rate', 0)}%."
            )

        report_html = self._build_report_html(
            stats, trends, hotspots, narrative, top_issues_list
        )

        authority_users = db.execute(
            select(User)
            .where(
                User.role.in_([UserRole.AUTHORITY, UserRole.ADMIN, "authority", "admin"]),
                User.is_active == True
            )
        ).scalars().all()

        sent_count = 0
        for user in authority_users:
            try:
                send_email(
                    to_email=user.email,
                    subject=f"📊 Weekly Community Report - {datetime.utcnow().strftime('%B %d, %Y')}",
                    html_body=report_html
                )
                sent_count += 1
            except Exception as e:
                self.record_error(f"Report email failed for {user.email}: {e}")

        self.record_action(
            f"Weekly report sent to {sent_count} authorities",
            {"recipients": sent_count, "stats_period": "last_7_days"}
        )

    def _build_report_html(
        self,
        stats: dict,
        trends: dict,
        hotspots: dict,
        narrative: str,
        top_categories: list
    ) -> str:
        """Build clean HTML weekly report email."""
        weekly_change = stats.get("weekly_change_percent", 0)
        trend_arrow = "📈" if weekly_change > 0 else "📉" if weekly_change < 0 else "➡️"
        trend_color = "#DC2626" if weekly_change > 10 else "#16A34A" if weekly_change < -5 else "#D97706"

        category_rows = ""
        for cat_data in top_categories[:5]:
            category_rows += f"""
                <tr>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0;">
                        {str(cat_data.get('category', 'unknown')).title()}
                    </td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #E2E8F0; text-align: right;">
                        <strong>{cat_data.get('count', 0)}</strong>
                    </td>
                </tr>
            """

        hotspot_rows = ""
        for area in hotspots.get("high_risk_areas", [])[:3]:
            hotspot_rows += f"""
                <li style="margin-bottom: 6px;">
                    <strong>{area.get('area', 'Unknown')}</strong> ({area.get('city', '')}) - Risk Score: {area.get('risk_score', 0):.0f}/100
                </li>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: -apple-system, sans-serif; max-width: 650px; margin: 0 auto; padding: 20px; color: #1E293B;">
            <div style="text-align: center; padding: 30px 0; background: linear-gradient(135deg, #1E40AF, #2563EB); border-radius: 12px; color: white; margin-bottom: 30px;">
                <h1 style="margin: 0; font-size: 1.6rem;">📊 Weekly Community Report</h1>
                <p style="margin: 8px 0 0; opacity: 0.9;">
                    {datetime.utcnow().strftime('%B %d, %Y')} • Smart Community Platform
                </p>
            </div>

            <p style="font-size: 1rem; line-height: 1.6; color: #475569;">
                {narrative}
            </p>

            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 12px; margin: 24px 0;">
                <div style="background: #EFF6FF; padding: 16px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 2rem; font-weight: 700; color: #2563EB;">{stats.get('reported', 0)}</div>
                    <div style="font-size: 0.8rem; color: #64748B;">Reported</div>
                </div>
                <div style="background: #F0FDF4; padding: 16px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 2rem; font-weight: 700; color: #16A34A;">{stats.get('resolved', 0)}</div>
                    <div style="font-size: 0.8rem; color: #64748B;">Resolved</div>
                </div>
                <div style="background: #FFF7ED; padding: 16px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 2rem; font-weight: 700; color: #D97706;">{stats.get('total_open', 0)}</div>
                    <div style="font-size: 0.8rem; color: #64748B;">Still Open</div>
                </div>
                <div style="background: #F8FAFC; padding: 16px; border-radius: 10px; text-align: center;">
                    <div style="font-size: 2rem; font-weight: 700; color: {trend_color};">{trend_arrow}{abs(weekly_change):.0f}%</div>
                    <div style="font-size: 0.8rem; color: #64748B;">vs Last Week</div>
                </div>
            </div>

            <h3 style="color: #1E293B; margin-top: 28px;">📋 Issues by Category</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: #F8FAFC;">
                        <th style="padding: 10px 12px; text-align: left; font-size: 0.85rem;">Category</th>
                        <th style="padding: 10px 12px; text-align: right; font-size: 0.85rem;">Issues</th>
                    </tr>
                </thead>
                <tbody>{category_rows}</tbody>
            </table>

            {"<h3 style='margin-top: 28px;'>⚠️ Problem Hotspots</h3><ul>" + hotspot_rows + "</ul>" if hotspot_rows else ""}

            <div style="margin-top: 32px; text-align: center;">
                <a href="{settings.FRONTEND_URL}/dashboard.html"
                   style="background: #2563EB; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; display: inline-block;">
                    Open Dashboard →
                </a>
            </div>

            <p style="color: #94A3B8; font-size: 0.8rem; text-align: center; margin-top: 30px;">
                Generated automatically by Smart Community Platform AI Analyst Agent<br>
                {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
            </p>
        </body>
        </html>
        """
