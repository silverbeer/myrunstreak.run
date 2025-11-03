#!/usr/bin/env python3
"""
RunStreak Chat using PydanticAI + Lambda API.

No local database needed - uses your existing Lambda infrastructure!
"""

import os
from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext


# ============================================================================
# Configuration
# ============================================================================

API_BASE_URL = "https://9fmuhcz4y0.execute-api.us-east-2.amazonaws.com/dev"


# ============================================================================
# Pydantic Models
# ============================================================================

class APIResponse(BaseModel):
    """Generic API response."""
    data: dict[str, Any]

    def format(self) -> str:
        """Format the response nicely."""
        import json
        return json.dumps(self.data, indent=2, default=str)


class APIDependency(BaseModel):
    """Dependency for API access."""
    base_url: str = Field(default=API_BASE_URL)
    timeout: float = Field(default=30.0)

    def get_client(self) -> httpx.Client:
        """Get an HTTP client."""
        return httpx.Client(base_url=self.base_url, timeout=self.timeout)


# ============================================================================
# Create the Agent
# ============================================================================

agent = Agent(
    'openai:gpt-4o',  # Or 'openai:gpt-3.5-turbo' for cheaper option
    deps_type=APIDependency,
    system_prompt="""You are an enthusiastic running coach and data analyst helping a runner
    understand their training data.

    The runner has maintained a daily running streak since August 24, 2014 - that's over 4,000
    consecutive days of running! 🔥 Be encouraging and help them celebrate their achievements.

    Available data through API endpoints:
    - Overall statistics (total runs, distance, pace)
    - Recent runs
    - Monthly statistics
    - Streak information
    - Personal records
    - Paginated list of all runs

    Key conversions:
    - Database stores km (multiply by 0.621371 for miles)
    - Pace in min/km (divide by 0.621371 for min/mile)
    - Temperature in Celsius (°C × 9/5 + 32 = °F)

    Default to imperial units (miles, °F) for American runners.

    Be conversational, enthusiastic, and celebrate their incredible consistency!""",
)


# ============================================================================
# Tools (API Endpoints)
# ============================================================================

@agent.tool
async def get_overall_stats(ctx: RunContext[APIDependency]) -> APIResponse:
    """
    Get overall running statistics.

    Returns all-time totals, averages, and personal bests.
    """
    with ctx.deps.get_client() as client:
        response = client.get("/stats/overall")
        response.raise_for_status()
        return APIResponse(data=response.json())


@agent.tool
async def get_recent_runs(
    ctx: RunContext[APIDependency],
    limit: int = 10
) -> APIResponse:
    """
    Get recent runs.

    Args:
        ctx: Runtime context
        limit: Number of runs to return (default 10, max 100)

    Returns:
        Recent runs with distance, pace, weather, etc.
    """
    limit = min(limit, 100)

    with ctx.deps.get_client() as client:
        response = client.get("/runs/recent", params={"limit": limit})
        response.raise_for_status()
        return APIResponse(data=response.json())


@agent.tool
async def get_monthly_stats(
    ctx: RunContext[APIDependency],
    limit: int = 12
) -> APIResponse:
    """
    Get monthly running statistics.

    Args:
        ctx: Runtime context
        limit: Number of months to return (default 12, max 60)

    Returns:
        Monthly breakdown with run count, total distance, and averages.
    """
    limit = min(limit, 60)

    with ctx.deps.get_client() as client:
        response = client.get("/stats/monthly", params={"limit": limit})
        response.raise_for_status()
        return APIResponse(data=response.json())


@agent.tool
async def get_streak_info(ctx: RunContext[APIDependency]) -> APIResponse:
    """
    Get running streak analysis.

    Returns current streak, longest streak, and top 10 streaks.
    """
    with ctx.deps.get_client() as client:
        response = client.get("/stats/streaks")
        response.raise_for_status()
        return APIResponse(data=response.json())


@agent.tool
async def get_personal_records(ctx: RunContext[APIDependency]) -> APIResponse:
    """
    Get personal records.

    Returns longest run, fastest pace, best week, best month, etc.
    """
    with ctx.deps.get_client() as client:
        response = client.get("/stats/records")
        response.raise_for_status()
        return APIResponse(data=response.json())


@agent.tool
async def list_runs(
    ctx: RunContext[APIDependency],
    offset: int = 0,
    limit: int = 50
) -> APIResponse:
    """
    List all runs with pagination.

    Args:
        ctx: Runtime context
        offset: Starting position (default 0)
        limit: Number of runs to return (default 50, max 100)

    Returns:
        Paginated list of runs
    """
    limit = min(limit, 100)

    with ctx.deps.get_client() as client:
        response = client.get("/runs", params={"offset": offset, "limit": limit})
        response.raise_for_status()
        return APIResponse(data=response.json())


# ============================================================================
# Helper Functions
# ============================================================================

def format_api_response(response: APIResponse, response_type: str) -> str:
    """Format API responses in a readable way."""
    data = response.data

    if response_type == "overall":
        return f"""📊 Overall Statistics:

🏃 Total Runs: {data.get('total_runs', 0):,}
📏 Total Distance: {data.get('total_km', 0) * 0.621371:.1f} miles
📈 Average per Run: {data.get('avg_km', 0) * 0.621371:.2f} miles
🏆 Longest Run: {data.get('longest_run_km', 0) * 0.621371:.2f} miles
⚡ Average Pace: {data.get('avg_pace_min_per_km', 0) / 0.621371:.2f} min/mile"""

    elif response_type == "streaks":
        return f"""🔥 Streak Information:

Current Streak: {data.get('current_streak', 0):,} days
Longest Streak: {data.get('longest_streak', 0):,} days

Top Streaks:
""" + "\n".join([
            f"  {i+1}. {s['start_date']} to {s['end_date']}: {s['length_days']} days {'← Current' if s.get('is_current') else ''}"
            for i, s in enumerate(data.get('top_streaks', [])[:5])
        ])

    elif response_type == "records":
        records = data
        output = "🏆 Personal Records:\n\n"

        if 'longest_run' in records:
            lr = records['longest_run']
            output += f"📏 Longest Run: {lr['distance_km'] * 0.621371:.2f} miles on {lr['date']}\n"

        if 'fastest_pace' in records:
            fp = records['fastest_pace']
            output += f"⚡ Fastest Pace: {fp['pace_min_per_km'] / 0.621371:.2f} min/mile ({fp['distance_km'] * 0.621371:.1f} mi on {fp['date']})\n"

        if 'most_km_month' in records:
            mm = records['most_km_month']
            output += f"📅 Best Month: {mm['month']} - {mm['total_km'] * 0.621371:.1f} miles in {mm['run_count']} runs\n"

        return output

    # Default: pretty JSON
    import json
    return json.dumps(data, indent=2, default=str)


# ============================================================================
# Main Chat Interface
# ============================================================================

async def main():
    """Interactive chat loop."""
    print("="*70)
    print("🏃 Welcome to RunStreak Chat!")
    print("="*70)
    print("Powered by PydanticAI + Your Lambda API 🚀")
    print(f"\nConnected to: {API_BASE_URL}")
    print("\nI can help you explore your running data. Try asking:")
    print("  • What are my overall stats?")
    print("  • Show my current streak")
    print("  • What are my personal records?")
    print("  • Show my last 20 runs")
    print("  • Monthly stats for 2025")
    print("  • How consistent am I? (monthly breakdown)")
    print("\nType 'quit' to exit.\n")

    # Initialize API dependency
    deps = APIDependency(base_url=API_BASE_URL)

    # Test connection
    try:
        with deps.get_client() as client:
            response = client.get("/stats/overall")
            response.raise_for_status()
        print("✅ Connected to API successfully!\n")
    except Exception as e:
        print(f"❌ Error connecting to API: {e}")
        print(f"Make sure {API_BASE_URL} is accessible\n")
        return

    # Conversation history
    conversation_history = []

    while True:
        try:
            user_input = input("You: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n🏃 Keep up the streak! See you next run! 👋\n")
                break

            if not user_input:
                continue

            print("\n🤖 Assistant: ", end="", flush=True)

            # Run the agent with streaming
            async with agent.run_stream(
                user_input,
                deps=deps,
                message_history=conversation_history
            ) as result:
                # Stream the response in real-time
                async for text in result.stream():
                    print(text, end="", flush=True)

                print("\n")

                # Update conversation history
                conversation_history = result.new_messages()

        except KeyboardInterrupt:
            print("\n\n🏃 Keep up the streak! 👋\n")
            break
        except httpx.HTTPError as e:
            print(f"\n\n❌ API Error: {e}\n")
        except Exception as e:
            print(f"\n\n❌ Error: {e}\n")


if __name__ == "__main__":
    import asyncio

    # Check for API key
    if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Error: No API key found")
        print("\nSet one of:")
        print("  export OPENAI_API_KEY='sk-...'         # For GPT-4o (default)")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'  # For Claude")
        print("\nThen update line 53 to use your preferred model:")
        print("  'openai:gpt-4o' (recommended)")
        print("  'openai:gpt-3.5-turbo' (cheaper)")
        print("  'anthropic:claude-3-5-sonnet-20241022'")
        exit(1)

    asyncio.run(main())
