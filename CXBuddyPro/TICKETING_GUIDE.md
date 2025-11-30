# CXBuddy Ticketing System Guide

## Overview

The CXBuddy ticketing system automatically logs every customer call as a service ticket. Each call is assigned a unique ticket ID, and the complete conversation transcript is stored for audit trails, analytics, and quality assurance.

## Key Features

### 1. **Automatic Ticket Creation**
- Every WebSocket connection creates a new ticket
- Ticket ID format: `GXS-YYYYMMDD-XXXXXXXX` (e.g., `GXS-20251128-A1B2C3D4`)
- Includes session ID, timestamp, and initial status

### 2. **Conversation Transcript Logging**
- All user and agent messages are automatically logged
- Tool calls (knowledge base searches) are tracked
- Timestamps for every interaction
- Proper speaker identification (user/agent)

### 3. **Auto-Categorization**
When a call ends, the system automatically categorizes tickets based on conversation keywords:

| Category | Keywords |
|----------|----------|
| `account_inquiry` | balance, account, savings, main account |
| `card_inquiry` | card, flexi, debit, freeze, lost, stolen |
| `interest_rates` | interest, rate, apr, yield |
| `loan_inquiry` | loan, flexiloan, borrow |
| `technical_issue` | error, bug, broken, not working, issue |
| `fees_charges` | fee, charge, cost, price |
| `promotions` | promotion, campaign, cashback, reward |
| `general_inquiry` | (default if no keywords match) |

### 4. **Status Tracking**
Tickets progress through these states:
- `open` - Call just started
- `in_progress` - Actively being handled
- `resolved` - Issue resolved
- `closed` - Call ended (auto-set on disconnect)

### 5. **Priority Levels**
- `low` - General inquiries
- `normal` - Standard customer service (default)
- `high` - Urgent issues
- `urgent` - Critical problems

## API Endpoints

### Get Statistics
```bash
GET /api/tickets/stats
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "total_tickets": 42,
    "by_status": {
      "open": 3,
      "in_progress": 5,
      "resolved": 12,
      "closed": 22
    },
    "by_category": {
      "account_inquiry": 18,
      "card_inquiry": 8,
      "interest_rates": 6,
      "loan_inquiry": 4,
      "technical_issue": 2,
      "fees_charges": 3,
      "promotions": 1
    },
    "avg_resolution_hours": 0.5
  }
}
```

### List All Tickets
```bash
GET /api/tickets?status=closed&limit=50&offset=0
```

**Parameters:**
- `status` (optional): Filter by status (open, in_progress, resolved, closed)
- `limit` (optional): Number of tickets to return (default: 50)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "ticket_id": "GXS-20251128-A1B2C3D4",
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "customer_name": "Unknown",
      "status": "closed",
      "priority": "normal",
      "category": "interest_rates",
      "created_at": "2025-11-28T01:00:00Z",
      "updated_at": "2025-11-28T01:05:00Z",
      "resolved_at": "2025-11-28T01:05:00Z",
      "summary": "Customer asking about Saving Pockets interest rate",
      "resolution_notes": null
    }
  ],
  "count": 1
}
```

### Get Ticket Details
```bash
GET /api/tickets/{ticket_id}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "ticket": {
      "ticket_id": "GXS-20251128-A1B2C3D4",
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "customer_name": "Unknown",
      "status": "closed",
      "priority": "normal",
      "category": "interest_rates",
      "created_at": "2025-11-28T01:00:00Z",
      "updated_at": "2025-11-28T01:05:00Z",
      "resolved_at": "2025-11-28T01:05:00Z",
      "summary": "Customer asking about Saving Pockets interest rate",
      "resolution_notes": null
    },
    "interactions": [
      {
        "interaction_id": 1,
        "ticket_id": "GXS-20251128-A1B2C3D4",
        "timestamp": "2025-11-28T01:00:00Z",
        "speaker": "agent",
        "message": "Hey there! This is Riley from GXS Bank. How can I help you today?",
        "tool_calls": null
      },
      {
        "interaction_id": 2,
        "ticket_id": "GXS-20251128-A1B2C3D4",
        "timestamp": "2025-11-28T01:00:15Z",
        "speaker": "user",
        "message": "What's the interest rate for Saving Pockets?",
        "tool_calls": null
      },
      {
        "interaction_id": 3,
        "ticket_id": "GXS-20251128-A1B2C3D4",
        "timestamp": "2025-11-28T01:00:16Z",
        "speaker": "agent",
        "message": "[Tool Call: search_gxs_help_center]",
        "tool_calls": [
          {
            "name": "search_gxs_help_center",
            "arguments": "{\"query\":\"Saving Pockets interest rate\"}"
          }
        ]
      },
      {
        "interaction_id": 4,
        "ticket_id": "GXS-20251128-A1B2C3D4",
        "timestamp": "2025-11-28T01:00:20Z",
        "speaker": "agent",
        "message": "The Saving Pockets earn up to 3.88% p.a. on your first $100,000...",
        "tool_calls": null
      }
    ],
    "metadata": []
  }
}
```

## Database Schema

### Tickets Table
```sql
CREATE TABLE tickets (
    ticket_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    customer_name TEXT,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'normal',
    category TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    summary TEXT,
    resolution_notes TEXT
);
```

### Interactions Table
```sql
CREATE TABLE interactions (
    interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    speaker TEXT NOT NULL,
    message TEXT,
    tool_calls TEXT,
    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
);
```

### Ticket Metadata Table
```sql
CREATE TABLE ticket_metadata (
    metadata_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
);
```

## Programmatic Usage

### Initialize Ticketing System
```python
import ticketing

# Initialize on server startup
ticketing.initialize_ticketing("./tickets.db")
```

### Create Ticket for New Call
```python
ticket_id = ticketing.ticketing_system.create_ticket(
    session_id="550e8400-e29b-41d4-a716-446655440000",
    customer_name="Unknown",  # Can be updated later
    category=None,  # Will be auto-categorized
    priority="normal"
)
# Returns: "GXS-20251128-A1B2C3D4"
```

### Log User Message
```python
ticketing.ticketing_system.log_interaction(
    ticket_id=ticket_id,
    speaker="user",
    message="What's the interest rate for Saving Pockets?",
    tool_calls=None
)
```

### Log Agent Response
```python
ticketing.ticketing_system.log_interaction(
    ticket_id=ticket_id,
    speaker="agent",
    message="The Saving Pockets earn up to 3.88% p.a. on your first $100,000...",
    tool_calls=None
)
```

### Log Tool Call
```python
ticketing.ticketing_system.log_interaction(
    ticket_id=ticket_id,
    speaker="agent",
    message="[Tool Call: search_gxs_help_center]",
    tool_calls=[{
        "name": "search_gxs_help_center",
        "arguments": "{\"query\":\"Saving Pockets interest rate\"}"
    }]
)
```

### Add Metadata
```python
# Store additional context
ticketing.ticketing_system.add_metadata(ticket_id, "customer_id", "CUST123456")
ticketing.ticketing_system.add_metadata(ticket_id, "product", "GXS_SAVINGS_ACCOUNT")
ticketing.ticketing_system.add_metadata(ticket_id, "account_number", "1234567890")
```

### Update Ticket Status
```python
ticketing.ticketing_system.update_ticket(
    ticket_id=ticket_id,
    status="resolved",
    summary="Customer inquiry about Saving Pockets interest rate",
    category="interest_rates",
    priority="normal",
    resolution_notes="Provided current interest rate information"
)
```

### Close Ticket (Auto-categorize)
```python
# Called automatically on WebSocket disconnect
ticketing.ticketing_system.close_session(ticket_id, auto_categorize=True)
```

### Get Statistics
```python
stats = ticketing.ticketing_system.get_stats()
# Returns:
# {
#     "total_tickets": 42,
#     "by_status": {"open": 3, "closed": 39},
#     "by_category": {"account_inquiry": 18, "card_inquiry": 8, ...},
#     "avg_resolution_hours": 0.5
# }
```

### Export Ticket to JSON
```python
ticketing.ticketing_system.export_ticket_to_json(
    ticket_id=ticket_id,
    output_path="./exports/ticket_GXS-20251128-A1B2C3D4.json"
)
```

## Integration with External Systems

### Export Format
Tickets can be exported to JSON for integration with external ticketing systems (Zendesk, Salesforce Service Cloud, Freshdesk, etc.):

```json
{
  "ticket": {
    "ticket_id": "GXS-20251128-A1B2C3D4",
    "external_id": "GXS-20251128-A1B2C3D4",
    "subject": "Customer asking about Saving Pockets interest rate",
    "status": "closed",
    "priority": "normal",
    "category": "interest_rates",
    "created_at": "2025-11-28T01:00:00Z",
    "resolved_at": "2025-11-28T01:05:00Z",
    "customer": {
      "name": "Unknown",
      "session_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  },
  "interactions": [
    {
      "timestamp": "2025-11-28T01:00:00Z",
      "speaker": "agent",
      "message": "Hey there! This is Riley from GXS Bank. How can I help you today?"
    },
    {
      "timestamp": "2025-11-28T01:00:15Z",
      "speaker": "user",
      "message": "What's the interest rate for Saving Pockets?"
    }
  ],
  "metadata": {
    "customer_id": "CUST123456",
    "product": "GXS_SAVINGS_ACCOUNT"
  }
}
```

### Batch Export Script
```python
import ticketing
from pathlib import Path

# Export all closed tickets from the last 24 hours
tickets = ticketing.ticketing_system.get_tickets(status="closed", limit=1000)
export_dir = Path("./exports")
export_dir.mkdir(exist_ok=True)

for ticket in tickets:
    ticket_id = ticket["ticket_id"]
    output_path = export_dir / f"ticket_{ticket_id}.json"
    ticketing.ticketing_system.export_ticket_to_json(ticket_id, str(output_path))
    print(f"Exported: {ticket_id}")
```

## Analytics & Reporting

### Common Queries

**Top 10 Categories:**
```sql
SELECT category, COUNT(*) as count
FROM tickets
WHERE category IS NOT NULL
GROUP BY category
ORDER BY count DESC
LIMIT 10;
```

**Average Resolution Time by Category:**
```sql
SELECT 
    category,
    AVG((julianday(resolved_at) - julianday(created_at)) * 24) as avg_hours
FROM tickets
WHERE resolved_at IS NOT NULL
GROUP BY category
ORDER BY avg_hours DESC;
```

**Tickets Created Per Hour (Last 24 Hours):**
```sql
SELECT 
    strftime('%Y-%m-%d %H:00', created_at) as hour,
    COUNT(*) as count
FROM tickets
WHERE created_at >= datetime('now', '-24 hours')
GROUP BY hour
ORDER BY hour;
```

**Tool Call Frequency:**
```sql
SELECT 
    json_extract(tool_calls, '$[0].name') as tool_name,
    COUNT(*) as count
FROM interactions
WHERE tool_calls IS NOT NULL
GROUP BY tool_name
ORDER BY count DESC;
```

## Best Practices

### 1. **Ticket Naming**
- Update `customer_name` when customer identifies themselves
- Use metadata to store customer ID, account number, etc.

### 2. **Status Management**
- Keep tickets in `in_progress` while actively handling
- Move to `resolved` when issue is addressed
- Auto-close on disconnect (system handles this)

### 3. **Categorization**
- Let auto-categorization run first
- Manually override category if needed using `update_ticket()`
- Add custom categories by extending keyword mapping in `ticketing.py`

### 4. **Privacy & Compliance**
- Transcripts contain sensitive customer information
- Implement proper access controls on API endpoints
- Consider encryption for stored transcripts
- Set up data retention policies (auto-delete after N days)

### 5. **Performance**
- Database is indexed on `ticket_id`, `status`, `created_at`
- For high-volume deployments, consider PostgreSQL instead of SQLite
- Archive old tickets periodically to maintain performance

## Example Workflow

```python
# 1. Customer connects (WebSocket)
ticket_id = ticketing.ticketing_system.create_ticket(
    session_id=session_id,
    customer_name="Unknown"
)

# 2. Agent greets customer
ticketing.ticketing_system.log_interaction(
    ticket_id, "agent", 
    "Hey there! This is Riley from GXS Bank. How can I help you today?"
)

# 3. Customer asks question (auto-transcribed)
ticketing.ticketing_system.log_interaction(
    ticket_id, "user",
    "What's the interest rate for Saving Pockets?"
)

# 4. Agent searches knowledge base
ticketing.ticketing_system.log_interaction(
    ticket_id, "agent", "[Tool Call: search_gxs_help_center]",
    tool_calls=[{"name": "search_gxs_help_center", "arguments": "..."}]
)

# 5. Agent responds
ticketing.ticketing_system.log_interaction(
    ticket_id, "agent",
    "The Saving Pockets earn up to 3.88% p.a. on your first $100,000..."
)

# 6. Customer disconnects (auto-close)
ticketing.ticketing_system.close_session(ticket_id, auto_categorize=True)
# → Status: "closed"
# → Category: "interest_rates" (auto-detected)
# → Summary: "Customer asking about Saving Pockets interest rate"
```

## Monitoring

### Check Health
```bash
curl http://localhost:8003/health
```

### View Recent Statistics
```bash
curl http://localhost:8003/api/tickets/stats | jq
```

### List Active Tickets
```bash
curl http://localhost:8003/api/tickets?status=open | jq
```

### View Specific Ticket
```bash
curl http://localhost:8003/api/tickets/GXS-20251128-A1B2C3D4 | jq
```

## Troubleshooting

### Database Locked
If you get "database is locked" errors:
```python
# Increase timeout in ticketing.py initialization
self.conn = sqlite3.connect(db_path, timeout=30.0)
```

### Missing Transcripts
- Ensure WebSocket messages are being logged in `relay_azure_to_browser_with_logging()`
- Check for `conversation.item.input_audio_transcription.completed` events
- Verify `response.audio_transcript.done` events are being captured

### Category Not Auto-Detected
- Add keywords to `_auto_categorize()` method in `ticketing.py`
- Check transcript for actual keywords used by customer
- Manually set category using `update_ticket()`

## Future Enhancements

1. **Sentiment Analysis**: Analyze customer sentiment from transcript
2. **Agent Performance Metrics**: Track resolution time, searches per ticket, customer satisfaction
3. **Email Notifications**: Send ticket summary to customer after call
4. **Real-time Dashboard**: WebSocket-based live ticket dashboard
5. **Multi-language Support**: Translate tickets for international support teams
6. **AI-Powered Insights**: Use GPT to generate ticket summaries and suggested resolutions
