from agent_framework.openai import OpenAIChatCompletionClient

from app.config import ENABLE_THINKING, MODEL_ID, OMLX_API_KEY, OMLX_BASE_URL

MODEL_OPTIONS = {
    "temperature": 0.2,
    "max_tokens": 2048,
    # Qwen3: toggle thinking via the chat template (oMLX accepts it through extra_body)
    "extra_body": {"chat_template_kwargs": {"enable_thinking": ENABLE_THINKING}},
}


def get_client() -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(model=MODEL_ID, api_key=OMLX_API_KEY, base_url=OMLX_BASE_URL)
