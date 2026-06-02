"""
L0: Event Ingestion

This layer is responsible for receiving transaction events from Azure Service Bus.
It's implemented as an Azure Function with a Service Bus Topic trigger.
"""
import azure.functions as func
from config import get_config

app = func.FunctionApp()
config = get_config()

@app.service_bus_topic_trigger(
    arg_name="message",
    topic_name=config.SERVICE_BUS_TOPIC_NAME,
    subscription_name=config.SERVICE_BUS_PIPELINE_SUB_NAME,
    connection="SERVICE_BUS_CONNECTION_STRING"
)
def event_receiver(message: func.ServiceBusMessage):
    """
    Receives a message from the Service Bus topic and passes it to the orchestrator.
    In a real Azure Functions deployment, this would trigger L1.
    For local testing, we can simulate this call.
    """
    message_body = message.get_body().decode('utf-8')
    print(f"L0: Received event: {message_body}")
    # In a real application, you would queue a task for L1 or call it via HTTP,
    # rather than importing directly.
    # from L1_orchestrator import orchestrator
    # orchestrator.handle_event(message_body)
