import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Optional
from agents.sites_agent import SitesAgent
from agents.search_agent import SearchAgent
from agents.grading_agent import GradingAgent
from agents.ranker_agent import RankerAgent

class SwarmState(TypedDict):
    status: str
    errors: Optional[list]

def run_sites_agent(state: SwarmState):
    print("--- Running Sites Agent ---")
    try:
        agent = SitesAgent()
        agent.run()
        return {"status": "sites_done"}
    except Exception as e:
        return {"status": "error", "errors": [str(e)]}

def run_search_agent(state: SwarmState):
    print("--- Running Search Agent ---")
    try:
        agent = SearchAgent()
        agent.run()
        return {"status": "search_done"}
    except Exception as e:
        return {"status": "error", "errors": [str(e)]}
        
def run_grading_agent(state: SwarmState):
    print("--- Running Grading Agent ---")
    try:
        agent = GradingAgent()
        agent.run()
        return {"status": "grading_done"}
    except Exception as e:
        return {"status": "error", "errors": [str(e)]}
        
def run_ranker_agent(state: SwarmState):
    print("--- Running Ranker Agent ---")
    try:
        agent = RankerAgent()
        agent.run()
        return {"status": "ranker_done"}
    except Exception as e:
        return {"status": "error", "errors": [str(e)]}

def build_workflow():
    workflow = StateGraph(SwarmState)
    
    # Add nodes
    workflow.add_node("sites", run_sites_agent)
    workflow.add_node("search", run_search_agent)
    workflow.add_node("grade", run_grading_agent)
    workflow.add_node("rank", run_ranker_agent)
    
    # Add edges
    workflow.add_edge(START, "sites")
    workflow.add_edge("sites", "search")
    workflow.add_edge("search", "grade")
    workflow.add_edge("grade", "rank")
    workflow.add_edge("rank", END)
    
    return workflow.compile()

if __name__ == "__main__":
    app = build_workflow()
    print("Starting Multi-Agent Swarm Workflow...")
    
    # Initial state
    initial_state = {"status": "started", "errors": []}
    
    # We can stream the steps
    for output in app.stream(initial_state):
        for key, value in output.items():
            print(f"Node '{key}' completed with state update: {value}")
            if "error" in value.get("status", ""):
                print("Workflow halted due to error.")
                sys.exit(1)
    
    print("Workflow completed successfully. Check final_ranking.md")
