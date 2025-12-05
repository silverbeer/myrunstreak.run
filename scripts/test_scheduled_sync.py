#!/usr/bin/env python3
"""
Quick test script to verify the scheduled sync Lambda is working.

Usage:
    uv run python scripts/test_scheduled_sync.py [--invoke] [--logs-only]

Options:
    --invoke     Trigger the Lambda manually (default: just check logs)
    --logs-only  Only show recent logs, don't invoke
"""

import argparse
import base64
import json
import re
import sys
from datetime import UTC, datetime, timedelta

import boto3
from botocore.exceptions import ClientError

# Configuration
AWS_REGION = "us-east-2"
LAMBDA_FUNCTION_NAME = "myrunstreak-sync-runner-dev"
LOG_GROUP_NAME = f"/aws/lambda/{LAMBDA_FUNCTION_NAME}"
API_GATEWAY_URL = "https://inc6slepzb.execute-api.us-east-2.amazonaws.com/dev"


def get_aws_clients() -> tuple[boto3.client, boto3.client, boto3.client]:
    """Get AWS clients for Lambda, CloudWatch Logs, and Events."""
    session = boto3.Session(region_name=AWS_REGION)
    return (
        session.client("lambda"),
        session.client("logs"),
        session.client("events"),
    )


def parse_sync_results(events: list[dict]) -> dict | None:
    """Parse log events to extract sync results."""
    results = {
        "streak_days": None,
        "total_distance_km": None,
        "total_distance_miles": None,
        "runs_synced": None,
        "sources_synced": None,
        "username": None,
        "last_sync_time": None,
        "activities_found": None,
    }

    for event in events:
        message = event.get("message", "")

        # Extract streak and distance from recalculated stats
        # "Recalculated stats for user ...: 4121 day streak, 29350.89 km"
        streak_match = re.search(r"(\d+) day streak, ([\d.]+) km", message)
        if streak_match:
            results["streak_days"] = int(streak_match.group(1))
            results["total_distance_km"] = float(streak_match.group(2))
            results["total_distance_miles"] = round(
                results["total_distance_km"] * 0.621371, 2
            )

        # Extract username
        # "Authenticated as: tom.drake"
        user_match = re.search(r"Authenticated as: ([a-zA-Z0-9_.]+)", message)
        if user_match:
            results["username"] = user_match.group(1)

        # Extract runs synced
        # "Successfully synced 1 runs for source"
        runs_match = re.search(r"Successfully synced (\d+) runs", message)
        if runs_match:
            results["runs_synced"] = int(runs_match.group(1))

        # Extract activities found
        # "Found 1 activities"
        activities_match = re.search(r"Found (\d+) activities", message)
        if activities_match:
            results["activities_found"] = int(activities_match.group(1))

        # Extract sync completion
        # "Sync completed: 1 runs from 1 sources"
        completion_match = re.search(
            r"Sync completed: (\d+) runs from (\d+) sources", message
        )
        if completion_match:
            results["runs_synced"] = int(completion_match.group(1))
            results["sources_synced"] = int(completion_match.group(2))

        # Get timestamp of sync
        if "daily_sync" in message and results["last_sync_time"] is None:
            results["last_sync_time"] = datetime.fromtimestamp(
                event["timestamp"] / 1000
            )

    # Check if we found any results
    if results["streak_days"] is not None:
        return results
    return None


def display_sync_summary(results: dict) -> None:
    """Display a nice summary of the sync results."""
    print("\n" + "=" * 60)
    print("📊 LATEST SYNC RESULTS")
    print("=" * 60)

    if results["last_sync_time"]:
        print(f"\n⏰ Last Sync: {results['last_sync_time'].strftime('%Y-%m-%d %H:%M:%S')}")

    if results["username"]:
        print(f"👤 User: {results['username']}")

    print("\n" + "-" * 60)
    print("🏃 RUN STREAK STATS")
    print("-" * 60)

    if results["streak_days"]:
        years = results["streak_days"] // 365
        remaining_days = results["streak_days"] % 365
        print(f"\n   🔥 STREAK: {results['streak_days']:,} days")
        if years > 0:
            print(f"              ({years} years, {remaining_days} days)")

    if results["total_distance_km"]:
        print(f"\n   📏 TOTAL DISTANCE: {results['total_distance_km']:,.2f} km")
        print(f"                      {results['total_distance_miles']:,.2f} miles")

    print("\n" + "-" * 60)
    print("📥 SYNC DETAILS")
    print("-" * 60)

    if results["activities_found"] is not None:
        print(f"\n   Activities found: {results['activities_found']}")

    if results["runs_synced"] is not None:
        print(f"   Runs synced: {results['runs_synced']}")

    if results["sources_synced"] is not None:
        print(f"   Sources processed: {results['sources_synced']}")

    print("\n" + "=" * 60)


def check_lambda_exists(lambda_client: boto3.client) -> bool:
    """Check if the Lambda function exists."""
    try:
        response = lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)
        print(f"✅ Lambda function exists: {LAMBDA_FUNCTION_NAME}")
        print(f"   Last modified: {response['Configuration']['LastModified']}")
        print(f"   Memory: {response['Configuration']['MemorySize']} MB")
        print(f"   Timeout: {response['Configuration']['Timeout']}s")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"❌ Lambda function not found: {LAMBDA_FUNCTION_NAME}")
        else:
            print(f"❌ Error checking Lambda: {e}")
        return False


def check_eventbridge_rules(events_client: boto3.client) -> None:
    """Check EventBridge rules for the sync Lambda."""
    print("\n📅 EventBridge Schedules:")

    rule_names = [
        "myrunstreak-sync-morning-dev",
        "myrunstreak-sync-midday-dev",
    ]

    for rule_name in rule_names:
        try:
            rule = events_client.describe_rule(Name=rule_name)
            state = "✅ ENABLED" if rule["State"] == "ENABLED" else "❌ DISABLED"
            print(f"   {rule_name}: {state}")
            print(f"      Schedule: {rule['ScheduleExpression']}")
            print(f"      Description: {rule.get('Description', 'N/A')}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                print(f"   ❌ Rule not found: {rule_name}")
            else:
                print(f"   ❌ Error: {e}")


def get_recent_logs(logs_client: boto3.client, hours: int = 24, quiet: bool = False) -> list[dict]:
    """Get recent log events from CloudWatch."""
    if not quiet:
        print(f"\n📜 Fetching logs (last {hours} hours)...")

    now = datetime.now(UTC)
    start_time = int((now - timedelta(hours=hours)).timestamp() * 1000)
    end_time = int(now.timestamp() * 1000)

    try:
        # Get log streams
        streams_response = logs_client.describe_log_streams(
            logGroupName=LOG_GROUP_NAME,
            orderBy="LastEventTime",
            descending=True,
            limit=5,
        )

        if not streams_response.get("logStreams"):
            print("   No log streams found")
            return []

        all_events = []

        for stream in streams_response["logStreams"][:3]:
            stream_name = stream["logStreamName"]

            try:
                events_response = logs_client.get_log_events(
                    logGroupName=LOG_GROUP_NAME,
                    logStreamName=stream_name,
                    startTime=start_time,
                    endTime=end_time,
                    limit=50,
                )

                for event in events_response.get("events", []):
                    event["streamName"] = stream_name
                    all_events.append(event)

            except ClientError as e:
                print(f"   Error reading stream {stream_name}: {e}")

        # Sort by timestamp
        all_events.sort(key=lambda x: x["timestamp"], reverse=True)

        return all_events[:30]

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"   Log group not found: {LOG_GROUP_NAME}")
        else:
            print(f"   Error: {e}")
        return []


def display_logs(events: list[dict], verbose: bool = False) -> None:
    """Display log events in a readable format."""
    if not events:
        print("   No recent log events found")
        return

    # First, try to parse and show a nice summary
    results = parse_sync_results(events)
    if results:
        display_sync_summary(results)

    # Show raw logs if verbose
    if verbose:
        print(f"\n📜 Raw Log Entries ({len(events)} found):\n")

        for event in events[:20]:
            timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
            message = event["message"].strip()

            # Truncate long messages
            if len(message) > 200:
                message = message[:200] + "..."

            # Color-code based on content
            if "ERROR" in message or "error" in message:
                prefix = "❌"
            elif "SUCCESS" in message or "synced" in message.lower():
                prefix = "✅"
            elif "START" in message or "END" in message:
                prefix = "🔄"
            else:
                prefix = "  "

            print(f"   {prefix} [{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def invoke_lambda(lambda_client: boto3.client) -> dict | None:
    """Invoke the Lambda function manually."""
    print("\n🚀 Invoking Lambda function...")

    payload = {
        "source": "manual_test",
        "action": "daily_sync",
    }

    try:
        response = lambda_client.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType="RequestResponse",
            LogType="Tail",
            Payload=json.dumps(payload),
        )

        # Decode the response
        response_payload = json.loads(response["Payload"].read().decode())

        if response.get("FunctionError"):
            print(f"   ❌ Function Error: {response['FunctionError']}")
            print(f"   {json.dumps(response_payload, indent=2, default=str)}")
            return None

        print("   ✅ Function executed successfully")

        # Display the response nicely
        print("\n" + "=" * 60)
        print("📤 LAMBDA RESPONSE")
        print("=" * 60)

        body = response_payload.get("body")
        if body:
            if isinstance(body, str):
                body = json.loads(body)

            print(f"\n   Status: {body.get('status', 'N/A')}")
            print(f"   Message: {body.get('message', 'N/A')}")

            if "results" in body:
                results = body["results"]
                print(f"\n   📊 Sync Results:")
                print(f"      Total runs synced: {results.get('total_runs_synced', 0)}")
                print(f"      Sources processed: {results.get('sources_processed', 0)}")
                print(f"      Failures: {results.get('failures', 0)}")

                if results.get("details"):
                    print(f"\n   📋 Details per source:")
                    for detail in results["details"]:
                        status_icon = "✅" if detail.get("status") == "success" else "❌"
                        print(f"      {status_icon} {detail.get('source_type', 'unknown')}: {detail.get('runs_synced', 0)} runs")

        print("\n" + "=" * 60)

        return response_payload

    except ClientError as e:
        print(f"   ❌ Error invoking Lambda: {e}")
        return None


def check_api_health() -> None:
    """Check API Gateway health endpoint."""
    import urllib.request

    print("\n🌐 API Gateway Health Check:")

    try:
        with urllib.request.urlopen(f"{API_GATEWAY_URL}/health", timeout=10) as response:
            data = json.loads(response.read().decode())
            print(f"   ✅ API Gateway is healthy")
            print(f"   Status: {data.get('status')}")
            print(f"   Environment: {data.get('environment')}")
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test the scheduled sync Lambda")
    parser.add_argument(
        "--invoke",
        action="store_true",
        help="Invoke the Lambda manually",
    )
    parser.add_argument(
        "--logs-only",
        action="store_true",
        help="Only show recent logs",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show raw log entries",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours of logs to fetch (default: 24)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🧪 MyRunStreak Scheduled Sync Test")
    print("=" * 60)

    # Check API health first (doesn't require AWS creds)
    check_api_health()

    # Get AWS clients
    try:
        lambda_client, logs_client, events_client = get_aws_clients()

        # Get AWS account info
        sts = boto3.client("sts", region_name=AWS_REGION)
        identity = sts.get_caller_identity()
        print(f"\n🔑 AWS Account: {identity['Account']}")
        print(f"   Region: {AWS_REGION}")

        if identity["Account"] != "855323747881":
            print("\n⚠️  WARNING: You are not using the correct AWS account!")
            print("   Expected: 855323747881")
            print("   Current:  " + identity["Account"])
            print("\n   To fix, set environment variables or AWS_PROFILE:")
            print("   export AWS_PROFILE=silverbeer")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ AWS credentials error: {e}")
        print("\n   Make sure you have AWS credentials configured.")
        print("   Try: export AWS_PROFILE=silverbeer")
        sys.exit(1)

    if args.logs_only:
        events = get_recent_logs(logs_client, args.hours)
        display_logs(events, verbose=args.verbose)
        return

    # Check Lambda exists
    print("\n" + "-" * 60)
    if not check_lambda_exists(lambda_client):
        sys.exit(1)

    # Check EventBridge rules
    check_eventbridge_rules(events_client)

    # Get recent logs and show summary
    events = get_recent_logs(logs_client, args.hours)
    display_logs(events, verbose=args.verbose)

    # Optionally invoke
    if args.invoke:
        print("\n" + "-" * 60)
        invoke_lambda(lambda_client)

        # Wait a moment and show new logs
        print("\n⏳ Waiting 5 seconds for logs to propagate...")
        import time
        time.sleep(5)

        print("\n📜 Fetching updated logs after invocation...")
        events = get_recent_logs(logs_client, hours=1, quiet=True)
        display_logs(events, verbose=args.verbose)

    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
