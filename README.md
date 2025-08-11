# Puch Leaderboard FastMCP Server

A FastMCP server that provides validate, bearer token, and Puch AI leaderboard functions.

## Features

- **Validate Tool**: Validates data, tokens, and formats
- **Bearer Token Tool**: Generate, validate, and revoke bearer tokens
- **Health Check Tool**: Monitor server status
- **Leaderboard Stats Tool**: Get Puch AI hackathon leaderboard statistics for specific teams
- **Automatic Data Sync**: Syncs leaderboard data every 30 seconds and stores in SQLite

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

Or install with pip:
```bash
pip install fastmcp fastapi uvicorn pydantic python-multipart aiohttp python-dotenv
```

2. Create a `.env` file with your configuration:
```bash
# Authentication token for MCP server
AUTH_TOKEN=your-secure-token-here

# Your phone number (required by Puch)
MY_NUMBER=+1234567890
```

## Usage

### Running the FastMCP Server

```bash
fastmcp dev main.py
```

The server runs over stdio and can be integrated with MCP clients. It automatically starts syncing leaderboard data every 30 seconds.

### Available Tools

#### 1. Validate Tool (Required by Puch)
Returns your phone number from environment variables.

Example usage:
```json
{
  "name": "validate",
  "arguments": {}
}
```

#### 2. Data Validation Tool
Validates different types of data:
- `token`: Validates bearer tokens
- `data`: Validates general data
- `format`: Validates JSON format

Example usage:
```json
{
  "name": "data_validation",
  "arguments": {
    "data": "test data",
    "type": "data"
  }
}
```

#### 2. Bearer Token Tool
Manages bearer tokens:
- `generate`: Create new tokens
- `validate`: Verify existing tokens
- `revoke`: Remove tokens

Example usage:
```json
{
  "name": "bearer_token",
  "arguments": {
    "action": "generate",
    "user_id": "user123"
  }
}
```

#### 3. Health Check Tool
Returns server status information including database and sync status.

Example usage:
```json
{
  "name": "health_check",
  "arguments": {}
}
```

#### 4. Leaderboard Stats Tool
Get Puch AI hackathon leaderboard statistics for a specific team.

Example usage:
```json
{
  "name": "get_leaderboard_stats",
  "arguments": {
    "team_name": "InfiniteCoffee"
  }
}
```

Returns team information including:
- Team name and size
- Unique visitors count
- Individual submission details (server ID, submission time, visitors)
- Last updated timestamp

#### 5. Database Status Tool
Get comprehensive database status and statistics.

Example usage:
```json
{
  "name": "database_status",
  "arguments": {}
}
```

Returns database information including:
- Total records and unique teams
- Latest update timestamp
- Top 5 teams by visitor count
- Sync status and database file path

#### 6. Refresh Leaderboard Tool
Manually trigger a refresh of leaderboard data from the Puch AI API.

Example usage:
```json
{
  "name": "refresh_leaderboard",
  "arguments": {}
}
```

Useful for immediate data updates without waiting for the automatic 30-second sync.

#### 7. Top 5 Leaderboard Tool
Get a formatted top 5 leaderboard perfect for WhatsApp sharing.

Example usage:
```json
{
  "name": "top_5_leaderboard",
  "arguments": {}
}
```

Returns a beautifully formatted leaderboard with:
- 🥇🥈🥉 Medal emojis for top 3 teams
- Team names, sizes, and visitor counts
- WhatsApp-friendly formatting with bold text
- Last updated timestamp

#### 8. Top 10 Leaderboard Tool
Get a comprehensive top 10 leaderboard for extended rankings.

Example usage:
```json
{
  "name": "top_10_leaderboard",
  "arguments": {}
}
```

Returns a detailed top 10 leaderboard with:
- 🥇🥈🥉 Medal emojis for top 3 teams
- Extended rankings up to 10th place
- Team names, sizes, and visitor counts
- WhatsApp-friendly formatting

#### 9. Team Rank Tool
Get rank information for a specific team (content-safe version).

Example usage:
```json
{
  "name": "get_leaderboard_stats",
  "arguments": {
    "team_name": "InfiniteCoffee"
  }
}
```

Returns only rank information for content safety:
- Team name and current rank position
- Last updated timestamp
- No detailed visitor counts or submission details

## WhatsApp Integration

All tools now return messages formatted specifically for WhatsApp:
- ✅ **Emojis**: Visual indicators for success, error, and status
- ✅ **Bold text**: Uses WhatsApp markdown for emphasis
- ✅ **Clean formatting**: Easy to read on mobile devices
- ✅ **Rich information**: Detailed responses with clear status indicators

## Startup Behavior

The server automatically:
1. **Initializes the SQLite database** when the module is imported
2. **Seeds initial data** if the database is empty (fetches from Puch AI API)
3. **Starts background sync** every 30 seconds to keep data fresh
4. **Creates necessary tables and indexes** for optimal performance

## Database

The server uses SQLite to store leaderboard data:
- **File**: `puch_leaderboard.db`
- **Table**: `leaderboard`
- **Auto-sync**: Every 30 seconds from the Puch AI API
- **Indexed**: Fast lookups by team name

## Testing

Run the test script to verify functionality:

```bash
python test_mcp.py
```

## Development

This project uses:
- Python 3.11+
- FastMCP for streamlined MCP server development
- Async/await for non-blocking operations
- SQLite for data persistence
- aiohttp for HTTP requests
- Background tasks for data synchronization

## Project Structure

```
puch-leaderboard/
├── main.py              # Main FastMCP server with leaderboard sync
├── test_mcp.py          # Test script
├── requirements.txt      # Python dependencies
├── pyproject.toml       # Project configuration
├── README.md            # This file
└── puch_leaderboard.db  # SQLite database (created automatically)
```

## Why FastMCP?

FastMCP provides several advantages over the standard MCP library:
- **Simpler syntax**: Use decorators instead of complex handlers
- **Automatic schema generation**: Tool schemas are inferred from function signatures
- **Better performance**: Optimized for high-throughput scenarios
- **Cleaner code**: Less boilerplate and more readable implementations

## License

MIT License
