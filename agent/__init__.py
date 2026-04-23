"""AlphaWhale agent — AI-powered finance tools, chains, and graphs."""

from pathlib import Path

from dotenv import load_dotenv

# Load .env from monorepo root into os.environ so LangChain, OpenAI,
# and LangSmith all pick up their standard env vars automatically.
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_ENV_FILE)
