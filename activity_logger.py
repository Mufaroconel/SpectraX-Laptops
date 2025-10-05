import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from openpyxl import Workbook, load_workbook
import logging

logger = logging.getLogger(__name__)

ACTIVITY_LOG_FILE = "activity_log.xlsx"

class ActivityLogger:
    def __init__(self, file_path: str = ACTIVITY_LOG_FILE):
        self.file_path = file_path
        self.ensure_log_file_exists()
    
    def ensure_log_file_exists(self):
        """Create the activity log Excel file if it doesn't exist."""
        if not os.path.exists(self.file_path):
            wb = Workbook()
            ws = wb.active
            ws.title = "Activity_Log"
            
            # Add headers
            headers = [
                "timestamp", "phone_number", "user_name", "activity_type", 
                "message_type", "user_input", "bot_response", "button_id",
                "admin_flag", "session_id", "additional_data"
            ]
            ws.append(headers)
            
            wb.save(self.file_path)
            logger.info(f"Created activity log file: {self.file_path}")
    
    def log_activity(
        self,
        phone_number: str,
        activity_type: str,
        user_name: str = None,
        message_type: str = None,
        user_input: str = None,
        bot_response: str = None,
        button_id: str = None,
        admin_flag: bool = False,
        session_id: str = None,
        additional_data: Dict[str, Any] = None
    ):
        """Log an activity to the Excel file."""
        try:
            # Load existing workbook
            wb = load_workbook(self.file_path)
            ws = wb.active
            
            # Prepare data
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            additional_data_json = json.dumps(additional_data) if additional_data else None
            
            # Truncate long text fields for Excel compatibility
            user_input = (user_input[:500] + "...") if user_input and len(user_input) > 500 else user_input
            bot_response = (bot_response[:500] + "...") if bot_response and len(bot_response) > 500 else bot_response
            
            # Add row
            row_data = [
                timestamp,
                phone_number,
                user_name,
                activity_type,
                message_type,
                user_input,
                bot_response,
                button_id,
                admin_flag,
                session_id,
                additional_data_json
            ]
            
            ws.append(row_data)
            wb.save(self.file_path)
            
            logger.info(f"Logged activity: {activity_type} for {phone_number}")
            
        except Exception as e:
            logger.exception(f"Failed to log activity: {e}")
    
    def get_user_activity_count(self, phone_number: str) -> int:
        """Get total activity count for a user."""
        try:
            if not os.path.exists(self.file_path):
                return 0
                
            wb = load_workbook(self.file_path, read_only=True)
            ws = wb.active
            
            count = 0
            for row in ws.iter_rows(min_row=2, values_only=True):  # Skip header
                if row[1] == phone_number:  # phone_number column
                    count += 1
            
            return count
        except Exception as e:
            logger.exception(f"Failed to get activity count: {e}")
            return 0
    
    def get_recent_activities(self, limit: int = 10) -> list:
        """Get recent activities for admin dashboard."""
        try:
            if not os.path.exists(self.file_path):
                return []
                
            wb = load_workbook(self.file_path, read_only=True)
            ws = wb.active
            
            activities = []
            rows = list(ws.iter_rows(min_row=2, values_only=True))  # Skip header
            
            # Get last N rows (most recent)
            for row in rows[-limit:]:
                if row[0]:  # timestamp exists
                    activities.append({
                        'timestamp': row[0],
                        'phone_number': row[1],
                        'user_name': row[2],
                        'activity_type': row[3],
                        'admin_flag': row[8]
                    })
            
            return list(reversed(activities))  # Most recent first
        except Exception as e:
            logger.exception(f"Failed to get recent activities: {e}")
            return []

# Global activity logger instance
activity_logger = ActivityLogger()
