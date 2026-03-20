"""
Zep检索工具服务
封装GraphSearch、Nodes读取、边查询等工具，供Report Agent使用

核心检索工具（优化后）：
1. InsightForge（深度洞察检索）- 最强大的混合检索，自动生成子问题and多维度检索
2. PanoramaSearch（广度Search）- Get全貌，Include过期内容
3. QuickSearch（简单Search）- 快速检索
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges

logger = get_logger('mirofish.zep_tools')


@dataclass
class SearchResult:
    """Search结果"""
    facts: List[str]
    edges: List[Dict[str, Any]]
    nodes: List[Dict[str, Any]]
    query: str
    total_count: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": self.facts,
            "edges": self.edges,
            "nodes": self.nodes,
            "query": self.query,
            "total_count": self.total_count
        }
    
    def to_text(self) -> str:
        """转换为文本格式，供LLM理解"""
        text_parts = [f"Search查询: {self.query}", f"找到 {self.total_count} items相关Info"]
        
        if self.facts:
            text_parts.append("\n### 相关事实:")
            for i, fact in enumerate(self.facts, 1):
                text_parts.append(f"{i}. {fact}")
        
        return "\n".join(text_parts)


@dataclass
class NodeInfo:
    """NodesInfo"""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "labels": self.labels,
            "summary": self.summary,
            "attributes": self.attributes
        }
    
    def to_text(self) -> str:
        """转换为文本格式"""
        entity_type = next((l for l in self.labels if l not in ["Entity", "Node"]), "未知Type")
        return f"Entity: {self.name} (Type: {entity_type})\n摘要: {self.summary}"


@dataclass
class EdgeInfo:
    """边Info"""
    uuid: str
    name: str
    fact: str
    source_node_uuid: str
    target_node_uuid: str
    source_node_name: Optional[str] = no
    target_node_name: Optional[str] = no
    # 时间Info
    created_at: Optional[str] = no
    valid_at: Optional[str] = no
    invalid_at: Optional[str] = no
    expired_at: Optional[str] = no
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "uuid": self.uuid,
            "name": self.name,
            "fact": self.fact,
            "source_node_uuid": self.source_node_uuid,
            "target_node_uuid": self.target_node_uuid,
            "source_node_name": self.source_node_name,
            "target_node_name": self.target_node_name,
            "created_at": self.created_at,
            "valid_at": self.valid_at,
            "invalid_at": self.invalid_at,
            "expired_at": self.expired_at
        }
    
    def to_text(self, include_temporal: bool = False) -> str:
        """转换为文本格式"""
        source = self.source_node_name or self.source_node_uuid[:8]
        target = self.target_node_name or self.target_node_uuid[:8]
        base_text = f"Relation: {source} --[{self.name}]--> {target}\n事实: {self.fact}"
        
        if include_temporal:
            valid_at = self.valid_at or "未知"
            invalid_at = self.invalid_at or "至今"
            base_text += f"\n时效: {valid_at} - {invalid_at}"
            if self.expired_at:
                base_text += f" (Completed过期: {self.expired_at})"
        
        return base_text
    
    @property
    def is_expired(self) -> bool:
        """是否Completed过期"""
        return self.expired_at is not no
    
    @property
    def is_invalid(self) -> bool:
        """是否Completed失效"""
        return self.invalid_at is not no


@dataclass
class InsightForgeResult:
    """
    深度洞察检索结果 (InsightForge)
    Contain多items子问题的检索结果，以及综合分析
    """
    query: str
    simulation_requirement: str
    sub_queries: List[str]
    
    # 各维度检索结果
    semantic_facts: List[str] = field(default_factory=list)  # 语义Search结果
    entity_insights: List[Dict[str, Any]] = field(default_factory=list)  # Entity洞察
    relationship_chains: List[str] = field(default_factory=list)  # Relation链
    
    # 统计Info
    total_facts: int = 0
    total_entities: int = 0
    total_relationships: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "simulation_requirement": self.simulation_requirement,
            "sub_queries": self.sub_queries,
            "semantic_facts": self.semantic_facts,
            "entity_insights": self.entity_insights,
            "relationship_chains": self.relationship_chains,
            "total_facts": self.total_facts,
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships
        }
    
    def to_text(self) -> str:
        """转换为详细的文本格式，供LLM理解"""
        text_parts = [
            f"## 未来预测深度分析",
            f"分析问题: {self.query}",
            f"预测场景: {self.simulation_requirement}",
            f"\n### 预测数据统计",
            f"- 相关预测事实: {self.total_facts}items",
            f"- 涉及Entity: {self.total_entities}items",
            f"- Relation链: {self.total_relationships}items"
        ]
        
        # 子问题
        if self.sub_queries:
            text_parts.append(f"\n### 分析的子问题")
            for i, sq in enumerate(self.sub_queries, 1):
                text_parts.append(f"{i}. {sq}")
        
        # 语义Search结果
        if self.semantic_facts:
            text_parts.append(f"\n### 【关键事实】(请在报告中引用这些原文)")
            for i, fact in enumerate(self.semantic_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # Entity洞察
        if self.entity_insights:
            text_parts.append(f"\n### 【核心Entity】")
            for entity in self.entity_insights:
                text_parts.append(f"- **{entity.get('name', '未知')}** ({entity.get('type', 'Entity')})")
                if entity.get('summary'):
                    text_parts.append(f"  摘要: \"{entity.get('summary')}\"")
                if entity.get('related_facts'):
                    text_parts.append(f"  相关事实: {len(entity.get('related_facts', []))}items")
        
        # Relation链
        if self.relationship_chains:
            text_parts.append(f"\n### 【Relation链】")
            for chain in self.relationship_chains:
                text_parts.append(f"- {chain}")
        
        return "\n".join(text_parts)


@dataclass
class PanoramaResult:
    """
    广度Search结果 (Panorama)
    Contain所yes相关Info，Include过期内容
    """
    query: str
    
    # 全部Nodes
    all_nodes: List[NodeInfo] = field(default_factory=list)
    # 全部边（Include过期的）
    all_edges: List[EdgeInfo] = field(default_factory=list)
    # 当前yes效的事实
    active_facts: List[str] = field(default_factory=list)
    # Completed过期/失效的事实（历史Log）
    historical_facts: List[str] = field(default_factory=list)
    
    # 统计
    total_nodes: int = 0
    total_edges: int = 0
    active_count: int = 0
    historical_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "all_nodes": [n.to_dict() for n in self.all_nodes],
            "all_edges": [e.to_dict() for e in self.all_edges],
            "active_facts": self.active_facts,
            "historical_facts": self.historical_facts,
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "active_count": self.active_count,
            "historical_count": self.historical_count
        }
    
    def to_text(self) -> str:
        """转换为文本格式（完整版本，不截断）"""
        text_parts = [
            f"## 广度Search结果（未来全景视图）",
            f"查询: {self.query}",
            f"\n### 统计Info",
            f"- 总Nodes数: {self.total_nodes}",
            f"- 总边数: {self.total_edges}",
            f"- 当前yes效事实: {self.active_count}items",
            f"- 历史/过期事实: {self.historical_count}items"
        ]
        
        # 当前yes效的事实（完整Output，不截断）
        if self.active_facts:
            text_parts.append(f"\n### 【当前yes效事实】(模拟结果原文)")
            for i, fact in enumerate(self.active_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # 历史/过期事实（完整Output，不截断）
        if self.historical_facts:
            text_parts.append(f"\n### 【历史/过期事实】(演变过程Log)")
            for i, fact in enumerate(self.historical_facts, 1):
                text_parts.append(f"{i}. \"{fact}\"")
        
        # 关键Entity（完整Output，不截断）
        if self.all_nodes:
            text_parts.append(f"\n### 【涉及Entity】")
            for node in self.all_nodes:
                entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entity")
                text_parts.append(f"- **{node.name}** ({entity_type})")
        
        return "\n".join(text_parts)


@dataclass
class AgentInterview:
    """单itemsAgent的采访结果"""
    agent_name: str
    agent_role: str  # 角色Type（如：学生、教师、媒体等）
    agent_bio: str  # 简介
    question: str  # 采Access题
    response: str  # 采访回答
    key_quotes: List[str] = field(default_factory=list)  # 关键引言
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "agent_bio": self.agent_bio,
            "question": self.question,
            "response": self.response,
            "key_quotes": self.key_quotes
        }
    
    def to_text(self) -> str:
        text = f"**{self.agent_name}** ({self.agent_role})\n"
        # 显示完整的agent_bio，不截断
        text += f"_简介: {self.agent_bio}_\n\n"
        text += f"**Q:** {self.question}\n\n"
        text += f"**A:** {self.response}\n"
        if self.key_quotes:
            text += "\n**关键引言:**\n"
            for quote in self.key_quotes:
                # 清理各种引号
                clean_quote = quote.replace('\u201c', '').replace('\u201d', '').replace('"', '')
                clean_quote = clean_quote.replace('\u300c', '').replace('\u300d', '')
                clean_quote = clean_quote.strip()
                # 去掉开头的标点
                while clean_quote and clean_quote[0] in '，,；;：:、。！？\n\r\t ':
                    clean_quote = clean_quote[1:]
                # 过滤Contain问题编号的垃圾内容（问题1-9）
                skip = False
                for d in '123456789':
                    if f'\u95ee\u9898{d}' in clean_quote:
                        skip = True
                        break
                if skip:
                    continue
                # 截断过长内容（按句号截断，but非硬截断）
                if len(clean_quote) > 150:
                    dot_pos = clean_quote.find('\u3002', 80)
                    if dot_pos > 0:
                        clean_quote = clean_quote[:dot_pos + 1]
                    else:
                        clean_quote = clean_quote[:147] + "..."
                if clean_quote and len(clean_quote) >= 10:
                    text += f'> "{clean_quote}"\n'
        return text


@dataclass
class InterviewResult:
    """
    采访结果 (Interview)
    Contain多items模拟Agent的采访回答
    """
    interview_topic: str  # 采访主题
    interview_questions: List[str]  # 采Access题列表
    
    # 采访选择的Agent
    selected_agents: List[Dict[str, Any]] = field(default_factory=list)
    # 各Agent的采访回答
    interviews: List[AgentInterview] = field(default_factory=list)
    
    # 选择Agent的理由
    selection_reasoning: str = ""
    # 整合后的采访摘要
    summary: str = ""
    
    # 统计
    total_agents: int = 0
    interviewed_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interview_topic": self.interview_topic,
            "interview_questions": self.interview_questions,
            "selected_agents": self.selected_agents,
            "interviews": [i.to_dict() for i in self.interviews],
            "selection_reasoning": self.selection_reasoning,
            "summary": self.summary,
            "total_agents": self.total_agents,
            "interviewed_count": self.interviewed_count
        }
    
    def to_text(self) -> str:
        """转换为详细的文本格式，供LLM理解和报告引用"""
        text_parts = [
            "## 深度采访报告",
            f"**采访主题:** {self.interview_topic}",
            f"**采访人数:** {self.interviewed_count} / {self.total_agents} 位模拟Agent",
            "\n### 采访对象选择理由",
            self.selection_reasoning or "（自动选择）",
            "\n---",
            "\n### 采访实录",
        ]

        if self.interviews:
            for i, interview in enumerate(self.interviews, 1):
                text_parts.append(f"\n#### 采访 #{i}: {interview.agent_name}")
                text_parts.append(interview.to_text())
                text_parts.append("\n---")
        else:
            text_parts.append("（no采访Log）\n\n---")

        text_parts.append("\n### 采访摘要and核心观点")
        text_parts.append(self.summary or "（no摘要）")

        return "\n".join(text_parts)


class ZepToolsService:
    """
    Zep检索工具服务
    
    【核心检索工具 - 优化后】
    1. insight_forge - 深度洞察检索（最强大，自动生成子问题，多维度检索）
    2. panorama_search - 广度Search（Get全貌，Include过期内容）
    3. quick_search - 简单Search（快速检索）
    4. interview_agents - 深度采访（采访模拟Agent，Get多视角观点）
    
    【基础工具】
    - search_graph - Graph语义Search
    - get_all_nodes - GetGraph所yesNodes
    - get_all_edges - GetGraph所yes边（含时间Info）
    - get_node_detail - GetNodes详细Info
    - get_node_edges - GetNodes相关的边
    - get_entities_by_type - 按TypeGetEntity
    - get_entity_summary - GetEntity的Relation摘要
    """
    
    # Retry配置
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0
    
    def __init__(self, api_key: Optional[str] = no, llm_client: Optional[LLMClient] = no):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY 未配置")
        
        self.client = Zep(api_key=self.api_key)
        # LLM客户端用于InsightForge生成子问题
        self._llm_client = llm_client
        logger.info("ZepToolsService InitializeComplete")
    
    @property
    def llm(self) -> LLMClient:
        """延迟InitializeLLM客户端"""
        if self._llm_client is no:
            self._llm_client = LLMClient()
        return self._llm_client
    
    def _call_with_retry(self, func, operation_name: str, max_retries: int = no):
        """带Retry机制的API调用"""
        max_retries = max_retries or self.MAX_RETRIES
        last_exception = no
        delay = self.RETRY_DELAY
        
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} 第 {attempt + 1} 次尝试Failed: {str(e)[:100]}, "
                        f"{delay:.1f}秒后Retry..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(f"Zep {operation_name} 在 {max_retries} 次尝试后仍Failed: {str(e)}")
        
        raise last_exception
    
    def search_graph(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Graph语义Search
        
        使用混合Search（语义+BM25）在Graph中Search相关Info。
        IfZep Cloud的search API不可用，则降级为本地关键词匹配。
        
        Args:
            graph_id: GraphID (Standalone Graph)
            query: Search查询
            limit: Back结果数量
            scope: Search范围，"edges" or "nodes"
            
        Returns:
            SearchResult: Search结果
        """
        logger.info(f"GraphSearch: graph_id={graph_id}, query={query[:50]}...")
        
        # 尝试使用Zep Cloud Search API
        try:
            search_results = self._call_with_retry(
                func=lambda: self.client.graph.search(
                    graph_id=graph_id,
                    query=query,
                    limit=limit,
                    scope=scope,
                    reranker="cross_encoder"
                ),
                operation_name=f"GraphSearch(graph={graph_id})"
            )
            
            facts = []
            edges = []
            nodes = []
            
            # 解析边Search结果
            if hasattr(search_results, 'edges') and search_results.edges:
                for edge in search_results.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        facts.append(edge.fact)
                    edges.append({
                        "uuid": getattr(edge, 'uuid_', no) or getattr(edge, 'uuid', ''),
                        "name": getattr(edge, 'name', ''),
                        "fact": getattr(edge, 'fact', ''),
                        "source_node_uuid": getattr(edge, 'source_node_uuid', ''),
                        "target_node_uuid": getattr(edge, 'target_node_uuid', ''),
                    })
            
            # 解析NodesSearch结果
            if hasattr(search_results, 'nodes') and search_results.nodes:
                for node in search_results.nodes:
                    nodes.append({
                        "uuid": getattr(node, 'uuid_', no) or getattr(node, 'uuid', ''),
                        "name": getattr(node, 'name', ''),
                        "labels": getattr(node, 'labels', []),
                        "summary": getattr(node, 'summary', ''),
                    })
                    # Nodes摘要也算作事实
                    if hasattr(node, 'summary') and node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(f"SearchComplete: 找到 {len(facts)} items相关事实")
            
            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts)
            )
            
        except Exception as e:
            logger.warning(f"Zep Search APIFailed，降级为本地Search: {str(e)}")
            # 降级：使用本地关键词匹配Search
            return self._local_search(graph_id, query, limit, scope)
    
    def _local_search(
        self, 
        graph_id: str, 
        query: str, 
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        本地关键词匹配Search（作为Zep Search API的降级solution）
        
        Get所yes边/Nodes，然后在本地进行关键词匹配
        
        Args:
            graph_id: GraphID
            query: Search查询
            limit: Back结果数量
            scope: Search范围
            
        Returns:
            SearchResult: Search结果
        """
        logger.info(f"使用本地Search: query={query[:30]}...")
        
        facts = []
        edges_result = []
        nodes_result = []
        
        # 提取查询关键词（简单分词）
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]
        
        def match_score(text: str) -> int:
            """计算文本and查询的匹配分数"""
            if not text:
                return 0
            text_lower = text.lower()
            # 完全匹配查询
            if query_lower in text_lower:
                return 100
            # 关键词匹配
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score
        
        try:
            if scope in ["edges", "both"]:
                # Get所yes边and匹配
                all_edges = self.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.fact) + match_score(edge.name)
                    if score > 0:
                        scored_edges.append((score, edge))
                
                # 按分数Sort
                scored_edges.sort(key=lambda x: x[0], reverse=True)
                
                for score, edge in scored_edges[:limit]:
                    if edge.fact:
                        facts.append(edge.fact)
                    edges_result.append({
                        "uuid": edge.uuid,
                        "name": edge.name,
                        "fact": edge.fact,
                        "source_node_uuid": edge.source_node_uuid,
                        "target_node_uuid": edge.target_node_uuid,
                    })
            
            if scope in ["nodes", "both"]:
                # Get所yesNodesand匹配
                all_nodes = self.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.name) + match_score(node.summary)
                    if score > 0:
                        scored_nodes.append((score, node))
                
                scored_nodes.sort(key=lambda x: x[0], reverse=True)
                
                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "labels": node.labels,
                        "summary": node.summary,
                    })
                    if node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")
            
            logger.info(f"本地SearchComplete: 找到 {len(facts)} items相关事实")
            
        except Exception as e:
            logger.error(f"本地SearchFailed: {str(e)}")
        
        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )
    
    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """
        GetGraph的所yesNodes（分pageGet）

        Args:
            graph_id: GraphID

        Returns:
            Nodes列表
        """
        logger.info(f"GetGraph {graph_id} 的所yesNodes...")

        nodes = fetch_all_nodes(self.client, graph_id)

        result = []
        for node in nodes:
            node_uuid = getattr(node, 'uuid_', no) or getattr(node, 'uuid', no) or ""
            result.append(NodeInfo(
                uuid=str(node_uuid) if node_uuid else "",
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            ))

        logger.info(f"Get到 {len(result)} itemsNodes")
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """
        GetGraph的所yes边（分pageGet，Contain时间Info）

        Args:
            graph_id: GraphID
            include_temporal: 是否Contain时间Info（默认True）

        Returns:
            边列表（Containcreated_at, valid_at, invalid_at, expired_at）
        """
        logger.info(f"GetGraph {graph_id} 的所yes边...")

        edges = fetch_all_edges(self.client, graph_id)

        result = []
        for edge in edges:
            edge_uuid = getattr(edge, 'uuid_', no) or getattr(edge, 'uuid', no) or ""
            edge_info = EdgeInfo(
                uuid=str(edge_uuid) if edge_uuid else "",
                name=edge.name or "",
                fact=edge.fact or "",
                source_node_uuid=edge.source_node_uuid or "",
                target_node_uuid=edge.target_node_uuid or ""
            )

            # 添加时间Info
            if include_temporal:
                edge_info.created_at = getattr(edge, 'created_at', no)
                edge_info.valid_at = getattr(edge, 'valid_at', no)
                edge_info.invalid_at = getattr(edge, 'invalid_at', no)
                edge_info.expired_at = getattr(edge, 'expired_at', no)

            result.append(edge_info)

        logger.info(f"Get到 {len(result)} items边")
        return result
    
    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """
        Get单itemsNodes的详细Info
        
        Args:
            node_uuid: NodesUUID
            
        Returns:
            NodesInfoorno
        """
        logger.info(f"GetNodesDetails: {node_uuid[:8]}...")
        
        try:
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=node_uuid),
                operation_name=f"GetNodesDetails(uuid={node_uuid[:8]}...)"
            )
            
            if not node:
                return no
            
            return NodeInfo(
                uuid=getattr(node, 'uuid_', no) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            )
        except Exception as e:
            logger.error(f"GetNodesDetailsFailed: {str(e)}")
            return no
    
    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
        GetNodes相关的所yes边
        
        ThroughGetGraph所yes边，然后过滤出and指定Nodes相关的边
        
        Args:
            graph_id: GraphID
            node_uuid: NodesUUID
            
        Returns:
            边列表
        """
        logger.info(f"GetNodes {node_uuid[:8]}... 的相关边")
        
        try:
            # GetGraph所yes边，然后过滤
            all_edges = self.get_all_edges(graph_id)
            
            result = []
            for edge in all_edges:
                # Check边是否and指定Nodes相关（作为SourceorTarget）
                if edge.source_node_uuid == node_uuid or edge.target_node_uuid == node_uuid:
                    result.append(edge)
            
            logger.info(f"找到 {len(result)} itemsandNodes相关的边")
            return result
            
        except Exception as e:
            logger.warning(f"GetNodes边Failed: {str(e)}")
            return []
    
    def get_entities_by_type(
        self, 
        graph_id: str, 
        entity_type: str
    ) -> List[NodeInfo]:
        """
        按TypeGetEntity
        
        Args:
            graph_id: GraphID
            entity_type: EntityType（如 Student, PublicFigure 等）
            
        Returns:
            符合Type的Entity列表
        """
        logger.info(f"GetType为 {entity_type} 的Entity...")
        
        all_nodes = self.get_all_nodes(graph_id)
        
        filtered = []
        for node in all_nodes:
            # Checklabels是否Contain指定Type
            if entity_type in node.labels:
                filtered.append(node)
        
        logger.info(f"找到 {len(filtered)} items {entity_type} Type的Entity")
        return filtered
    
    def get_entity_summary(
        self, 
        graph_id: str, 
        entity_name: str
    ) -> Dict[str, Any]:
        """
        Get指定Entity的Relation摘要
        
        Searchand该Entity相关的所yesInfo，and生成摘要
        
        Args:
            graph_id: GraphID
            entity_name: Entity名称
            
        Returns:
            Entity摘要Info
        """
        logger.info(f"GetEntity {entity_name} 的Relation摘要...")
        
        # 先Search该Entity相关的Info
        search_result = self.search_graph(
            graph_id=graph_id,
            query=entity_name,
            limit=20
        )
        
        # 尝试在所yesNodes中找到该Entity
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = no
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break
        
        related_edges = []
        if entity_node:
            # 传入graph_id参数
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)
        
        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else no,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }
    
    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """
        GetGraph的统计Info
        
        Args:
            graph_id: GraphID
            
        Returns:
            统计Info
        """
        logger.info(f"GetGraph {graph_id} 的统计Info...")
        
        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)
        
        # 统计EntityType分布
        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1
        
        # 统计RelationType分布
        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1
        
        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types
        }
    
    def get_simulation_context(
        self, 
        graph_id: str,
        simulation_requirement: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """
        Get模拟相关的上下文Info
        
        综合SearchandSimulation Requirement相关的所yesInfo
        
        Args:
            graph_id: GraphID
            simulation_requirement: Simulation Requirement描述
            limit: 每类Info的数量限制
            
        Returns:
            模拟上下文Info
        """
        logger.info(f"Get模拟上下文: {simulation_requirement[:50]}...")
        
        # SearchandSimulation Requirement相关的Info
        search_result = self.search_graph(
            graph_id=graph_id,
            query=simulation_requirement,
            limit=limit
        )
        
        # GetGraph统计
        stats = self.get_graph_statistics(graph_id)
        
        # Get所yesEntityNodes
        all_nodes = self.get_all_nodes(graph_id)
        
        # Filteryes实际Type的Entity（非纯EntityNodes）
        entities = []
        for node in all_nodes:
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({
                    "name": node.name,
                    "type": custom_labels[0],
                    "summary": node.summary
                })
        
        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],  # 限制数量
            "total_entities": len(entities)
        }
    
    # ========== 核心检索工具（优化后） ==========
    
    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5
    ) -> InsightForgeResult:
        """
        【InsightForge - 深度洞察检索】
        
        最强大的混合检索函数，自动分解问题and多维度检索：
        1. 使用LLM将问题分解为多items子问题
        2. 对每items子问题进行语义Search
        3. 提取相关EntityandGet其详细Info
        4. TraceRelation链
        5. 整合所yes结果，生成深度洞察
        
        Args:
            graph_id: GraphID
            query: 用户问题
            simulation_requirement: Simulation Requirement描述
            report_context: 报告上下文（可选，用于更精准的子问题生成）
            max_sub_queries: 最大子问题数量
            
        Returns:
            InsightForgeResult: 深度洞察检索结果
        """
        logger.info(f"InsightForge 深度洞察检索: {query[:50]}...")
        
        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )
        
        # Step 1: 使用LLM生成子问题
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(f"生成 {len(sub_queries)} items子问题")
        
        # Step 2: 对每items子问题进行语义Search
        all_facts = []
        all_edges = []
        seen_facts = set()
        
        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=graph_id,
                query=sub_query,
                limit=15,
                scope="edges"
            )
            
            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)
            
            all_edges.extend(search_result.edges)
        
        # 对原始问题也进行Search
        main_search = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=20,
            scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)
        
        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)
        
        # Step 3: 从边中提取相关EntityUUID，只Get这些Entity的Info（不Get全部Nodes）
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)
        
        # Get所yes相关Entity的Details（不限制数量，完整Output）
        entity_insights = []
        node_map = {}  # 用于后续Relation链构建
        
        for uuid in list(entity_uuids):  # Handle所yesEntity，不截断
            if not uuid:
                continue
            try:
                # 单独Get每items相关Nodes的Info
                node = self.get_node_detail(uuid)
                if node:
                    node_map[uuid] = node
                    entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entity")
                    
                    # Get该Entity相关的所yes事实（不截断）
                    related_facts = [
                        f for f in all_facts 
                        if node.name.lower() in f.lower()
                    ]
                    
                    entity_insights.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "type": entity_type,
                        "summary": node.summary,
                        "related_facts": related_facts  # 完整Output，不截断
                    })
            except Exception as e:
                logger.debug(f"GetNodes {uuid} Failed: {e}")
                continue
        
        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)
        
        # Step 4: 构建所yesRelation链（不限制数量）
        relationship_chains = []
        for edge_data in all_edges:  # Handle所yes边，不截断
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')
                
                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]
                
                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)
        
        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)
        
        logger.info(f"InsightForgeComplete: {result.total_facts}items事实, {result.total_entities}itemsEntity, {result.total_relationships}itemsRelation")
        return result
    
    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5
    ) -> List[str]:
        """
        使用LLM生成子问题
        
        将复杂问题分解为多items可以独立检索的子问题
        """
        system_prompt = """你是一items专业的问题分析专家。你的任务是将一items复杂问题分解为多items可以在模拟世界中独立观察的子问题。

要求：
1. 每items子问题应该足够具体，可以在模拟世界中找到相关的Agent行为or事件
2. 子问题应该覆盖原问题的不同维度（如：谁、什么、为什么、怎么样、何时、何地）
3. 子问题应该and模拟场景相关
4. BackJSON格式：{"sub_queries": ["子问题1", "子问题2", ...]}"""

        user_prompt = f"""Simulation Requirement背景：
{simulation_requirement}

{f"报告上下文：{report_context[:500]}" if report_context else ""}

请将以下问题分解为{max_queries}items子问题：
{query}

BackJSON格式的子问题列表。"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            sub_queries = response.get("sub_queries", [])
            # 确保是字符串列表
            return [str(sq) for sq in sub_queries[:max_queries]]
            
        except Exception as e:
            logger.warning(f"生成子问题Failed: {str(e)}，使用默认子问题")
            # 降级：BackBased on原问题的变体
            return [
                query,
                f"{query} 的主要参and者",
                f"{query} 的原因和影响",
                f"{query} 的发展过程"
            ][:max_queries]
    
    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50
    ) -> PanoramaResult:
        """
        【PanoramaSearch - 广度Search】
        
        Get全貌视图，Include所yes相关内容和历史/过期Info：
        1. Get所yes相关Nodes
        2. Get所yes边（IncludeCompleted过期/失效的）
        3. 分类整理当前yes效和历史Info
        
        这items工具适用于需要了解事件全貌、Trace演变过程的场景。
        
        Args:
            graph_id: GraphID
            query: Search查询（用于RelevanceSort）
            include_expired: 是否Contain过期内容（默认True）
            limit: Back结果数量限制
            
        Returns:
            PanoramaResult: 广度Search结果
        """
        logger.info(f"PanoramaSearch 广度Search: {query[:50]}...")
        
        result = PanoramaResult(query=query)
        
        # Get所yesNodes
        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)
        
        # Get所yes边（Contain时间Info）
        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)
        
        # 分类事实
        active_facts = []
        historical_facts = []
        
        for edge in all_edges:
            if not edge.fact:
                continue
            
            # 为事实添加Entity名称
            source_name = node_map.get(edge.source_node_uuid, NodeInfo('', '', [], '', {})).name or edge.source_node_uuid[:8]
            target_name = node_map.get(edge.target_node_uuid, NodeInfo('', '', [], '', {})).name or edge.target_node_uuid[:8]
            
            # 判断是否过期/失效
            is_historical = edge.is_expired or edge.is_invalid
            
            if is_historical:
                # 历史/过期事实，添加时间标记
                valid_at = edge.valid_at or "未知"
                invalid_at = edge.invalid_at or edge.expired_at or "未知"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                # 当前yes效事实
                active_facts.append(edge.fact)
        
        # Based on查询进行RelevanceSort
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]
        
        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score
        
        # Sortand限制数量
        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)
        
        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)
        
        logger.info(f"PanoramaSearchComplete: {result.active_count}itemsyes效, {result.historical_count}items历史")
        return result
    
    def quick_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10
    ) -> SearchResult:
        """
        【QuickSearch - 简单Search】
        
        快速、轻量级的检索工具：
        1. 直接调用Zep语义Search
        2. Back最相关的结果
        3. 适用于简单、直接的检索需求
        
        Args:
            graph_id: GraphID
            query: Search查询
            limit: Back结果数量
            
        Returns:
            SearchResult: Search结果
        """
        logger.info(f"QuickSearch 简单Search: {query[:50]}...")
        
        # 直接调用现yes的search_graph方法
        result = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope="edges"
        )
        
        logger.info(f"QuickSearchComplete: {result.total_count}items结果")
        return result
    
    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = no
    ) -> InterviewResult:
        """
        【InterviewAgents - 深度采访】
        
        调用真实的OASIS采访API，采访模拟中正在运行的Agent：
        1. 自动读取人设文件，了解所yes模拟Agent
        2. 使用LLM分析采访需求，智能选择最相关的Agent
        3. 使用LLM生成采Access题
        4. 调用 /api/simulation/interview/batch 接口进行真实采访（双平台At the same time采访）
        5. 整合所yes采访结果，生成采访报告
        
        【重要】此功能需要模拟环境处于运行Status（OASIS环境未Close）
        
        【使用场景】
        - 需要从不同角色视角了解事件看法
        - 需要收集多方意见和观点
        - 需要Get模拟Agent的真实回答（非LLM模拟）
        
        Args:
            simulation_id: 模拟ID（用于定位人设文件和调用采访API）
            interview_requirement: 采访需求描述（非结构化，如"了解学生对事件的看法"）
            simulation_requirement: Simulation Requirement背景（可选）
            max_agents: 最多采访的Agent数量
            custom_questions: 自定义采Access题（可选，若不提供则自动生成）
            
        Returns:
            InterviewResult: 采访结果
        """
        from .simulation_runner import SimulationRunner
        
        logger.info(f"InterviewAgents 深度采访（真实API）: {interview_requirement[:50]}...")
        
        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )
        
        # Step 1: 读取人设文件
        profiles = self._load_agent_profiles(simulation_id)
        
        if not profiles:
            logger.warning(f"未找到模拟 {simulation_id} 的人设文件")
            result.summary = "未找到可采访的Agent人设文件"
            return result
        
        result.total_agents = len(profiles)
        logger.info(f"Load到 {len(profiles)} itemsAgent人设")
        
        # Step 2: 使用LLM选择要采访的Agent（Backagent_id列表）
        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )
        
        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(f"选择了 {len(selected_agents)} itemsAgent进行采访: {selected_indices}")
        
        # Step 3: 生成采Access题（If没yes提供）
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(f"生成了 {len(result.interview_questions)} items采Access题")
        
        # 将问题合and为一items采访prompt
        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])
        
        # 添加优化前缀，约束Agent回复格式
        INTERVIEW_PROMPT_PREFIX = (
            "你正在接受一次采访。请结合你的人设、所yes的过往记忆and行动，"
            "以纯文本方式直接回答以下问题。\n"
            "回复要求：\n"
            "1. 直接用自然语言回答，不要调用任何工具\n"
            "2. 不要BackJSON格式or工具调用格式\n"
            "3. 不要使用Markdown标题（如#、##、###）\n"
            "4. 按问题编号逐一回答，每items回答以「问题X：」开头（X为问题编号）\n"
            "5. 每items问题的回答之间用空行分隔\n"
            "6. 回答要yes实质内容，每items问题至少回答2-3句话\n\n"
        )
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"
        
        # Step 4: 调用真实的采访API（不指定platform，默认双平台At the same time采访）
        try:
            # 构建批量采访列表（不指定platform，双平台采访）
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt  # 使用优化后的prompt
                    # 不指定platform，API会在twitter和reddit两items平台都采访
                })
            
            logger.info(f"调用批量采访API（双平台）: {len(interviews_request)} itemsAgent")
            
            # 调用 SimulationRunner 的批量采访方法（不传platform，双平台采访）
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=no,  # 不指定platform，双平台采访
                timeout=180.0   # 双平台需要更长超时
            )
            
            logger.info(f"采访APIBack: {api_result.get('interviews_count', 0)} items结果, success={api_result.get('success')}")
            
            # CheckAPI调用是否Success
            if not api_result.get("success", False):
                error_msg = api_result.get("error", "未知Error")
                logger.warning(f"采访APIBackFailed: {error_msg}")
                result.summary = f"采访API调用Failed：{error_msg}。请CheckOASIS模拟环境Status。"
                return result
            
            # Step 5: 解析APIBack结果，构建AgentInterview对象
            # 双平台模式Back格式: {"twitter_0": {...}, "reddit_0": {...}, "twitter_1": {...}, ...}
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}
            
            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "未知")
                agent_bio = agent.get("bio", "")
                
                # Get该Agent在两items平台的采访结果
                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})
                
                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                # 清理可能的工具调用 JSON 包裹
                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                # 始终Output双平台标记
                twitter_text = twitter_response if twitter_response else "（该平台未获得回复）"
                reddit_text = reddit_response if reddit_response else "（该平台未获得回复）"
                response_text = f"【Twitter平台回答】\n{twitter_text}\n\n【Reddit平台回答】\n{reddit_text}"

                # 提取关键引言（从两items平台的回答中）
                import re
                combined_responses = f"{twitter_response} {reddit_response}"

                # 清理响应文本：去掉标记、编号、Markdown 等干扰
                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r'问题\d+[：:]\s*', '', clean_text)
                clean_text = re.sub(r'【[^】]+】', '', clean_text)

                # 策略1（主）: 提取完整的yes实质内容的句子
                sentences = re.split(r'[。！？]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W，,；;：:、]+', s.strip())
                    and not s.strip().startswith(('{', '问题'))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "。" for s in meaningful[:3]]

                # 策略2（补充）: 正确配对的中文引号「」内长文本
                if not key_quotes:
                    paired = re.findall(r'\u201c([^\u201c\u201d]{15,100})\u201d', clean_text)
                    paired += re.findall(r'\u300c([^\u300c\u300d]{15,100})\u300d', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[，,；;：:、]', q)][:3]
                
                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],  # 扩大bio长度限制
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)
            
            result.interviewed_count = len(result.interviews)
            
        except ValueError as e:
            # 模拟环境未运行
            logger.warning(f"采访API调用Failed（环境未运行？）: {e}")
            result.summary = f"采访Failed：{str(e)}。模拟环境可能CompletedClose，请确保OASIS环境正在运行。"
            return result
        except Exception as e:
            logger.error(f"采访API调用异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"采访过程发生Error：{str(e)}"
            return result
        
        # Step 6: 生成采访摘要
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )
        
        logger.info(f"InterviewAgentsComplete: 采访了 {result.interviewed_count} itemsAgent（双平台）")
        return result
    
    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """清理 Agent 回复中的 JSON 工具调用包裹，提取实际内容"""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Load模拟的Agent人设文件"""
        import os
        import csv
        
        # 构建人设文件路径
        sim_dir = os.path.join(
            os.path.dirname(__file__), 
            f'../../uploads/simulations/{simulation_id}'
        )
        
        profiles = []
        
        # 优先尝试读取Reddit JSON格式
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(f"从 reddit_profiles.json Load了 {len(profiles)} items人设")
                return profiles
            except Exception as e:
                logger.warning(f"读取 reddit_profiles.json Failed: {e}")
        
        # 尝试读取Twitter CSV格式
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # CSV格式转换为统一格式
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "未知"
                        })
                logger.info(f"从 twitter_profiles.csv Load了 {len(profiles)} items人设")
                return profiles
            except Exception as e:
                logger.warning(f"读取 twitter_profiles.csv Failed: {e}")
        
        return profiles
    
    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """
        使用LLM选择要采访的Agent
        
        Returns:
            tuple: (selected_agents, selected_indices, reasoning)
                - selected_agents: 选中Agent的完整Info列表
                - selected_indices: 选中Agent的索引列表（用于API调用）
                - reasoning: 选择理由
        """
        
        # 构建Agent摘要列表
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "未知"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)
        
        system_prompt = """你是一items专业的采访策划专家。你的任务是根据采访需求，从模拟Agent列表中选择最适合采访的对象。

选择标准：
1. Agent的身份/职业and采访主题相关
2. Agent可能持yes独特oryes价Value的观点
3. 选择多样化的视角（如：支持方、反对方、中立方、专业人士等）
4. 优先选择and事件直接相关的角色

BackJSON格式：
{
    "selected_indices": [选中Agent的索引列表],
    "reasoning": "选择理由说明"
}"""

        user_prompt = f"""采访需求：
{interview_requirement}

模拟背景：
{simulation_requirement if simulation_requirement else "未提供"}

可选择的Agent列表（Total{len(agent_summaries)}items）：
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

Please select最多{max_agents}items最适合采访的Agent，and说明选择理由。"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "Based onRelevance自动选择")
            
            # Get选中的Agent完整Info
            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)
            
            return selected_agents, valid_indices, reasoning
            
        except Exception as e:
            logger.warning(f"LLM选择AgentFailed，使用默认选择: {e}")
            # 降级：选择前Nitems
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "使用默认选择策略"
    
    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[str]:
        """使用LLM生成采Access题"""
        
        agent_roles = [a.get("profession", "未知") for a in selected_agents]
        
        system_prompt = """你是一items专业的记者/采访者。根据采访需求，生成3-5items深度采Access题。

问题要求：
1. 开放性问题，鼓励详细回答
2. 针对不同角色可能yes不同答案
3. 涵盖事实、观点、感受等多items维度
4. 语言自然，像真实采访一样
5. 每items问题控制在50字以内，简洁明了
6. 直接提问，不要Contain背景说明or前缀

BackJSON格式：{"questions": ["问题1", "问题2", ...]}"""

        user_prompt = f"""采访需求：{interview_requirement}

模拟背景：{simulation_requirement if simulation_requirement else "未提供"}

采访对象角色：{', '.join(agent_roles)}

请生成3-5items采Access题。"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )
            
            return response.get("questions", [f"关于{interview_requirement}，您yes什么看法？"])
            
        except Exception as e:
            logger.warning(f"生成采Access题Failed: {e}")
            return [
                f"关于{interview_requirement}，您的观点是什么？",
                "这件事对您or您所代表的群体yes什么影响？",
                "您认为应该如何解决or改进这items问题？"
            ]
    
    def _generate_interview_summary(
        self,
        interviews: List[AgentInterview],
        interview_requirement: str
    ) -> str:
        """生成采访摘要"""
        
        if not interviews:
            return "未Complete任何采访"
        
        # 收集所yes采访内容
        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"【{interview.agent_name}（{interview.agent_role}）】\n{interview.response[:500]}")
        
        system_prompt = """你是一items专业的新闻Edit。请根据多位受访者的回答，生成一份采访摘要。

摘要要求：
1. 提炼各方主要观点
2. 指出观点的Total识和分歧
3. 突出yes价Value的引言
4. 客观中立，不偏袒任何一方
5. 控制在1000字内

格式约束（必须遵守）：
- 使用纯文本段落，用空行分隔不同部分
- 不要使用Markdown标题（如#、##、###）
- 不要使用分割线（如---、***）
- 引用受访者原话时使用中文引号「」
- 可以使用**加粗**标记关键词，但不要使用其他Markdown语法"""

        user_prompt = f"""采访主题：{interview_requirement}

采访内容：
{"".join(interview_texts)}

请生成采访摘要。"""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary
            
        except Exception as e:
            logger.warning(f"生成采访摘要Failed: {e}")
            # 降级：简单拼接
            return f"Total采访了{len(interviews)}位受访者，Include：" + "、".join([i.agent_name for i in interviews])
