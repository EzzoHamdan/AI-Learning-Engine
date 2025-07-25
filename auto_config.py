"""
Auto-configuration utilities for the AI Quiz Generator.
Provides smart defaults and graceful fallbacks for easy setup.
"""

import os
import subprocess
import sys
from typing import Tuple
import requests


def ensure_env_file_exists():
    """Create a basic .env file if it doesn't exist."""
    env_path = ".env"
    if not os.path.exists(env_path):
        default_env = """# AI Quiz Generator Configuration
# Auto-generated default configuration

# API Keys (add your keys here when you get them)
OPENAI_API_KEY=""
GOOGLE_AI_API_KEY="" 

# Provider Selection
USE_LOCAL_AI=true
USE_GOOGLE_AI=false
USE_OPENAI=false

# Local AI Settings
LOCAL_AI_MODEL="gemma2:2b"

# Debug mode
DEBUG=false
"""
        with open(env_path, 'w') as f:
            f.write(default_env)
        print("ℹ️ Created default .env configuration file")


def check_and_install_dependencies():
    """Check if all required packages are installed, install if missing."""
    try:
        # Check for key packages
        import streamlit
        import openai
        import fitz  # PyMuPDF
        import docx
        import pptx
        return True
    except ImportError as e:
        print(f"⚠️ Missing dependency: {e.name}")
        print("📦 Installing required packages...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                          check=True)
            print("✅ Packages installed successfully!")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install packages automatically")
            print("Please run: pip install -r requirements.txt")
            return False


def detect_available_providers() -> dict:
    """Automatically detect which AI providers are available."""
    providers = {
        'local_ai': False,
        'google_ai': False, 
        'openai': False
    }
    
    # Check Local AI (Ollama)
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        if response.status_code == 200:
            providers['local_ai'] = True
    except:
        pass
    
    # Check Google AI
    google_key = os.getenv("GOOGLE_AI_API_KEY", "")
    if google_key and len(google_key) > 10:
        providers['google_ai'] = True
    
    # Check OpenAI
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key and len(openai_key) > 10:
        providers['openai'] = True
    
    return providers


def get_setup_status() -> Tuple[bool, str, list]:
    """Get overall setup status and recommendations."""
    ensure_env_file_exists()
    deps_ok = check_and_install_dependencies()
    providers = detect_available_providers()
    
    available_providers = []
    if providers['local_ai']:
        available_providers.append("Local AI (Ollama)")
    if providers['google_ai']:
        available_providers.append("Google AI") 
    if providers['openai']:
        available_providers.append("OpenAI")
    
    if available_providers:
        status = f"✅ Ready! Available providers: {', '.join(available_providers)}"
        ready = True
    else:
        status = "⚠️ No AI providers configured. Run setup_easy.py for guided setup."
        ready = False
        available_providers = ["Manual Configuration Required"]
    
    return ready, status, available_providers


def show_quick_setup_guide():
    """Display quick setup instructions for users."""
    print("\n" + "="*60)
    print("🚀 AI QUIZ GENERATOR - QUICK SETUP")
    print("="*60)
    
    ready, status, providers = get_setup_status()
    print(f"\n📊 Status: {status}")
    
    if not ready:
        print("\n🛠️ Quick Setup Options:")
        print("\n1. 🏠 LOCAL AI (Recommended - Free & Private)")
        print("   • Install Ollama: https://ollama.ai")
        print("   • Run: ollama pull gemma2:2b")
        print("   • Run: ollama serve")
        
        print("\n2. 🆕 GOOGLE AI (Free tier available)")
        print("   • Get API key: https://aistudio.google.com/app/apikey")
        print("   • Add to .env: GOOGLE_AI_API_KEY=\"your_key\"")
        
        print("\n3. ⚡ OPENAI (Pay-per-use)")
        print("   • Get API key: https://platform.openai.com/api-keys")
        print("   • Add to .env: OPENAI_API_KEY=\"your_key\"")
        
        print("\n💡 Or run: python setup_easy.py")
        print("   for guided setup wizard!")
    
    print("\n🚀 To start: streamlit run app.py")
    print("="*60)


if __name__ == "__main__":
    show_quick_setup_guide()
