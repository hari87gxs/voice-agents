"""
CXBuddy Ticketing System
Logs customer interactions as service tickets for tracking and analysis.

Integrates with SQLite for lightweight storage, exportable to standard ticketing systems.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)


class TicketingSystem:
    """
    Manages customer service tickets for voice interactions.
    Each call creates a ticket with transcript, metadata, and resolution status.
    """
    
    def __init__(self, db_path: str = "./tickets.db"):
        """
        Initialize ticketing system with SQLite database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_database()
        logger.info(f"✓ Ticketing system initialized: {db_path}")
    
    def _init_database(self):
        """Create database schema if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tickets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                session_id TEXT,
                customer_name TEXT,
                status TEXT DEFAULT 'open',
                priority TEXT DEFAULT 'normal',
                category TEXT,
                created_at TEXT,
                updated_at TEXT,
                resolved_at TEXT,
                summary TEXT,
                resolution_notes TEXT
            )
        """)
        
        # Interactions table (stores conversation transcript)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT,
                timestamp TEXT,
                speaker TEXT,
                message TEXT,
                tool_calls TEXT,
                FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
            )
        """)
        
        # Metadata table (stores additional context)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ticket_metadata (
                metadata_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT,
                key TEXT,
                value TEXT,
                FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
            )
        """)
        
        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_status 
            ON tickets(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_created 
            ON tickets(created_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_ticket 
            ON interactions(ticket_id)
        """)
        
        conn.commit()
        conn.close()
    
    def create_ticket(
        self,
        session_id: str,
        customer_name: Optional[str] = None,
        category: str = "general_inquiry",
        priority: str = "normal"
    ) -> str:
        """
        Create a new service ticket for a customer call.
        
        Args:
            session_id: WebSocket session ID
            customer_name: Customer's name (if provided)
            category: Ticket category (e.g., 'account_inquiry', 'technical_issue')
            priority: Ticket priority ('low', 'normal', 'high', 'urgent')
            
        Returns:
            ticket_id: Unique ticket identifier
        """
        ticket_id = f"GXS-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        now = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tickets (
                ticket_id, session_id, customer_name, status, 
                priority, category, created_at, updated_at
            ) VALUES (?, ?, ?, 'open', ?, ?, ?, ?)
        """, (ticket_id, session_id, customer_name or "Anonymous", 
              priority, category, now, now))
        
        conn.commit()
        conn.close()
        
        logger.info(f"📋 Created ticket: {ticket_id} for session {session_id}")
        return ticket_id
    
    def log_interaction(
        self,
        ticket_id: str,
        speaker: str,
        message: str,
        tool_calls: Optional[List[Dict]] = None
    ):
        """
        Log a conversation interaction to the ticket.
        
        Args:
            ticket_id: Ticket identifier
            speaker: 'user' or 'agent'
            message: Transcript text
            tool_calls: List of tool calls made (for agent messages)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO interactions (
                ticket_id, timestamp, speaker, message, tool_calls
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            ticket_id,
            datetime.now().isoformat(),
            speaker,
            message,
            json.dumps(tool_calls) if tool_calls else None
        ))
        
        # Update ticket timestamp
        cursor.execute("""
            UPDATE tickets SET updated_at = ? WHERE ticket_id = ?
        """, (datetime.now().isoformat(), ticket_id))
        
        conn.commit()
        conn.close()
    
    def update_ticket(
        self,
        ticket_id: str,
        status: Optional[str] = None,
        summary: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        resolution_notes: Optional[str] = None
    ):
        """
        Update ticket details.
        
        Args:
            ticket_id: Ticket identifier
            status: New status ('open', 'in_progress', 'resolved', 'closed')
            summary: Ticket summary
            category: Updated category
            priority: Updated priority
            resolution_notes: How the issue was resolved
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if status:
            updates.append("status = ?")
            params.append(status)
            if status in ['resolved', 'closed']:
                updates.append("resolved_at = ?")
                params.append(datetime.now().isoformat())
        
        if summary:
            updates.append("summary = ?")
            params.append(summary)
        
        if category:
            updates.append("category = ?")
            params.append(category)
        
        if priority:
            updates.append("priority = ?")
            params.append(priority)
        
        if resolution_notes:
            updates.append("resolution_notes = ?")
            params.append(resolution_notes)
        
        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(ticket_id)
            
            query = f"UPDATE tickets SET {', '.join(updates)} WHERE ticket_id = ?"
            cursor.execute(query, params)
            conn.commit()
            logger.info(f"✓ Updated ticket {ticket_id}")
        
        conn.close()
    
    def add_metadata(self, ticket_id: str, key: str, value: str):
        """
        Add metadata to a ticket (e.g., customer ID, product involved).
        
        Args:
            ticket_id: Ticket identifier
            key: Metadata key
            value: Metadata value
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ticket_metadata (ticket_id, key, value)
            VALUES (?, ?, ?)
        """, (ticket_id, key, value))
        
        conn.commit()
        conn.close()
    
    def get_ticket(self, ticket_id: str) -> Optional[Dict]:
        """
        Retrieve full ticket details with transcript.
        
        Args:
            ticket_id: Ticket identifier
            
        Returns:
            Dictionary with ticket details and conversation history
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get ticket
        cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
        ticket_row = cursor.fetchone()
        
        if not ticket_row:
            conn.close()
            return None
        
        ticket = dict(ticket_row)
        
        # Get interactions
        cursor.execute("""
            SELECT * FROM interactions 
            WHERE ticket_id = ? 
            ORDER BY timestamp ASC
        """, (ticket_id,))
        
        interactions = [dict(row) for row in cursor.fetchall()]
        
        # Parse tool_calls JSON
        for interaction in interactions:
            if interaction['tool_calls']:
                interaction['tool_calls'] = json.loads(interaction['tool_calls'])
        
        ticket['interactions'] = interactions
        
        # Get metadata
        cursor.execute("""
            SELECT key, value FROM ticket_metadata WHERE ticket_id = ?
        """, (ticket_id,))
        
        metadata = {row['key']: row['value'] for row in cursor.fetchall()}
        ticket['metadata'] = metadata
        
        conn.close()
        return ticket
    
    def get_tickets(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get list of tickets with optional filtering.
        
        Args:
            status: Filter by status
            limit: Maximum number of tickets to return
            offset: Pagination offset
            
        Returns:
            List of ticket dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM tickets"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        tickets = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return tickets
    
    def get_stats(self) -> Dict:
        """
        Get ticketing system statistics.
        
        Returns:
            Dictionary with stats (total, open, resolved, avg resolution time)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total tickets
        cursor.execute("SELECT COUNT(*) as total FROM tickets")
        total = cursor.fetchone()[0]
        
        # By status
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM tickets 
            GROUP BY status
        """)
        by_status = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Average resolution time (in hours)
        cursor.execute("""
            SELECT AVG(
                (julianday(resolved_at) - julianday(created_at)) * 24
            ) as avg_hours
            FROM tickets
            WHERE resolved_at IS NOT NULL
        """)
        avg_resolution_hours = cursor.fetchone()[0] or 0
        
        # By category
        cursor.execute("""
            SELECT category, COUNT(*) as count 
            FROM tickets 
            GROUP BY category
        """)
        by_category = {row[0]: row[1] for row in cursor.fetchall()}
        
        conn.close()
        
        return {
            'total_tickets': total,
            'by_status': by_status,
            'by_category': by_category,
            'avg_resolution_hours': round(avg_resolution_hours, 2)
        }
    
    def export_ticket_to_json(self, ticket_id: str, output_path: str):
        """
        Export ticket to JSON file (for integration with other systems).
        
        Args:
            ticket_id: Ticket identifier
            output_path: Path to save JSON file
        """
        ticket = self.get_ticket(ticket_id)
        
        if ticket:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(ticket, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ Exported ticket {ticket_id} to {output_path}")
        else:
            logger.error(f"✗ Ticket {ticket_id} not found")
    
    def close_session(self, ticket_id: str, auto_categorize: bool = True):
        """
        Close a ticket when call ends. Optionally auto-categorize based on content.
        
        Args:
            ticket_id: Ticket identifier
            auto_categorize: Automatically categorize based on transcript keywords
        """
        ticket = self.get_ticket(ticket_id)
        
        if not ticket:
            return
        
        # Auto-categorize based on conversation keywords
        if auto_categorize and ticket['interactions']:
            category = self._auto_categorize(ticket)
            summary = self._generate_summary(ticket)
            
            self.update_ticket(
                ticket_id,
                status='resolved',
                category=category,
                summary=summary,
                resolution_notes='Call completed via voice agent'
            )
        else:
            self.update_ticket(ticket_id, status='resolved')
        
        logger.info(f"✓ Closed ticket {ticket_id}")
    
    def _auto_categorize(self, ticket: Dict) -> str:
        """
        Auto-categorize ticket based on transcript keywords.
        
        Args:
            ticket: Ticket dictionary with interactions
            
        Returns:
            Category string
        """
        # Combine all messages
        all_text = " ".join([
            interaction['message'].lower() 
            for interaction in ticket['interactions']
        ])
        
        # Keyword-based categorization
        categories = {
            'account_inquiry': ['balance', 'account', 'savings', 'main account'],
            'card_inquiry': ['card', 'flexi', 'debit', 'freeze', 'lost', 'stolen'],
            'interest_rates': ['interest', 'rate', 'apr', 'yield'],
            'loan_inquiry': ['loan', 'flexiloan', 'borrow'],
            'technical_issue': ['error', 'bug', 'broken', 'not working', 'issue'],
            'fees_charges': ['fee', 'charge', 'cost', 'price'],
            'promotions': ['promotion', 'campaign', 'cashback', 'reward'],
        }
        
        for category, keywords in categories.items():
            if any(keyword in all_text for keyword in keywords):
                return category
        
        return 'general_inquiry'
    
    def _generate_summary(self, ticket: Dict) -> str:
        """
        Generate a brief summary of the ticket.
        
        Args:
            ticket: Ticket dictionary with interactions
            
        Returns:
            Summary string
        """
        # Get first user message (usually contains the main question)
        user_messages = [
            i['message'] for i in ticket['interactions'] 
            if i['speaker'] == 'user'
        ]
        
        if user_messages:
            first_question = user_messages[0]
            # Truncate to 200 chars
            return first_question[:200] + ('...' if len(first_question) > 200 else '')
        
        return "Customer inquiry via voice agent"


# Global instance (initialized in server.py)
ticketing_system: Optional[TicketingSystem] = None


def initialize_ticketing(db_path: str = "./tickets.db") -> TicketingSystem:
    """
    Initialize global ticketing system instance.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        TicketingSystem instance
    """
    global ticketing_system
    ticketing_system = TicketingSystem(db_path)
    return ticketing_system
