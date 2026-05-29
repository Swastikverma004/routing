import os
import sys
import subprocess
import getpass

def register_task():
    # 1. Get paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    cron_script = os.path.join(current_dir, "cron_job.py")
    
    if not os.path.exists(cron_script):
        print(f"[ERROR] Could not find cron_job.py at {cron_script}")
        sys.exit(1)
        
    # We want to run it via the same Python 3.12 launcher
    py_executable = "py"
    py_args = f"-3.12 {cron_script}"
    
    # Task Name
    task_name = "WheatFlourDailyRouting"
    
    # Get current user to run task as
    username = getpass.getuser()
    
    # Create the command. We set Cwd to current_dir by running cmd.exe /c
    # This ensures relative paths like sqlite:///deliveries.db and logs/ work correctly!
    run_command = f'cmd.exe /c "cd /d {current_dir} && py -3.12 cron_job.py"'
    
    # 2. Formulate schtasks command
    # /SC DAILY : Schedule daily
    # /TN task_name : Task name
    # /TR run_command : Command to run
    # /ST 06:00 : Start time (6:00 AM)
    # /F : Force create (overwrites existing task)
    cmd = [
        "schtasks", "/create",
        "/sc", "DAILY",
        "/tn", task_name,
        "/tr", run_command,
        "/st", "06:00",
        "/f"
    ]
    
    print(f"Registering Windows Scheduled Task '{task_name}'...")
    print(f"Trigger: Daily at 06:00 AM")
    print(f"Run Command: {run_command}\n")
    
    try:
        # Run schtasks
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("[SUCCESS] Task registered successfully in Windows Task Scheduler!")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to register task: {e}")
        print("Standard Output:", e.stdout)
        print("Standard Error:", e.stderr)
        print("\nNote: Registering scheduled tasks on Windows sometimes requires running the terminal as Administrator.")
        print("If you encounter a permission error, you can manually run this command in an Elevated Command Prompt:")
        print(f"  {' '.join(cmd)}")
        sys.exit(1)

if __name__ == "__main__":
    register_task()
