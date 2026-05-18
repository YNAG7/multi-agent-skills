import json
from langchain_core.tools import tool
import requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import re
import trafilatura
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.embeddings import DashScopeEmbeddings

embedding_model = DashScopeEmbeddings(model="text-embedding-v3")
RSS_GROUPS={
    "综合时政": [
        "https://www.chinanews.com.cn/rss/china.xml",       
        "https://www.chinanews.com.cn/rss/world.xml",       
        "https://www.chinanews.com.cn/rss/importnews.xml"   
    ],
    "大众热点": [
        "https://www.chinanews.com.cn/rss/scroll-news.xml", 
        "https://www.chinanews.com.cn/rss/society.xml"      
    ],
    "生活消费": [
        "https://www.chinanews.com.cn/rss/life.xml",        
        "https://www.chinanews.com.cn/rss/jk.xml",          
        "https://www.chinanews.com.cn/rss/culture.xml"      
    ],
    "宏观财经": [
        "https://www.chinanews.com.cn/rss/finance.xml",     
        "https://www.chinanews.com.cn/rss/importnews.xml"   
    ],
    "出海方向": [
        "https://www.chinanews.com.cn/rss/ydyl.xml",        
        "https://www.chinanews.com.cn/rss/aseaninfo.xml"    
    ]
}

def fetch_news_by_group(group_name: str, top_n_per_feed: int = 3) -> list[dict]:
    if group_name not in RSS_GROUPS:
        return []

        
    urls = RSS_GROUPS[group_name]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    all_news_data = []
    
    for url in urls:
        try:
            print(f"正在抓取数据源: {url} ...")
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8' 
            
            root = ET.fromstring(response.text)
            
            for item in root.findall('./channel/item')[:top_n_per_feed]:
                title = item.find('title').text if item.find('title') is not None else '无标题'
                link = item.find('link').text if item.find('link') is not None else '无链接'
                description = item.find('description').text if item.find('description') is not None else '无摘要'
                
                # ====== 时间处理核心逻辑（保留年月日 + 几点几分几秒） ======
                raw_pub_date = item.find('pubDate').text if item.find('pubDate') is not None else None
                pub_date = '未知时间'
                
                if raw_pub_date:
                    try:
                        # 尝试将 RSS 格式时间转为标准 datetime 对象
                        dt = parsedate_to_datetime(raw_pub_date)
                        # 格式化为 YYYY-MM-DD HH:MM:SS，把具体的“几点”拿回来！
                        pub_date = dt.strftime('%Y-%m-%d %H:%M:%S') 
                    except Exception:
                        # 如果上面的解析失败，用正则提取数字做个兜底
                        match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', raw_pub_date)
                        pub_date = match.group(0) if match else raw_pub_date
                # ==============================================================
                
                clean_description = re.sub('<[^<]+>', '', description).strip()
                
                news_item = {
                    "title": title,
                    "description": clean_description,
                    "time": pub_date,
                    "url": link
                }
                
                all_news_data.append(news_item)
                
        except Exception as e:
            print(f"[news_search] 数据源 {url} 抓取失败: {str(e)}\n{'-' * 40}")
            continue
            
    return all_news_data

def read_news_article(url: str, timeout: int = 15, include_html: bool = False) -> str:
    """
    根据新闻链接抓取正文内容，返回结构化 JSON。
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ArticleReader/1.0"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding or "utf-8"
        html = resp.text

        downloaded = trafilatura.extract(
            html,
            include_links=False,
            include_images=False,
            include_formatting=False,
            with_metadata=True,
            output_format="json",
            url=url,
        )

        if downloaded:
            data = json.loads(downloaded)
            output = {
                "success": True,
                "url": url,
                "title": data.get("title", ""),
                "author": data.get("author", ""),
                "date": data.get("date", ""),
                "site_name": data.get("sitename", ""),
                "language": data.get("language", ""),
                "text": data.get("text", ""),
                "excerpt": (data.get("text", "")[:500] + "...") if data.get("text") and len(data.get("text", "")) > 500 else data.get("text", ""),
            }
        else:
            output = {
                "success": False,
                "url": url,
                "title": "",
                "author": "",
                "date": "",
                "site_name": "",
                "language": "",
                "text": "",
                "excerpt": "",
                "error": "正文提取失败，页面可能是反爬、脚本渲染或非正文页。",
            }

        if include_html:
            output["html"] = html[:20000]

        return json.dumps(output, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "url": url,
                "error": str(e),
                "text": "",
            },
            ensure_ascii=False,
            indent=2,
        )
        
def filter_news_by_query(user_query: str, news_list: list, top_k: int = 3) -> list:
    """
    对抓取到的即时新闻进行纯内存级的 RAG 检索，不持久化到本地向量库。
    
    :param user_query: 用户的输入/查询意图 (如: "今天有什么适合做美妆带货的新闻")
    :param news_list: 从 rss_search.py 抓取下来的字典列表
    :param top_k: 返回最相关的几条新闻
    :return: 过滤并按相关度排序后的新闻字典列表
    """
    if not news_list:
        return []

    # 1. 将字典数据组装成 LangChain 的 Document 对象
    docs = []
    for news in news_list:
        # 小技巧：把 title 和 description 拼在一起做 page_content，检索精度更高
        # 原始的 dict 塞进 metadata 里，方便检索后直接提取原数据
        content = f"标题：{news['title']}\n摘要：{news['description']}"
        doc = Document(
            page_content=content,
            metadata={
                "title": news['title'],
                "description": news['description'],
                "time": news['time'],
                "url": news['url']
            }
        )
        docs.append(doc)

    try:
        # 2. 核心：构建纯内存的 Chroma 向量库
        # 注意：这里千万不要传 persist_directory！
        memory_vector_store = Chroma.from_documents(
            documents=docs,
            embedding=embedding_model
        )

        # 3. 执行检索
        retriever = memory_vector_store.as_retriever(search_kwargs={"k": top_k})
        retrieved_docs = retriever.invoke(user_query)

        # 4. 把检索出来的 Document 还原成你的字典格式
        filtered_news = [doc.metadata for doc in retrieved_docs]
        
        # 5. （可选）手动清理内存引用，虽然 Python 会自动 GC
        del memory_vector_store
        
        return filtered_news

    except Exception as e:
        return news_list[:top_k]


@tool(description=(
    "根据用户查询主题，在指定资讯池中检索相关新闻并抓取正文。"
    "query 是检索主题；group_name 只能是：综合时政、大众热点、生活消费、宏观财经、出海方向；"
    "若不确定，默认使用 综合时政。"
    "top_k 表示返回的相关新闻条数，默认 3，建议范围为 3 到 10；"
))
def get_news(query: str, group_name: str = "综合时政", top_k: int = 3) -> list:

    # 1. 从 RSS 抓取新闻 (稍微多抓一点供检索)
    all_news_data = fetch_news_by_group(group_name, top_n_per_feed=5)  

    if not all_news_data:
        return []

    # 2. 内存级 RAG 检索
    filtered_news = filter_news_by_query(query, all_news_data, top_k=top_k)
    
    # 3. 抓取正文并组装最终数据
    final_news = []
    for item in filtered_news:
        # 抓取正文，拿到的是 JSON 字符串
        article_json_str = read_news_article(item['url'])
        
        try:
            # 将字符串解析回 Python 字典
            article_data = json.loads(article_json_str)
            
            # 【修改 3】：合并数据。保留原有的标题和链接，把正文追加进去
            item['full_text'] = article_data.get('text', '')
            
            # 如果正文提取失败，可以用原来的摘要兜底
            if not item['full_text'] and article_data.get('error'):
                item['full_text'] = f"正文抓取失败，原摘要为: {item['description']}"
                
        except Exception as e:
            item['full_text'] = item['description']
            
        final_news.append(item)
        
    return final_news


TOOL_EXPORTS = [
    get_news,
]