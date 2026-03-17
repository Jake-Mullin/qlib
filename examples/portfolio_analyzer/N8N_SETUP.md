# n8n Workflow Setup - Ultimate Stock Portfolio Analyzer

Automated daily portfolio analysis with **Gmail** email reports and **Notion** database updates.

## Overview

Every weekday at 6:00 AM EST, this workflow:

1. Runs the Portfolio Analyzer (fetches live data, runs 7 investor agents)
2. Parses the results
3. Sends a **styled HTML email** to your Gmail with top picks, earnings alerts, and full portfolio
4. Updates your **Notion database** - each stock gets a row with verdict, score, target, etc.
5. If anything fails, sends you an error email instead

**Workflow nodes:**

```
[Cron 6AM] -> [Run Analyzer] -> [Read JSON] -> [Parse Results] -> [Format Email] -> [Send Gmail]
                    |                                  |
                    |                                  +-----------> [Update Notion DB]
                    |
                    +-(on error)-> [Format Error Email] -> [Send Error Gmail]
```

## Prerequisites

- **n8n** instance (self-hosted or cloud), version 1.0+
- **Python 3.8+** with `yfinance` and `rich` installed on the n8n host
- **Gmail account** (for receiving daily reports)
- **Notion account** (free tier works - for the visual database)
- Network access to Yahoo Finance and Notion API

## Step 1: Import the Workflow

1. Open your n8n instance in a browser
2. Go to **Workflows** in the left sidebar
3. Click **"..."** menu (top right) > **Import from File**
4. Select `n8n_workflow.json` from this directory
5. The workflow will appear - open it to configure

## Step 2: Set Up Gmail

n8n uses OAuth2 to send emails through your Gmail. No app passwords needed.

1. In n8n, go to **Credentials** (left sidebar)
2. Click **Add Credential** > search for **Gmail OAuth2**
3. Follow the setup wizard:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a project (or use an existing one)
   - Enable the **Gmail API** (APIs & Services > Library > search "Gmail API")
   - Go to **APIs & Services > Credentials**
   - Click **Create Credentials > OAuth client ID**
   - Application type: **Web application**
   - Add n8n's redirect URI (n8n will show you the exact URL)
   - Copy the **Client ID** and **Client Secret** into n8n
4. Click **Sign in with Google** in n8n and authorize
5. In the workflow, click both Gmail nodes ("Send Gmail" and "Send Error Gmail") and select your new credential

**Set your email address:** Either set the `PORTFOLIO_EMAIL` environment variable, or edit the "Send To" field directly in both Gmail nodes.

## Step 3: Set Up Notion

### Create the Integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **New Integration**
3. Name it "Portfolio Analyzer"
4. Select your workspace
5. Click **Submit** and copy the **Internal Integration Token** (starts with `ntn_`)

### Create the Database

1. In Notion, create a new **full-page database** (type `/database` and select "Database - Full page")
2. Name it "Portfolio Tracker"
3. Add these columns (the n8n workflow will populate them):

| Column Name | Type | Notes |
|---|---|---|
| Ticker | Title | (default first column) |
| Company | Text | |
| Verdict | Select | Options: Buy (green), Hold (yellow), Pass (gray), Avoid (red) |
| Score | Number | Format: Number |
| Price | Number | Format: Dollar |
| 1Y Target | Number | Format: Dollar |
| Upside % | Number | Format: Percent |
| Sector | Select | Auto-populated |
| Earnings Date | Date | |
| Earnings Countdown | Number | Days until earnings |
| Valuation Score | Number | |
| Quality Score | Number | |
| Momentum Score | Number | |
| Agent Consensus | Number | |
| Bull Case | Text | |
| Bear Case | Text | |
| Top Bull Agent | Text | |
| Top Bear Agent | Text | |
| Last Updated | Date | |

4. **Share with your integration:** Click "..." (top right of the database page) > **Connections** > search for "Portfolio Analyzer" > click to add

5. **Copy the database ID:** From the database URL:
   ```
   https://notion.so/your-workspace/DATABASE_ID_HERE?v=...
   ```
   The database ID is the 32-character string before the `?`

### Alternative: Auto-Create the Database

Instead of manually creating columns, you can use the Python module to create it:

```python
from examples.portfolio_analyzer.notion_integration import NotionClient

client = NotionClient("your-notion-api-key")
db_id = client.create_database("parent-page-id", "Portfolio Tracker")
print(f"Database created: {db_id}")
```

### Set Environment Variables

In your n8n instance, set these variables (Settings > Variables, or via env):

| Variable | Required | Description |
|---|---|---|
| `NOTION_API_KEY` | Yes | Your Notion integration token (`ntn_...`) |
| `NOTION_DATABASE_ID` | Yes | The 32-char database ID from the URL |
| `PORTFOLIO_EMAIL` | Yes | Your Gmail address for reports |

For self-hosted n8n (docker-compose):

```yaml
environment:
  - NOTION_API_KEY=ntn_your_token_here
  - NOTION_DATABASE_ID=your_database_id_here
  - PORTFOLIO_EMAIL=you@gmail.com
```

## Step 4: Activate

1. Open the workflow in n8n
2. Toggle the **Active** switch (top right) to ON
3. The workflow will now run every weekday at 6 AM EST

To test immediately: click **Execute Workflow** (play button) to run it once.

## Customizing the Schedule

Open the "Daily 6AM EST (Weekdays)" node and modify the cron expression:

| Schedule | Cron Expression |
|---|---|
| Every weekday at 6:00 AM | `0 6 * * 1-5` |
| Every weekday at 8:30 AM | `30 8 * * 1-5` |
| Every day at 7:00 AM (incl. weekends) | `0 7 * * *` |
| Every Monday at 9:00 AM (weekly) | `0 9 * * 1` |
| Every 4 hours on weekdays | `0 */4 * * 1-5` |

The workflow timezone is `America/New_York` (set in workflow settings).

## Adding or Removing Tickers

### Option 1: Edit the Default List

In `run_analyzer.py`, change:

```python
DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "MU", "AMD", "CRM"]
```

### Option 2: Override in the n8n Command

Edit the "Run Portfolio Analyzer" node command:

```bash
cd /home/user/qlib && python -m examples.portfolio_analyzer --tickers AAPL MSFT NVDA MU --export /tmp/portfolio_results.json --no-details
```

### Option 3: Use an Environment Variable

```bash
cd /home/user/qlib && python -m examples.portfolio_analyzer --tickers $PORTFOLIO_TICKERS --export /tmp/portfolio_results.json --no-details
```

Then set `PORTFOLIO_TICKERS=AAPL MSFT NVDA` as an env var.

## What Your Notion Database Will Look Like

Once running, your Notion database will have:
- **Filter by Verdict** - click the filter icon to show only "Buy" stocks
- **Sort by Score** - see your highest-conviction picks at the top
- **Color-coded verdicts** - green for Buy, yellow for Hold, red for Avoid
- **Earnings countdown** - sort by this to see upcoming earnings
- **Auto-updates daily** - existing rows update, new stocks get added

You can also create **Notion views** (Board, Calendar, Gallery) on the same database:
- **Board view** grouped by Verdict = Kanban-style Buy/Hold/Pass/Avoid columns
- **Calendar view** by Earnings Date = see when each stock reports
- **Gallery view** = card-style overview of each stock

## Troubleshooting

### Gmail not sending

- Verify your Gmail OAuth2 credential is connected (green checkmark in Credentials)
- Check that the Gmail API is enabled in Google Cloud Console
- Check n8n execution logs for OAuth errors
- Make sure the `PORTFOLIO_EMAIL` is set correctly

### Notion not updating

- Verify `NOTION_API_KEY` and `NOTION_DATABASE_ID` are set
- Make sure the database is **shared with your integration** (Connections menu)
- Check that all column names match exactly (case-sensitive)
- Test the API key: `curl -H "Authorization: Bearer ntn_your_key" -H "Notion-Version: 2022-06-28" https://api.notion.com/v1/users/me`

### Script fails / times out

- Check Python deps: `pip install yfinance rich requests`
- Run manually: `cd /home/user/qlib && python -m examples.portfolio_analyzer --export /tmp/test.json --no-details`
- Increase timeout in the "Run Portfolio Analyzer" node if needed (default: 300s)
- Yahoo Finance may rate-limit large portfolios - reduce ticker count if needed

### Timezone issues

- The workflow has `timezone: "America/New_York"` in settings
- Verify your n8n instance system timezone matches expectations
