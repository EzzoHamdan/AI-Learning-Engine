#!/usr/bin/env python3
"""
AI Quiz Generator - Easy Setup Wizard
====================================
This script helps you configure the AI Quiz Generator with minimal effort.
Perfect for both programmers and non-technical users!
"""

import subprocess
import sys


# Color codes for pretty output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    """Print a colorful header."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKBLUE}ℹ️  {text}{Colors.ENDC}")


def check_python_version() -> bool:
    """Check if Python version is compatible."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print_success(f"Python {version.major}.{version.minor} detected - Compatible!")
        return True
    else:
        print_error(f"Python {version.major}.{version.minor} detected - Requires Python 3.8+")
        return False


def install_dependencies() -> bool:
    """Install the project and its dependencies (editable install)."""
    print_info("Installing the app and its dependencies...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."], check=True, capture_output=True
        )
        print_success("All packages installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install packages: {e}")
        return False


def _ollama_settings():
    """The configured Ollama settings.

    Imported lazily: the wizard runs `install_dependencies()` first, so the
    package is not importable until after that step.
    """
    from learning_engine.settings import get_settings

    return get_settings().llm.ollama


def get_ollama_models() -> list[str]:
    """Get list of available Ollama models (the one probe lives in llm/providers)."""
    from learning_engine.llm.providers import list_ollama_models

    return list_ollama_models(_ollama_settings().base_url)


def check_ollama_available() -> bool:
    """Check if Ollama is running with at least one model installed."""
    return bool(get_ollama_models())


def setup_local_ai():
    """Guide user through Local AI setup."""
    print_header("LOCAL AI SETUP (FREE & PRIVATE)")
    print("Local AI runs completely on your computer - no API keys needed!")
    print("This is the recommended option for privacy and cost.\n")

    default_model = _ollama_settings().chat_model

    models = get_ollama_models()
    if models:
        print_success(f"Ollama is running with {len(models)} models available:")
        for model in models:
            print(f"  • {model}")
        return True, models[0]
    print_info("Ollama is not running, not installed, or has no models.")

    print("\n📥 To set up Local AI:")
    print("1. Visit: https://ollama.ai")
    print("2. Download and install Ollama")
    print("3. Open a terminal/command prompt")
    print(f"4. Run: ollama pull {default_model}")
    print("5. Run: ollama serve")

    choice = input("\nDo you want to continue with Local AI setup? (y/N): ").lower().strip()
    if choice == "y":
        print("\n⏳ Please complete the Ollama setup above, then press Enter to continue...")
        input()

        models = get_ollama_models()
        if models:
            print_success("Local AI is now ready!")
            return True, models[0]

    return False, None


def setup_google_ai():
    """Guide user through Google AI setup."""
    print_header("GOOGLE AI STUDIO SETUP (FREE TIER, NO CARD)")
    print("Google AI Studio issues a key with a free tier — no credit card needed.")
    print("There is a daily request cap; Google changes it, so check their")
    print("rate-limits page rather than trusting a number printed here.\n")

    print("📝 To get your Google AI API key:")
    print("1. Visit: https://aistudio.google.com/app/apikey")
    print("2. Sign in with your Google account")
    print("3. Click 'Create API Key'")
    print("4. Copy the API key that starts with 'AIza...'")

    api_key = input("\nEnter your Google AI API key (or press Enter to skip): ").strip()

    if api_key:
        if api_key.startswith("AIza"):
            print_success("Google AI API key looks valid!")
            return True, api_key
        else:
            print_warning("API key doesn't look right. Should start with 'AIza'")

    return False, None


def setup_openrouter():
    """Guide user through OpenRouter setup."""
    print_header("OPENROUTER SETUP (FREE TIER, NO CARD)")
    print("OpenRouter puts many models behind one key, including free ones.")
    print("This is a SECOND free allowance on top of Google AI Studio's —")
    print("configure both and you can switch in the sidebar when one runs out.\n")

    print("📝 To get your OpenRouter API key:")
    print("1. Visit: https://openrouter.ai/keys")
    print("2. Sign in (GitHub or Google works)")
    print("3. Click 'Create Key'")
    print("4. Copy the API key that starts with 'sk-or-'")

    api_key = input("\nEnter your OpenRouter API key (or press Enter to skip): ").strip()

    if api_key:
        if api_key.startswith("sk-or-"):
            print_success("OpenRouter API key looks valid!")
            return True, api_key
        else:
            print_warning("API key doesn't look right. Should start with 'sk-or-'")

    return False, None


def setup_openai():
    """Guide user through OpenAI setup."""
    print_header("OPENAI SETUP (PAY-PER-USE)")
    print("OpenAI provides high-quality results but charges per use.")
    print("Good for professional use or when you need the best quality.\n")

    print("📝 To get your OpenAI API key:")
    print("1. Visit: https://platform.openai.com/api-keys")
    print("2. Sign in or create an account")
    print("3. Click 'Create new secret key'")
    print("4. Copy the API key that starts with 'sk-'")
    print("5. Add billing information (required for API usage)")

    api_key = input("\nEnter your OpenAI API key (or press Enter to skip): ").strip()

    if api_key:
        if api_key.startswith("sk-"):
            print_success("OpenAI API key looks valid!")
            return True, api_key
        else:
            print_warning("API key doesn't look right. Should start with 'sk-'")

    return False, None


def create_env_file(
    local_ai: bool = False,
    local_model: str = "",
    google_ai: bool = False,
    google_key: str = "",
    openrouter: bool = False,
    openrouter_key: str = "",
    openai: bool = False,
    openai_key: str = "",
):
    """Create the .env configuration file.

    The default provider is the first free option configured — a wizard that
    silently started someone on the paid provider would be a bad default.
    """
    if local_ai:
        default_provider = "ollama"
    elif google_ai:
        default_provider = "google"
    elif openrouter:
        default_provider = "openrouter"
    elif openai:
        default_provider = "openai"
    else:
        default_provider = "ollama"

    env_content = f"""# AI Quiz Generator Configuration
# Generated by setup wizard. See .env.example for every available setting.

# API Keys
OPENAI_API_KEY="{openai_key}"
GOOGLE_AI_API_KEY="{google_key}"
OPENROUTER_API_KEY="{openrouter_key}"

# Which provider to start on: ollama | google | openrouter | openai
LLM__DEFAULT_PROVIDER={default_provider}

# Advanced Settings
LLM__OLLAMA__CHAT_MODEL="{local_model}"
DEBUG=false
"""

    with open(".env", "w") as f:
        f.write(env_content)

    print_success("Configuration file (.env) created!")


def main():
    """Main setup wizard."""
    print_header("AI QUIZ GENERATOR - EASY SETUP")
    print("Welcome! This wizard will help you set up the AI Quiz Generator.")
    print("You can choose from multiple AI providers based on your needs.")
    print("💸 Three of the four are FREE and need no credit card — you can set")
    print("   up more than one and switch between them from the sidebar.\n")

    # Check Python version
    if not check_python_version():
        print_error("Please upgrade to Python 3.8+ and try again.")
        sys.exit(1)

    # Install dependencies
    if not install_dependencies():
        print_error("Failed to install dependencies. Please check your internet connection.")
        sys.exit(1)

    # Provider setup
    configurations = []

    print_info("Let's configure your AI provider(s). You can set up multiple options!")

    # Option 1: Local AI (recommended)
    print_info("\n🏠 Option 1: Local AI (Recommended)")
    local_ai, local_model = setup_local_ai()
    if local_ai:
        configurations.append(("Local AI", local_ai, local_model))

    # Option 2: Google AI (free tier)
    print_info("\n🆕 Option 2: Google AI Studio (free tier)")
    google_ai, google_key = setup_google_ai()
    if google_ai:
        configurations.append(("Google AI", google_ai, google_key))

    # Option 3: OpenRouter (free tier) — a second, independent free allowance.
    print_info("\n🆓 Option 3: OpenRouter (free tier)")
    openrouter, openrouter_key = setup_openrouter()
    if openrouter:
        configurations.append(("OpenRouter", openrouter, openrouter_key))

    # Option 4: OpenAI
    print_info("\n⚡ Option 4: OpenAI (paid)")
    openai_ai, openai_key = setup_openai()
    if openai_ai:
        configurations.append(("OpenAI", openai_ai, openai_key))

    # Create configuration
    if not configurations:
        print_warning("No AI providers configured. You can still run the app and configure later.")
        create_env_file()
    else:
        print_success(f"\n✨ Great! You've configured {len(configurations)} AI provider(s):")
        for name, _, _ in configurations:
            print(f"  • {name}")

        # Create .env file
        create_env_file(
            local_ai=local_ai,
            local_model=local_model or _ollama_settings().chat_model,
            google_ai=google_ai,
            google_key=google_key or "",
            openrouter=openrouter,
            openrouter_key=openrouter_key or "",
            openai=openai_ai,
            openai_key=openai_key or "",
        )

    print_header("SETUP COMPLETE!")
    print_success("🎉 Setup completed successfully!")
    print_info("\n📚 Next steps:")
    print("1. Run the app: type 'streamlit run app.py' in your terminal")
    print("2. Upload a document (PDF, Word, or PowerPoint)")
    print("3. Generate your first AI quiz!")
    print("\n💡 Tips:")
    print("• Start with a short document (1-3 pages) for best results")
    print("• Try different difficulty levels to match your needs")
    print("• Local AI is private but may be slower than cloud options")
    print("• Google AI Studio and OpenRouter have separate free allowances —")
    print("  set up both, and switch in the sidebar when one hits its daily cap")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_info("\n\nSetup cancelled by user.")
    except Exception as e:
        print_error(f"Setup failed with error: {e}")
        print_info("You can still set up manually by copying .env.example to .env")
