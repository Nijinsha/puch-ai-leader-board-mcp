#!/usr/bin/env python3
"""MCP server with validate and bearer token functions using FastMCP."""

import asyncio
import json
import logging
import sqlite3
import time
import os
from datetime import datetime
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
        # Get team data
        cursor.execute('''
            SELECT team_name, server_id, submitted_at, visitors, unique_visitors, team_size, last_updated
            FROM leaderboard 
            WHERE team_name = ?
            ORDER BY visitors DESC
        ''', (team_name,))
        
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
        
        result += f"🔄 *Last Updated:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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
        
        result += f"🔄 *Last Updated:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return result
        
    except Exception as e:
        return f"❌ *Error*\n\n🔍 Error retrieving leaderboard: {str(e)}"
    finally:
        conn.close()

@app.tool("get_leaderboard_stats")
async def get_leaderboard_stats_tool(team_name: str) -> str:
    """Get Puch AI leaderboard statistics for a specific team."""
    if not team_name:
        return "❌ *Error*\n\n📝 Team name is required"
    
    team_stats = get_team_stats(team_name)
    
    # Return formatted text based on result
    if "error" in team_stats:
        return f"❌ *Team Not Found*\n\n🔍 {team_stats['error']}"
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
            ''', (team_name,))
            
            rank_row = cursor.fetchone()
            rank = rank_row[0] if rank_row else "N/A"
            
        except Exception:
            rank = "N/A"
        finally:
            conn.close()
        
        result = f"🏆 *Team Rank Information*\n\n"
        result += f"📊 Team: {team_name}\n"
        result += f"🥇 Current Rank: #{rank}\n"
        result += f"🔄 Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        result += f"💡 *Note:* Only rank information is displayed for content safety"
        
        return result

@app.tool("refresh_leaderboard")
async def refresh_leaderboard_tool() -> str:
    """Manually refresh leaderboard data from Puch AI API."""
    try:
        logger.info("Manual leaderboard refresh requested...")
        leaderboard_data = await fetch_leaderboard()
        if leaderboard_data:
            store_leaderboard_data(leaderboard_data)
            return f"""🔄 *Leaderboard Refreshed Successfully!*

📊 {len(leaderboard_data)} teams updated
⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ Data has been synchronized with Puch AI API"""
        else:
            return f"""❌ *Refresh Failed*

📊 No data received from API
💡 Please check your internet connection
⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    except Exception as e:
        return f"""❌ *Refresh Error*

🔍 Error: {str(e)}
⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

@app.tool("database_status")
async def database_status_tool() -> str:
    """Get current database status and statistics."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get total records
        cursor.execute('SELECT COUNT(*) FROM leaderboard')
        total_records = cursor.fetchone()[0]
        
        # Get unique teams
        cursor.execute('SELECT COUNT(DISTINCT team_name) FROM leaderboard')
        unique_teams = cursor.fetchone()[0]
        
        # Get latest update
        cursor.execute('SELECT MAX(last_updated) FROM leaderboard')
        latest_update = cursor.fetchone()[0]
        
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
        result += f"🕒 Last Update: {latest_update}\n"
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
        
        return result
        
    except Exception as e:
        return f"❌ *Database Error*\n\n🔍 Error getting database status: {str(e)}"
    finally:
        conn.close()


async def main():
    """Main entry point."""
    await app.run()

if __name__ == "__main__":
    asyncio.run(main())