# Genesis Slack Interface

Slack bot (Socket Mode) that connects to Genesis agents via MonitoredInterface, enabling interactive conversations through Slack channels and threads.

## Prerequisites

- Python 3.10
- Genesis installed (`pip install -e .` from project root)
- Slack extras: `pip install -e ".[slack]"`
- RTI Connext DDS configured (run `./setup.sh` from project root)
- An OpenAI or Anthropic API key in `.env`

## Slack App Setup (One-Time)

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) and click **Create New App**
2. Choose **From scratch**, name it "Genesis", pick your workspace
3. Under **OAuth & Permissions**, add Bot Token Scopes:
   - `chat:write`, `channels:history`, `groups:history`, `im:history`, `mpim:history`, `commands`
4. Click **Install to Workspace**, copy the **Bot User OAuth Token** (`xoxb-...`)
5. Under **Socket Mode**, enable it, create an **App-Level Token** (`xapp-...`) with `connections:write` scope
6. Under **Slash Commands**, create:
   - `/genesis-agents`
   - `/genesis-connect`
   - `/genesis-disconnect`
   - `/genesis-status`
7. Under **Event Subscriptions**, subscribe to bot events:
   - `message.channels`, `message.groups`, `message.im`, `message.mpim`
8. Add tokens to your `.env` file:
   ```bash
   echo 'SLACK_BOT_TOKEN=xoxb-your-token' >> ../../.env
   echo 'SLACK_APP_TOKEN=xapp-your-token' >> ../../.env
   ```

## Running

```bash
./run_slack.sh
```

The script will:
1. Start a PersistentMemoryAgent in the background
2. Wait for DDS discovery
3. Start the Slack bot in the foreground (Socket Mode — no public URL needed)
4. Print setup instructions if tokens are not set

Press **Ctrl+C** to stop both the bot and the agent.

### Options

```bash
./run_slack.sh --config config/slack_config.json  # Use config file
./run_slack.sh --verbose                           # Debug logging
```

## Slash Commands

| Command | Description |
|---------|-------------|
| `/genesis-agents` | List available agents (Block Kit buttons) |
| `/genesis-connect <service>` | Connect to a specific agent |
| `/genesis-disconnect` | Disconnect from current agent |
| `/genesis-status` | Show connected agent and conversation ID |

Send any message to chat with the connected agent. Responses are sent in threads.

## Configuration

Configuration can be set via environment variables or a JSON config file. Environment variables take precedence.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SLACK_BOT_TOKEN` | Bot User OAuth Token (`xoxb-...`) (required) |
| `SLACK_APP_TOKEN` | App-Level Token (`xapp-...`) for Socket Mode (required) |

### Config File

See `config/slack_config.example.json` for the full structure.

## Architecture

```
Slack User → slack-bolt (Socket Mode) → SlackGenesisInterface → MonitoredInterface → DDS → Genesis Agent
```

Sessions are scoped by channel and thread. Each thread gets a unique `conversation_id` (`slack-{channel}:{thread_ts}`), so conversations are isolated and persist across bot restarts when using PersistentMemoryAgent.
