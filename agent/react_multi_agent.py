from agent.graph.builder import build_multi_agent_graph
from skills.registry import SKILL_REGISTRY

class ReactMultiAgent:
    def __init__(self):
        # ① 构建新的单主图
        self.graph, self.conn, self.memory = build_multi_agent_graph()

        # ② 打印图结构，方便你检查现在是不是单主图
        try:
            print("\n========== 🗺️ 当前 Agent 工作流架构 ==========")
            print(self.graph.get_graph(xray=True).draw_ascii())
            print("===============================================\n")
        except Exception:
            pass

    def execute_stream(self, query: str, thread_id: str):
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        input_data = {
            "messages": [("user", query)]
        }

        # ① 先缓存“最后一次真正的 assistant 文本”
        final_text_parts = []

        # ② 这里不直接 yield 每一段 general_agent 内容
        for msg, metadata in self.graph.stream(input_data, config, stream_mode="messages"):

            node_name = metadata.get("langgraph_node")
            content = getattr(msg, "content", None)

            # ③ 只关心 general_agent 的文本
            if not content or node_name != "agent":
                continue

            # ④ 如果这一条消息带 tool_calls，说明这是“准备调工具”的那轮，不展示
            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                continue

            # ⑤ 有些模型在消息块里也可能带 tool_call_chunks，同样跳过
            tool_call_chunks = getattr(msg, "tool_call_chunks", None)
            if tool_call_chunks:
                continue

            # ⑥ 剩下的内容认为是最终回答片段，缓存起来
            final_text_parts.append(content)

        # ⑦ 最后只把最终回答输出给前端
        final_answer = "".join(final_text_parts).strip()
        if final_answer:
            yield final_answer