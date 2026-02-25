# Crypto Summary Bot v2

AI-powered Telegram bot that provides daily morning and evening cryptocurrency summaries for OWB and Rainbow (RNBW) tokens.

## Features

- **Scheduled Summaries**: Automatic reports at 8:00 AM and 11:00 PM MSK
- **AI-Powered Analysis**: Uses Google Gemma (via OpenRouter) to analyze market data
- **Multi-Source Data**: CoinMarketCap, DexScreener, and Twitter/X
- **Admin Panel**: Password-protected admin dashboard with "Run Summary" button
- **Developer Panel**: Add/remove coins, edit AI templates, teach AI new context
- **User Analytics**: Track user engagement and bot usage
- **Trainable AI**: AI remembers context through persistent memory and editable templates
- **Support Project**: Built-in donation button with EVM address

## Data Sources

| Source | Data |
|--------|------|
| CoinMarketCap | Prices, market cap, volume, % changes |
| DexScreener | DEX pairs, buy/sell transactions, liquidity |
| Twitter/X (Nitter RSS) | Social sentiment, news, hashtag mentions |

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/BOSSincrypto/crypto-summary-bot-v2.git
cd crypto-summary-bot-v2
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# Required
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
OPENROUTER_API_KEY=your_openrouter_api_key

# Recommended
COINMARKETCAP_API_KEY=your_cmc_api_key

# Optional (override default Nitter instances, comma-separated)
# NITTER_INSTANCES=https://nitter.poast.org,https://xcancel.com

# Admin password (default: admin123)
ADMIN_PASSWORD=your_secure_password

# Database path (default: bot.db, use /data/bot.db for fly.io)
DB_PATH=bot.db
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run locally

```bash
python run.py
```

## API Keys Setup

### Telegram Bot Token
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Use `/newbot` to create a new bot
3. Copy the token provided

### OpenRouter API Key
1. Sign up at [openrouter.ai](https://openrouter.ai/)
2. Go to API Keys section
3. Create a new API key
4. The bot uses `google/gemma-3n-e4b-it` model

### CoinMarketCap API Key
1. Sign up at [coinmarketcap.com/api](https://coinmarketcap.com/api/)
2. Get your free API key from the dashboard
3. Free tier allows 333 calls/day

### Twitter/X Data (via Nitter RSS)
No API key needed! The bot uses free Nitter RSS feeds to fetch tweets.
Nitter instances are built-in with automatic fallback.
Optionally override with `NITTER_INSTANCES` env var (comma-separated URLs).

## Deploy to Fly.io

### 1. Install Fly CLI

```bash
curl -L https://fly.io/install.sh | sh
```

### 2. Login and create app

```bash
fly auth login
fly launch --no-deploy
```

### 3. Create persistent volume

```bash
fly volumes create bot_data --size 1 --region ams
```

### 4. Set secrets

```bash
fly secrets set TELEGRAM_BOT_TOKEN=your_token
fly secrets set OPENROUTER_API_KEY=your_key
fly secrets set COINMARKETCAP_API_KEY=your_key
fly secrets set ADMIN_PASSWORD=your_password
# Optional (override Nitter instances):
# fly secrets set NITTER_INSTANCES=https://nitter.poast.org,https://xcancel.com
```

### 5. Deploy

```bash
fly deploy
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Main menu with all options |
| `/summary` | Generate on-demand summary |
| `/price` | Quick price check |
| `/help` | Help and tips |
| `/support` | Support the project (EVM donation) |
| `/admin` | Admin panel (password required) |
| `/dev` | Developer panel (password required) |

## Admin Panel

Access with `/admin` + admin password:
- **Run Summary Now** — Test summary generation instantly
- **User Analytics** — View user stats and engagement
- **Manage Coins** — View tracked coins
- **AI Templates** — View system and summary templates
- **AI Memory** — View learned context
- **Bot Settings** — View API configuration status

## Developer Panel

Access with `/dev` + admin password:
- **Add New Coin** — Step-by-step coin addition
- **Manage Coins** — Toggle active/inactive, remove coins
- **Edit AI Templates** — Modify system prompt and summary format
- **Manage AI Memory** — Add/remove learned context
- **Teach AI** — Quick knowledge addition (key: value format)
- **System Stats** — Detailed system overview

## Architecture

```
bot/
├── main.py              # Entry point, handler registration
├── config.py            # Environment configuration
├── database.py          # SQLite database layer
├── scheduler.py         # Scheduled summary jobs
├── handlers/
│   ├── start.py         # /start, /help, main menu
│   ├── summary.py       # Summary generation & price checks
│   ├── admin.py         # Admin panel & analytics
│   ├── developer.py     # Developer tools & coin management
│   └── support.py       # Donation/support page
└── services/
    ├── coinmarketcap.py # CoinMarketCap API client
    ├── dexscreener.py   # DexScreener API client
    ├── twitter.py       # Twitter/X via Nitter RSS
    └── ai_agent.py      # OpenRouter AI agent
```

## License

MIT
