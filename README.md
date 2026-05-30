# 🏃 Strava AI Coach

A conversational AI coach built with **LangChain + Streamlit + Claude** that connects to your Strava account and lets you chat about your workouts.

## Features

- 🔗 Connects directly to Strava API
- 📊 Shows summary stats (total km, hours, elevation)
- 🏃 Lists recent activities with filtering by sport type
- 💬 Conversational AI powered by Claude + LangChain
- 🧠 Maintains chat history for follow-up questions
- 💡 Suggested questions to get started

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Get your API keys

**Anthropic API Key:**
- Sign up at [console.anthropic.com](https://console.anthropic.com)
- Create an API key

**Strava Credentials:**
1. Go to [strava.com/settings/api](https://www.strava.com/settings/api)
2. Create a new app (use `http://localhost` as the website and `http://localhost:8080` as the OAuth callback URL)
3. Note your **Client ID** and **Client Secret**

### 3. Get your Strava Access Token

```bash
python get_token.py
```

This opens your browser, lets you authorize the app, and prints your access token.

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your actual keys
```

### 5. Run the app

```bash
streamlit run app.py
```

## Usage

1. Open `http://localhost:8501` in your browser
2. Enter your API keys in the left sidebar (or set them in `.env`)
3. Click **Connect & Load Data**
4. Start chatting with your AI coach!

## Example Questions

- "What's my average pace this month?"
- "How many km did I run last week?"
- "Which activity had the highest heart rate?"
- "Am I overtraining? How's my weekly load looking?"
- "What should my next workout be?"
- "How has my cycling speed improved over time?"
- "What's my longest run ever in this dataset?"

## Project Structure

```
strava-ai-assistant/
├── app.py              # Streamlit UI
├── strava_client.py    # Strava API v3 client
├── ai_agent.py         # LangChain + Claude agent
├── get_token.py        # OAuth helper to get access token
├── requirements.txt
├── .env.example
└── README.md
```

## Token Refresh

Strava access tokens expire after 6 hours. To refresh:
- Re-run `python get_token.py`
- Or implement the refresh token flow using your `refresh_token`

## Notes

- Free Anthropic tier is sufficient for typical usage
- The app loads activities once per session; click "Connect" again to refresh
- Chat history is maintained within a session but not persisted across restarts
