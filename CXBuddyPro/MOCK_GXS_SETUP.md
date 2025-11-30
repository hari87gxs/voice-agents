# Mock GXS Authentication & API System

This directory contains a complete mock GXS authentication and backend API system for testing Riley's real-time account integration features.

## Components

### 1. Mock GXS Login App (`mock_gxs_app.html`)
A web-based mock GXS Bank login interface that simulates customer authentication.

**Features:**
- Select from 3 demo user accounts (Personal, Business, Premium)
- Generates JWT tokens with user information
- One-click launch to Riley with authenticated session
- Copy JWT for manual testing

**Demo Users:**
- **John Doe** (Personal Account)
  - Account: 1234567890
  - Main Balance: $15,234.50
  - Savings: $42,890.00
  
- **Jane Smith** (Business Account)
  - Account: 2345678901
  - Main Balance: $89,456.75
  - Savings: $125,000.00
  - Business: Smith Trading Pte Ltd
  
- **Mike Wong** (Premium Account)
  - Account: 3456789012
  - Main Balance: $234,567.80
  - Savings: $500,000.00

### 2. Mock GXS API Server (`mock_gxs_api.py`)
A FastAPI-based backend that simulates GXS Bank APIs for account data, transactions, and card management.

**Endpoints:**
- `GET /api/account/balance` - Account balances
- `GET /api/account/details` - Full account information
- `GET /api/transactions/recent` - Recent transactions (5-20)
- `GET /api/card/details` - Card information and limits
- `POST /api/card/freeze` - Freeze FlexiCard
- `POST /api/card/unfreeze` - Unfreeze FlexiCard

**Authentication:**
All endpoints require JWT token in `Authorization: Bearer <token>` header.

### 3. GXS API Integration Module (`gxs_api.py`)
Python client for Riley to interact with mock GXS APIs.

**Features:**
- JWT token management
- Automatic authentication handling
- User-friendly response formatting
- Error handling and session expiration

### 4. Updated Riley Integration
Riley's server and client have been updated to:
- Accept JWT tokens from URL parameters
- Display authenticated user name
- Pass JWT to backend via WebSocket
- Call account-related functions when authenticated

## Setup & Usage

### Step 1: Install Dependencies
```bash
cd /Users/hari/Documents/haricode/CXBuddy
pip install fastapi uvicorn aiohttp
```

### Step 2: Start Mock GXS API Server
```bash
python3 mock_gxs_api.py
```
Server runs on: http://localhost:8004

### Step 3: Open Mock GXS Login App
```bash
open mock_gxs_app.html
```

Or visit in browser:
```
file:///Users/hari/Documents/haricode/CXBuddy/mock_gxs_app.html
```

### Step 4: Login and Test
1. Open `mock_gxs_app.html` in browser
2. Select a demo user (e.g., John Doe)
3. Enter any password
4. Click "Login to GXS"
5. Click "🤖 Talk to Riley with this account →"
6. Riley opens in new tab with JWT token
7. Start a call and ask account-related questions!

## Testing Riley's New Capabilities

Once logged in, try asking Riley:

### Balance Queries
- "What's my account balance?"
- "How much do I have in my savings account?"
- "What's my total balance?"

### Transaction History
- "Show me my recent transactions"
- "What did I spend money on recently?"
- "Can I see my last 10 transactions?"

### Card Management
- "What's the status of my FlexiCard?"
- "How much credit do I have available?"
- "Freeze my card"
- "Unfreeze my card"

### Account Details
- "What's my account number?"
- "Tell me about my account"

## Architecture

```
┌─────────────────┐
│ Mock GXS Login  │ (HTML)
│   mock_gxs_app  │
└────────┬────────┘
         │ Generates JWT
         ↓
┌─────────────────┐      WebSocket + JWT      ┌──────────────┐
│     Riley       │ ←────────────────────────→ │   Browser    │
│   (server.py)   │                            │  (client.js) │
└────────┬────────┘                            └──────────────┘
         │
         │ gxs_api.py
         │ (API Client)
         ↓
┌─────────────────┐      HTTP + JWT
│  Mock GXS API   │ ←──────────────────
│ (mock_gxs_api)  │
└─────────────────┘
```

## JWT Token Format

Mock JWT tokens contain:
```json
{
  "sub": "USR-001",
  "name": "John Doe",
  "email": "john.doe@email.com",
  "accountNumber": "1234567890",
  "accountType": "Personal Account",
  "iat": 1732766400,
  "exp": 1732852800
}
```

## Development Notes

### Extending Mock Data
Edit `MOCK_USERS` and `MOCK_TRANSACTIONS` dictionaries in `mock_gxs_api.py` to add more users or customize data.

### Adding New API Endpoints
1. Add endpoint to `mock_gxs_api.py`
2. Add corresponding method to `gxs_api.py` (GXSAPIClient class)
3. Update `handle_function_call()` in `server.py`
4. Add tool definition to `config.json`

### Security Notes
⚠️ This is a MOCK system for development only:
- JWT signature is not validated (just base64 encoded)
- No real authentication or encryption
- All data is hardcoded in memory
- Not suitable for production use

## Next Steps for Production

To integrate with real GXS APIs:

1. **Replace mock_gxs_api.py** with real GXS API endpoints
2. **Update gxs_api.py** to point to production URLs
3. **Implement real JWT validation** with secret keys
4. **Add proper error handling** for rate limits, timeouts
5. **Implement OAuth2/OIDC** flow for production auth
6. **Add logging and monitoring**
7. **Implement rate limiting** and request throttling
8. **Add data encryption** for sensitive information

## Troubleshooting

### "Cannot connect to GXS services"
- Make sure `mock_gxs_api.py` is running on port 8004
- Check firewall settings

### "Not authenticated" errors
- Ensure you logged in via `mock_gxs_app.html` first
- Check JWT token is in URL when opening Riley
- JWT expires after 24 hours - login again

### No user name showing
- Clear browser cache and session storage
- Make sure JavaScript is enabled
- Check browser console for errors

## Files Created

- `mock_gxs_app.html` - Mock login interface
- `mock_gxs_api.py` - Mock API server
- `gxs_api.py` - API client for Riley
- Updated: `server.py` - JWT handling and function calls
- Updated: `client.js` - JWT in WebSocket connection
- Updated: `index.html` - Display authenticated user
- Updated: `config.json` - New API tool definitions
