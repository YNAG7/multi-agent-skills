from utils.config_handler import prompts_conf
from utils.logger_handler import logger

    
def load_rag_prompt():
    try:
        rag_prompt_path= prompts_conf.get('rag_summarize_prompt_path')
    except KeyError as e:
        logger.error(f"[load_rag_prompt]在yaml配置项中没有rag_summarize_prompt_path配置项")
        raise e
    try:
        return open(rag_prompt_path, 'r', encoding='utf-8').read()
    except Exception as e:
        logger.error(f"[load_rag_prompt]解析RAG总结提示词出错: {str(e)}")
        raise e
    
def load_router_prompt():
    try:
        router_prompt_path= prompts_conf.get('router_prompt_path')
    except KeyError as e:
        logger.error(f"[load_router_prompt]在yaml配置项中没有router_prompt_path配置项")
        raise e
    try:
        return open(router_prompt_path, 'r', encoding='utf-8').read()
    except Exception as e:
        logger.error(f"[load_router_prompt]解析路由提示词出错: {str(e)}")
        raise e
    
