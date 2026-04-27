# Genesis Telegram Interface

Telegram bot that connects to Genesis agents via MonitoredInterface, enabling interactive conversations through Telegram.

## Prerequisites

- Python 3.10
- Genesis installed (`pip install -e .` from project root)
- Telegram extras: `pip install -e ".[telegram]"`
- RTI Connext DDS configured (run `./setup.sh` from project root)
- An OpenAI or Anthropic API key in `.env`

## BotFather Setup (One-Time)

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts to create a bot
3. Copy the bot token (looks like: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
4. Add to your `.env` file:
   ```bash
   echo 'TELEGRAM_BOT_TOKEN=your-token-here' >> ../../.env
   ```

## Running

```bash
./run_telegram.sh
```

The script will:
1. Start a PersistentMemoryAgent in the background
2. Wait for DDS discovery
3. Start the Telegram bot in the foreground
4. Print setup instructions if `TELEGRAM_BOT_TOKEN` is not set

Press **Ctrl+C** to stop both the bot and the agent.

### Options

```bash
./run_telegram.sh --config config/telegram_config.json  # Use config file
./run_telegram.sh --verbose                              # Debug logging
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with command list |
| `/agents` | List available agents (inline keyboard) |
| `/disconnect` | Disconnect from current agent |
| `/status` | Show connected agent and conversation ID |

Send any text message to chat with the connected agent.

## Configuration

Configuration can be set via environment variables or a JSON config file. Environment variables take precedence.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather (required) |

### Config File

See `config/telegram_config.example.json` for the full structure.

## Architecture

```
Telegram User → python-telegram-bot → TelegramGenesisInterface → MonitoredInterface → DDS → Genesis Agent
```

Each Telegram chat gets a deterministic `conversation_id` (`telegram-{chat_id}`), so conversations persist across bot restarts when using PersistentMemoryAgent.
