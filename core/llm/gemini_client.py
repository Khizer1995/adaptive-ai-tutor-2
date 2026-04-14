import os
import random
import time
from typing import Any, Dict, Iterable, List, Optional


class GeminiClient:
    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        fallback_models: Optional[List[str]] = None,
        max_retries: int = 3,
        backoff_base_seconds: float = 2.0,
        models_ttl_seconds: int = 900,
    ):
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except Exception:
            pass

        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in .env")

        self.model = model
        self.fallback_models = fallback_models or ["gemini-2.0-flash-lite"]
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self.models_ttl_seconds = models_ttl_seconds

        self._available_models_cache: Optional[List[str]] = None
        self._available_models_cached_at: float = 0.0
        self.client = genai.Client(api_key=api_key)

    def generate(self, prompt: str, task_type: str) -> Dict[str, Any]:
        candidate_models = self._candidate_models()
        errors: List[str] = []

        for model_name in candidate_models:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    text = response.text or ""
                    return {
                        "provider": "gemini",
                        "model": model_name,
                        "task_type": task_type,
                        "content": text,
                    }
                except Exception as exc:
                    err_text = str(exc)
                    errors.append(f"model={model_name} attempt={attempt} error={err_text}")

                    # Move to next model immediately when current one is invalid.
                    if self._is_not_found_error(err_text):
                        break

                    if self._is_retryable_error(err_text) and attempt < self.max_retries:
                        self._sleep_with_backoff(attempt)
                        continue

                    # Non-retryable error or max retries reached: try next model.
                    break

        raise RuntimeError(
            "All Gemini model attempts failed: " + " | ".join(errors[-10:])
        )

    def _candidate_models(self) -> List[str]:
        discovered_models = self._get_available_models()
        configured_priority = [self.model, *self.fallback_models]

        if discovered_models:
            ordered: List[str] = []
            seen = set()

            # Prefer user-configured model order, but only if present.
            for model_name in configured_priority:
                if model_name in discovered_models and model_name not in seen:
                    ordered.append(model_name)
                    seen.add(model_name)

            # Then include any other discovered Gemini models.
            for model_name in discovered_models:
                if model_name not in seen:
                    ordered.append(model_name)
                    seen.add(model_name)

            return ordered

        # If model discovery fails, still attempt configured models.
        return self._dedupe_preserve_order(configured_priority)

    def _get_available_models(self) -> List[str]:
        now = time.time()
        if (
            self._available_models_cache is not None
            and (now - self._available_models_cached_at) < self.models_ttl_seconds
        ):
            return self._available_models_cache

        model_names: List[str] = []

        try:
            models_obj = self.client.models
            iterator: Optional[Iterable[Any]] = None

            if hasattr(models_obj, "list"):
                iterator = models_obj.list()
            elif hasattr(models_obj, "list_models"):
                iterator = models_obj.list_models()

            if iterator is not None:
                for item in iterator:
                    name = self._extract_model_name(item)
                    if name and name.startswith("gemini-") and self._supports_generate_content(item):
                        model_names.append(name)
        except Exception:
            # Soft-fail: caller falls back to configured static model list.
            model_names = []

        deduped = self._dedupe_preserve_order(model_names)
        self._available_models_cache = deduped
        self._available_models_cached_at = now
        return deduped

    def _extract_model_name(self, item: Any) -> str:
        name = getattr(item, "name", "") or ""
        if isinstance(item, dict):
            name = item.get("name", name)
        if name.startswith("models/"):
            return name.split("/", 1)[1]
        return name

    def _supports_generate_content(self, item: Any) -> bool:
        methods = getattr(item, "supported_generation_methods", None)
        if methods is None:
            methods = getattr(item, "supported_actions", None)
        if isinstance(item, dict):
            methods = item.get("supported_generation_methods", methods)
            methods = item.get("supported_actions", methods)

        if not methods:
            # If API doesn't expose methods, keep model eligible.
            return True

        normalized = {str(m).strip().lower() for m in methods}
        return "generatecontent" in normalized or "generate_content" in normalized

    def _sleep_with_backoff(self, attempt: int) -> None:
        delay = self.backoff_base_seconds * (2 ** (attempt - 1))
        jitter = random.uniform(0.0, 0.5)
        time.sleep(delay + jitter)

    def _is_not_found_error(self, err_text: str) -> bool:
        lowered = err_text.lower()
        return "not_found" in lowered or " 404 " in lowered or "code': 404" in lowered

    def _is_retryable_error(self, err_text: str) -> bool:
        lowered = err_text.lower()
        retry_tokens = (
            "unavailable",
            "resource_exhausted",
            "deadline_exceeded",
            "internal",
            " 429 ",
            " 500 ",
            " 502 ",
            " 503 ",
            " 504 ",
            "code': 429",
            "code': 500",
            "code': 502",
            "code': 503",
            "code': 504",
        )
        return any(token in lowered for token in retry_tokens)

    def _dedupe_preserve_order(self, items: List[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for value in items:
            if value not in seen:
                ordered.append(value)
                seen.add(value)
        return ordered
