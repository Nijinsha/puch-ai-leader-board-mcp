

# =========================
# Imports and Configuration
# =========================
import re
import difflib
from textwrap import dedent
import asyncio
import json
import logging
import sqlite3
import time
import os
from datetime import datetime
import pytz
from typing import Any, Dict, List
import aiohttp
from dotenv import load_dotenv
from fastmcp import FastMCP

# ================
# Helper Functions
# ================
def emoji_bar(value: int, max_value: int, length: int = 10, emoji: str = '🟩') -> str:
    """Create an emoji-based progress bar.
    
    Args:
        value: Current value to represent
        max_value: Maximum value for scaling
        length: Maximum number of emoji characters to use
        emoji: The emoji character to use for the bar
        
    Returns:
        A string of emojis representing the value as a proportion of max_value
    """
    if max_value == 0:
        return ''
    bars = int((value / max_value) * length)
    return emoji * bars

def sanitize_response(text: str) -> str:
    # Remove special characters except emojis and common punctuation
    return re.sub(r"[<>{}\\^`$|~]", "", text)

# ================
# App Setup
# ================
# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get authentication token from .env
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "default-secure-token")
MY_NUMBER = os.getenv("MY_NUMBER", "Unknown")

# Create FastMCP server instance with version
app = FastMCP("puch-leaderboard-mcp", version="1.1.0")

# =====================
# About Tool (Discovery)
# =====================
@app.tool("about", description="Get the MCP server name and description for discovery and documentation.")
async def about() -> str:
    server_name = "Puch AI Leaderboard MCP"
    server_description = dedent("""
    This MCP server provides leaderboard and analytics tools for the Puch AI Hackathon. It enables LLMs, chatbots, and WhatsApp clients to query the top teams, compare team stats, and get minimal, branded leaderboard output. All endpoints are designed for easy integration and minimal, WhatsApp-friendly formatting.
    """)
    response = {
        "name": server_name,
        "description": server_description.strip()
    }
    return json.dumps(response)

# --- Tool: Team Comparison ---
@app.tool("compare_teams")
async def compare_teams_tool(team_names: str) -> str:
    """Compare two or more teams side-by-side by unique visitors and team size.
    
    Returns:
        str: JSON string containing comparison data with structure:
        {
            "status": "success" | "error",
            "message": str,  # Only for error responses
            "teams": List[Dict[str, Any]],  # List of team comparisons
            "notes": List[str]  # Fuzzy matching notes
        }
    """
    import aiohttp
    import difflib
    names = [name.strip() for name in team_names.split(",") if name.strip()]
    if len(names) < 2:
        error_response = {
            "status": "error",
            "message": "Please provide at least two team names separated by commas"
        }
        return json.dumps(error_response)
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.puch.ai/hackathon-leaderboard?page=1&limit=20"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
            }
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return add_powered_by("❌ *Error*\n\nCould not fetch leaderboard data from API.")
                data = await resp.json()
        leaderboard = data.get("leaderboard", [])
        all_teams = [team.get("team_name", "") for team in leaderboard]
        matched_names = []
        notes = []
        for name in names:
            match = difflib.get_close_matches(name, all_teams, n=1, cutoff=0.6)
            actual = match[0] if match else name
            matched_names.append(actual)
            if actual != name:
                notes.append(f"'{name}'→'{actual}'")
        teams = [t for t in leaderboard if t.get("team_name") in matched_names]
        if not teams:
            error_response = {
                "status": "error",
                "message": "No data found for the given teams",
                "powered_by": "https://puch.ai/mcp/4I2A7Z5bWA"
            }
            return json.dumps(error_response)

        teams_data = []
        for idx, team in enumerate(teams, 1):
            team_name = team.get("team_name", "?")
            visitors = team.get("unique_visitors", 0)
            submissions = team.get("submissions", [])
            total_invocations = sum(sub.get("mcp_metrics", {}).get("invocations_total", 0) for sub in submissions)
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}\u20E3" if 4 <= idx <= 9 else f"{idx}."
            
            teams_data.append({
                "rank": idx,
                "medal": medal,
                "name": team_name,
                "metrics": {
                    "visitors": visitors,
                    "invocations": total_invocations
                }
            })
        
        response = {
            "status": "success",
            "teams": teams_data,
            "notes": notes if notes else [],
            "powered_by": "https://puch.ai/mcp/4I2A7Z5bWA"
        }
        return json.dumps(response)
    except Exception as e:
        error_response = {
            "status": "error",
            "message": f"Error comparing teams: {str(e)}"
        }
        return json.dumps(error_response)

# --- Tool: Milestone Alerts ---
MILESTONES = [1000, 5000, 10000, 25000, 50000]

@app.tool("milestone_alert")
async def milestone_alert_tool(team_name: str) -> str:
    """Notify if a team has reached a visitor milestone.
    
    Returns:
        str: JSON string containing milestone data with structure:
        {
            "status": "success" | "error",
            "message": str,  # Error message if status is error
            "team": {
                "name": str,
                "rank": int,
                "medal": str,
                "metrics": {
                    "visitors": int,
                    "invocations": int
                }
            }
        }
    """
    import aiohttp
    import difflib
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.puch.ai/hackathon-leaderboard?page=1&limit=20"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
            }
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    error_response = {
                        "status": "error",
                        "message": "Could not fetch leaderboard data from API"
                    }
                    return json.dumps(error_response)
                data = await resp.json()
        leaderboard = data.get("leaderboard", [])
        all_teams = [team.get("team_name", "") for team in leaderboard]
        match = difflib.get_close_matches(team_name, all_teams, n=1, cutoff=0.6)
        actual_team = match[0] if match else team_name
        team = next((t for t in leaderboard if t.get("team_name") == actual_team), None)
        if not team:
            error_response = {
                "status": "error",
                "message": f"No data found for team: {team_name}"
            }
            return json.dumps(error_response)
        unique_visitors = team.get("unique_visitors", 0)
        submissions = team.get("submissions", [])
        total_invocations = sum(sub.get("mcp_metrics", {}).get("invocations_total", 0) for sub in submissions)
        rank = all_teams.index(actual_team) + 1 if actual_team in all_teams else "N/A"
        if rank == 1:
            medal = "🥇"
        elif rank == 2:
            medal = "🥈"
        elif rank == 3:
            medal = "🥉"
        elif 4 <= rank <= 9:
            medal = f"{rank}\u20E3"
        else:
            medal = f"{rank}."
        response = {
            "status": "success",
            "team": {
                "name": actual_team,
                "rank": rank,
                "medal": medal,
                "metrics": {
                    "visitors": unique_visitors,
                    "invocations": total_invocations
                }
            }
        }
        return json.dumps(response)
    except Exception as e:
        error_response = {
            "status": "error",
            "message": f"Error checking milestone: {str(e)}"
        }
        return json.dumps(error_response)

# --- Tool: Personalized Stats (Subscribe) ---
subscriptions = {}  # user_id -> team_name

@app.tool("subscribe_team")
async def subscribe_team_tool(user_id: str, team_name: str) -> str:
    """Subscribe a user to a team for updates (in-memory demo)."""
    if not user_id or not team_name:
        return "❌ *Error*\n\nUser ID and team name required."
    # Fuzzy match team name
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT DISTINCT team_name FROM leaderboard')
        all_teams = [row[0] for row in cursor.fetchall()]
        match = difflib.get_close_matches(team_name, all_teams, n=1, cutoff=0.6)
        actual_team = match[0] if match else team_name
        subscriptions[user_id] = actual_team
        note = f" (subscribed to '{actual_team}')" if actual_team != team_name else ""
        response = {
            "status": "success",
            "message": f"User {user_id} will receive updates for team: {actual_team}",
            "note": note if note else None
        }
        return json.dumps(response)
    except Exception as e:
        error_response = {
            "status": "error",
            "message": f"Error subscribing: {str(e)}"
        }
        return json.dumps(error_response)
    finally:
        conn.close()

@app.tool("my_team_stats")
async def my_team_stats_tool(user_id: str) -> str:
    """Get personalized stats for the user's subscribed team."""
    team_name = subscriptions.get(user_id)
    if not team_name:
        error_response = {
            "status": "error",
            "message": "Not subscribed. Use 'subscribe_team' to subscribe."
        }
        return json.dumps(error_response)
    return await get_leaderboard_stats_tool(team_name)

# --- Tool: Top Movers ---
previous_ranks = {}  # team_name -> previous rank

def get_current_ranks():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''SELECT team_name, unique_visitors FROM leaderboard GROUP BY team_name ORDER BY unique_visitors DESC''')
        rows = cursor.fetchall()
        ranks = {row[0]: i+1 for i, row in enumerate(rows)}
        return ranks
    except Exception:
        return {}
    finally:
        conn.close()

@app.tool("top_movers")
async def top_movers_tool() -> str:
    """Show teams that have moved up or down the most since the last update."""
    global previous_ranks
    current_ranks = get_current_ranks()
    if not previous_ranks:
        previous_ranks = current_ranks.copy()
        response = {
            "status": "info",
            "message": "Tracking started. Please check again after the next update."
        }
        return json.dumps(response)
    # Calculate movement
    movement = []
    for team, curr_rank in current_ranks.items():
        prev_rank = previous_ranks.get(team, curr_rank)
        change = prev_rank - curr_rank  # positive = moved up
        if change != 0:
            movement.append((team, change))
    # Sort by biggest movers
    movement.sort(key=lambda x: abs(x[1]), reverse=True)
    
    response = {
        "status": "success",
        "movements": []
    }
    
    if not movement:
        response["message"] = "No significant changes since last update"
    else:
        for team, change in movement[:5]:
            response["movements"].append({
                "team": team,
                "change": change,
                "direction": "up" if change > 0 else "down"
            })
    
    previous_ranks = current_ranks.copy()
    return json.dumps(response)
# Enhanced leaderboard with server info and metrics
@app.tool(
    name="top_n_leaderboard",
    description="""
MCP Tool: Top N Leaderboard

Use case: Get top N teams with server info, visitors, and invocations.

Request:
- n (int): Number of teams (default: 5)

Response Format (JSON-like):
- Rank emoji + Team name
- Visitors count
- Invocations total
- Server name (if available)
- Server description preview (first 50 chars)
- Tools used

Example:
🥇 TeamName [Server: VibeServer]
   👀 1410 visitors | ⚡️ 282 calls
   🛠️ Tools: tool1, tool2
   � About: AI-powered mood planner and recommendations"""
)
async def top_n_leaderboard_tool(n: int = 5) -> str:
    """Get top N teams with server info, visitors, and tool usage stats.
    
    Args:
        n: Number of teams to return (default: 5)
    
    Returns:
        str: JSON string containing team data with structure:
        {
            "status": str,  # "success" or "error"
            "total_teams": int,
            "teams": List[Dict[str, Any]]  # List of team data dictionaries
        }

        Team data dictionary structure:
        {
            "rank": int,
            "medal": str,
            "name": str,
            "server": {
                "name": str,
                "description": str
            },
            "metrics": {
                "visitors": int,
                "invocations": int
            },
            "tools": List[str]
        }
    """
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.puch.ai/hackathon-leaderboard?page=1&limit=20"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
            }
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return add_powered_by("❌ *Error*\n\nCould not fetch leaderboard data from API.")
                data = await resp.json()
        leaderboard = data.get("leaderboard", [])
        if not leaderboard:
            return {
                "status": "error",
                "message": "No data available",
                "powered_by": "https://puch.ai/mcp/4I2A7Z5bWA"
            }
            
        teams_data = []
        for i, team in enumerate(leaderboard[:n], 1):
            team_name = team.get("team_name", "?")
            visitors = team.get("unique_visitors", 0)
            submissions = team.get("submissions", [])
            total_invocations = sum(sub.get("mcp_metrics", {}).get("invocations_total", 0) for sub in submissions)
            
            # Get server info from latest submission
            latest_submission = submissions[0] if submissions else {}
            server_name = latest_submission.get("server_name", "")
            server_desc = latest_submission.get("server_description", "")
            if server_desc:
                server_desc = server_desc.split("\n")[0][:50] + ("..." if len(server_desc) > 50 else "")

            # Get unique tools used
            tools_used = set()
            for sub in submissions:
                metrics = sub.get("mcp_metrics", {})
                tools_used.update(metrics.get("tool_invocations", {}).keys())
            
            # Format rank emoji
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}\u20E3" if 4 <= i <= 9 else f"{i}."
            
            # Build team data
            team_data = {
                "rank": i,
                "medal": medal,
                "name": team_name,
                "server": {
                    "name": server_name,
                    "description": server_desc
                },
                "metrics": {
                    "visitors": visitors,
                    "invocations": total_invocations
                },
                "tools": sorted(list(tools_used))[:3]
            }
            teams_data.append(team_data)
            
        # Create the final structured response
        response = {
            "status": "success",
            "total_teams": len(teams_data),
            "teams": teams_data
        }
        
        # Convert dictionary to JSON string
        return json.dumps(response)
    except Exception as e:
        error_response = {
            "status": "error",
            "message": f"Error retrieving leaderboard: {str(e)}",
            "powered_by": "https://puch.ai/mcp/4I2A7Z5bWA"
        }
        return json.dumps(error_response)

# Store for bearer tokens
bearer_tokens: Dict[str, str] = {}

# Database setup
DB_PATH = "puch_leaderboard.db"
LEADERBOARD_URL = "https://api.puch.ai/hackathon-leaderboard"

def init_database() -> None:
    """Initialize SQLite database with required schema.
    
    Creates the following:
    1. leaderboard table with team data
    2. Index on team_name for faster lookups
    
    Schema:
    - id: Unique identifier for each record
    - team_name: Name of the team
    - server_id: Unique identifier for the team's server
    - submitted_at: Timestamp of submission
    - visitors: Total number of visitors
    - unique_visitors: Number of unique visitors
    - team_size: Number of team members
    - last_updated: Timestamp of last update
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Create leaderboard table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_name TEXT NOT NULL,
                server_id TEXT,
                submitted_at TEXT,
                visitors INTEGER,
                unique_visitors INTEGER,
                team_size INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create index for faster lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_team_name ON leaderboard(team_name)')
        
        conn.commit()
        logger.info("Database initialized successfully")
        
    except sqlite3.Error as e:
        logger.error(f"Database initialization failed: {e}")
        conn.rollback()
        raise
        
    finally:
        conn.close()

# Initialize database when module is imported
init_database()

async def seed_initial_data():
    """Seed initial leaderboard data on startup if database is empty."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if database has any data
        cursor.execute('SELECT COUNT(*) FROM leaderboard')
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.info("Database is empty, seeding initial data...")
            # Fetch and store initial data
            leaderboard_data = await fetch_leaderboard()
            if leaderboard_data:
                store_leaderboard_data(leaderboard_data)
                logger.info("Initial data seeded successfully")
            else:
                logger.warning("Failed to fetch initial data")
        else:
            logger.info(f"Database already has {count} records, skipping initial seed")
            
    except Exception as e:
        logger.error(f"Error seeding initial data: {e}")
    finally:
        conn.close()


# Start initial data seed and background sync when module is imported
async def startup_tasks():
    await seed_initial_data()
    asyncio.create_task(sync_leaderboard())

asyncio.create_task(startup_tasks())

async def fetch_leaderboard():
    """Fetch leaderboard data from Puch AI API."""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:137.0) Gecko/20100101 Firefox/137.0',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://puch.ai/',
                'Origin': 'https://puch.ai'
            }
            
            async with session.get(f"{LEADERBOARD_URL}?page=1&limit=100", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('leaderboard', [])
                else:
                    logger.error(f"Failed to fetch leaderboard: {response.status}")
                    return []
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        return []

def store_leaderboard_data(leaderboard_data: List[Dict]):
    """Store leaderboard data in SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Clear existing data
        cursor.execute('DELETE FROM leaderboard')
        
        # Insert new data
        for team in leaderboard_data:
            team_name = team.get('team_name', '')
            unique_visitors = team.get('unique_visitors', 0)
            team_size = team.get('team_size', 0)
            
            for submission in team.get('submissions', []):
                cursor.execute('''
                    INSERT INTO leaderboard 
                    (team_name, server_id, submitted_at, visitors, unique_visitors, team_size, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    team_name,
                    submission.get('server_id', ''),
                    submission.get('submitted_at', ''),
                    submission.get('visitors', 0),
                    unique_visitors,
                    team_size,
                    datetime.now().isoformat()
                ))
        
        conn.commit()
        logger.info(f"Stored {len(leaderboard_data)} teams in database")
        
    except Exception as e:
        logger.error(f"Error storing leaderboard data: {e}")
        conn.rollback()
    finally:
        conn.close()

async def sync_leaderboard():
    """Background task to sync leaderboard every 30 seconds."""
    while True:
        try:
            logger.info("Syncing leaderboard...")
            leaderboard_data = await fetch_leaderboard()
            if leaderboard_data:
                store_leaderboard_data(leaderboard_data)
            else:
                logger.warning("No leaderboard data received")
        except Exception as e:
            logger.error(f"Error in leaderboard sync: {e}")
        
        await asyncio.sleep(30)

def get_team_stats(team_name: str) -> Dict[str, Any]:
    """Get team statistics from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Fuzzy match team name
        cursor.execute('SELECT DISTINCT team_name FROM leaderboard')
        all_teams = [row[0] for row in cursor.fetchall()]
        match = difflib.get_close_matches(team_name, all_teams, n=1, cutoff=0.6)
        actual_team = match[0] if match else team_name
        # Get team data
        cursor.execute('''
            SELECT team_name, server_id, submitted_at, visitors, unique_visitors, team_size, last_updated
            FROM leaderboard 
            WHERE team_name = ?
            ORDER BY visitors DESC
        ''', (actual_team,))
        rows = cursor.fetchall()
        if not rows:
            return json.dumps({"error": f"Team '{team_name}' not found"})
        # Process data
        team_data = {
            "team_name": rows[0][0],
            "unique_visitors": rows[0][4],
            "team_size": rows[0][5],
            "last_updated": rows[0][6],
            "submissions": []
        }
        for row in rows:
            submission = {
                "server_id": row[1],
                "submitted_at": row[2],
                "visitors": row[3]
            }
            team_data["submissions"].append(submission)
        # If fuzzy match was used, add a note
        if actual_team != team_name:
            team_data["fuzzy_note"] = f"(Showing results for '{actual_team}')"
        return json.dumps(team_data)
    except Exception as e:
        logger.error(f"Error getting team stats: {e}")
        error_response = {"error": f"Database error: {str(e)}"}
        return json.dumps(error_response)
    finally:
        conn.close()

# --- Tool: validate (required by Puch) ---
@app.tool
async def validate() -> str:
    """Required by Puch - returns MY_NUMBER from .env"""
    return MY_NUMBER

@app.tool("bearer_token")
async def bearer_token_tool(action: str, token: str = None, user_id: str = None) -> str:
    """Generate or validate bearer tokens."""
    if action == "generate":
        user_id = user_id or "default_user"
        # Generate a simple token (in production, use proper JWT or similar)
        import secrets
        token = f"bearer_{secrets.token_urlsafe(32)}"
        bearer_tokens[user_id] = token
        return f"🔑 *Token Generated Successfully*\n\n👤 User ID: {user_id}\n🔑 Token: `{token}`\n\n✅ Token has been created and stored"
    
    elif action == "validate":
        if not token:
            return "❌ *Validation Failed*\n\n🔑 Token is required for validation"
        
        if token in bearer_tokens.values():
            user_id = next(k for k, v in bearer_tokens.items() if v == token)
            return f"✅ *Token Validation Successful*\n\n🔑 Token: `{token}`\n👤 User ID: {user_id}\n\n✅ Token is valid and active"
        else:
            return f"❌ *Token Validation Failed*\n\n🔑 Token: `{token}`\n\n❌ Token not found or expired"
    
    elif action == "revoke":
        if not token:
            return "❌ *Revocation Failed*\n\n🔑 Token is required for revocation"
        
        if token in bearer_tokens.values():
            user_id = next(k for k, v in bearer_tokens.items() if v == token)
            del bearer_tokens[user_id]
            return f"🗑️ *Token Revoked Successfully*\n\n🔑 Token: `{token}`\n👤 User ID: {user_id}\n\n✅ Token has been removed from the system"
        else:
            return f"❌ *Revocation Failed*\n\n🔑 Token: `{token}`\n\n❌ Token not found"
    
    else:
        return f"❌ *Action Failed*\n\n❓ Unknown action: {action}"

@app.tool("data_validation")
async def data_validation_tool(data: str, type: str) -> str:
    """Validate input data or tokens."""
    if type == "token":
        # Validate if token exists and is valid
        if data in bearer_tokens.values():
            return "✅ *Token Validation Successful*\n\n🔑 Token is valid and active"
        else:
            return "❌ *Token Validation Failed*\n\n🔑 Token is invalid or expired"
    elif type == "data":
        # Basic data validation
        if data and len(data.strip()) > 0:
            return "✅ *Data Validation Successful*\n\n📝 Data is valid and properly formatted"
        else:
            return "❌ *Data Validation Failed*\n\n📝 Data is empty or invalid"
    elif type == "format":
        # Format validation (basic JSON check)
        try:
            json.loads(data)
            return "✅ *Format Validation Successful*\n\n📋 Data format is valid JSON"
        except json.JSONDecodeError:
            return "❌ *Format Validation Failed*\n\n📋 Data format is invalid JSON"
    else:
        return f"❌ *Validation Error*\n\n❓ Unknown validation type: {type}"

@app.tool("health_check")
async def health_check_tool() -> str:
    """Check server health status."""
    return f"""🟢 *Server Health Check*

🏗️ Server: puch-leaderboard-mcp
📊 Version: 0.1.0
🔑 Active Tokens: {len(bearer_tokens)}
💾 Database: SQLite
🔄 Leaderboard Sync: Active
⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ Server is running smoothly and all systems are operational"""



@app.tool("get_leaderboard_stats")
async def get_leaderboard_stats_tool(team_name: str) -> str:
    """Get Puch AI leaderboard statistics for a specific team."""
    if not team_name:
        return add_powered_by("❌ *Error*\n\n📝 Team name is required")
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.puch.ai/hackathon-leaderboard?page=1&limit=20"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
            }
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return add_powered_by("❌ *Error*\n\nCould not fetch leaderboard data from API.")
                data = await resp.json()
        leaderboard = data.get("leaderboard", [])
        import difflib
        all_teams = [team.get("team_name", "") for team in leaderboard]
        match = difflib.get_close_matches(team_name, all_teams, n=1, cutoff=0.6)
        actual_team = match[0] if match else team_name
        team = next((t for t in leaderboard if t.get("team_name") == actual_team), None)
        if not team:
            return add_powered_by(f"❌ *Team Not Found*\n\n🔍 No data for team: {team_name}")
        unique_visitors = team.get("unique_visitors", 0)
        submissions = team.get("submissions", [])
        total_invocations = sum(sub.get("mcp_metrics", {}).get("invocations_total", 0) for sub in submissions)
        rank = all_teams.index(actual_team) + 1 if actual_team in all_teams else "N/A"
        if rank == 1:
            medal = "🥇"
        elif rank == 2:
            medal = "🥈"
        elif rank == 3:
            medal = "�"
        elif 4 <= rank <= 9:
            medal = f"{rank}\u20E3"
        else:
            medal = f"{rank}."
        safe_team_name = sanitize_response(actual_team)
        result = f"{medal} {safe_team_name}\n   👀 Unique Visitors: {unique_visitors}\n   ⚡️ Invocations: {total_invocations}\n"
        return add_powered_by(result)
    except Exception as e:
        return add_powered_by(f"❌ *Error*\n\n🔍 Error retrieving team stats: {str(e)}")

@app.tool("refresh_leaderboard")
async def refresh_leaderboard_tool() -> str:
    """Manually refresh leaderboard data from Puch AI API."""
    try:
        logger.info("Manual leaderboard refresh requested...")
        leaderboard_data = await fetch_leaderboard()
        if leaderboard_data:
            store_leaderboard_data(leaderboard_data)
            return sanitize_response(f"""🔄 *Leaderboard Refreshed Successfully!*

📊 {len(leaderboard_data)} teams updated

✅ Data has been synchronized with Puch AI API""")
        else:
            return sanitize_response(f"""❌ *Refresh Failed*

📊 No data received from API
💡 Please check your internet connection""")
    except Exception as e:
        return sanitize_response(f"""❌ *Refresh Error*

🔍 Error: {str(e)}""")

@app.tool("database_status")
async def database_status_tool() -> str:
    """Get current database status and statistics."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        # Get total records
        cursor.execute('SELECT COUNT(*) FROM leaderboard')
        total_records = cursor.fetchone()[0]

        # Get unique teams
        cursor.execute('SELECT COUNT(DISTINCT team_name) FROM leaderboard')
        unique_teams = cursor.fetchone()[0]

        # Get top 5 teams by visitors
        cursor.execute('''
            SELECT team_name, unique_visitors, team_size
            FROM leaderboard 
            GROUP BY team_name 
            ORDER BY unique_visitors DESC 
            LIMIT 5
        ''')
        top_teams = []
        for row in cursor.fetchall():
            top_teams.append({
                "team_name": row[0],
                "unique_visitors": row[1],
                "team_size": row[2]
            })

        # Add emoji based on data status
        if total_records > 0:
            status_emoji = "🟢"
            status_message = "Database is healthy and contains data"
        else:
            status_emoji = "🟡"
            status_message = "Database is empty, waiting for initial data"

        # Format for WhatsApp
        result = f"{status_emoji} *Database Status*\n\n"
        result += f"📊 Total Records: {total_records:,}\n"
        result += f"👥 Unique Teams: {unique_teams}\n"
        # Last Update removed as per request
        result += f"🔄 Sync Status: Active (30s interval)\n\n"

        if top_teams:
            result += "🏆 *Top Teams:*\n"
            for i, team in enumerate(top_teams[:3], 1):
                if i == 1:
                    medal = "🥇"
                elif i == 2:
                    medal = "🥈"
                elif i == 3:
                    medal = "🥉"
                else:
                    medal = f"{i}️⃣"
                result += f"{medal} {team['team_name']} ({team['unique_visitors']:,} visitors)\n"

        return sanitize_response(result)
    except Exception as e:
        return sanitize_response(f"❌ *Database Error*\n\n🔍 Error getting database status: {str(e)}")
    finally:
        conn.close()
async def main():
    """Main entry point."""
    await app.run()

if __name__ == "__main__":
    asyncio.run(main())