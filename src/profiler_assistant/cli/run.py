"""
CLI entry for Firefox Profiler Assistant (LLM-powered).
Purpose: Provide a user-facing command-line interface to run a deterministic
first report or an interactive agent session over a Firefox profile, while
applying policy gating and prompt preambles when available.
"""

import argparse
import json
import logging
import os
import sys
from typing import List, Optional, Tuple

from profiler_assistant.downloader import get_profile_from_url
from profiler_assistant.parsing import load_and_parse_profile
from profiler_assistant.agent.react_agent import run_react_agent
from profiler_assistant.rag import pipeline as rag_pipeline
from profiler_assistant.rag.config import load_rag_config, iter_candidate_files
from profiler_assistant.logging_config import configure_logging, LEVEL_MAP
from profiler_assistant.policy import gate as policy_gate


LOG = logging.getLogger(__name__)
POLICY_LOG = logging.getLogger("profiler_assistant.policy")


# ======================= RAG ====================================

def refresh_rag_knowledge_index() -> None:
    """
    Refresh the RAG knowledge index from local project sources (config/rag.toml).
    Errors are printed (visible) but never crash the main flow.
    """
    try:
        cfg = load_rag_config()  # fixed path: config/rag.toml
        any_found = False
        for file_path in iter_candidate_files(cfg):
            any_found = True
            rag_pipeline.build_all(file_path, domain="kb", index_dir=".fpa_index")
        if not any_found:
            print("[RAG] No knowledge files matched include/exclude patterns.")
    except FileNotFoundError as e:
        print(f"[RAG] Config error: {e}")
    except Exception as e:
        print(f"[RAG] Indexing failed: {e}")


# ======================= Policy helpers ========================

def _policy_present_on(profile: object) -> bool:
    """
    Detect whether a policy is already attached to 'profile'.
    Works for dicts (profile['policy']) or objects (profile.policy / profile._policy).
    """
    try:
        if isinstance(profile, dict):
            present = "policy" in profile
            LOG.debug("Policy presence (dict): %s", present)
            return present
        if hasattr(profile, "policy") and getattr(profile, "policy") is not None:
            LOG.debug("Policy presence (obj.policy): True")
            return True
        if hasattr(profile, "_policy") and getattr(profile, "_policy") is not None:
            LOG.debug("Policy presence (obj._policy): True")
            return True
        LOG.debug("Policy presence (object): False")
        return False
    except Exception:
        LOG.debug("Policy presence check failed; assuming False")
        return False


def _apply_policy_to_profile(profile: object, policy_payload: dict) -> object:
    """
    Attach a policy payload onto the profile; returns the updated profile object.
    """
    if isinstance(profile, dict):
        newp = dict(profile)
        newp["policy"] = policy_payload
        return newp
    try:
        setattr(profile, "policy", policy_payload)
        return profile
    except Exception:
        pass
    try:
        setattr(profile, "_policy", policy_payload)
    except Exception:
        LOG.warning("Unable to attach policy to profile object; continuing without attach.")
    return profile


def _decide_policy_action(profile: object, flag: str) -> dict:
    """
    Decide what to do with policy for this run. Uses policy_gate if available,
    passing only the presence/absence signal to keep it type-agnostic.
    """
    present = _policy_present_on(profile)

    if policy_gate is not None:
        shim = {"policy": {}} if present else {}
        decision = policy_gate.decide_policy_action(shim, flag)
        POLICY_LOG.info(
            "step=decide_policy flag=%s action=%s reason=%s",
            flag, decision.get("action"), decision.get("reason")
        )
        return decision

    # Fallback logic if gate module is absent
    if flag == "none":
        POLICY_LOG.info("step=decide_policy flag=no-policy action=bypass reason=flag")
        return {"action": "bypass", "reason": "flag=no-policy"}
    if not present:
        if flag in ("once", "always"):
            POLICY_LOG.info("step=decide_policy flag=%s action=inject reason=absent", flag)
            return {"action": "inject", "reason": "absent"}
    else:
        if flag == "always":
            POLICY_LOG.info("step=decide_policy flag=always action=replace reason=flag")
            return {"action": "replace", "reason": "flag=always"}
        POLICY_LOG.info("step=decide_policy flag=%s action=skip reason=already_present", flag)
        return {"action": "skip", "reason": "already_present"}

    POLICY_LOG.info("step=decide_policy flag=%s action=skip reason=default", flag)
    return {"action": "skip", "reason": "default"}


def _inject_policy(profile: object) -> object:
    """
    Load the default policy and attach it to the profile.
    """
    source = "fallback-inline"
    policy_payload = {"rules": []}
    if policy_gate is not None:
        try:
            policy_payload = policy_gate.load_default_policy()
            source = "default-policy"
        except Exception:
            source = "fallback-inline"

    POLICY_LOG.info("step=inject_policy source=%s", source)
    return _apply_policy_to_profile(profile, policy_payload)


# ======================= Profile loading ======================================

def _load_profile_from_source(profile_source: str) -> Tuple[object, str, bool]:
    """
    Load and parse a profile from a local path, a URL, or a raw JSON string.
    Returns (profile_obj_or_dict, resolved_path_or_hint, is_temp_file).
    """
    LOG.info("Loading profile source: %s", profile_source)
    is_temp_file = False
    resolved = profile_source

    if profile_source.startswith("http://") or profile_source.startswith("https://"):
        resolved = get_profile_from_url(profile_source)
        is_temp_file = True
        LOG.info("Downloaded profile to temporary file: %s", resolved)
        profile = load_and_parse_profile(resolved)
        return profile, resolved, is_temp_file

    if os.path.exists(profile_source):
        profile = load_and_parse_profile(profile_source)
        return profile, profile_source, is_temp_file

    try:
        as_json = json.loads(profile_source)
        if isinstance(as_json, dict):
            LOG.info("Interpreted profile source as raw JSON string.")
            return as_json, "<raw-json>", is_temp_file
    except Exception:
        pass

    LOG.error("Unable to interpret profile source: %s", profile_source)
    raise ValueError("profile_source must be a local path, a valid URL, or a JSON string")


# ======================= Report =================================

def _make_tracer():
    """
    Build a tracer compatible with ensure_general_analysis().
    Prefers profiler_assistant.agent.tracing.decision_hooks if present;
    otherwise falls back to a simple logger-backed tracer that emits to
    profiler_assistant.policy.
    """
    try:
        from profiler_assistant.agent.tracing import decision_hooks  # type: ignore

        # Prefer a factory if exported
        factory = getattr(decision_hooks, "build_cli_tracer", None)
        if callable(factory):
            return factory(logger=POLICY_LOG)

        # Try a class surface
        cls = getattr(decision_hooks, "DecisionTracer", None)
        if cls is not None:
            return cls(logger=POLICY_LOG)

        # Try function-style hooks
        begin = getattr(decision_hooks, "begin", None)
        end = getattr(decision_hooks, "end", None)
        emit = getattr(decision_hooks, "emit", None)
        if callable(begin) and callable(end) and callable(emit):
            class _HooksAdapter:
                def start(self, title): begin(title)
                def end(self, title, ms=None): end(title, ms=ms)
                def event(self, msg, **kv): emit(msg, **kv)
            return _HooksAdapter()

        LOG.debug("decision_hooks present but no known tracer surface.")
    except Exception as e:
        LOG.debug("decision_hooks unavailable; using logger tracer. err=%s", e)

    # Fallback: logger-backed tracer
    class _LoggerTracer:
        def start(self, title): POLICY_LOG.info("trace=start title=%s", title)
        def end(self, title, ms=None):
            if ms is not None:
                POLICY_LOG.info("trace=end title=%s duration_ms=%s", title, ms)
            else:
                POLICY_LOG.info("trace=end title=%s", title)
        def event(self, msg, **kv):
            kvs = " ".join(f"{k}={v}" for k, v in kv.items())
            if kvs:
                POLICY_LOG.info("trace=event %s %s", msg, kvs)
            else:
                POLICY_LOG.info("trace=event %s", msg)
    return _LoggerTracer()


def _run_report(profile_source: str, policy_flag: str) -> int:
    """
    'report' mode using P1–P4:
      - load/parse profile (URL/file/raw JSON)
      - apply policy gating (inject/replace/skip/bypass)
      - refresh knowledge index (best-effort)
      - P2: apply policy preamble (idempotent per module)
      - P3: run ensure_general_analysis(profile_path, tracer, options)
      - print the first report
      - fallback: one-shot agent if P1–P4 utilities are unavailable or fail base checks
    """
    LOG.info("Entering report mode")
    profile, resolved, is_temp = _load_profile_from_source(profile_source)
    POLICY_LOG.info(
        "step=detect_policy result=%s source=%s",
        "present" if _policy_present_on(profile) else "absent",
        "profile",
    )

    try:
        # Decide & apply policy (on the in-memory profile object)
        decision = _decide_policy_action(profile, policy_flag)
        action = decision.get("action")
        if action in ("inject", "replace"):
            profile = _inject_policy(profile)
        elif action == "bypass":
            POLICY_LOG.info("step=run action=bypass")
        elif action == "deny":
            POLICY_LOG.error("step=run action=deny")
            return 10

        # Best-effort RAG (visible, non-fatal)
        refresh_rag_knowledge_index()

        # ---- Policy preamble
        preamble_mode = {"once": "policy-once", "always": "policy-always", "none": "no-policy"}.get(
            policy_flag, "policy-once"
        )
        try:
            import profiler_assistant.policy.preamble as preamble_mod  # type: ignore
            apply_fn = getattr(preamble_mod, "apply_preamble", None) \
                       or getattr(preamble_mod, "ensure_preamble", None) \
                       or getattr(preamble_mod, "inject_policy_preamble", None)
            if callable(apply_fn):
                POLICY_LOG.info("step=preamble_apply mode=%s", preamble_mode)
                apply_fn(profile, mode=preamble_mode)
            else:
                LOG.debug("preamble.py found but no known apply function; skipping.")
        except ImportError:
            LOG.debug("preamble.py not found; skipping preamble apply.")
        except Exception as e:
            LOG.debug("Preamble application failed: %s", e, exc_info=True)

        # ---- Agent gate + branch discipline
        try:
            from profiler_assistant.agent import agent_gate

            # Build tracer (decision_hooks if available; logger fallback)
            tracer = _make_tracer()

            ensure_general_analysis = getattr(agent_gate, "ensure_general_analysis", None)
            BaseCheckError = getattr(agent_gate, "BaseCheckError", RuntimeError)

            if callable(ensure_general_analysis):
                options = {"mode": "report"}

                POLICY_LOG.info("step=ensure_general_analysis begin")
                # IMPORTANT: ensure_general_analysis expects the *profile path*, not the Profile object
                result = ensure_general_analysis(resolved, tracer=tracer, options=options)
                POLICY_LOG.info("step=ensure_general_analysis end")

                # Prefer textual fields; fall back to stringified result
                report_text = None
                if isinstance(result, dict):
                    report_text = (
                        result.get("report")
                        or result.get("summary")
                        or result.get("final")
                        or result.get("text")
                    )
                if report_text is None:
                    report_text = str(result) if result is not None else "(no report text produced)"

                print("📄 First report:\n")
                print(report_text)
                return 0

            # If ensure_general_analysis is missing, fall back to one-shot agent
            LOG.debug("ensure_general_analysis not available; falling back to one-shot agent.")

        except BaseCheckError as e:
            # Base checks failed — surface a concise message, then fall back to one-shot agent
            LOG.error("General analysis failed base checks: %s", e)
            print("⚠️ Base Checks failed:", str(e))
            LOG.debug("Falling back to one-shot agent after BaseCheckError.")
        except ImportError:
            LOG.debug("agent_gate not found; falling back to one-shot agent.")
        except Exception as e:
            LOG.exception("General analysis failed: %s", e)
            return 12

        # ---- Fallback: one-shot agent (keeps report usable)
        history = []
        question = (
            "Run the General Analysis per the project's Base Checks and Branching Rules. "
            "Produce the first report with: key threads, notable markers, performance issues, "
            "and media playback anomalies. Declare chosen branch & reason."
        )
        result = run_react_agent(profile, question, history)
        if "final" in result:
            print("📄 First report:\n")
            print(result["final"])
            return 0
        elif "tool_result" in result:
            summary = str(result["tool_result"])[:2000]
            print("📄 First report (tool result):\n")
            print(summary)
            return 0
        else:
            print("❌ Report generation error:", result.get("error", "unknown"))
            return 12

    except ValueError as e:
        LOG.error("Report argument/profile error: %s", e)
        return 13
    except Exception as e:
        LOG.exception("Unhandled exception during report generation: %s", e)
        return 12
    finally:
        if is_temp and os.path.exists(resolved):
            os.remove(resolved)
            print(f"[*] Cleaned up temporary file: {resolved}")



# ======================= Agent (interactive) ==================================

def _run_agent(profile_source: str, policy_flag: str) -> int:
    """
    Interactive ReAct agent loop, wrapped with the same policy gating + RAG refresh.
    """
    LOG.info("Entering agent mode")
    profile, resolved, is_temp = _load_profile_from_source(profile_source)
    POLICY_LOG.info(
        "step=detect_policy result=%s source=%s",
        "present" if _policy_present_on(profile) else "absent",
        "profile",
    )

    try:
        decision = _decide_policy_action(profile, policy_flag)
        action = decision.get("action")
        if action in ("inject", "replace"):
            profile = _inject_policy(profile)
        elif action == "bypass":
            POLICY_LOG.info("step=run action=bypass")
        elif action == "deny":
            POLICY_LOG.error("step=run action=deny")
            return 10

        refresh_rag_knowledge_index()

        history = []
        print("🧠 Firefox Profiler Assistant (LLM CLI)\nType 'exit' to quit.\n")
        while True:
            question = input("👤 You: ")
            if question.strip().lower() in {"exit", "quit"}:
                break

            result = run_react_agent(profile, question, history)

            if "final" in result:
                print("🤖", result["final"])
                history.append({"role": "assistant", "content": result["final"]})
            elif "tool_result" in result:
                summary = str(result["tool_result"])[:1000]
                print("🔧 Tool result:", summary)
                history.append({"role": "assistant", "content": f"Tool result: {summary}"})
            else:
                print("❌", result.get("error", "unknown"))
        return 0
    finally:
        if is_temp and os.path.exists(resolved):
            os.remove(resolved)
            print(f"[*] Cleaned up temporary file: {resolved}")


# ======================= Parser & dispatch ====================================

def _add_common_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--log-level",
        choices=list(LEVEL_MAP.keys()),
        default="WARNING",
        help="Set logging level (default: WARNING).",
    )


def _add_policy_flags(p: argparse.ArgumentParser) -> None:
    g = p.add_mutually_exclusive_group()
    g.add_argument("--policy-once", dest="policy_flag", action="store_const", const="once",
                   help="Inject policy only if missing (default).")
    g.add_argument("--policy-always", dest="policy_flag", action="store_const", const="always",
                   help="Always (re)inject policy.")
    g.add_argument("--no-policy", dest="policy_flag", action="store_const", const="none",
                   help="Bypass policy gating entirely.")
    p.set_defaults(policy_flag="once")


def get_parser() -> argparse.ArgumentParser:
    """
    Build the argparse parser with subcommands:
      - report <profile>
      - agent  <profile>
    """
    parser = argparse.ArgumentParser(description="Firefox Profiler Assistant (LLM-powered CLI)")
    subs = parser.add_subparsers(dest="command")

    p_report = subs.add_parser("report", help="Generate the first (one-shot) report from a profile (P1–P4 aware)")
    _add_common_flags(p_report)
    _add_policy_flags(p_report)
    p_report.add_argument("profile", type=str, help="Path to profile.json, a share URL, or raw JSON string")

    p_agent = subs.add_parser("agent", help="Run the interactive ReAct agent on a profile")
    _add_common_flags(p_agent)
    _add_policy_flags(p_agent)
    p_agent.add_argument("profile", type=str, help="Path to profile.json, a share URL, or raw JSON string")

    return parser


def _default_to_agent_argv(argv: List[str]) -> List[str]:
    """
    If no subcommand is present, treat args as:
      profiler-assistant [options] <profile>
    and rewrite to:
      profiler-assistant agent [options] <profile>
    Works when options come before the profile.
    """
    if not argv:
        return argv

    # Already contains a subcommand?
    if any(arg in {"report", "agent"} for arg in argv):
        return argv

    # Find the first non-option token (candidate profile)
    for i, arg in enumerate(argv):
        if not arg.startswith("-"):
            return argv[:i] + ["agent"] + argv[i:]

    # If we never found a non-option (only options given), leave unchanged
    return argv


def main(argv: Optional[List[str]] = None) -> None:
    """
    Entry: default-to-agent dispatch, early logging config, and command routing.
    """
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    argv_effective = _default_to_agent_argv(raw_argv)

    parser = get_parser()
    args = parser.parse_args(argv_effective)

    # Configure logging early
    configure_logging(args.log_level)
    LOG.debug("CLI args parsed: %s", vars(args))

    # Dispatch
    try:
        if getattr(args, "command", None) == "report":
            exit_code = _run_report(args.profile, args.policy_flag)
        else:
            exit_code = _run_agent(args.profile, args.policy_flag)
    except ValueError as e:
        LOG.error("Argument/profile error: %s", e)
        sys.exit(13)
    except Exception as e:
        LOG.exception("Unhandled exception in CLI: %s", e)
        sys.exit(12)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
