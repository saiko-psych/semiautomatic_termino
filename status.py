import json
import os
from datetime import datetime

class StatusManager:
    def __init__(self, path="status.json", debug=True):
        self.path = path
        self.debug = debug
        self.data = self._load()
    
    def _log(self, msg):
        if self.debug:
            print(f"[STATUS] {msg}")
    
    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    content = f.read().strip()
                    if not content:
                        self._log("Status file is empty – starting fresh.")
                        return {}
                    self._log("Status file loaded.")
                    return json.loads(content)
            except json.JSONDecodeError as e:
                self._log(f"WARNING: Status file is corrupted ({e}) – creating new one.")
                return {}
        self._log("Status file not found – starting fresh.")
        return {}
    
    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.data, f, indent=2)
        self._log("Status file saved.")
    
    def is_done_today(self, task_name):
        """
        Checks if a task was successfully completed today.
        
        Returns:
            True if task is done today or SKIP is set
            False if task is not done yet or has failed
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Task doesn't exist
        if task_name not in self.data:
            self._log(f"{task_name}: Not executed yet today.")
            return False
        
        value = self.data[task_name]
        
        # Special values
        if value == "SKIP":
            self._log(f"{task_name}: 'SKIP' detected – will be skipped.")
            return True
        
        if value == "RESET":
            self._log(f"{task_name}: 'RESET' detected – will be forced.")
            return False
        
        # Simple date format (old version)
        if isinstance(value, str) and value == today:
            self._log(f"{task_name}: Already done today ({today}).")
            return True
        
        # New format with detailed information
        if isinstance(value, dict):
            task_date = value.get("date")
            task_status = value.get("status")
            
            # Task was successfully completed today
            if task_date == today and task_status == "success":
                self._log(f"{task_name}: Already successfully completed today ({today}).")
                return True
            
            # Task failed today
            if task_date == today and task_status == "failed":
                self._log(f"{task_name}: Failed today – will retry.")
                return False
        
        self._log(f"{task_name}: Not done yet today.")
        return False
    
    def mark_done(self, task_name):
        """Marks a task as successfully completed."""
        today = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().isoformat()
        
        self.data[task_name] = {
            "date": today,
            "status": "success",
            "timestamp": timestamp
        }
        
        self._log(f"{task_name}: ✓ Marked as successfully completed ({today}).")
        self.save()
    
    def mark_failed(self, task_name, error_msg=""):
        """Marks a task as failed."""
        today = datetime.now().strftime("%Y-%m-%d")
        timestamp = datetime.now().isoformat()
        
        self.data[task_name] = {
            "date": today,
            "status": "failed",
            "error": error_msg,
            "timestamp": timestamp
        }
        
        self._log(f"{task_name}: ✗ Marked as failed: {error_msg}")
        self.save()
    
    def get_status(self, task_name):
        """
        Returns the detailed status of a task.
        
        Returns:
            dict with information or None if task doesn't exist
        """
        if task_name not in self.data:
            return None
        
        value = self.data[task_name]
        
        # Old format (date only)
        if isinstance(value, str):
            return {
                "date": value,
                "status": "success" if value not in ["SKIP", "RESET"] else value,
                "timestamp": None,
                "error": None
            }
        
        # New format
        return value
    
    def reset_task(self, task_name):
        """Resets a task so it will be executed again."""
        if task_name in self.data:
            del self.data[task_name]
            self._log(f"{task_name}: Reset.")
            self.save()
    
    def get_all_failed_today(self):
        """Returns all tasks that failed today."""
        today = datetime.now().strftime("%Y-%m-%d")
        failed_tasks = {}
        
        for task_name, value in self.data.items():
            if isinstance(value, dict):
                if value.get("date") == today and value.get("status") == "failed":
                    failed_tasks[task_name] = value
        
        return failed_tasks