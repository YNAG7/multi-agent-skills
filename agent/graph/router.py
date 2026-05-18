from agent.graph.state import AgentState
from agent.graph.select_router import select_skill


def router_node(state: AgentState):
    # 取用户最后一句话做路由
    last_msg = state["messages"][-1].content

    # 只判断一个主 skill
    main_skill = select_skill(last_msg)

    # 打印出来，方便调试
    print(f"\n[🚦 路由判断] main_skill={main_skill}")

    # 把路由结果写回 state
    return {
        "main_skill": main_skill,
    }