import tempfile

from core.profile_manager import ProfileManager


def test_student_profile_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProfileManager(profiles_dir=tmpdir)

        created = pm.create_profile("TEST-001", name="Test User", level="beginner")
        assert created["student_id"] == "TEST-001"

        created["last_score"] = 0.7
        pm.save("TEST-001", created)

        loaded = pm.load("TEST-001")
        assert loaded["student_id"] == "TEST-001"
        assert loaded["last_score"] == 0.7
