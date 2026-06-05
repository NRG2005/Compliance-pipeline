"""
L3: Regulation Interpreter

Main entry point for the legal reasoning layer.
"""
from .hybrid_retrieval import search_regulations
from .legal_reasoning import generate_legal_analysis

async def interpret_regulation(event, suspicion_score):
    """
    Orchestrates the regulation interpretation process.

    Returns the analysis dict so callers (pipeline runner) can route to L4/L5.
    """
    # 1. Hybrid Retrieval
    print("L3: Performing hybrid retrieval from Azure AI Search.")
    retrieval_result = search_regulations(event)
    regulation_chunks = retrieval_result["chunks"]

    # 2. Legal Reasoning
    print("L3: Generating legal reasoning and sub-scores.")
    analysis = generate_legal_analysis(event, regulation_chunks)
    analysis["retrieval_match"] = retrieval_result["retrieval_match"]

    # 3. Determine verdict and print results
    final_score = analysis['final_score']
    if final_score >= 0.9:
        verdict = "AUTO_FILE"
        # Route to L4 (auto-file) — handled by the pipeline runner
    elif final_score >= 0.5:
        verdict = "HUMAN_REVIEW"
        # Route to L5 (human review) — handled by the pipeline runner
    else:
        verdict = "ESCALATE"
        # Route to L5 with priority escalation — handled by the pipeline runner

    analysis["verdict"] = verdict

    print(f"L3: ===== Regulation Interpretation Complete =====")
    print(f"L3: Final Score : {final_score}")
    print(f"L3: Verdict     : {verdict}")
    print(f"L3: ===============================================")

    return analysis
