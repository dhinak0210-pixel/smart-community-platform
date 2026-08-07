"""Groq LLM integration using llama3-8b-8192 for complex reasoning and summarization."""

import logging
import asyncio
import json
import re
from typing import Optional, Any

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-8b-instant"
MAX_TOKENS_DEFAULT = 500
TEMPERATURE_DEFAULT = 0.3


# ------------------------------------------------------------------------------
# BASE GROQ API CALL
# ------------------------------------------------------------------------------

async def call_groq(
    prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = MAX_TOKENS_DEFAULT,
    temperature: float = TEMPERATURE_DEFAULT
) -> Optional[str]:
    """Call Groq API asynchronously using run_in_executor."""
    from backend.ml.model_manager import model_manager

    client = model_manager.get("groq_client")
    if client is None:
        logger.warning("Groq client not available")
        return None

    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        loop = asyncio.get_running_loop()

        def _chat():
            return client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

        response = await loop.run_in_executor(None, _chat)

        if response and response.choices and len(response.choices) > 0:
            result = response.choices[0].message.content
            logger.debug(f"Groq response: {len(result)} chars")
            return result
        return None

    except Exception as e:
        logger.error(f"Groq API call failed: {e}")
        return None


# ------------------------------------------------------------------------------
# DOMAIN-SPECIFIC LLM FUNCTIONS
# ------------------------------------------------------------------------------

async def generate_issue_summary(
    title: str,
    description: str,
    category: str,
    status: str,
    location: str,
    vote_count: int
) -> str:
    """Generate a concise public summary of an issue report."""
    prompt = f"""
    Summarize this community issue report in 2-3 sentences.
    Be factual, clear, and helpful for both citizens and authorities.
    Do not add information not in the original report.

    Title: {title}
    Category: {category}
    Location: {location}
    Status: {status}
    Community Support: {vote_count} votes
    Description: {description[:500]}

    Write a concise summary:
    """

    system = "You are a helpful community platform assistant. Write clear, factual summaries."

    result = await call_groq(prompt, system, max_tokens=150)
    return result or f"{title} - {description[:200]}"


async def generate_authority_response(
    issue_title: str,
    issue_description: str,
    issue_category: str,
    current_status: str,
    department: Optional[str]
) -> str:
    """Generate a professional authority response template for status updates."""
    prompt = f"""
    Generate a professional, empathetic response from a local authority
    to a citizen who reported a community issue.
    Response should:
    - Acknowledge the report
    - Show the issue is being taken seriously
    - Mention next steps
    - Be 2-3 sentences max

    Issue: {issue_title}
    Category: {issue_category}
    Status being set to: {current_status}
    Department: {department or 'relevant department'}

    Write the authority response:
    """

    system = "You are a professional government communications officer. Write formal but empathetic responses."

    result = await call_groq(prompt, system, max_tokens=200)
    return result or "We have received your report and are reviewing it. Our team will take appropriate action."


async def generate_weekly_report_summary(
    stats: dict[str, Any],
    top_issues: list[dict[str, Any]],
    resolved_this_week: int,
    total_open: int
) -> str:
    """Generate weekly analytics report summary for city officials."""
    top_cats = ", ".join([i.get("category", "") for i in top_issues[:3]])
    prompt = f"""
    Generate a brief weekly summary report for a Smart Community Platform.
    Write in professional report style. 3-4 sentences.

    This week's stats:
    - Issues reported: {stats.get('reported_this_week', 0)}
    - Issues resolved: {resolved_this_week}
    - Currently open: {total_open}
    - Resolution rate: {stats.get('resolution_rate', 0):.1f}%
    - Top problem categories: {top_cats}

    Write the weekly summary:
    """

    system = "You are an analyst writing a government weekly report. Be professional and data-focused."

    result = await call_groq(prompt, system, max_tokens=300)
    return result or f"This week, {stats.get('reported_this_week', 0)} issues were reported and {resolved_this_week} were resolved."


async def answer_citizen_question(
    question: str,
    relevant_issues: list[dict[str, Any]],
    platform_stats: dict[str, Any]
) -> str:
    """Answer a citizen query using Retrieval-Augmented Generation (RAG)."""
    context_parts = []
    for issue in relevant_issues[:5]:
        context_parts.append(f"Issue: {issue.get('text', '')[:200]}")
    context = "\n".join(context_parts)

    prompt = f"""
    Answer this citizen question about their community platform.
    Use the context provided. If you don't know, say so honestly.
    Be helpful, friendly, and concise (2-3 sentences max).

    Citizen Question: {question}

    Relevant Issues Context:
    {context}

    Platform Statistics:
    - Total issues: {platform_stats.get('total', 0)}
    - Resolved: {platform_stats.get('resolved', 0)}
    - Resolution rate: {platform_stats.get('resolution_rate', 0):.1f}%

    Answer:
    """

    system = """You are a helpful community platform assistant.
    Answer questions about local issues, platform status, and community concerns.
    Be honest if information is not available."""

    result = await call_groq(prompt, system, max_tokens=200, temperature=0.4)
    return result or "I don't have enough information to answer that question accurately. Please check the platform map for specific issue details."


async def classify_with_llm(
    title: str,
    description: str
) -> Optional[dict[str, Any]]:
    """Ultimate classification fallback using Groq LLaMA 3."""
    prompt = f"""
    Classify this community issue report.
    Reply with ONLY a JSON object. No explanation.

    Issue Title: {title}
    Description: {description[:300]}

    Reply format:
    {{
        "category": "one of: infrastructure, waste, safety, environment, utilities, traffic, noise, flooding, other",
        "priority": "one of: critical, high, medium, low",
        "reasoning": "one sentence"
    }}
    """

    result = await call_groq(prompt, max_tokens=150, temperature=0.1)

    if result:
        try:
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return {
                    "category": parsed.get("category", "other"),
                    "priority": parsed.get("priority", "medium"),
                    "reasoning": parsed.get("reasoning", ""),
                    "method": "llm_classification"
                }
        except Exception as e:
            logger.warning(f"Failed to parse LLM JSON classification: {e}")

    return None
