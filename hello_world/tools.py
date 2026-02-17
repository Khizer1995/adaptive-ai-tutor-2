from crewai.tools import tool
from profile_manager import ProfileManager

class MonitoringTools:
    @tool("analyze_sentiment_and_update")
    def analyze_sentiment_and_update(chat_text: str, student_id: str):
        """Analyzes text for keywords like 'confused' or 'help' to update frustration levels."""
        manager = ProfileManager()
        profile = manager.load_profile(student_id)
        
        # Logic: Increment frustration for 'red flag' keywords
        red_flags = ["confused", "don't understand", "help", "too hard", "repeat"]
        if any(flag in chat_text.lower() for flag in red_flags):
            profile.frustration_level = min(10, profile.frustration_level + 2)
        
        # Logic: Check for 'green flags' of mastery
        green_flags = ["i get it", "makes sense", "thank you", "clear"]
        if any(flag in chat_text.lower() for flag in green_flags):
            profile.frustration_level = max(0, profile.frustration_level - 1)
            
        manager.save_profile(profile)
        return f"Updated frustration level to {profile.frustration_level}"