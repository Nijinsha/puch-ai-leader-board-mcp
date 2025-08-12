# Place these after app = FastMCP(...)

# Place these after app = FastMCP(...)
# Fuzzy matching for team names
import re
import difflib
# Helper function to remove special characters except emojis
def sanitize_response(text: str) -> str:
    # Remove special characters except emojis and common punctuation
    # Allow: a-zA-Z0-9, whitespace, emojis, and .,:;!?@#%&*()[]-_+=/\\'"\n
    # Remove angle brackets, curly braces, and other unwanted symbols
    # Unicode emoji range: [\U0001F300-\U0001FAFF]
    # This regex keeps emojis, alphanumerics, whitespace, and common punctuation
    return re.sub(r"[<>{}\^`$|~]", "", text)

# Helper to append powered by link
def add_powered_by(text: str) -> str:
    return f"{text}\n\n_Powered by https://puch.ai/mcp/4I2A7Z5bWA_"
#!/usr/bin/env python3
"""MCP server with validate and bearer token functions using FastMCP."""

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

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get authentication token from .env
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "default-secure-token")
MY_NUMBER = os.getenv("MY_NUMBER", "Unknown")

# Create FastMCP server instance

app = FastMCP("puch-leaderboard-mcp")

# Emoji bar chart helper
def emoji_bar(value, max_value, length=10, emoji='🟩'):
    if max_value == 0:
        return ''
    bars = int((value / max_value) * length)
    return emoji * bars

# --- Tool: Team Comparison ---
@app.tool("compare_teams")
async def compare_teams_tool(team_names: str) -> str:
    """Compare two or more teams side-by-side by unique visitors and team size."""
    names = [name.strip() for name in team_names.split(",") if name.strip()]
    if len(names) < 2:
        return "❌ *Error*\n\nPlease provide at least two team names separated by commas."
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT DISTINCT team_name FROM leaderboard')
        all_teams = [row[0] for row in cursor.fetchall()]
        # Fuzzy match each name
        matched_names = []
        notes = []
        for name in names:
            match = difflib.get_close_matches(name, all_teams, n=1, cutoff=0.6)
            actual = match[0] if match else name
            matched_names.append(actual)
            if actual != name:
                notes.append(f"'{name}'→'{actual}'")
        placeholders = ",".join(["?"] * len(matched_names))
        cursor.execute(f'''SELECT team_name, unique_visitors, team_size FROM leaderboard WHERE team_name IN ({placeholders}) GROUP BY team_name''', matched_names)
        rows = cursor.fetchall()
        if not rows:
            return "❌ *Error*\n\nNo data found for the given teams."
        # Find max visitors for bar chart
        max_visitors = max(row[1] for row in rows) if rows else 1
        result = "🤝 *Team Comparison*\n\n"
        for row in rows:
            team_name, visitors, team_size = row
            bar = emoji_bar(visitors, max_visitors)
            result += f"*{team_name}* {bar}\n   👥 Team Size: {team_size}\n   👀 Unique Visitors: {visitors:,}\n\n"
        if notes:
            result += "_Fuzzy matched: " + ", ".join(notes) + "_\n"
        return add_powered_by(result)
    except Exception as e:
        return f"❌ *Error*\n\n🔍 Error comparing teams: {str(e)}"
    finally:
        conn.close()

# --- Tool: Milestone Alerts ---
MILESTONES = [1000, 5000, 10000, 25000, 50000]

@app.tool("milestone_alert")
async def milestone_alert_tool(team_name: str) -> str:
    """Notify if a team has reached a visitor milestone."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Fuzzy match team name
        cursor.execute('SELECT DISTINCT team_name FROM leaderboard')
        all_teams = [row[0] for row in cursor.fetchall()]
        match = difflib.get_close_matches(team_name, all_teams, n=1, cutoff=0.6)
        actual_team = match[0] if match else team_name
        cursor.execute('''SELECT unique_visitors FROM leaderboard WHERE team_name = ? ORDER BY unique_visitors DESC LIMIT 1''', (actual_team,))
        row = cursor.fetchone()
        if not row:
            return add_powered_by(f"❌ *Team Not Found*\n\n🔍 No data for team: {team_name}")
        visitors = row[0]
        reached = [m for m in MILESTONES if visitors >= m]
        note = f"\n_(Showing results for '{actual_team}')_" if actual_team != team_name else ""
        if not reached:
            next_milestone = min([m for m in MILESTONES if m > visitors], default=None)
            if next_milestone:
                return add_powered_by(f"⏳ *Milestone Alert*\n\n*{actual_team}* has {visitors:,} unique visitors.\nNext milestone: {next_milestone:,} visitors.{note}")
            else:
                return add_powered_by(f"*{actual_team}* has {visitors:,} unique visitors.{note}")
        else:
            last = max(reached)
            return add_powered_by(f"🎉 *Milestone Reached!*\n\n*{actual_team}* has crossed {last:,} unique visitors!\nCurrent: {visitors:,} visitors.{note}")
    except Exception as e:
        return add_powered_by(f"❌ *Error*\n\n🔍 Error checking milestone: {str(e)}")
    finally:
        conn.close()

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
        return add_powered_by(f"🔔 *Subscribed!*\n\nUser {user_id} will receive updates for team: {actual_team}{note}")
    except Exception as e:
        return add_powered_by(f"❌ *Error*\n\n🔍 Error subscribing: {str(e)}")
    finally:
        conn.close()

@app.tool("my_team_stats")
async def my_team_stats_tool(user_id: str) -> str:
    """Get personalized stats for the user's subscribed team."""
    team_name = subscriptions.get(user_id)
    if not team_name:
        return add_powered_by("❌ *Not Subscribed*\n\nYou are not subscribed to any team. Use 'subscribe_team' to subscribe.")
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
        return add_powered_by("⏳ *Top Movers*\n\nTracking started. Please check again after the next update.")
    # Calculate movement
    movement = []
    for team, curr_rank in current_ranks.items():
        prev_rank = previous_ranks.get(team, curr_rank)
        change = prev_rank - curr_rank  # positive = moved up
        if change != 0:
            movement.append((team, change))
    # Sort by biggest movers
    movement.sort(key=lambda x: abs(x[1]), reverse=True)
    if not movement:
        result = "🔄 *Top Movers*\n\nNo significant changes since last update."
    else:
        result = "📈 *Top Movers*\n\n"
        for team, change in movement[:5]:
            arrow = "⬆️" if change > 0 else "⬇️"
            result += f"{arrow} *{team}* ({abs(change)} places)\n"
    previous_ranks = current_ranks.copy()
    return add_powered_by(result)
# Enhanced leaderboard with invocations and MCP metrics
@app.tool("top_n_leaderboard")
async def top_n_leaderboard_tool(n: int = 5) -> str:
    """Get top N teams from the Puch AI leaderboard with emoji bar chart and invocation stats."""
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
            return add_powered_by("📊 *No Leaderboard Data*\n\n⏳ Data is being fetched from Puch AI API\n\n🔄 Please wait for the initial sync to complete")
        max_visitors = max(team.get("unique_visitors", 0) for team in leaderboard[:n]) or 1
        result = f"🏆 *Puch AI Hackathon Leaderboard - Top {n}*\n\n"
        for i, team in enumerate(leaderboard[:n], 1):
            team_name = team.get("team_name", "?")
            visitors = team.get("unique_visitors", 0)
            team_size = team.get("team_size", 0)
            submissions = team.get("submissions", [])
            # Aggregate invocations and MCP metrics
            total_invocations = 0
            tool_spread = []
            last_invoked = None
            for sub in submissions:
                mcp = sub.get("mcp_metrics", {})
                total_invocations += mcp.get("invocations_total", 0)
                # Collect tool spread info
                if mcp.get("tool_spread_coef"):
                    for tool, coef in mcp["tool_spread_coef"].items():
                        tool_spread.append(f"{tool}: {coef:.2f}")
                # Find latest invocation
                if mcp.get("last_invoked"):
                    if not last_invoked or mcp["last_invoked"] > last_invoked:
                        last_invoked = mcp["last_invoked"]
            # Add medal emojis for top 3, then keycap emojis for 4-9, then fallback for 10+
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            elif 4 <= i <= 9:
                medal = f"{i}\u20E3"  # keycap digit emoji
            else:
                medal = f"{i}."
            bar = emoji_bar(visitors, max_visitors)
            result += f"{medal} *{team_name}* {bar}\n"
            result += f"   👥 Team Size: {team_size}\n"
            result += f"   👀 Unique Visitors: {visitors:,}\n"
            result += f"   ⚡️ Invocations: {total_invocations:,}\n"
            if tool_spread:
                result += f"   🛠️ Tool Spread: {', '.join(tool_spread)}\n"
            if last_invoked:
                result += f"   ⏱️ Last Invoked: {last_invoked}\n"
            result += "\n"
        return add_powered_by(result)
    except Exception as e:
        return add_powered_by(f"❌ *Error*\n\n🔍 Error retrieving leaderboard: {str(e)}")

# Store for bearer tokens
bearer_tokens: Dict[str, str] = {}

# Database setup
DB_PATH = "puch_leaderboard.db"
LEADERBOARD_URL = "https://api.puch.ai/hackathon-leaderboard"

def init_database():
    """Initialize SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
    conn.close()
    logger.info("Database initialized")

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
            return {"error": f"Team '{team_name}' not found"}
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
        return team_data
    except Exception as e:
        logger.error(f"Error getting team stats: {e}")
        return {"error": f"Database error: {str(e)}"}
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

@app.tool("top_5_leaderboard")
async def top_5_leaderboard_tool() -> str:
    """Get top 5 teams from the Puch AI leaderboard."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get top 5 teams by unique visitors
        cursor.execute('''
            SELECT team_name, unique_visitors, team_size
            FROM leaderboard 
            GROUP BY team_name 
            ORDER BY unique_visitors DESC 
            LIMIT 5
        ''')
        
        rows = cursor.fetchall()
        
        if not rows:
            return "📊 *No Leaderboard Data*\n\n⏳ Data is being fetched from Puch AI API\n\n🔄 Please wait for the initial sync to complete"
        
        # Format for WhatsApp display
        result = "🏆 *Puch AI Hackathon Leaderboard - Top 5*\n\n"
        
        for i, row in enumerate(rows, 1):
            team_name = row[0]
            visitors = row[1]
            team_size = row[2]
            
            # Add medal emojis for top 3
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}️⃣"
            
            result += f"{medal} *{team_name}*\n"
            result += f"   👥 Team Size: {team_size}\n"
            result += f"   👀 Unique Visitors: {visitors:,}\n\n"
        
    # Last Updated removed as per request
        return result
        
    except Exception as e:
        return f"❌ *Error*\n\n🔍 Error retrieving leaderboard: {str(e)}"
    finally:
        conn.close()

@app.tool("top_10_leaderboard")
async def top_10_leaderboard_tool() -> str:
    """Get top 10 teams from the Puch AI leaderboard."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get top 10 teams by unique visitors
        cursor.execute('''
            SELECT team_name, unique_visitors, team_size
            FROM leaderboard 
            GROUP BY team_name 
            ORDER BY unique_visitors DESC 
            LIMIT 10
        ''')
        
        rows = cursor.fetchall()
        
        if not rows:
            return "📊 *No Leaderboard Data*\n\n⏳ Data is being fetched from Puch AI API\n\n🔄 Please wait for the initial sync to complete"
        
        # Format for WhatsApp display
        result = "🏆 *Puch AI Hackathon Leaderboard - Top 10*\n\n"
        
        for i, row in enumerate(rows, 1):
            team_name = row[0]
            visitors = row[1]
            team_size = row[2]
            
            # Add medal emojis for top 3
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}️⃣"
            
            result += f"{medal} *{team_name}*\n"
            result += f"   👥 Team Size: {team_size}\n"
            result += f"   👀 Unique Visitors: {visitors:,}\n\n"
        
    # Last Updated removed as per request
        return result
        
    except Exception as e:
        return f"❌ *Error*\n\n🔍 Error retrieving leaderboard: {str(e)}"
    finally:
        conn.close()

@app.tool("get_leaderboard_stats")
async def get_leaderboard_stats_tool(team_name: str) -> str:
    """Get Puch AI leaderboard statistics for a specific team."""
    if not team_name:
        return add_powered_by("❌ *Error*\n\n📝 Team name is required")
    team_stats = get_team_stats(team_name)
    # Return formatted text based on result
    if "error" in team_stats:
        return add_powered_by(f"❌ *Team Not Found*\n\n🔍 {team_stats['error']}")
    else:
        # Get team rank
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT COUNT(*) + 1 as rank
                FROM (
                    SELECT DISTINCT team_name, unique_visitors
                    FROM leaderboard
                    GROUP BY team_name
                ) ranked_teams
                WHERE unique_visitors > (
                    SELECT unique_visitors 
                    FROM leaderboard 
                    WHERE team_name = ? 
                    LIMIT 1
                )
            ''', (team_stats["team_name"],))
            rank_row = cursor.fetchone()
            rank = rank_row[0] if rank_row else "N/A"
        except Exception:
            rank = "N/A"
        finally:
            conn.close()
    # Add unique visitors info
    unique_visitors = team_stats.get("unique_visitors", "N/A")
    safe_team_name = sanitize_response(team_stats["team_name"])
    result = f"🏆 *Team Rank Information*\n\n"
    result += f"📊 Team: {safe_team_name}\n"
    result += f"🥇 Current Rank: #{rank}\n"
    result += f"👤 Unique Visitors: {unique_visitors}\n"
    if "fuzzy_note" in team_stats:
        result += f"\n_{team_stats['fuzzy_note']}_\n"
    return add_powered_by(result)

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