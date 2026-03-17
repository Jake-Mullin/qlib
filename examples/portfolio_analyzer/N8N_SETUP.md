# n8n Workflow Setup - Ultimate Stock Portfolio Analyzer

This guide explains how to set up the automated daily portfolio analysis workflow in n8n.

## Overview

The workflow runs the Portfolio Analyzer every weekday at 6:00 AM EST, parses the results, and sends a formatted summary to Slack. If the analyzer fails, an error notification is sent instead.

**Workflow nodes:**

1. **Cron Trigger** - Fires at 6:00 AM EST, Monday through Friday
2. **Execute Command** - Runs the analyzer script with JSON export
3. **Read File** - Loads the exported JSON results
4. **Parse JSON** - Extracts macro data, verdicts, top picks, and earnings alerts
5. **Format Message** - Builds a human-readable summary report
6. **Send to Slack** - Posts the report via webhook
7. **Error Handler** - Catches script failures and sends an error notification

## Prerequisites

- n8n instance (self-hosted or cloud), version 1.0 or later
- Python 3.8+ with `yfinance` and `rich` installed on the n8n host
- Network access to Yahoo Finance from the n8n host
- The qlib repository cloned at `/home/user/qlib`

## Importing the Workflow

1. Open your n8n instance in a browser.
2. Go to **Workflows** in the left sidebar.
3. Click the **"..."** menu (top right) and select **Import from File**.
4. Select `n8n_workflow.json` from this directory.
5. The workflow will appear in your workflow list. Open it to configure.

Alternatively, you can copy the contents of `n8n_workflow.json` and use **Import from URL / Paste** in the n8n UI.

## Environment Variables

Set these environment variables in your n8n instance under **Settings > Variables** (or via `N8N_` prefixed env vars if self-hosted):

| Variable | Required | Description |
|---|---|---|
| `SLACK_WEBHOOK_URL` | Yes | Your Slack incoming webhook URL |

For self-hosted n8n, you can set this in your `.env` file or docker-compose:

```bash
# In your n8n .env file or docker-compose environment section
SLACK_WEBHOOK_URL=<your-slack-webhook-url-here>
```

If you prefer not to use environment variables, you can edit the webhook URL directly in the "Send to Slack" and "Send Error to Slack" nodes.

## Configuring the Slack Webhook

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps).
2. Click **Create New App** (or select an existing app).
3. Choose **From scratch**, give it a name (e.g., "Portfolio Analyzer"), and select your workspace.
4. In the app settings, go to **Incoming Webhooks** and toggle it **On**.
5. Click **Add New Webhook to Workspace**.
6. Select the channel where reports should be posted and click **Allow**.
7. Copy the webhook URL (it looks like `https://hooks.slack.com/services/T.../B.../xxx`).
8. Set it as the `SLACK_WEBHOOK_URL` environment variable (see above).

### Using Email Instead of Slack

To send reports via email instead of Slack:

1. Delete the "Send to Slack" and "Send Error to Slack" nodes.
2. Add an **Email Send** node (n8n-nodes-base.emailSend) in their place.
3. Configure your SMTP credentials in n8n under **Credentials**.
4. Set the email subject to something like `Portfolio Report - {{$json.generated_at}}`.
5. Set the email body to `{{$json.message}}`.
6. Reconnect the wires from "Format Summary Message" and "Format Error Message" to the new email nodes.

## Customizing the Schedule

The cron trigger is set to `0 6 * * 1-5` (6:00 AM, Monday-Friday).

To change it, open the "Daily 6AM EST (Weekdays)" node and modify the cron expression:

| Schedule | Cron Expression |
|---|---|
| Every weekday at 6:00 AM | `0 6 * * 1-5` |
| Every weekday at 8:30 AM | `30 8 * * 1-5` |
| Every day (including weekends) at 7:00 AM | `0 7 * * *` |
| Every Monday at 9:00 AM (weekly) | `0 9 * * 1` |
| Every 4 hours on weekdays | `0 */4 * * 1-5` |

**Important:** The workflow timezone is set to `America/New_York`. If your n8n instance uses a different default timezone, verify the workflow-level timezone setting under **Settings** (gear icon in the workflow editor). The cron times are interpreted in the workflow timezone.

## Adding or Removing Tickers

The default tickers are defined in the analyzer script at:

```
/home/user/qlib/examples/portfolio_analyzer/run_analyzer.py
```

The default list is: `AAPL, MSFT, NVDA, GOOGL, AMZN, META, TSLA, MU, AMD, CRM`

### Option 1: Edit the Default List

Edit the `DEFAULT_TICKERS` list in `run_analyzer.py`:

```python
DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "MU", "AMD", "CRM"]
```

Add or remove tickers as needed. This changes the defaults for all invocations.

### Option 2: Override via the Command

Edit the "Run Portfolio Analyzer" node in the workflow and modify the command:

```bash
cd /home/user/qlib && python -m examples.portfolio_analyzer --tickers AAPL MSFT NVDA GOOGL AMZN --export /tmp/portfolio_results.json --no-details
```

Use the `--tickers` flag followed by space-separated ticker symbols. This overrides the defaults without changing the source code.

### Option 3: Use an Environment Variable

Modify the command in the Execute Command node to read from an env var:

```bash
cd /home/user/qlib && python -m examples.portfolio_analyzer --tickers $PORTFOLIO_TICKERS --export /tmp/portfolio_results.json --no-details
```

Then set `PORTFOLIO_TICKERS` as an environment variable (`AAPL MSFT NVDA`). This lets you change tickers without editing the workflow.

## Troubleshooting

### The workflow runs but the script fails

- Check that Python and dependencies are installed: `pip install yfinance rich`
- Verify the working directory exists: `ls /home/user/qlib`
- Run the command manually to see errors: `cd /home/user/qlib && python -m examples.portfolio_analyzer --export /tmp/portfolio_results.json --no-details`

### No Slack message arrives

- Verify `SLACK_WEBHOOK_URL` is set correctly in n8n environment variables.
- Test the webhook manually: `curl -X POST -H 'Content-type: application/json' --data '{"text":"Test"}' YOUR_WEBHOOK_URL`
- Check the n8n execution log for HTTP errors on the Slack node.

### The script times out

- The default timeout is 300 seconds (5 minutes). If you have many tickers, increase the timeout in the "Run Portfolio Analyzer" node.
- Yahoo Finance rate limits may slow down large portfolios. Consider reducing the ticker count or adding delays in the analyzer.

### Timezone issues

- Verify your n8n instance system timezone matches your expectations.
- The workflow has `timezone: "America/New_York"` in its settings, which should override the instance default for this workflow.
