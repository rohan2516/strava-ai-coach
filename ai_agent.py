from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from strava_client import StravaClient
from datetime import datetime


SYSTEM_PROMPT = """You are an expert AI fitness coach and data analyst with deep knowledge of endurance sports, training theory, and athlete performance optimization.

You have been given the athlete's recent Strava activity data. Your job is to:
1. Answer questions about their workouts with precision and insight
2. Identify trends, patterns, and areas for improvement
3. Provide evidence-based coaching advice
4. Be encouraging but honest about the data

=== ATHLETE PROFILE ===
{athlete_profile}

=== ACTIVITY DATA ===
{activity_data}

=== TODAY'S DATE ===
{today}

Guidelines:
- Always reference specific activities, dates, and numbers when answering
- Use proper units (km, km/h, bpm, minutes/km for pace)
- When calculating weekly/monthly stats, group activities by date
- For training advice, consider load, recovery, and progression
- Be conversational but data-driven
- If asked about something not in the data, say so clearly
- Keep responses focused and readable — use bullet points or short paragraphs
"""


class StravaAgent:
    """
    LangChain-powered conversational agent over Strava activity data.
    Uses Claude as the LLM backbone.
    """

    def __init__(self, anthropic_api_key: str, activities: list[dict], athlete: dict = None):
        self.activities = activities
        self.athlete = athlete or {}

        self.llm = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=anthropic_api_key,
            temperature=0.3,
            max_tokens=1500,
        )

        # Build context once at init
        self.activity_context = StravaClient.format_activities_for_llm(activities)
        self.athlete_context = StravaClient.format_athlete_for_llm(athlete)

        self.system_prompt = SYSTEM_PROMPT.format(
            athlete_profile=self.athlete_context or "Not available",
            activity_data=self.activity_context,
            today=datetime.now().strftime("%A, %B %d, %Y"),
        )

    def ask(self, question: str, history: list[dict] = None) -> str:
        """
        Ask a question about the athlete's Strava data.

        Args:
            question: The user's question
            history: Previous chat messages [{"role": "user"|"assistant", "content": str}]

        Returns:
            The AI coach's response as a string
        """
        messages = [SystemMessage(content=self.system_prompt)]

        # Inject conversation history (last 10 turns max to manage context)
        for msg in (history or [])[-10:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=question))

        response = self.llm.invoke(messages)
        return response.content

    def get_summary(self) -> str:
        """Generate a quick summary of recent training without a specific question."""
        return self.ask(
            "Give me a brief executive summary of my recent training: "
            "key stats, highlights, and one actionable coaching tip."
        )
