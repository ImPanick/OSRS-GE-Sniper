"""
Auto-updater script for OSRS GE Sniper
Handles pulling updates from GitHub and restarting services
"""
import subprocess
import os
import json
import logging
from datetime import datetime
from typing import Dict, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPDATE_LOG_FILE = "update_log.json"
REPO_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def get_update_log() -> list:
    """Get update history"""
    log_path = os.path.join(REPO_ROOT, UPDATE_LOG_FILE)
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def log_update(status: str, message: str, commit_hash: Optional[str] = None, error: Optional[str] = None):
    """Log an update attempt"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "message": message,
        "commit_hash": commit_hash,
        "error": error
    }
    
    log_path = os.path.join(REPO_ROOT, UPDATE_LOG_FILE)
    history = get_update_log()
    history.append(log_entry)
    
    # Keep only last 50 entries
    history = history[-50:]
    
    try:
        with open(log_path, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write update log: {e}")

def get_current_commit() -> Optional[str]:
    """Get current git commit hash"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.error(f"Failed to get current commit: {e}")
    return None

def get_remote_commit() -> Optional[str]:
    """Get latest commit from remote"""
    try:
        # Fetch latest changes
        subprocess.run(
            ['git', 'fetch', 'origin'],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=30
        )
        
        # Get remote commit hash
        result = subprocess.run(
            ['git', 'rev-parse', 'origin/main'],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.error(f"Failed to get remote commit: {e}")
    return None

def check_for_updates() -> Dict:
    """Check if updates are available"""
    try:
        current = get_current_commit()
        remote = get_remote_commit()
        
        if not current or not remote:
            return {
                "available": False,
                "error": "Could not determine commit hashes"
            }
        
        if current == remote:
            return {
                "available": False,
                "current_commit": current,
                "remote_commit": remote
            }
        
        return {
            "available": True,
            "current_commit": current,
            "remote_commit": remote
        }
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        return {
            "available": False,
            "error": str(e)
        }

def is_docker_environment() -> bool:
    """Check if running in Docker"""
    return os.path.exists('/.dockerenv') or os.path.exists('/proc/self/cgroup')

def is_git_repo(path: str) -> bool:
    """Check if path is a git repository"""
    return os.path.exists(os.path.join(path, '.git'))

def update_code(restart_services: bool = True) -> Dict:
    """
    Pull latest code from GitHub
    
    Args:
        restart_services: Whether to restart Docker services after update
    
    Returns:
        Dict with update status
    """
    try:
        # Check if we're in a git repo
        if not is_git_repo(REPO_ROOT):
            if is_docker_environment():
                return {
                    "success": False,
                    "message": "Git repository not available in Docker. Please update by rebuilding the container.",
                    "docker_note": "Run: cd docker && docker-compose up -d --build"
                }
            else:
                return {
                    "success": False,
                    "message": "Not a git repository. Please clone the repository first."
                }
        
        current_commit = get_current_commit()
        
        # Stash any local changes
        logger.info("Stashing local changes...")
        stash_result = subprocess.run(
            ['git', 'stash'],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Fetch latest changes
        logger.info("Fetching latest changes from GitHub...")
        fetch_result = subprocess.run(
            ['git', 'fetch', 'origin'],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if fetch_result.returncode != 0:
            error_msg = fetch_result.stderr or "Unknown error"
            log_update("failed", "Failed to fetch updates", current_commit, error_msg)
            return {
                "success": False,
                "message": f"Failed to fetch updates: {error_msg}",
                "current_commit": current_commit
            }
        
        # Check if we're on main branch
        branch_result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"
        
        # Pull latest changes
        logger.info(f"Pulling latest changes from {branch}...")
        pull_result = subprocess.run(
            ['git', 'pull', 'origin', branch],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if pull_result.returncode != 0:
            error_msg = pull_result.stderr or "Unknown error"
            log_update("failed", "Failed to pull updates", current_commit, error_msg)
            return {
                "success": False,
                "message": f"Failed to pull updates: {error_msg}",
                "current_commit": current_commit
            }
        
        new_commit = get_current_commit()
        
        if current_commit == new_commit:
            log_update("no_changes", "Already up to date", current_commit)
            return {
                "success": True,
                "message": "Already up to date",
                "current_commit": current_commit,
                "updated": False
            }
        
        log_update("success", f"Updated from {current_commit[:8]} to {new_commit[:8]}", new_commit)
        
        result = {
            "success": True,
            "message": f"Successfully updated to commit {new_commit[:8]}",
            "current_commit": current_commit,
            "new_commit": new_commit,
            "updated": True
        }
        
        # Restart services if in Docker
        if restart_services and is_docker_environment():
            logger.info("Restarting Docker services...")
            restart_result = restart_docker_services()
            result["docker_restart"] = restart_result
        
        return result
        
    except subprocess.TimeoutExpired:
        error_msg = "Update operation timed out"
        log_update("failed", error_msg, current_commit, error_msg)
        return {
            "success": False,
            "message": error_msg,
            "current_commit": get_current_commit()
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Update error: {error_msg}")
        log_update("failed", "Update failed", get_current_commit(), error_msg)
        return {
            "success": False,
            "message": f"Update error: {error_msg}",
            "current_commit": get_current_commit()
        }

def restart_docker_services() -> Dict:
    """Restart Docker services using docker-compose"""
    try:
        docker_compose_path = os.path.join(REPO_ROOT, "docker", "docker-compose.yml")
        if not os.path.exists(docker_compose_path):
            return {
                "success": False,
                "message": "docker-compose.yml not found"
            }
        
        # Rebuild and restart services
        logger.info("Rebuilding Docker containers...")
        rebuild_result = subprocess.run(
            ['docker-compose', 'up', '-d', '--build'],
            cwd=os.path.join(REPO_ROOT, "docker"),
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes for build
        )
        
        if rebuild_result.returncode != 0:
            return {
                "success": False,
                "message": f"Failed to rebuild containers: {rebuild_result.stderr}"
            }
        
        return {
            "success": True,
            "message": "Docker services restarted successfully"
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Docker restart timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Docker restart error: {str(e)}"
        }

def get_update_status() -> Dict:
    """Get current update status and history"""
    update_check = check_for_updates()
    history = get_update_log()
    current_commit = get_current_commit()
    
    return {
        "updates_available": update_check.get("available", False),
        "current_commit": current_commit,
        "remote_commit": update_check.get("remote_commit"),
        "is_docker": is_docker_environment(),
        "recent_updates": history[-10:] if history else []
    }

