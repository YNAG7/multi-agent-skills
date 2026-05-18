import os

# 1. 开启全局追踪魔法开关
os.environ["LANGCHAIN_TRACING_V2"] = "true"
# 2. 给你的项目起个响亮的名字，它会变成 LangSmith 里的一个文件夹
os.environ["LANGCHAIN_PROJECT"] = "扫地机多智能体项目"
# 3. 粘贴你刚刚复制的 API Key
os.environ["LANGCHAIN_API_KEY"] = "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"
import time
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import streamlit as st
from agent.react_multi_agent import ReactMultiAgent

# 标题
st.title("智扫通机器人智能客服")
st.divider()

SESSION_ID = "user_1001_chat_thread"

if "agent" not in st.session_state:
    st.session_state["agent"] = ReactMultiAgent()

if "display_messages" not in st.session_state:
    st.session_state.display_messages = []
    # 去 LangGraph 的物理数据库里查当前 SESSION_ID 的档案袋
    config = {"configurable": {"thread_id": SESSION_ID}}
    state = st.session_state.agent.graph.get_state(config)
    
    # 如果档案袋里有内容，就把它们提取出来放到前端
    if state.values and "messages" in state.values:
        for msg in state.values["messages"]:
            # 过滤1：如果是用户发的消息
            if isinstance(msg, HumanMessage):
                st.session_state.display_messages.append({"role": "user", "content": msg.content})
                
            # 过滤2：如果是大模型回复的消息（并且必须有文本内容，屏蔽掉纯调用工具的那条隐形消息）
            elif isinstance(msg, AIMessage) and msg.content:
                if not getattr(msg, "tool_calls", None):
                    st.session_state.display_messages.append({"role": "assistant", "content": msg.content})
                
            # 注意：我们故意忽略了 SystemMessage 和 ToolMessage，因为这些是系统底层逻辑，不需要展示给用户看。

# 3. 渲染历史记录到屏幕上
for msg in st.session_state.display_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


# 用户输入提示词
prompt = st.chat_input()

if prompt:
    st.session_state.display_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        stream_generator = st.session_state.agent.execute_stream(
            query=prompt, 
            thread_id=SESSION_ID 
        )
        
        
        # 渲染流式打字机效果
        for chunk in stream_generator:
            if not chunk:
                continue
            chunk = str(chunk)

            for ch in chunk:
                full_response += ch
                message_placeholder.markdown(full_response + "▌")
                time.sleep(0.02)
        message_placeholder.markdown(full_response)
        
    # 将 AI 的话显示在屏幕上
    st.session_state.display_messages.append({"role": "assistant", "content": full_response})