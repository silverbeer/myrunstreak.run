#!/usr/bin/env python3
"""
Quick diagnostic tool to check MyRunStreak system status.

Usage:
    AWS_PROFILE=silverbeer uv run python scripts/check_status.py
"""

import json
import subprocess
from datetime import UTC, datetime


def run_aws_cmd(cmd: list[str]) -> dict | list | str | None:
    """Run an AWS CLI command and return JSON output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except subprocess.CalledProcessError as e:
        print(f"  Error: {e.stderr}")
        return None
    except json.JSONDecodeError:
        return result.stdout.strip() if result.stdout else None


def check_eventbridge_rules() -> None:
    """Check EventBridge scheduled rules."""
    print("\n" + "=" * 60)
    print("EVENTBRIDGE SCHEDULES")
    print("=" * 60)

    rules = run_aws_cmd([
        "aws", "events", "list-rules",
        "--query", "Rules[?contains(Name, `myrunstreak`)]",
        "--output", "json",
    ])

    if not rules:
        print("  No EventBridge rules found")
        return

    for rule in rules:
        name = rule.get("Name", "Unknown")
        state = rule.get("State", "Unknown")
        schedule = rule.get("ScheduleExpression", "N/A")
        description = rule.get("Description", "")

        status_icon = "✅" if state == "ENABLED" else "❌"
        print(f"\n  {status_icon} {name}")
        print(f"     State: {state}")
        print(f"     Schedule: {schedule}")
        if description:
            print(f"     Description: {description[:60]}...")


def check_lambda_logs(function_name: str, hours: int = 24) -> dict:
    """Check recent Lambda invocations from CloudWatch logs."""
    print(f"\n  Checking logs for {function_name}...")

    # Get log streams
    streams = run_aws_cmd([
        "aws", "logs", "describe-log-streams",
        "--log-group-name", f"/aws/lambda/{function_name}",
        "--order-by", "LastEventTime",
        "--descending",
        "--limit", "5",
        "--output", "json",
    ])

    if not streams or "logStreams" not in streams:
        return {"status": "no_logs", "message": "No log streams found"}

    # Get recent log events
    result = subprocess.run(
        [
            "aws", "logs", "tail",
            f"/aws/lambda/{function_name}",
            "--since", f"{hours}h",
            "--format", "short",
        ],
        capture_output=True,
        text=True,
    )

    logs = result.stdout if result.returncode == 0 else ""

    # Parse logs for status
    invocations = logs.count("START RequestId")
    errors = logs.count("ERROR")
    successes = logs.count("Sync completed") + logs.count("SUCCESS")

    # Check for specific error patterns
    has_missing_env = "Field required" in logs or "validation errors" in logs

    return {
        "invocations": invocations,
        "errors": errors,
        "successes": successes,
        "has_missing_env_vars": has_missing_env,
        "raw_logs": logs[-2000:] if logs else "",  # Last 2000 chars
    }


def check_cloudwatch_logs() -> None:
    """Check CloudWatch logs for all Lambda functions."""
    print("\n" + "=" * 60)
    print("CLOUDWATCH LOGS (Last 24 hours)")
    print("=" * 60)

    functions = [
        "myrunstreak-sync-runner-dev",
        "myrunstreak-publish-status-dev",
        "myrunstreak-query-runner-dev",
    ]

    for func in functions:
        result = check_lambda_logs(func)
        print(f"\n  📋 {func}")
        print(f"     Invocations: {result.get('invocations', 0)}")
        print(f"     Errors: {result.get('errors', 0)}")
        print(f"     Successes: {result.get('successes', 0)}")

        if result.get("has_missing_env_vars"):
            print("     ⚠️  Missing environment variables detected!")


def check_gcs_status_file() -> dict:
    """Check the 'Did I Run Today' status file in GCS."""
    print("\n" + "=" * 60)
    print("GCS STATUS FILE (Did I Run Today)")
    print("=" * 60)

    gcs_url = "https://storage.googleapis.com/myrunstreak-public/status.json"

    try:
        result = subprocess.run(
            ["curl", "-s", gcs_url],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            print(f"\n  ✅ Status file found at {gcs_url}")
            print(f"\n  Updated: {data.get('updated_at', 'Unknown')}")
            print(f"  Ran today: {'✅ YES' if data.get('ran_today') else '❌ NO'}")

            streak = data.get("streak", {})
            print(f"  Streak: {streak.get('current_days', 0)} days")
            print(f"  Streak started: {streak.get('started', 'Unknown')}")

            last_run = data.get("last_run", {})
            if last_run:
                print(f"\n  Last run: {last_run.get('date')}")
                print(f"    Distance: {last_run.get('distance_mi')} miles")
                print(f"    Duration: {last_run.get('duration_min')} min")

            print(f"\n  Month total: {data.get('month_total_mi', 0)} miles")
            print(f"  Year total: {data.get('year_total_mi', 0)} miles")

            return {"status": "ok", "data": data}
        else:
            print(f"\n  ❌ Could not fetch status file from {gcs_url}")
            return {"status": "error", "message": "Failed to fetch"}

    except json.JSONDecodeError as e:
        print(f"\n  ❌ Invalid JSON in status file: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        print(f"\n  ❌ Error checking status file: {e}")
        return {"status": "error", "message": str(e)}


def check_lambda_env_vars() -> None:
    """Check Lambda environment variable configuration."""
    print("\n" + "=" * 60)
    print("LAMBDA ENVIRONMENT VARIABLES")
    print("=" * 60)

    func = "myrunstreak-sync-runner-dev"
    config = run_aws_cmd([
        "aws", "lambda", "get-function-configuration",
        "--function-name", func,
        "--output", "json",
    ])

    if not config:
        print(f"  ❌ Could not get config for {func}")
        return

    env_vars = config.get("Environment", {}).get("Variables", {})

    required_vars = [
        "SMASHRUN_CLIENT_ID",
        "SMASHRUN_CLIENT_SECRET",
        "SUPABASE_URL",
        "SUPABASE_KEY",
    ]

    print(f"\n  Lambda: {func}")
    print(f"  Environment variables configured: {len(env_vars)}")

    for var in required_vars:
        # Check both upper and lower case versions
        has_var = var in env_vars or var.lower() in env_vars
        status = "✅" if has_var else "❌ MISSING"
        print(f"     {status} {var}")

    # Show what IS configured
    if env_vars:
        print("\n  Configured variables:")
        for key in sorted(env_vars.keys()):
            value = env_vars[key]
            # Mask secrets
            if "secret" in key.lower() or "key" in key.lower() or "password" in key.lower():
                display_value = value[:4] + "***" if len(value) > 4 else "***"
            else:
                display_value = value[:50] + "..." if len(value) > 50 else value
            print(f"     {key}: {display_value}")


def main() -> None:
    """Run all diagnostic checks."""
    print("\n" + "🏃" * 30)
    print("  MyRunStreak System Status Check")
    print(f"  {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("🏃" * 30)

    check_eventbridge_rules()
    check_cloudwatch_logs()
    gcs_result = check_gcs_status_file()
    check_lambda_env_vars()

    print("\n" + "=" * 60)
    print("OVERALL STATUS")
    print("=" * 60)

    # Determine overall health
    if gcs_result.get("status") == "ok":
        data = gcs_result.get("data", {})
        ran_today = data.get("ran_today", False)
        streak = data.get("streak", {}).get("current_days", 0)

        if ran_today:
            print("\n  ✅ ALL SYSTEMS OPERATIONAL")
            print("     - You ran today!")
            print(f"     - Streak: {streak} days")
        else:
            print("\n  ⚠️  SYSTEMS OPERATIONAL - No run logged today")
            print(f"     - Streak: {streak} days")
            print("     - Go for a run to keep your streak alive!")
    else:
        print("\n  ❌ SYSTEM ISSUES DETECTED")
        print("     - Check CloudWatch logs for errors")
        print("     - Verify Lambda has Secrets Manager permissions")


if __name__ == "__main__":
    main()
