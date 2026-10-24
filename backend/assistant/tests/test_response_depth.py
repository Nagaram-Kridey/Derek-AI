from types import SimpleNamespace

from assistant.chat_policy import reply_budget, interactive_tools
from assistant.commands import telegram_blocks


def test_detailed_telegram_preserves_all_text_in_small_bubbles():
    text = "\n\n".join(f"Section {i}: " + "explanation " * 70 for i in range(12))
    blocks = telegram_blocks(text, truncate=False)
    assert len(blocks) > 12
    assert all(len(block) <= 500 for block in blocks)
    assert " ".join(" ".join(blocks).split()) == " ".join(text.split())


def test_detail_budget_and_voice_action_capacity():
    command = SimpleNamespace(channel="telegram", input_mode="text", input_text="Explain caching")
    assert reply_budget(command, style="detailed") > reply_budget(command, style="brief")
    command.channel, command.input_mode = "web", "voice"
    command.input_text = "Create a workflow"
    assert reply_budget(command, style="brief") >= 2048


def test_ordinary_questions_trim_tools_but_confirmed_intent_keeps_controls():
    command = SimpleNamespace(input_text="Explain caching")
    tools = [{"name": "search_web"}, {"name": "control_workspace"}]
    assert interactive_tools(command, tools) == tools[:1]
    command.input_text = "pause my workflow"
    assert interactive_tools(command, tools) == tools
