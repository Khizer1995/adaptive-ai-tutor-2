from crewai import Agent
from models import StudentProfile

class MonitorAgent():
    def monitor_student_agent(self):
        return Agent(
            role='Learning Progress Monitor',
            goal='Analyze student interactions to detect frustration or mastery.',
            backstory="""You are an expert in educational psychology. Your job is to 
            look at the conversation history between a student and a teacher. 
            You identify if the student is confused, happy, or has successfully 
            learned a concept. You provide structured updates for the student profile.""",
            verbose=True,
            allow_delegation=False,
            # We will add tools here on Day 5!
            tools=[]
        )