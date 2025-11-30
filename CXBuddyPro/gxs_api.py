"""
GXS API Integration Module
Handles authentication and API calls to mock GXS backend
"""

import os
import json
import base64
import logging
from typing import Optional, Dict, Any
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)

# Mock GXS API base URL
GXS_API_BASE = os.getenv("GXS_API_BASE", "http://localhost:8004")


class GXSAPIClient:
    """Client for interacting with GXS Bank APIs"""
    
    def __init__(self):
        self.base_url = GXS_API_BASE
        self.current_jwt: Optional[str] = None
        self.current_user: Optional[Dict] = None
    
    def set_jwt(self, jwt_token: str):
        """Set JWT token for authenticated requests"""
        self.current_jwt = jwt_token
        
        # Decode JWT to get user info
        try:
            parts = jwt_token.split('.')
            if len(parts) == 3:
                payload = json.loads(base64.b64decode(parts[1] + '=='))
                self.current_user = payload
                logger.info(f"🔐 Authenticated as: {payload.get('name', 'Unknown')}")
        except Exception as e:
            logger.error(f"Failed to decode JWT: {e}")
    
    def clear_jwt(self):
        """Clear authentication"""
        self.current_jwt = None
        self.current_user = None
        logger.info("🔓 Cleared authentication")
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return self.current_jwt is not None
    
    def get_user_name(self) -> str:
        """Get authenticated user's name"""
        if self.current_user:
            return self.current_user.get('name', 'Customer')
        return 'Customer'
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated API request"""
        if not self.current_jwt:
            return {
                "success": False,
                "error": "Not authenticated. Please log in through the GXS app first."
            }
        
        headers = {
            "Authorization": f"Bearer {self.current_jwt}",
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, **kwargs) as response:
                    data = await response.json()
                    
                    if response.status == 200:
                        logger.info(f"✓ API call successful: {endpoint}")
                        return data
                    elif response.status == 401:
                        logger.warning(f"⚠️ Authentication failed: {endpoint}")
                        return {
                            "success": False,
                            "error": "Your session has expired. Please log in again."
                        }
                    else:
                        logger.error(f"❌ API error {response.status}: {endpoint}")
                        return {
                            "success": False,
                            "error": f"API error: {data.get('detail', 'Unknown error')}"
                        }
        except aiohttp.ClientConnectorError:
            logger.error(f"❌ Cannot connect to GXS API at {self.base_url}")
            return {
                "success": False,
                "error": "Cannot connect to GXS services. Please try again later."
            }
        except Exception as e:
            logger.error(f"❌ API request failed: {e}")
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }
    
    async def get_account_balance(self) -> str:
        """Get account balance information"""
        result = await self._make_request("GET", "/api/account/balance")
        
        if not result.get("success"):
            return result.get("error", "Failed to retrieve balance")
        
        data = result["data"]
        main_balance = data["mainAccount"]["balance"]
        savings_balance = data["savingsAccount"]["balance"]
        total = data["totalBalance"]
        
        response = f"""Here's your account balance:

💰 **Main Account**: SGD ${main_balance:,.2f}
💎 **Savings Account**: SGD ${savings_balance:,.2f} (3.88% p.a.)
📊 **Total Balance**: SGD ${total:,.2f}

Is there anything else you'd like to know about your accounts?"""
        
        return response
    
    async def get_account_details(self) -> str:
        """Get full account details"""
        result = await self._make_request("GET", "/api/account/details")
        
        if not result.get("success"):
            return result.get("error", "Failed to retrieve account details")
        
        data = result["data"]
        
        response = f"""Here are your account details:

👤 **Name**: {data['name']}
📧 **Email**: {data['email']}
🏦 **Account Type**: {data['accountType']}
🔢 **Account Number**: {data['accountNumber']}
✅ **Status**: {data['accountStatus'].title()}
📅 **Opened**: {data['openedDate']}

💰 **Main Account**: SGD ${data['mainAccount']['balance']:,.2f}
💎 **Savings Account**: SGD ${data['savingsAccount']['balance']:,.2f}
"""
        
        if 'businessName' in data:
            response += f"\n🏢 **Business**: {data['businessName']}\n"
        
        response += "\nHow else can I help you today?"
        
        return response
    
    async def get_recent_transactions(self, limit: int = 5) -> str:
        """Get recent transactions"""
        result = await self._make_request("GET", f"/api/transactions/recent?limit={limit}")
        
        if not result.get("success"):
            return result.get("error", "Failed to retrieve transactions")
        
        transactions = result["data"]["transactions"]
        
        if not transactions:
            return "You don't have any recent transactions."
        
        response = f"Here are your last {len(transactions)} transactions:\n\n"
        
        for txn in transactions:
            amount = txn['amount']
            symbol = "➖" if amount < 0 else "✅"
            response += f"{symbol} **{txn['date']}** - {txn['description']}: SGD ${abs(amount):,.2f}\n"
        
        response += "\nWould you like to see more transactions or check anything else?"
        
        return response
    
    async def get_card_details(self) -> str:
        """Get card details"""
        result = await self._make_request("GET", "/api/card/details")
        
        if not result.get("success"):
            return result.get("error", "Failed to retrieve card details")
        
        data = result["data"]
        
        status_emoji = "✅" if data['cardStatus'] == 'active' else "🔒"
        
        response = f"""Here are your GXS FlexiCard details:

{status_emoji} **Status**: {data['cardStatus'].title()}
💳 **Card**: {data['cardNumber']}
📅 **Expires**: {data['expiryDate']}

💰 **Credit Limit**: SGD ${data['creditLimit']:,.2f}
✅ **Available**: SGD ${data['availableCredit']:,.2f}
📊 **Used**: SGD ${data['usedCredit']:,.2f}

Need help with your card?"""
        
        return response
    
    async def freeze_card(self) -> str:
        """Freeze the card"""
        result = await self._make_request("POST", "/api/card/freeze")
        
        if not result.get("success"):
            return result.get("error", "Failed to freeze card")
        
        return f"""✅ **Card Frozen Successfully**

Your GXS FlexiCard has been temporarily frozen. All transactions are now blocked.

To unfreeze your card, just ask me anytime!"""
    
    async def unfreeze_card(self) -> str:
        """Unfreeze the card"""
        result = await self._make_request("POST", "/api/card/unfreeze")
        
        if not result.get("success"):
            return result.get("error", "Failed to unfreeze card")
        
        return f"""✅ **Card Unfrozen Successfully**

Your GXS FlexiCard is now active again. You can use it for transactions.

Is there anything else I can help with?"""


# Global API client instance
gxs_api = GXSAPIClient()
