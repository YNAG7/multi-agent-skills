from agent.graph.state import AgentState
from agent.graph.select_router import select_skill

def router_node(state: AgentState):
    last_msg = state["messages"][-1].content
    
    # 此时 select_skill 返回的是一个 List[Dict]
    route_plan = select_skill(last_msg) 
    
    print(f"\n[🚦 路由生成计划] {route_plan}")


    return {
        "tasks": route_plan
    }