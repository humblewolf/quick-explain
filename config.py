import os


def load_env_file():
    """
    Load environment variables from a .env file if present.
    Checks the directory containing config.py and current working directory.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]

    for env_path in candidates:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip().strip("'\"")
                            if key:
                                os.environ[key] = val
            except Exception as e:
                print(f"Warning: Could not read {env_path}: {e}")
            break


load_env_file()


# ---------------------------------------------------------------------
# Configuration Properties
# ---------------------------------------------------------------------

# Window opacity (0.0 to 1.0) - default 0.5 (50% opacity)
WINDOW_OPACITY = float(os.environ.get("WINDOW_OPACITY", "0.5"))

# Default window size as percentage of screen dimensions (0.1 to 1.0)
WINDOW_WIDTH_RATIO = float(os.environ.get("WINDOW_WIDTH_RATIO", "0.7"))
WINDOW_HEIGHT_RATIO = float(os.environ.get("WINDOW_HEIGHT_RATIO", "0.7"))

# Window decoration (False = frameless floating pane, True = standard OS window titlebar)
WINDOW_DECORATED = os.environ.get("WINDOW_DECORATED", "false").lower() in (
    "true",
    "1",
    "yes",
)

# OpenAI Model & API Key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")


def load_system_prompt():
    """
    Load system prompt from system_prompt.txt if present.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "system_prompt.txt"),
        os.path.join(os.getcwd(), "system_prompt.txt"),
    ]
    for prompt_path in candidates:
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return content
            except Exception as e:
                print(f"Warning: Could not read {prompt_path}: {e}")

    return "You are a helpful general-purpose explainer."


SYSTEM_PROMPT = load_system_prompt()

