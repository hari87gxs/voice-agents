"""
Mock GXS Bank API Server
Simulates GXS backend APIs for account data, transactions, and cards
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict
import json
import base64
from datetime import datetime, timedelta
import random

app = FastAPI(title="Mock GXS Bank API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock user database
MOCK_USERS = {
    'USR-001': {
        'userId': 'USR-001',
        'name': 'John Doe',
        'email': 'john.doe@email.com',
        'accountType': 'Personal Account',
        'accountNumber': '1234567890',
        'mainAccountBalance': 15234.50,
        'savingsBalance': 42890.00,
        'cardNumber': '5123-****-****-8901',
        'cardLastFour': '8901',
        'cardStatus': 'active',
        'cardLimit': 50000.00,
        'cardAvailable': 48500.00
    },
    'USR-002': {
        'userId': 'USR-002',
        'name': 'Jane Smith',
        'email': 'jane.smith@email.com',
        'accountType': 'Business Account',
        'accountNumber': '2345678901',
        'mainAccountBalance': 89456.75,
        'savingsBalance': 125000.00,
        'cardNumber': '5123-****-****-4562',
        'cardLastFour': '4562',
        'cardStatus': 'active',
        'cardLimit': 100000.00,
        'cardAvailable': 95600.00,
        'businessName': 'Smith Trading Pte Ltd'
    },
    'USR-003': {
        'userId': 'USR-003',
        'name': 'Mike Wong',
        'email': 'mike.wong@email.com',
        'accountType': 'Premium Account',
        'accountNumber': '3456789012',
        'mainAccountBalance': 234567.80,
        'savingsBalance': 500000.00,
        'cardNumber': '5123-****-****-7893',
        'cardLastFour': '7893',
        'cardStatus': 'active',
        'cardLimit': 200000.00,
        'cardAvailable': 198200.00
    }
}

# Mock transactions
MOCK_TRANSACTIONS = {
    'USR-001': [
        {'date': '2025-11-27', 'description': 'Grab Transport', 'amount': -25.50, 'type': 'debit'},
        {'date': '2025-11-26', 'description': 'NTUC FairPrice', 'amount': -87.30, 'type': 'debit'},
        {'date': '2025-11-25', 'description': 'Salary Credit', 'amount': 5500.00, 'type': 'credit'},
        {'date': '2025-11-24', 'description': 'Starbucks', 'amount': -12.80, 'type': 'debit'},
        {'date': '2025-11-23', 'description': 'Netflix Subscription', 'amount': -17.98, 'type': 'debit'},
    ],
    'USR-002': [
        {'date': '2025-11-27', 'description': 'Supplier Payment', 'amount': -45000.00, 'type': 'debit'},
        {'date': '2025-11-26', 'description': 'Client Invoice Payment', 'amount': 125000.00, 'type': 'credit'},
        {'date': '2025-11-25', 'description': 'Office Rent', 'amount': -8500.00, 'type': 'debit'},
        {'date': '2025-11-24', 'description': 'Equipment Purchase', 'amount': -12300.00, 'type': 'debit'},
        {'date': '2025-11-23', 'description': 'Client Payment', 'amount': 68000.00, 'type': 'credit'},
    ],
    'USR-003': [
        {'date': '2025-11-27', 'description': 'Property Investment', 'amount': -500000.00, 'type': 'debit'},
        {'date': '2025-11-26', 'description': 'Dividend Payment', 'amount': 15000.00, 'type': 'credit'},
        {'date': '2025-11-25', 'description': 'Luxury Car Down Payment', 'amount': -80000.00, 'type': 'debit'},
        {'date': '2025-11-24', 'description': 'Investment Returns', 'amount': 25000.00, 'type': 'credit'},
        {'date': '2025-11-23', 'description': 'Club Membership', 'amount': -5000.00, 'type': 'debit'},
    ]
}


def verify_jwt(authorization: Optional[str] = Header(None)) -> Dict:
    """Extract and verify mock JWT token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization token provided")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # Decode mock JWT (just base64 decode the payload)
        parts = token.split('.')
        if len(parts) != 3:
            raise HTTPException(status_code=401, detail="Invalid token format")
        
        # Decode payload
        payload = json.loads(base64.b64decode(parts[1] + '=='))
        
        # Check expiration
        if payload.get('exp', 0) < datetime.now().timestamp():
            raise HTTPException(status_code=401, detail="Token expired")
        
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


@app.get("/")
async def root():
    return {
        "service": "Mock GXS Bank API",
        "version": "1.0.0",
        "endpoints": [
            "/api/account/balance",
            "/api/account/details",
            "/api/transactions/recent",
            "/api/card/details",
            "/api/card/freeze",
            "/api/card/unfreeze"
        ]
    }


@app.get("/api/account/balance")
async def get_account_balance(authorization: Optional[str] = Header(None)):
    """Get account balances"""
    user_data = verify_jwt(authorization)
    user_id = user_data.get('sub')
    
    if user_id not in MOCK_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = MOCK_USERS[user_id]
    
    return {
        "success": True,
        "data": {
            "accountNumber": user['accountNumber'],
            "mainAccount": {
                "balance": user['mainAccountBalance'],
                "currency": "SGD",
                "accountName": "Main Account"
            },
            "savingsAccount": {
                "balance": user['savingsBalance'],
                "currency": "SGD",
                "accountName": "Savings Account",
                "interestRate": 3.88
            },
            "totalBalance": user['mainAccountBalance'] + user['savingsBalance']
        }
    }


@app.get("/api/account/details")
async def get_account_details(authorization: Optional[str] = Header(None)):
    """Get full account details"""
    user_data = verify_jwt(authorization)
    user_id = user_data.get('sub')
    
    if user_id not in MOCK_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = MOCK_USERS[user_id]
    
    response = {
        "success": True,
        "data": {
            "userId": user['userId'],
            "name": user['name'],
            "email": user['email'],
            "accountType": user['accountType'],
            "accountNumber": user['accountNumber'],
            "accountStatus": "active",
            "openedDate": "2024-01-15",
            "mainAccount": {
                "balance": user['mainAccountBalance'],
                "currency": "SGD"
            },
            "savingsAccount": {
                "balance": user['savingsBalance'],
                "currency": "SGD",
                "interestRate": 3.88
            }
        }
    }
    
    # Add business name for business accounts
    if 'businessName' in user:
        response['data']['businessName'] = user['businessName']
    
    return response


@app.get("/api/transactions/recent")
async def get_recent_transactions(
    authorization: Optional[str] = Header(None),
    limit: int = 5
):
    """Get recent transactions"""
    user_data = verify_jwt(authorization)
    user_id = user_data.get('sub')
    
    if user_id not in MOCK_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    transactions = MOCK_TRANSACTIONS.get(user_id, [])[:limit]
    
    return {
        "success": True,
        "data": {
            "transactions": transactions,
            "count": len(transactions)
        }
    }


@app.get("/api/card/details")
async def get_card_details(authorization: Optional[str] = Header(None)):
    """Get card details"""
    user_data = verify_jwt(authorization)
    user_id = user_data.get('sub')
    
    if user_id not in MOCK_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = MOCK_USERS[user_id]
    
    return {
        "success": True,
        "data": {
            "cardNumber": user['cardNumber'],
            "cardLastFour": user['cardLastFour'],
            "cardStatus": user['cardStatus'],
            "cardType": "GXS FlexiCard",
            "creditLimit": user['cardLimit'],
            "availableCredit": user['cardAvailable'],
            "usedCredit": user['cardLimit'] - user['cardAvailable'],
            "expiryDate": "12/2028"
        }
    }


@app.post("/api/card/freeze")
async def freeze_card(authorization: Optional[str] = Header(None)):
    """Freeze card (mock)"""
    user_data = verify_jwt(authorization)
    user_id = user_data.get('sub')
    
    if user_id not in MOCK_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update card status (in production, this would update database)
    MOCK_USERS[user_id]['cardStatus'] = 'frozen'
    
    return {
        "success": True,
        "message": "Card frozen successfully",
        "data": {
            "cardStatus": "frozen",
            "frozenAt": datetime.now().isoformat()
        }
    }


@app.post("/api/card/unfreeze")
async def unfreeze_card(authorization: Optional[str] = Header(None)):
    """Unfreeze card (mock)"""
    user_data = verify_jwt(authorization)
    user_id = user_data.get('sub')
    
    if user_id not in MOCK_USERS:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update card status
    MOCK_USERS[user_id]['cardStatus'] = 'active'
    
    return {
        "success": True,
        "message": "Card unfrozen successfully",
        "data": {
            "cardStatus": "active",
            "unfrozenAt": datetime.now().isoformat()
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
