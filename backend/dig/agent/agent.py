"""Agent loop with tool calling, SSE event streaming, and citation verification."""

import asyncio
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel

from dig.agent.prompts import get_system_prompt
from dig.agent.tools import registry
from dig.agent.verifier import (
    check_citations,
    collect_evidence_from_tool_results,
    finalize_answer,
)
from dig.config import settings
from dig.graph.client import get_graph
from dig.graph.models import GraphElements

logger = logging.getLogger(__name__)


class MissingApiKeyError(RuntimeError):
    """Raised when no LLM key is configured and offline mode was not requested."""


class AgentEvent(BaseModel):
    """An event emitted by the agent loop matching the SSE API contract."""

    event: str
    data: dict[str, Any]


class DecisionAgent:
    """Decision Archaeologist autonomous agent with tool-use loop and verifier."""

    def __init__(
        self,
        repo: str = "pallets/flask",
        graph_name: str | None = None,
        max_rounds: int = 8,
        client: Any | None = None,
    ):
        self.repo = repo
        self.graph = get_graph(graph_name) if graph_name else get_graph()
        self.max_rounds = max_rounds
        self._custom_client = client

    def _get_client(self) -> Any:
        """Return the LLM client.

        A real Gemini client is used whenever a key is configured. The canned
        ``OfflineModelSimulator`` is only used when explicitly requested with
        ``DIG_OFFLINE=1``; a missing key is an error, never a silent downgrade to
        scripted answers that would look like real, verified results.
        """
        if self._custom_client:
            return self._custom_client
        api_key = settings.google_api_key
        if api_key:
            return genai.Client(api_key=api_key)
        if settings.dig_offline:
            from dig.agent.offline import OfflineModelSimulator

            logger.warning("DIG_OFFLINE=1: answering with the canned offline simulator.")
            return OfflineModelSimulator()
        raise MissingApiKeyError(
            "No Gemini API key configured. Set GEMINI_API_KEY (or GOOGLE_API_KEY) in .env, "
            "or set DIG_OFFLINE=1 to use canned demo answers from the seed graph."
        )

    @property
    def is_offline(self) -> bool:
        """True when answers come from the canned simulator rather than a live model."""
        return not self._custom_client and not settings.google_api_key and settings.dig_offline

    def _build_tools_declaration(self) -> list[types.Tool]:
        """Convert tools from the registry into Gemini FunctionDeclaration tools."""
        declarations: list[types.FunctionDeclaration] = []
        for tool_meta in registry.list_tools():
            declarations.append(
                types.FunctionDeclaration(
                    name=tool_meta.name,
                    description=tool_meta.description,
                    parameters=tool_meta.parameters_schema,
                )
            )
        return [types.Tool(function_declarations=declarations)]

    async def ask_stream(
        self,
        question: str,
        session_id: str | None = None,
        user_id: str = "anonymous",
    ) -> AsyncGenerator[AgentEvent, None]:
        """Run the tool-use loop and yield SSE AgentEvent instances."""
        session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
        accumulated_path = GraphElements()
        tool_results_history: list[dict[str, Any]] = []

        system_prompt = get_system_prompt(repo=self.repo)

        # Check cross-session memory for relevant past findings
        try:
            from dig.agent.memory import recall_findings
            past_findings = recall_findings(user_id=user_id, topic=question, limit=3)
            if past_findings:
                yield AgentEvent(event="recall", data={"findings": past_findings})
                past_context = "\n".join(f"- {f['summary']}" for f in past_findings)
                system_prompt += f"\n\nEarlier in this user's sessions:\n{past_context}\n"
        except Exception as mem_err:
            logger.debug("Memory recall skipped: %s", mem_err)

        try:
            client = self._get_client()
        except Exception as e:
            logger.error("Could not initialize LLM client: %s", e)
            yield AgentEvent(event="error", data={"message": str(e)})
            yield AgentEvent(event="done", data={"session_id": session_id, "tool_rounds": 0})
            return

        # Check if client has a generate_content or chats interface
        gemini_tools = self._build_tools_declaration()
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=gemini_tools,
            temperature=0.1,
        )

        contents: list[types.Content] = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=question)],
            )
        ]

        round_num = 0
        did_repair = False

        while round_num < self.max_rounds:
            round_num += 1

            # Call LLM
            response = None
            try:
                # Run synchronous client generate_content in thread pool
                loop = asyncio.get_running_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: client.models.generate_content(
                        model=settings.agent_model,
                        contents=contents,
                        config=config,
                    ),
                )
            except Exception as exc:
                logger.error("LLM call failed on round %d: %s", round_num, exc)
                yield AgentEvent(event="error", data={"message": f"LLM generation failed: {exc}"})
                yield AgentEvent(event="done", data={"session_id": session_id, "tool_rounds": round_num})
                return

            candidate = response.candidates[0] if response and response.candidates else None
            if not candidate or not candidate.content or not candidate.content.parts:
                yield AgentEvent(event="error", data={"message": "Empty response from LLM"})
                yield AgentEvent(event="done", data={"session_id": session_id, "tool_rounds": round_num})
                return

            parts = candidate.content.parts
            function_calls = [p.function_call for p in parts if getattr(p, "function_call", None)]

            if function_calls:
                # Add assistant's message with function calls to history
                contents.append(candidate.content)

                # Process all function calls (parallel supported)
                response_parts: list[types.Part] = []
                for idx, fc in enumerate(function_calls):
                    call_id = f"call_{round_num}_{idx}"
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}

                    yield AgentEvent(
                        event="tool_call",
                        data={"id": call_id, "name": tool_name, "input": tool_args},
                    )

                    tool_meta = registry.get(tool_name)
                    if not tool_meta:
                        res = {
                            "data": None,
                            "graph_elements": GraphElements().model_dump(),
                            "summary": f"Error: Tool '{tool_name}' not found.",
                        }
                    else:
                        try:
                            # Pass current graph instance
                            res = tool_meta.func(graph=self.graph, **tool_args)
                        except Exception as tool_err:
                            logger.exception("Error executing tool %s: %s", tool_name, tool_err)
                            res = {
                                "data": None,
                                "graph_elements": GraphElements().model_dump(),
                                "summary": f"Tool error: {tool_err}",
                            }

                    # Accumulate graph elements
                    ge_dict = res.get("graph_elements", {})
                    ge = GraphElements(**ge_dict) if isinstance(ge_dict, dict) else GraphElements()
                    accumulated_path.nodes.extend(ge.nodes)
                    accumulated_path.edges.extend(ge.edges)

                    tool_results_history.append(res)

                    yield AgentEvent(
                        event="tool_result",
                        data={
                            "id": call_id,
                            "name": tool_name,
                            "summary": res.get("summary", ""),
                            "graph_elements": ge.model_dump(),
                        },
                    )

                    # Build function response part for Gemini
                    resp_dict = {
                        "summary": res.get("summary", ""),
                        "data": res.get("data"),
                    }
                    response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response=resp_dict,
                        )
                    )

                contents.append(types.Content(role="user", parts=response_parts))
                # Continue loop to allow model to inspect tool outputs
                continue

            # Model produced text answer (no function calls)
            text_parts = [p.text for p in parts if getattr(p, "text", None)]
            answer_text = "".join(text_parts).strip()

            yield AgentEvent(event="token", data={"text": answer_text})

            # Verification turn
            evidence_map = collect_evidence_from_tool_results(tool_results_history, graph=self.graph)
            known_ids = set(evidence_map.keys())
            check = check_citations(answer_text, known_ids)

            if not check.is_valid and not did_repair and round_num < self.max_rounds:
                logger.info(
                    "Answer verification failed: invalid=%s, flagged=%d. Triggering repair turn.",
                    check.invalid_ids,
                    len(check.flagged_sentences),
                )
                did_repair = True
                contents.append(candidate.content)
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=check.repair_prompt or "")],
                    )
                )
                # Next round will generate repaired answer
                continue

            # Finalize verified markdown, citations, and trust badge
            final_md, citations, verification = finalize_answer(
                answer_text,
                evidence_map,
                was_repaired=did_repair,
            )

            # Deduplicate nodes and edges in accumulated path
            seen_nodes = set()
            unique_nodes = []
            for n in accumulated_path.nodes:
                if n.id not in seen_nodes:
                    seen_nodes.add(n.id)
                    unique_nodes.append(n)
            seen_edges = set()
            unique_edges = []
            for e in accumulated_path.edges:
                if e.id not in seen_edges:
                    seen_edges.add(e.id)
                    unique_edges.append(e)

            final_path = GraphElements(nodes=unique_nodes, edges=unique_edges)

            yield AgentEvent(
                event="answer",
                data={
                    "markdown": final_md,
                    "citations": [c.model_dump() for c in citations],
                    "path": final_path.model_dump(),
                    "verification": verification.model_dump(),
                },
            )

            # Record finding to user memory
            try:
                from dig.agent.memory import record_finding
                dec_ids = [c.decision_id for c in citations if c.decision_id]
                first_two_sentences = " ".join(final_md.split(".")[:2]).strip()
                record_finding(
                    user_id=user_id,
                    session_id=session_id,
                    question_text=question,
                    summary=first_two_sentences or final_md[:120],
                    decision_ids=dec_ids,
                )
            except Exception as rec_err:
                logger.debug("Could not record finding: %s", rec_err)

            yield AgentEvent(
                event="done",
                data={
                    "session_id": session_id,
                    "tool_rounds": round_num,
                    "offline": self.is_offline,
                },
            )
            return

        # Max rounds reached without text completion
        yield AgentEvent(
            event="error",
            data={"message": f"Agent reached maximum tool rounds ({self.max_rounds}) without finishing."},
        )
        yield AgentEvent(
            event="done",
            data={"session_id": session_id, "tool_rounds": round_num},
        )
