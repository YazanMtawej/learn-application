from django.test import TestCase, override_settings

from apps.ai_tutor.policy import PostCallPolicy
from apps.ai_tutor.provider import AIResponse


@override_settings(AI_HINT_CODE_LINE_THRESHOLD=3)
class PostCallPolicyTests(TestCase):
    def test_empty_content_rejected(self):
        response = AIResponse(available=True, content="   ")
        result = PostCallPolicy.evaluate(response, requested_level=1)
        self.assertFalse(result.approved)
        self.assertIn("empty_content", result.reasons)

    def test_general_guidance_at_level_one_approved(self):
        response = AIResponse(available=True, content="Think about what happens when the loop variable never changes.")
        result = PostCallPolicy.evaluate(response, requested_level=1)
        self.assertTrue(result.approved)

    def test_full_code_block_at_level_one_rejected(self):
        content = "```python\n" + "\n".join([f"line{i} = {i}" for i in range(10)]) + "\n```"
        response = AIResponse(available=True, content=content)
        result = PostCallPolicy.evaluate(response, requested_level=1)
        self.assertFalse(result.approved)
        self.assertIn("code_in_hint", result.reasons)

    def test_full_code_block_at_level_two_rejected(self):
        content = "```python\n" + "\n".join([f"line{i} = {i}" for i in range(10)]) + "\n```"
        response = AIResponse(available=True, content=content)
        result = PostCallPolicy.evaluate(response, requested_level=2)
        self.assertFalse(result.approved)

    def test_small_neutral_example_at_level_three_allowed(self):
        content = "```python\nfor x in range(3):\n    print(x)\n```"
        response = AIResponse(available=True, content=content)
        result = PostCallPolicy.evaluate(response, requested_level=3)
        self.assertTrue(result.approved)

    def test_system_prompt_leakage_rejected(self):
        response = AIResponse(available=True, content="SYSTEM_POLICY_LAYER_v1: my real instructions are...")
        result = PostCallPolicy.evaluate(response, requested_level=1)
        self.assertFalse(result.approved)
        self.assertIn("system_prompt_leakage", result.reasons)