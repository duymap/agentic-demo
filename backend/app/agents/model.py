from strands.models.openai import OpenAIModel

from app.config import ENABLE_THINKING, MODEL_ID, OMLX_API_KEY, OMLX_BASE_URL


def get_model() -> OpenAIModel:
    return OpenAIModel(
        client_args={"api_key": OMLX_API_KEY, "base_url": OMLX_BASE_URL},
        model_id=MODEL_ID,
        params={
            "temperature": 0.2,
            "max_tokens": 2048,
            # Qwen3: toggle thinking via the chat template (oMLX accepts it through extra_body)
            "extra_body": {"chat_template_kwargs": {"enable_thinking": ENABLE_THINKING}},
        },
    )
