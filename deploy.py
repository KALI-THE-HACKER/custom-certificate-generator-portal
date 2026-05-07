#!/usr/bin/env python3
"""
Deployment configuration helper script
Allows easy configuration of the app_prefix for different deployment scenarios
"""

import json
import sys
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path(__file__).parent / "config.json"

def load_config() -> dict:
    """Load configuration from config.json"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config: dict) -> None:
    """Save configuration to config.json"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"✓ Configuration saved to {CONFIG_PATH}")

def get_current_prefix() -> str:
    """Get current app_prefix from config"""
    config = load_config()
    return config.get("app_prefix", "")

def set_app_prefix(prefix: str) -> None:
    """Set the app_prefix in config.json"""
    config = load_config()
    
    # Validate and normalize prefix
    prefix = prefix.strip()
    if prefix and not prefix.startswith("/"):
        prefix = "/" + prefix
    prefix = prefix.rstrip("/") if prefix != "/" else ""
    
    config["app_prefix"] = prefix
    save_config(config)
    
    print(f"App prefix set to: '{prefix}' (empty string = root '/')")
    print("\nExample URLs:")
    print(f"  Home: {prefix}/" if prefix else "  Home: /")
    print(f"  Generate: {prefix}/generate" if prefix else "  Generate: /generate")
    print(f"  Static: {prefix}/static/css/style.css" if prefix else "  Static: /static/css/style.css")

def show_current_config() -> None:
    """Display current configuration"""
    config = load_config()
    prefix = config.get("app_prefix", "")
    print(f"\nCurrent app_prefix: '{prefix}'")
    print(f"Deployment path: {'/' + prefix if prefix else '/' }")
    
    print("\n" + "=" * 60)
    print("Example URLs:")
    print("=" * 60)
    base = prefix if prefix else ""
    print(f"Home page:            http://your-domain{base}/")
    print(f"Generate endpoint:    http://your-domain{base}/generate")
    print(f"Static files:         http://your-domain{base}/static/...")
    print(f"Download cert:        http://your-domain{base}/download-certificate")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        # Show help
        print("Certificate Generator - Deployment Configuration Tool\n")
        print("Usage:")
        print("  python3 deploy.py show              - Show current configuration")
        print("  python3 deploy.py set <prefix>      - Set app_prefix (e.g., /certificate)")
        print("  python3 deploy.py set-root          - Set to root (/) deployment")
        print("\nExamples:")
        print("  python3 deploy.py set /certificate")
        print("  python3 deploy.py set /events/certs")
        print("  python3 deploy.py set-root")
        print("\nCommon scenarios:")
        print("  • Root deployment:         python3 deploy.py set-root")
        print("  • Subpath deployment:      python3 deploy.py set /certificate")
        print("  • Nested subpath:          python3 deploy.py set /events/certificates")
        return
    
    command = sys.argv[1].lower()
    
    if command == "show":
        show_current_config()
    elif command == "set-root":
        set_app_prefix("")
        show_current_config()
    elif command == "set":
        if len(sys.argv) < 3:
            print("Error: Please provide a prefix")
            print("Usage: python3 deploy.py set <prefix>")
            return
        prefix = sys.argv[2]
        set_app_prefix(prefix)
        show_current_config()
    else:
        print(f"Unknown command: {command}")
        print("Run 'python3 deploy.py' for help")

if __name__ == "__main__":
    main()
