from agentic_browser.agent import Agent


def test_example_extract_loop():
    agent = Agent(dry_run=True, max_steps=5, receipts_dir="/tmp/agentic-browser-test-receipts")
    result = agent.run("Open example.com and extract the main heading")
    agent.close()
    assert result.ok
    kinds = [r.step.kind for r in result.receipts]
    assert "goto" in kinds
    assert "extract_text" in kinds or "done" in kinds
