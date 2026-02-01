from langgraph.graph import StateGraph, END

from app.services.chat_state import BookingState
from app.services.chat_nodes import (
    parse_message_node,
    route_after_parse,
    greet_node,
    list_services_node,
    handle_service_selection_node,
    handle_slot_selection_node,
    handle_contact_node,
    confirm_booking_node,
    escalate_node,
    general_response_node,
    show_service_details_node,
    check_status_node,
    cancel_booking_node,
    reschedule_node,
    confirm_cancel_node,
)


def create_booking_graph():
    """
    Create and compile the LangGraph workflow for booking conversations.
    """
    
    # Create the graph with our state type
    workflow = StateGraph(BookingState)
    
    # Add all nodes
    workflow.add_node("parse_message_node", parse_message_node)
    workflow.add_node("greet_node", greet_node)
    workflow.add_node("list_services_node", list_services_node)
    workflow.add_node("handle_service_selection_node", handle_service_selection_node)
    workflow.add_node("handle_slot_selection_node", handle_slot_selection_node)
    workflow.add_node("handle_contact_node", handle_contact_node)
    workflow.add_node("confirm_booking_node", confirm_booking_node)
    workflow.add_node("escalate_node", escalate_node)
    workflow.add_node("general_response_node", general_response_node)
    workflow.add_node("show_service_details_node", show_service_details_node)
    workflow.add_node("check_status_node", check_status_node)
    workflow.add_node("cancel_booking_node", cancel_booking_node)
    workflow.add_node("reschedule_node", reschedule_node)
    workflow.add_node("confirm_cancel_node", confirm_cancel_node)
    
    # Set entry point
    workflow.set_entry_point("parse_message_node")
    
    # Add conditional routing after parse
    workflow.add_conditional_edges(
        "parse_message_node",
        route_after_parse,
        {
            "greet_node": "greet_node",
            "list_services_node": "list_services_node",
            "handle_service_selection_node": "handle_service_selection_node",
            "handle_slot_selection_node": "handle_slot_selection_node",
            "handle_contact_node": "handle_contact_node",
            "confirm_booking_node": "confirm_booking_node",
            "escalate_node": "escalate_node",
            "general_response_node": "general_response_node",
            "show_service_details_node": "show_service_details_node",
            "check_status_node": "check_status_node",
            "cancel_booking_node": "cancel_booking_node",
            "reschedule_node": "reschedule_node",
            "confirm_cancel_node": "confirm_cancel_node",
        }
    )
    
    # All handler nodes end the flow
    workflow.add_edge("greet_node", END)
    workflow.add_edge("list_services_node", END)
    workflow.add_edge("handle_service_selection_node", END)
    workflow.add_edge("handle_slot_selection_node", END)
    workflow.add_edge("handle_contact_node", END)
    workflow.add_edge("confirm_booking_node", END)
    workflow.add_edge("escalate_node", END)
    workflow.add_edge("general_response_node", END)
    workflow.add_edge("show_service_details_node", END)
    workflow.add_edge("check_status_node", END)
    workflow.add_edge("cancel_booking_node", END)
    workflow.add_edge("reschedule_node", END)
    workflow.add_edge("confirm_cancel_node", END)
    
    # Compile the graph
    compiled_graph = workflow.compile()
    
    return compiled_graph


# Create singleton instance
booking_graph = create_booking_graph()