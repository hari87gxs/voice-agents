# 🎭 Dual-Agent System - Riley & Hari

## System Architecture

CXBuddy now implements a **sophisticated dual-agent handoff system** that mirrors real-world banking customer service:

```
┌─────────────────────────────────────────────────────────────────┐
│                     GXS BANK AI SYSTEM                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐              ┌──────────────────┐         │
│  │  RILEY           │              │  HARI            │         │
│  │  General Support │◄────────────►│  Account Manager │         │
│  │  (Pre-Login)     │   Handoffs   │  (Post-Login)    │         │
│  └──────────────────┘              └──────────────────┘         │
│         │                                    │                   │
│         ├── Knowledge Base (ChromaDB)        │                   │
│         ├── GXS Help Center Search          ├── Account APIs    │
│         ├── Product Information             ├── Transactions    │
│         └── General Inquiries               ├── Card Management │
│                                             └── Personal Data   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Roles

### 🌟 Riley - General Support Agent (Pre-Login)

**Primary Function**: General GXS Bank information and pre-login customer support

**Expertise**:
- GXS Bank products and services
- Interest rates, fees, eligibility criteria
- Account opening procedures
- General banking questions
- Product comparisons

**Tools Available**:
1. `search_gxs_help_center` - Query GXS knowledge base
2. `handoff_to_hari` - Transfer authenticated customers to Account Manager

**When Riley Hands Off**:
- Customer logs in (JWT received)
- Customer asks about THEIR account/balance/transactions
- Customer requests personal account operations

**Example Queries Riley Handles**:
- "What is the GXS FlexiCard interest rate?"
- "How do I open a savings account?"
- "What fees does GXS charge?"
- "Tell me about your investment products"

### 🔐 Hari - Account Manager (Post-Login)

**Primary Function**: Authenticated personal account management

**Expertise**:
- Account balances and details
- Transaction history
- Card management (freeze/unfreeze)
- Personal account operations
- **Product ownership validation**

**Tools Available**:
1. `get_account_balance` - Real-time balance check
2. `get_account_details` - Full account information
3. `get_recent_transactions` - Transaction history
4. `get_card_details` - FlexiCard information
5. `freeze_card` - Temporarily freeze card
6. `unfreeze_card` - Restore card usage
7. `check_product_ownership` - Verify customer has specific product
8. `handoff_to_riley` - Transfer to General Support for products customer doesn't have

**When Hari Hands Off to Riley**:
- Customer asks about products they DON'T have (loans, investments, insurance)
- General GXS questions not specific to their account
- Product information inquiries

**Example Queries Hari Handles**:
- "What's my account balance?"
- "Show me my recent transactions"
- "Can you freeze my card?"
- "What's my account number?"

**Example Handoff Scenarios** (Hari → Riley):
- Customer: "Tell me about your loan products"
  - Hari: "I see you don't have a loan with us yet. Let me connect you with Riley who can help with that."
  
## Implementation Details

### 1. Agent Selection Logic

```python
# On WebSocket connection:
if jwt_token:
    # Authenticated → Start with Hari
    current_agent = "hari"
    current_config = CONFIG_HARI
else:
    # Not authenticated → Start with Riley  
    current_agent = "riley"
    current_config = CONFIG_RILEY
```

### 2. Configuration Files

- `config_riley.json` - Riley's system prompt, tools, voice config
- `config_hari.json` - Hari's system prompt, tools, voice config

Each agent has:
- Unique system prompt defining their role
- Specific toolset for their domain
- Handoff protocols
- Example queries they should/shouldn't handle

### 3. Handoff Protocol

**Riley → Hari Handoff**:
```javascript
Function: handoff_to_hari
Parameters: {
  reason: "account balance inquiry",
  customer_name: "Mike Wong"
}
Result: Agent switch + Hari greeting
```

**Hari → Riley Handoff**:
```javascript
Function: handoff_to_riley
Parameters: {
  reason: "product inquiry - loan",
  context: "Customer asking about personal loans"
}
Result: Agent switch + Riley takes over
```

### 4. Product Ownership Check

Hari can check if customer has specific products:
```javascript
Function: check_product_ownership
Parameters: {
  product_type: "loan" | "investment" | "insurance" | "mortgage" | "credit_line"
}

Response:
- has_product: false
- Automatic handoff to Riley for product information
```

### 5. Mock Product Ownership

Currently configured:
- ✅ **All users have**: Main Account, Savings Account, FlexiCard
- ❌ **No users have**: Loans, Investments, Insurance, Mortgages, Credit Lines

When Hari detects customer asking about products they don't have, automatic handoff to Riley.

## User Experience Flow

### Scenario 1: Unauthenticated User

```
User opens app → Riley greets
User: "What's the interest rate on savings?"
Riley: [Searches knowledge base] "3.88% p.a. on balances up to $100k..."

User logs in → JWT sent
Riley: "Great! Let me connect you with Hari for personalized service..."
[Agent switch to Hari]

Hari: "Hi Mike! I'm Hari, your Account Manager. How can I help?"
User: "What's my balance?"
Hari: [Calls API] "Your Main Account has SGD $234,567.80..."
```

### Scenario 2: Authenticated User Asking About Unowned Product

```
User logs in → Hari greets
User: "Tell me about personal loans"
Hari: [Checks ownership] "I see you don't have a loan yet..."
Hari: "Let me connect you with Riley..."
[Agent switch to Riley]

Riley: "Hi! I can help with our loan products. We offer..."
```

### Scenario 3: Round-Trip Handoff

```
Riley → (login) → Hari → (product inquiry) → Riley → (account question) → Hari
```

Full conversation continuity maintained across all handoffs.

## Technical Benefits

1. **Separation of Concerns**: Each agent has clear, focused responsibilities
2. **Security**: Hari only accessible with authentication
3. **Scalability**: Easy to add specialized agents (e.g., loan specialist, investment advisor)
4. **Context Preservation**: Handoffs maintain conversation history
5. **Real Banking Experience**: Mimics human customer service workflows

## Configuration

### Riley System Prompt Highlights

```json
{
  "role": "Riley - GXS General Support Agent (Pre-Login)",
  "core_instructions": [
    "Handle PRE-LOGIN queries only",
    "Never try to access personal account data",
    "Hand off authenticated users to Hari immediately",
    "Use search_gxs_help_center for all product questions"
  ],
  "handoff_protocol": [
    "WHEN TO HANDOFF: Customer is logged in OR asks about personal account",
    "SAY: 'Let me connect you with Hari, our Account Manager...'",
    "CALL: handoff_to_hari"
  ]
}
```

### Hari System Prompt Highlights

```json
{
  "role": "Hari - GXS Bank Account Manager",
  "core_instructions": [
    "ONLY handle authenticated customer account queries",
    "Can ONLY answer about products customer HAS",
    "If asked about products they DON'T have → handoff to Riley",
    "Always check authentication before providing data"
  ],
  "handoff_protocol": [
    "WHEN TO HANDOFF: Product customer doesn't own",
    "SAY: 'Let me connect you with Riley for product info...'",
    "CALL: handoff_to_riley OR check_product_ownership"
  ]
}
```

## Testing Scenarios

### Test 1: Pre-login General Questions
- Start unauthenticated
- Ask about GXS products
- Verify Riley answers using knowledge base

### Test 2: Login Triggers Handoff
- Login with JWT
- Verify automatic switch to Hari
- Check Hari greets by name

### Test 3: Account Operations
- As authenticated user
- Ask for balance, transactions, card details
- Verify Hari calls APIs correctly

### Test 4: Product Not Owned
- As authenticated user
- Ask Hari about loans/investments
- Verify handoff to Riley
- Verify Riley provides product info

### Test 5: Round-Trip
- Riley → Hari (login)
- Hari → Riley (product inquiry)
- Riley → Hari (account question)
- Verify smooth transitions

## Future Enhancements

1. **Agent Personalities**: Different voices for Riley vs Hari
2. **More Specialists**: Loan officer, investment advisor, fraud team
3. **Smart Routing**: AI determines best agent based on query intent
4. **Agent Metrics**: Track handoff success rates, resolution times
5. **Multi-Agent Conferences**: Multiple agents collaborating on complex cases

## Summary

The dual-agent system provides:
- ✅ **Clear role separation** between general support and account management
- ✅ **Intelligent handoffs** based on authentication and product ownership
- ✅ **Real banking experience** mimicking human customer service
- ✅ **Security** - account data only accessible to authenticated agent
- ✅ **Scalability** - easy to add specialized agents
- ✅ **Context preservation** across agent switches

This architecture is production-ready and mirrors real-world banking customer service workflows! 🎉
