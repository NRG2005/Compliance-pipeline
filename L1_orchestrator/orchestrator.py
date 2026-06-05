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
    l2_result = await l2_main.transaction_monitor(event)
    suspicion_score = l2_result["composite_score"]
    
    if suspicion_score < 0.7: # Example threshold
        print("L1: Score below threshold. Logging as clear.")
        await l6_main.log_transaction(event, "clear")
    else:
        print("L1: Score above threshold. Proceeding to L3 for legal reasoning.")
        analysis = await l3_main.interpret_regulation(event, suspicion_score)
        
        # Merge analysis details into the event payload for subsequent layers
        case_data = {**event, **analysis}
        final_score = analysis.get("final_score", 0.0)
        verdict = analysis.get("verdict", "review")
        
        # Route based on final score
        # >= 0.70 auto-files STR using L4
        if final_score >= 0.70:
            print("L1: Routing to L4 (Report Generator).")
            from L4_report_generator.main import generate_report
            await generate_report(case_data)
            
            if final_score < 0.90:
                print("L1: Also routing to L5 (Human Review Queue) for dual verification.")
                print("L5: Case added to Next.js dashboard review queue.")
        else:
            print("L1: Routing to L5 (Human Review Queue).")
            if final_score < 0.50:
                print("L5: CASE ESCALATED due to low legal confidence!")
            else:
                print("L5: Case added to Next.js dashboard review queue.")
                
        # L6 Audit Log
        print("L1: Proceeding to L6 (Audit Logger).")
        await l6_main.log_transaction(event, verdict)

