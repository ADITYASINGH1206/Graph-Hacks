#!/usr/bin/env bash
set -euo pipefail

echo "=========================================================="
echo " Decision Archaeologist: Demo Reset and Warmup Script"
echo "=========================================================="

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# 1. Start FalkorDB container if not running
echo "[1/4] Ensuring FalkorDB is running on port 6379..."
docker compose up -d falkordb
sleep 2

# 2. Seed graph with demo history and cached structure
echo "[2/4] Seeding graph with Flask historical decisions..."
python -m scripts.seed_demo_graph

# 3. Compute knowledge and expertise scores
echo "[3/4] Computing engineer expertise and KNOWS relationships..."
python -c '
from dig.extract.expertise import compute_and_write_expertise
res = compute_and_write_expertise()
print(f"Wrote {res[\"knows_edges\"]} KNOWS expertise edges.")
'

# 4. Verify graph and run warmup query
echo "[4/4] Warming cache for demo questions..."
python -c '
from dig.agent.agent import DecisionAgent
import asyncio
agent = DecisionAgent(max_rounds=3)
async def warm():
    async for ev in agent.ask_stream("Why was Python 3.6 dropped?"):
        if ev.event == "answer":
            print("  Warmup query passed: answer generated successfully.")
asyncio.run(warm())
'

echo ""
echo "=========================================================="
echo " Demo reset complete! Graph is fully seeded & cached."
echo " To start API server:  dig serve"
echo " To start Frontend UI: cd frontend && npm run dev"
echo " To run evaluation:    python eval/run_eval.py"
echo "=========================================================="
