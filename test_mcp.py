#!/usr/bin/env python3
"""Test script for the FastMCP server."""

import asyncio
import json
import subprocess
import sys
from typing import Dict, Any

async def test_fastmcp_server():
    """Test the FastMCP server by sending requests."""
    
    # Start the FastMCP server as a subprocess
    process = subprocess.Popen(
        [sys.executable, "main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Test 1: List tools
        print("Testing: List tools")
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        process.stdin.write(json.dumps(list_tools_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        print(f"Response: {response}")
        
        # Test 2: Validate (required by Puch)
        print("\nTesting: Validate (Puch required)")
        validate_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "validate",
                "arguments": {}
            }
        }
        
        process.stdin.write(json.dumps(validate_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        print(f"Response: {response}")
        
        # Test 3: Data validation
        print("\nTesting: Data validation")
        data_validation_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "data_validation",
                "arguments": {
                    "data": "test data",
                    "type": "data"
                }
            }
        }
        
        process.stdin.write(json.dumps(data_validation_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        print(f"Response: {response}")
        
        # Test 4: Health check
        print("\nTesting: Health check")
        health_check_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "health_check",
                "arguments": {}
            }
        }
        
        process.stdin.write(json.dumps(health_check_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        print(f"Response: {response}")
        
        # Test 5: Generate bearer token
        print("\nTesting: Generate bearer token")
        generate_token_request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "bearer_token",
                "arguments": {
                    "action": "generate",
                    "user_id": "test_user"
                }
            }
        }
        
        process.stdin.write(json.dumps(generate_token_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        print(f"Response: {response}")
        
        # Test 6: Get leaderboard stats
        print("\nTesting: Get leaderboard stats")
        leaderboard_request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "get_leaderboard_stats",
                "arguments": {
                    "team_name": "InfiniteCoffee"
                }
            }
        }
        
        process.stdin.write(json.dumps(leaderboard_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        print(f"Response: {response}")
        
        # Test 7: Database status
        print("\nTesting: Database status")
        db_status_request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "database_status",
                "arguments": {}
            }
        }
        
        process.stdin.write(json.dumps(db_status_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        print(f"Response: {response}")
        
        # Test 8: Refresh leaderboard
        print("\nTesting: Refresh leaderboard")
        refresh_request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "refresh_leaderboard",
                "arguments": {}
            }
        }
        
        process.stdin.write(json.dumps(refresh_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        print(f"Response: {response}")
        
        # Test 9: Top 5 leaderboard
        print("\nTesting: Top 5 leaderboard")
        top5_request = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {
                "name": "top_5_leaderboard",
                "arguments": {}
            }
        }
        
        process.stdin.write(json.dumps(top5_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        print(f"Response: {response}")
        
        # Test 10: Top 10 leaderboard
        print("\nTesting: Top 10 leaderboard")
        top10_request = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "top_10_leaderboard",
                "arguments": {}
            }
        }
        
        process.stdin.write(json.dumps(top10_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        print(f"Response: {response}")
        
    finally:
        # Clean up
        process.terminate()
        process.wait()
        print("\nFastMCP server test completed.")

if __name__ == "__main__":
    asyncio.run(test_fastmcp_server())
