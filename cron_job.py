import os
import sys
from datetime import datetime
from database import SessionLocal
from optimizer import run_delivery_optimization

def run_cron():
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    log_file_path = os.path.join("logs", "cron_optimization.log")
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] Starting daily route optimization cron job...\n"
    
    print(log_message.strip())
    
    db = SessionLocal()
    try:
        result = run_delivery_optimization(db)
        status = result.get("status", "unknown")
        msg = result.get("message", "no message")
        
        summary = f"[{timestamp}] STATUS: {status.upper()} | MESSAGE: {msg}\n"
        print(summary.strip())
        
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(log_message)
            f.write(summary)
            f.write("-" * 80 + "\n")
            
    except Exception as e:
        err_msg = f"[{timestamp}] CRITICAL ERROR during cron job: {e}\n"
        print(err_msg.strip(), file=sys.stderr)
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(log_message)
            f.write(err_msg)
            f.write("-" * 80 + "\n")
    finally:
        db.close()

if __name__ == "__main__":
    run_cron()
