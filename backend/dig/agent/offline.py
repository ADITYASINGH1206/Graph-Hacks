"""Offline model simulator for zero-network testing and caching (P12 requirement)."""

from google.genai import types


class OfflineModelSimulator:
    """Simulates Gemini function calling and answer generation offline against the graph."""

    def __init__(self):
        self.step = 0

    class Models:
        def __init__(self, parent):
            self.parent = parent

        def generate_content(
            self,
            model: str,
            contents: list[types.Content],
            config: types.GenerateContentConfig | None = None,
        ) -> types.GenerateContentResponse:
            self.parent.step += 1

            # Extract last user message or function response
            last_msg = contents[-1]
            last_text = ""
            fn_responses = []

            for p in last_msg.parts:
                if getattr(p, "text", None):
                    last_text += p.text
                if getattr(p, "function_response", None):
                    fn_responses.append(p.function_response)

            q_lower = contents[0].parts[0].text.lower() if contents and contents[0].parts else ""

            # Check if repair turn
            if "lack valid evidence" in last_text.lower():
                # Emit repaired answer citing valid evidence
                repaired = "Based on verified evidence from PR #4400, Python 3.6 and 3.7 support was removed [[ev:ev_drop_py36]]."
                part = types.Part.from_text(text=repaired)
                candidate = types.Candidate(content=types.Content(role="model", parts=[part]))
                return types.GenerateContentResponse(candidates=[candidate])

            # If function responses exist in history, generate grounded answer citing the evidence
            if fn_responses:
                fn_name = fn_responses[0].name
                resp_data = fn_responses[0].response

                if fn_name == "search_decisions":
                    items = resp_data.get("data", [])
                    if items:
                        first_id = items[0].get("id")
                        # Second round: trace evidence
                        fc = types.FunctionCall(
                            name="trace_to_source", args={"decision_id": first_id}
                        )
                        part = types.Part(function_call=fc)
                        candidate = types.Candidate(
                            content=types.Content(role="model", parts=[part])
                        )
                        return types.GenerateContentResponse(candidates=[candidate])

                if fn_name == "trace_to_source":
                    ev_items = resp_data.get("data", [])
                    eid = ev_items[0]["id"] if ev_items else "ev_drop_py36"
                    if "python 2" in q_lower or "py2" in q_lower:
                        text = f"Flask dropped Python 2 support in decision `dec_drop_py2` [[ev:{eid}]]."
                    elif "async" in q_lower:
                        text = (
                            f"Flask adopted async views in decision `dec_async_views` [[ev:{eid}]]."
                        )
                    else:
                        text = f"Flask dropped Python 3.6 support in decision `dec_drop_py36` [[ev:{eid}]]. The change was authored by @davidism."
                    part = types.Part.from_text(text=text)
                    candidate = types.Candidate(content=types.Content(role="model", parts=[part]))
                    return types.GenerateContentResponse(candidates=[candidate])

                if fn_name == "who_knows":
                    people = resp_data.get("data", [])
                    names = [f"@{p.get('login', 'davidism')}" for p in people[:3]]
                    text = f"The primary experts for flask/compat (decisions `dec_drop_py36` and `dec_drop_py2`) are {', '.join(names)}."
                    part = types.Part.from_text(text=text)
                    candidate = types.Candidate(content=types.Content(role="model", parts=[part]))
                    return types.GenerateContentResponse(candidates=[candidate])

                if fn_name == "who_decided":
                    people = resp_data.get("data", [])
                    names = [f"@{p.get('login')}" for p in people]
                    text = f"Decision `dec_drop_py36` was decided by {', '.join(names)} in PR #4400 [[ev:ev_drop_py36]]."
                    part = types.Part.from_text(text=text)
                    candidate = types.Candidate(content=types.Content(role="model", parts=[part]))
                    return types.GenerateContentResponse(candidates=[candidate])

                if fn_name == "central_people":
                    people = resp_data.get("data", [])
                    names = [f"@{p.get('login')} (rank {p.get('rank')})" for p in people[:3]]
                    text = f"The most central maintainers calculated by PageRank are {', '.join(names)}."
                    part = types.Part.from_text(text=text)
                    candidate = types.Candidate(content=types.Content(role="model", parts=[part]))
                    return types.GenerateContentResponse(candidates=[candidate])

                if fn_name == "impact_of":
                    impact = resp_data.get("data", {})
                    target_dec = "dec_drop_py36" if "3.6" in q_lower else "dec_drop_py2"
                    rels = impact.get("releases", ["2.2.0"])
                    text = f"Decision `{target_dec}` impacted modules such as `flask/compat` and downstream releases {', '.join(rels)}."
                    part = types.Part.from_text(text=text)
                    candidate = types.Candidate(content=types.Content(role="model", parts=[part]))
                    return types.GenerateContentResponse(candidates=[candidate])

                if fn_name == "decision_lineage":
                    lineage = resp_data.get("data", {})
                    hops = lineage.get("hops", [])
                    text = f"Decision lineage traverses {len(hops)} hops connecting `dec_drop_py36` and its predecessor `dec_drop_py2`."
                    part = types.Part.from_text(text=text)
                    candidate = types.Candidate(content=types.Content(role="model", parts=[part]))
                    return types.GenerateContentResponse(candidates=[candidate])

            # Initial round: Select appropriate tool based on query semantics
            if "central" in q_lower or "influential" in q_lower:
                fc = types.FunctionCall(name="central_people", args={"scope": "all", "limit": 5})
            elif "who knows" in q_lower or "expert" in q_lower or "maintainer" in q_lower:
                fc = types.FunctionCall(
                    name="who_knows", args={"module": "flask/compat", "limit": 5}
                )
            elif (
                "lineage" in q_lower
                or "superseded" in q_lower
                or "history" in q_lower
                and "lineage" in q_lower
            ):
                fc = types.FunctionCall(
                    name="decision_lineage", args={"decision_id": "dec_drop_py36"}
                )
            elif "impact" in q_lower:
                target_dec = "dec_drop_py36" if "3.6" in q_lower else "dec_drop_py2"
                fc = types.FunctionCall(name="impact_of", args={"decision_id": target_dec})
            elif "who decided" in q_lower:
                fc = types.FunctionCall(name="who_decided", args={"decision_id": "dec_drop_py36"})
            elif "python 2" in q_lower:
                fc = types.FunctionCall(name="search_decisions", args={"query": "Python 2"})
            elif "async" in q_lower:
                fc = types.FunctionCall(name="search_decisions", args={"query": "async"})
            else:
                fc = types.FunctionCall(name="search_decisions", args={"query": "Python 3.6"})

            part = types.Part(function_call=fc)
            candidate = types.Candidate(content=types.Content(role="model", parts=[part]))
            return types.GenerateContentResponse(candidates=[candidate])

    @property
    def models(self):
        return self.Models(self)
