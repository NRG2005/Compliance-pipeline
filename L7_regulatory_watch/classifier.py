"""
L7: Phi-4-mini Classifier

Classifies the type of change and writes a summary.
"""

def classify_changes(document_text):
    """
    Uses a small language model (like Phi-4-mini) to classify the change.
    """
    print("L7: Classifying document change type and summarizing...")
    # TODO: Implement the prompt for the classification and summary task
    # TODO: Call the LLM
    # TODO: Parse the output
    
    change_info = {
        "change_type": "amendment", # e.g., new, amendment, withdrawal
        "summary": "This is a plain English summary of the change.",
        "tags": ["KYC", "AML"]
    }
    return change_info
