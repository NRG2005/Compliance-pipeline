"""
L1: Orchestrator

Uses LangGraph to create a stateful graph that represents the pipeline's flow.
It decides whether to short-circuit or proceed with the full analysis.
"""
from L2_transaction_monitor import main as l2_main
from L3_regulation_interpreter import main as l3_main
from L6_audit_logger import main as l6_main
from .minhash_lsh import find_similar_case
from .regulation_hash import check_regulation_hash

async def handle_event(event):
    """
    Main entry point for the orchestrator.
    """
    # 1. Check case memory
    similar_case = find_similar_case(event)

    if similar_case:
        # 2. If similar case found, check if regulation has changed
        is_stale = check_regulation_hash(similar_case['rule_hash'])
        if not is_stale:
            # Short-circuit to L6
            print("L1: Case memory hit and rule unchanged. Short-circuiting to L6.")
            await l6_main.log_transaction(event, similar_case['verdict'])
            return

    # 3. Full pipeline execution
    print("L1: No case memory match or rule changed. Executing full pipeline.")
    suspicion_score = await l2_main.transaction_monitor(event)
    
    if suspicion_score < 0.7: # Example threshold
        print("L1: Score below threshold. Logging as clear.")
        await l6_main.log_transaction(event, "clear")
    else:
        print("L1: Score above threshold. Proceeding to L3 for legal reasoning.")
        await l3_main.interpret_regulation(event, suspicion_score)

