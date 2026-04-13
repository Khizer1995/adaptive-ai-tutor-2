from core.llm.router import ModelRouterAgent


class _DummyClient:
    def __init__(self, provider: str, should_fail: bool = False):
        self.provider = provider
        self.should_fail = should_fail

    def generate(self, prompt: str, task_type: str):
        if self.should_fail:
            raise RuntimeError("simulated failure")
        return {
            "provider": self.provider,
            "model": f"{self.provider}-mock",
            "task_type": task_type,
            "content": f"{self.provider}:{task_type}",
        }


def test_router_selects_gemini_for_reasoning():
    router = ModelRouterAgent()
    router.gemini_client = _DummyClient("gemini")
    result = router.route("deep_reasoning", "Explain recursion")
    assert result["selected_provider"] == "gemini"
    assert "gemini" in result["content"]


def test_router_selects_groq_for_quiz():
    router = ModelRouterAgent()
    router.groq_client = _DummyClient("groq")
    result = router.route("quiz_generation", "Create 3 MCQs")
    assert result["selected_provider"] == "groq"
    assert "groq" in result["content"]


def test_router_fallback_from_gemini_to_groq():
    router = ModelRouterAgent()
    router.gemini_client = _DummyClient("gemini", should_fail=True)
    router.groq_client = _DummyClient("groq")
    result = router.route("concept_explanation", "Explain linked list")
    assert result["selected_provider"] == "groq_fallback"
    assert "groq" in result["content"]
