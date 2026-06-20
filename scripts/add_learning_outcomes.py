"""
Add pretest/posttest scores to student profiles for evaluation metrics.
Calculates from existing learning_history.
"""

import json
from pathlib import Path

PROFILES_DIR = Path(__file__).resolve().parents[1] / "profiles"


def calculate_normalized_gain(pretest: float, posttest: float) -> float:
    """Hake normalized learning gain formula."""
    if pretest >= 1.0:
        return 0.0
    return round((posttest - pretest) / (1.0 - pretest), 4)


def update_profile(profile_path: Path):
    """Add pretest/posttest to a single profile."""
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile = json.load(f)
    except json.JSONDecodeError as e:
        print(f"  ✗ {profile_path.name}: JSON error - {e}")
        return False
    
    history = profile.get("learning_history", [])
    
    if not history:
        print(f"  ⚠ {profile_path.name}: No learning history")
        return False
    
    # Extract scores
    scores = [entry.get("score", 0.0) for entry in history if "score" in entry]
    
    if not scores or len(scores) < 2:
        print(f"  ⚠ {profile_path.name}: Insufficient scores ({len(scores)})")
        return False
    
    pretest = float(scores[0])
    posttest = float(scores[-1])
    gain = round(posttest - pretest, 4)
    normalized = calculate_normalized_gain(pretest, posttest)
    
    # Update profile
    profile["pretest_score"] = pretest
    profile["posttest_score"] = posttest
    profile["learning_gain"] = gain
    profile["normalized_learning_gain"] = normalized
    
    # Write back
    with open(profile_path, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=4)
    
    print(f"  ✓ {profile_path.name}: pretest={pretest:.2f}, posttest={posttest:.2f}, gain={gain:.2f}, norm={normalized:.2f}")
    return True


def main():
    print("Adding Learning Outcomes to Profiles\n")
    
    profile_files = list(PROFILES_DIR.glob("*.json"))
    updated = 0
    
    for profile_path in sorted(profile_files):
        if update_profile(profile_path):
            updated += 1
    
    print(f"\n✓ Updated {updated}/{len(profile_files)} profiles")


if __name__ == "__main__":
    main()
