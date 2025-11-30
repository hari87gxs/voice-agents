# Agent Handoff System

## Overview
Seamless agent-to-agent handoff allowing Riley (general support) and Hari (account manager) to transfer conversations.

## How It Works

### 1. **Server-Side (server.py)**
When a handoff function is called:
- `handoff_to_hari` - Riley transfers authenticated user to Hari
- `handoff_to_riley` - Hari transfers to Riley for general questions/products user doesn't have
- `check_product_ownership` - Checks if user has a product, triggers handoff if not

**Flow:**
1. Agent calls handoff function
2. Server logs the handoff request
3. AI speaks transition message ("Let me connect you to Riley...")
4. After 2.5s delay (for AI to finish speaking), server sends custom message to browser:
   ```json
   {
     "type": "agent.handoff",
     "target_agent": "riley" | "hari",
     "message": "Transferring to..."
   }
   ```

### 2. **Client-Side (client.js)**
When handoff message received:
1. Detects `agent.handoff` event type
2. Calls `handleAgentHandoff(targetAgent)`
3. **Hari handoff**: Redirects to login page (`http://localhost:8005/mock_gxs_app.html`)
4. **Riley handoff**: Clears JWT, redirects to base URL (`http://localhost:8003`)

### 3. **User Experience**
✅ **Smooth**: AI verbally announces handoff before redirect  
✅ **Seamless**: Auto-reconnect with correct agent  
✅ **Context-aware**: Hari requires authentication, Riley doesn't  

## Test Scenarios

### Scenario 1: Hari → Riley (Product Inquiry)
1. Login as Mike Wong
2. Talk to Hari
3. Ask: "Tell me about personal loans"
4. **Expected**: 
   - Hari: "Let me connect you to Riley..."
   - Auto-redirect to Riley (unauthenticated)
   - Riley answers about loans

### Scenario 2: Riley → Hari (Account Query)
1. Talk to Riley (no login)
2. Ask: "What's my account balance?"
3. **Expected**:
   - Riley: "Connecting you to Hari..."
   - Redirect to login page
   - After login, Hari provides balance

## Configuration

### Hari's Instructions (config_hari.json)
```
If asked about products they DON'T have: 
  USE check_product_ownership then handoff_to_riley
For general questions: 
  USE handoff_to_riley
```

### Riley's Tools (config_riley.json)
- `handoff_to_hari` - Transfer authenticated customers for account queries

### Hari's Tools (config_hari.json)
- `check_product_ownership` - Validate product ownership
- `handoff_to_riley` - Transfer for products not owned or general questions

## Technical Details

**Timing:**
- 2.5s delay between function completion and redirect
- Allows AI to finish speaking transition message
- Prevents abrupt disconnection

**State Management:**
- JWT stored in sessionStorage
- Cleared on Riley handoff
- Preserved on Hari handoff

**Error Handling:**
- If handoff signal fails to send, logged as error
- Client handles missing target gracefully
- WebSocket cleanup prevents memory leaks
