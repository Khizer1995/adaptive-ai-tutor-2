import os
from dotenv import load_dotenv
from crewai import Agent, Task, LLM
from tools import MonitoringTools

# 1. Load the Gemini API Key from .env
load_dotenv()

# 2. Define the Gemini LLM correctly for CrewAI
# Use the prefix 'gemini/' so the underlying engine knows the provider.
gemini_llm = LLM(
    model="gemini-3-flash-preview",
    api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.2  # Low temperature for more deterministic monitoring
)

class MonitoringSkeleton:
    def __init__(self):
        # 3. Initialize the Agent with the Gemini LLM
        self.monitor_agent = Agent(
            role='Learning Progress Monitor',
            goal='Analyze conversation logs to detect student frustration or mastery.',
            backstory="""You are an expert in educational psychology. You observe 
            interactions to update the Student Profile without intervening.""",
            llm=gemini_llm,
            tools=[MonitoringTools().analyze_sentiment_and_update],
            verbose=True
        )

    def create_monitoring_task(self, conversation_history):
        # 4. Define the Task 'Contract'
        return Task(
            description=f"Analyze this chat log for frustration and mastery: {conversation_history}",
            expected_output="""A summary including frustration_level (int), 
            mastered_topics (list), and suggested_learning_style (str).""",
            agent=self.monitor_agent
        )
