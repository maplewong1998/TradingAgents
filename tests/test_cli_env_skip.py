"""Tests for env-driven CLI behavior (#897, #873).

The config-layer override (TRADINGAGENTS_* -> DEFAULT_CONFIG) is covered by
test_env_overrides.py. These tests cover the CLI layer: an env-configured
provider/model/language must skip its interactive prompt and use the value.
"""

import os
import unittest
from unittest import mock

import pytest


@pytest.mark.unit
class TestProviderDefaultUrl(unittest.TestCase):
    def test_known_providers_resolve(self):
        from cli.utils import provider_default_url
        self.assertEqual(provider_default_url("openai"), "https://api.openai.com/v1")
        self.assertEqual(provider_default_url("DeepSeek"), "https://api.deepseek.com")
        self.assertIsNone(provider_default_url("google"))  # uses SDK default

    def test_unknown_provider_returns_none(self):
        from cli.utils import provider_default_url
        self.assertIsNone(provider_default_url("not-a-provider"))

    def test_ollama_honors_base_url_env(self):
        from cli.utils import provider_default_url
        with mock.patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://host:1234/v1"}):
            self.assertEqual(provider_default_url("ollama"), "http://host:1234/v1")


@pytest.mark.unit
class TestCliSkipsPromptsFromEnv(unittest.TestCase):
    def test_env_config_skips_llm_prompts(self):
        import cli.main as m

        env = {
            "TRADINGAGENTS_LLM_PROVIDER": "openai",
            "TRADINGAGENTS_DEEP_THINK_LLM": "kimi-k2.5",
            "TRADINGAGENTS_QUICK_THINK_LLM": "deepseek-v4-pro",
            "TRADINGAGENTS_LLM_BACKEND_URL": "https://opencode.ai/zen/go/v1",
            "TRADINGAGENTS_OUTPUT_LANGUAGE": "Japanese",
        }
        fake_cfg = dict(m.DEFAULT_CONFIG)
        fake_cfg.update({
            "llm_provider": "openai",
            "backend_url": "https://opencode.ai/zen/go/v1",
            "quick_think_llm": "deepseek-v4-pro",
            "deep_think_llm": "kimi-k2.5",
            "output_language": "Japanese",
        })

        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(m, "DEFAULT_CONFIG", fake_cfg), \
             mock.patch.object(m, "fetch_announcements", return_value=None), \
             mock.patch.object(m, "display_announcements"), \
             mock.patch.object(m, "get_ticker", return_value="AAPL"), \
             mock.patch.object(m, "get_analysis_date", return_value="2026-05-29"), \
             mock.patch.object(m, "select_analysts", return_value=[]), \
             mock.patch.object(m, "select_research_depth", return_value=1), \
             mock.patch.object(m, "ensure_api_key") as ensure_key, \
             mock.patch.object(m, "select_llm_provider") as prompt_provider, \
             mock.patch.object(m, "ask_output_language") as prompt_lang, \
             mock.patch.object(m, "select_shallow_thinking_agent") as prompt_quick, \
             mock.patch.object(m, "select_deep_thinking_agent") as prompt_deep, \
             mock.patch.object(m, "select_debate_gate", return_value="auto", create=True):
            sel = m.get_user_selections()

        # None of the LLM selection prompts should have been shown.
        prompt_provider.assert_not_called()
        prompt_lang.assert_not_called()
        prompt_quick.assert_not_called()
        prompt_deep.assert_not_called()
        # API key is still verified for the env-configured provider.
        ensure_key.assert_called_once()

        # The env values flow into the returned selections.
        self.assertEqual(sel["llm_provider"], "openai")
        self.assertEqual(sel["backend_url"], "https://opencode.ai/zen/go/v1")
        self.assertEqual(sel["quick_think_llm"], "deepseek-v4-pro")
        self.assertEqual(sel["deep_think_llm"], "kimi-k2.5")
        self.assertEqual(sel["output_language"], "Japanese")


@pytest.mark.unit
class TestResearchDepthSkippedFromEnv(unittest.TestCase):
    def test_both_round_envs_skip_depth_prompt(self):
        import cli.main as m

        env = {
            "TRADINGAGENTS_MAX_DEBATE_ROUNDS": "2",
            "TRADINGAGENTS_MAX_RISK_ROUNDS": "4",
        }
        fake_cfg = dict(m.DEFAULT_CONFIG)
        fake_cfg.update({"max_debate_rounds": 2, "max_risk_discuss_rounds": 4})

        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(m, "DEFAULT_CONFIG", fake_cfg), \
             mock.patch.object(m, "fetch_announcements", return_value=None), \
             mock.patch.object(m, "display_announcements"), \
             mock.patch.object(m, "get_ticker", return_value="AAPL"), \
             mock.patch.object(m, "get_analysis_date", return_value="2026-05-29"), \
             mock.patch.object(m, "select_analysts", return_value=[]), \
             mock.patch.object(m, "select_research_depth") as prompt_depth, \
             mock.patch.object(m, "ensure_api_key"), \
             mock.patch.object(m, "select_llm_provider", return_value=("openai", None)), \
             mock.patch.object(m, "ask_output_language", return_value="English"), \
             mock.patch.object(m, "select_shallow_thinking_agent", return_value="gpt-5.4-mini"), \
             mock.patch.object(m, "select_deep_thinking_agent", return_value="gpt-5.5"), \
             mock.patch.object(m, "ask_openai_reasoning_effort", return_value=None), \
             mock.patch.object(m, "select_debate_gate", return_value="auto", create=True):
            sel = m.get_user_selections()

        # The research-depth prompt is skipped; the value comes from the env config.
        prompt_depth.assert_not_called()
        self.assertEqual(sel["research_depth"], 2)


@pytest.mark.unit
class TestReasoningEffortSkippedFromEnv(unittest.TestCase):
    def test_effort_env_skips_step8_prompt(self):
        import cli.main as m

        env = {"TRADINGAGENTS_OPENAI_REASONING_EFFORT": "high"}
        fake_cfg = dict(m.DEFAULT_CONFIG)
        fake_cfg.update({"openai_reasoning_effort": "high"})

        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(m, "DEFAULT_CONFIG", fake_cfg), \
             mock.patch.object(m, "fetch_announcements", return_value=None), \
             mock.patch.object(m, "display_announcements"), \
             mock.patch.object(m, "get_ticker", return_value="AAPL"), \
             mock.patch.object(m, "get_analysis_date", return_value="2026-05-29"), \
             mock.patch.object(m, "select_analysts", return_value=[]), \
             mock.patch.object(m, "select_research_depth", return_value=1), \
             mock.patch.object(m, "ensure_api_key"), \
             mock.patch.object(m, "select_llm_provider", return_value=("openai", None)), \
             mock.patch.object(m, "ask_output_language", return_value="English"), \
             mock.patch.object(m, "select_shallow_thinking_agent", return_value="gpt-5.4-mini"), \
             mock.patch.object(m, "select_deep_thinking_agent", return_value="gpt-5.5"), \
             mock.patch.object(m, "ask_openai_reasoning_effort") as prompt_effort, \
             mock.patch.object(m, "select_debate_gate", return_value="auto", create=True):
            sel = m.get_user_selections()

        # The reasoning-effort prompt is skipped; the value comes from env config.
        prompt_effort.assert_not_called()
        self.assertEqual(sel["openai_reasoning_effort"], "high")


@pytest.mark.unit
class TestDebateGateSkippedFromEnv(unittest.TestCase):
    def test_gate_env_skips_the_policy_prompt(self):
        """SC-e02s02-P1-02 — TRADINGAGENTS_DEBATE_GATE is the non-interactive
        path: the policy prompt is not shown and the env value is used."""
        import cli.main as m

        env = {"TRADINGAGENTS_DEBATE_GATE": "never"}
        fake_cfg = dict(m.DEFAULT_CONFIG)
        fake_cfg.update({"debate_gate": "never"})

        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(m, "DEFAULT_CONFIG", fake_cfg), \
             mock.patch.object(m, "fetch_announcements", return_value=None), \
             mock.patch.object(m, "display_announcements"), \
             mock.patch.object(m, "get_ticker", return_value="AAPL"), \
             mock.patch.object(m, "get_analysis_date", return_value="2026-05-29"), \
             mock.patch.object(m, "select_analysts", return_value=[]), \
             mock.patch.object(m, "select_research_depth", return_value=1), \
             mock.patch.object(m, "ensure_api_key"), \
             mock.patch.object(m, "select_llm_provider", return_value=("openai", None)), \
             mock.patch.object(m, "ask_output_language", return_value="English"), \
             mock.patch.object(m, "select_shallow_thinking_agent", return_value="gpt-5.4-mini"), \
             mock.patch.object(m, "select_deep_thinking_agent", return_value="gpt-5.5"), \
             mock.patch.object(m, "ask_openai_reasoning_effort", return_value=None), \
             mock.patch("cli.gate_policy.ask_debate_gate") as prompt_gate:
            sel = m.get_user_selections()

        # The policy prompt is skipped; the value comes from the env config.
        prompt_gate.assert_not_called()
        self.assertEqual(sel["debate_gate"], "never")


@pytest.mark.unit
class TestDebateGateEnvNotice(unittest.TestCase):
    """The env notice, on the real wiring rather than a stubbed prompt.

    The class above stubs ``ask_debate_gate``, so it proves the menu is not shown
    but never exercises the branch that decides it: the gate policy step has its
    own env check, and these tests pin its two halves (notice + no prompt, and
    the value the config ends up with).
    """

    def _console(self) -> tuple:
        import io
        from rich.console import Console

        buf = io.StringIO()
        return Console(file=buf, force_terminal=False, width=220), buf

    def test_env_policy_short_circuits_the_menu_and_says_so(self):
        """SC-e02s02-P1-02 — with the env var set the step returns the config value
        without asking, and prints which env var decided it."""
        import cli.gate_policy as gp

        console, buf = self._console()
        with mock.patch.dict(os.environ, {"TRADINGAGENTS_DEBATE_GATE": "always"}), \
             mock.patch.object(gp, "console", console), \
             mock.patch.object(gp, "ask_debate_gate") as prompt:
            resolved = gp.select_debate_gate({}, "always", console, lambda *a: "")

        prompt.assert_not_called()          # no menu on the non-interactive path
        self.assertEqual(resolved, "always")
        self.assertIn("TRADINGAGENTS_DEBATE_GATE", buf.getvalue())

    def test_the_env_notice_is_printed_once_across_the_run(self):
        """The step and the config builder both resolve the policy, and both know
        the env var is set, so a naive pair of notices told the user the same thing
        twice in one run. One line is the contract: the fact does not become truer
        by being repeated, and a doubled notice reads as two separate settings."""
        import cli.gate_policy as gp

        console, buf = self._console()
        with mock.patch.dict(os.environ, {"TRADINGAGENTS_DEBATE_GATE": "never"}), \
             mock.patch.object(gp, "console", console), \
             mock.patch.object(gp, "ask_debate_gate") as prompt:
            selected = gp.select_debate_gate({}, "never", console, lambda *a: "")
            # The menu answer a prior step may have collected, as main.py passes it.
            resolved = gp.resolve_debate_gate("never", {"debate_gate": selected}, console)

        prompt.assert_not_called()
        self.assertEqual(resolved, "never")
        notice = [l for l in buf.getvalue().splitlines() if "TRADINGAGENTS_DEBATE_GATE" in l]
        self.assertEqual(len(notice), 1, f"the env notice must print once, got: {notice}")


if __name__ == "__main__":
    unittest.main()
