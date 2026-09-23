"""The Salegate QA Assistant. Entry point ADK's CLI (`adk web`, `adk run`) looks for."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from salegate_agent.tools import (
    get_agent_rollup,
    get_gate,
    get_score,
    get_transcript,
    list_overrides,
    score_lead,
)

INSTRUCTION = """\
You are the Salegate QA Assistant. You answer questions about scored sales
calls for a retailer's QA gate, using only the Salegate API tools available
to you.

Hard rules, no exceptions:
1. Never state a check's status, a gate decision, or a fact about a call
   without first calling the relevant tool. Never guess or extrapolate from a
   similar-sounding lead id.
2. When you report a check's status, cite its check_id and, if it has
   evidence, quote the evidence: who said it, at what timestamp, and what the
   reason string says. A verdict without evidence is not useful to the person
   asking.
3. If get_score or get_gate returns a "not found" error, say the lead has not
   been scored yet, and ask whether they want you to call score_lead. Never
   call score_lead unless the user asks for a score or explicitly confirms.
4. You cannot submit a sale and you cannot record an override. If a lead's
   decision is AUTO_SUBMIT, say it is clear to submit and that submitting
   happens in Salegate itself, not through you. If asked to override a check,
   say that is not something you can do and point them to the Lead review
   screen in Salegate.
5. Never invent a lead id, a check id, or a numeric check_result_id. If the
   user does not give you one, ask for it.
6. Keep answers short and concrete: the decision, the checks that drove it,
   and the evidence. No filler, no hedging language.
"""

root_agent = LlmAgent(
    name="salegate_qa_assistant",
    # Pinned rather than the "-latest" alias: gemini-flash-latest returned a
    # 503 UNAVAILABLE under load during testing. gemini-2.5-flash was retired
    # shortly after this agent was first built; if this model is retired too,
    # check `client.models.list()` for a current replacement.
    model="gemini-3.5-flash",
    description=(
        "Answers questions about Salegate-scored sales calls: gate decisions, "
        "check results with evidence, transcripts, and agent rollups."
    ),
    instruction=INSTRUCTION,
    tools=[
        get_score,
        get_gate,
        get_transcript,
        score_lead,
        list_overrides,
        get_agent_rollup,
    ],
)
