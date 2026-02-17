from crewai import Crew, Process
import re
from monitoring_crew import MonitoringSkeleton
from profile_manager import ProfileManager


def run_monitoring_check(chat_logs):
    # Initialize your skeleton
    monitor_setup = MonitoringSkeleton()
    
    # Create the task with current logs
    task = monitor_setup.create_monitoring_task(chat_logs)
    
    # Create a temporary crew to run the check
    crew = Crew(
        agents=[monitor_setup.monitor_agent],
        tasks=[task],
        process=Process.sequential
    )
    
    return crew.kickoff()

# Example of the 'Contract' in action:
# chat_example = "Student: I don't get this. It's too hard. Can you explain again?"
# result = run_monitoring_check(chat_example)

def sync_student_progress(student_id: str, agent_result: str):
    """
    Parses the agent's output and updates the JSON profile.
    """
    manager = ProfileManager()
    profile = manager.load_profile(student_id)
    
    # Extract numerical frustration level from agent text
    match = re.search(r"frustration_level[:\s]+(\d+)", agent_result.lower())
    if match:
        new_score = int(match.group(1))
        profile.frustration_level = new_score
        manager.save_profile(profile)
        print(f"✅ Sync Successful: {student_id} frustration set to {new_score}")
    else:
        print("⚠️ Sync Warning: Could not find frustration score in agent output.")