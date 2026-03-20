"""
OASIS Agent Profile生成器
将ZepGraph中的Entity转换为OASIS模拟平台所需的Agent Profile格式

优化改进：
1. 调用Zep检索功能二次丰富NodesInfo
2. 优化Notice词生成非常详细的人设
3. 区分items人Entity和抽象群体Entity
"""

import json
import random
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI
from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from .zep_entity_reader import EntityNode, ZepEntityReader

logger = get_logger('mirofish.oasis_profile')


@dataclass
class OasisAgentProfile:
    """OASIS Agent Profile数据结构"""
    # 通用字段
    user_id: int
    user_name: str
    name: str
    bio: str
    persona: str
    
    # 可选字段 - Reddit风格
    karma: int = 1000
    
    # 可选字段 - Twitter风格
    friend_count: int = 100
    follower_count: int = 150
    statuses_count: int = 500
    
    # 额外人设Info
    age: Optional[int] = no
    gender: Optional[str] = no
    mbti: Optional[str] = no
    country: Optional[str] = no
    profession: Optional[str] = no
    interested_topics: List[str] = field(default_factory=list)
    
    # 来SourceEntityInfo
    source_entity_uuid: Optional[str] = no
    source_entity_type: Optional[str] = no
    
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    
    def to_reddit_format(self) -> Dict[str, Any]:
        """转换为Reddit平台格式"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 库要求字段名为 username（no下划线）
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "created_at": self.created_at,
        }
        
        # 添加额外人设Info（Ifyes）
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_twitter_format(self) -> Dict[str, Any]:
        """转换为Twitter平台格式"""
        profile = {
            "user_id": self.user_id,
            "username": self.user_name,  # OASIS 库要求字段名为 username（no下划线）
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "created_at": self.created_at,
        }
        
        # 添加额外人设Info
        if self.age:
            profile["age"] = self.age
        if self.gender:
            profile["gender"] = self.gender
        if self.mbti:
            profile["mbti"] = self.mbti
        if self.country:
            profile["country"] = self.country
        if self.profession:
            profile["profession"] = self.profession
        if self.interested_topics:
            profile["interested_topics"] = self.interested_topics
        
        return profile
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为完整字典格式"""
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "name": self.name,
            "bio": self.bio,
            "persona": self.persona,
            "karma": self.karma,
            "friend_count": self.friend_count,
            "follower_count": self.follower_count,
            "statuses_count": self.statuses_count,
            "age": self.age,
            "gender": self.gender,
            "mbti": self.mbti,
            "country": self.country,
            "profession": self.profession,
            "interested_topics": self.interested_topics,
            "source_entity_uuid": self.source_entity_uuid,
            "source_entity_type": self.source_entity_type,
            "created_at": self.created_at,
        }


class OasisProfileGenerator:
    """
    OASIS Profile生成器
    
    将ZepGraph中的Entity转换为OASIS模拟所需的Agent Profile
    
    优化特性：
    1. 调用ZepGraph检索功能Get更丰富的上下文
    2. 生成非常详细的人设（Include基本Info、职业经历、性格特征、社交媒体行为等）
    3. 区分items人Entity和抽象群体Entity
    """
    
    # MBTIType列表
    MBTI_TYPES = [
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP"
    ]
    
    # 常见国家列表
    COUNTRIES = [
        "China", "US", "UK", "Japan", "Germany", "France", 
        "Canada", "Australia", "Brazil", "India", "South Korea"
    ]
    
    # items人TypeEntity（需要生成具体人设）
    INDIVIDUAL_ENTITY_TYPES = [
        "student", "alumni", "professor", "person", "publicfigure", 
        "expert", "faculty", "official", "journalist", "activist"
    ]
    
    # 群体/机构TypeEntity（需要生成群体代表人设）
    GROUP_ENTITY_TYPES = [
        "university", "governmentagency", "organization", "ngo", 
        "mediaoutlet", "company", "institution", "group", "community"
    ]
    
    def __init__(
        self, 
        api_key: Optional[str] = no,
        base_url: Optional[str] = no,
        model_name: Optional[str] = no,
        zep_api_key: Optional[str] = no,
        graph_id: Optional[str] = no
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise ValueError("LLM_API_KEY 未配置")
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        
        # Zep客户端用于检索丰富上下文
        self.zep_api_key = zep_api_key or Config.ZEP_API_KEY
        self.zep_client = no
        self.graph_id = graph_id
        
        if self.zep_api_key:
            try:
                self.zep_client = Zep(api_key=self.zep_api_key)
            except Exception as e:
                logger.warning(f"Zep客户端InitializeFailed: {e}")
    
    def generate_profile_from_entity(
        self, 
        entity: EntityNode, 
        user_id: int,
        use_llm: bool = True
    ) -> OasisAgentProfile:
        """
        从ZepEntity生成OASIS Agent Profile
        
        Args:
            entity: ZepEntityNodes
            user_id: 用户ID（用于OASIS）
            use_llm: 是否使用LLM生成详细人设
            
        Returns:
            OasisAgentProfile
        """
        entity_type = entity.get_entity_type() or "Entity"
        
        # Basic information
        name = entity.name
        user_name = self._generate_username(name)
        
        # 构建上下文Info
        context = self._build_entity_context(entity)
        
        if use_llm:
            # 使用LLM生成详细人设
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context
            )
        else:
            # 使用规则生成基础人设
            profile_data = self._generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes
            )
        
        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get("persona", entity.summary or f"A {entity_type} named {name}."),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )
    
    def _generate_username(self, name: str) -> str:
        """生成用户名"""
        # 移除特殊字符，转换为小写
        username = name.lower().replace(" ", "_")
        username = ''.join(c for c in username if c.isalnum() or c == '_')
        
        # 添加随机后缀避免重复
        suffix = random.randint(100, 999)
        return f"{username}_{suffix}"
    
    def _search_zep_for_entity(self, entity: EntityNode) -> Dict[str, Any]:
        """
        使用ZepGraph混合Search功能GetEntity相关的丰富Info
        
        Zep没yes内置混合Search接口，需要分别Searchedges和nodes然后合and结果。
        使用and行请求At the same timeSearch，提高效率。
        
        Args:
            entity: EntityNodes对象
            
        Returns:
            Containfacts, node_summaries, context的字典
        """
        import concurrent.futures
        
        if not self.zep_client:
            return {"facts": [], "node_summaries": [], "context": ""}
        
        entity_name = entity.name
        
        results = {
            "facts": [],
            "node_summaries": [],
            "context": ""
        }
        
        # 必须yesgraph_id才能进行Search
        if not self.graph_id:
            logger.debug(f"跳过Zep检索：未设置graph_id")
            return results
        
        comprehensive_query = f"关于{entity_name}的所yesInfo、活动、事件、Relation和背景"
        
        def search_edges():
            """Search边（事实/Relation）- 带Retry机制"""
            max_retries = 3
            last_exception = no
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=30,
                        scope="edges",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"Zep边Search第 {attempt + 1} 次Failed: {str(e)[:80]}, Retry中...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"Zep边Search在 {max_retries} 次尝试后仍Failed: {e}")
            return no
        
        def search_nodes():
            """SearchNodes（Entity摘要）- 带Retry机制"""
            max_retries = 3
            last_exception = no
            delay = 2.0
            
            for attempt in range(max_retries):
                try:
                    return self.zep_client.graph.search(
                        query=comprehensive_query,
                        graph_id=self.graph_id,
                        limit=20,
                        scope="nodes",
                        reranker="rrf"
                    )
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(f"ZepNodesSearch第 {attempt + 1} 次Failed: {str(e)[:80]}, Retry中...")
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.debug(f"ZepNodesSearch在 {max_retries} 次尝试后仍Failed: {e}")
            return no
        
        try:
            # and行Executeedges和nodesSearch
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                edge_future = executor.submit(search_edges)
                node_future = executor.submit(search_nodes)
                
                # Get结果
                edge_result = edge_future.result(timeout=30)
                node_result = node_future.result(timeout=30)
            
            # Handle边Search结果
            all_facts = set()
            if edge_result and hasattr(edge_result, 'edges') and edge_result.edges:
                for edge in edge_result.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        all_facts.add(edge.fact)
            results["facts"] = list(all_facts)
            
            # HandleNodesSearch结果
            all_summaries = set()
            if node_result and hasattr(node_result, 'nodes') and node_result.nodes:
                for node in node_result.nodes:
                    if hasattr(node, 'summary') and node.summary:
                        all_summaries.add(node.summary)
                    if hasattr(node, 'name') and node.name and node.name != entity_name:
                        all_summaries.add(f"相关Entity: {node.name}")
            results["node_summaries"] = list(all_summaries)
            
            # 构建综合上下文
            context_parts = []
            if results["facts"]:
                context_parts.append("事实Info:\n" + "\n".join(f"- {f}" for f in results["facts"][:20]))
            if results["node_summaries"]:
                context_parts.append("相关Entity:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10]))
            results["context"] = "\n\n".join(context_parts)
            
            logger.info(f"Zep混合检索Complete: {entity_name}, Get {len(results['facts'])} items事实, {len(results['node_summaries'])} items相关Nodes")
            
        except concurrent.futures.TimeoutError:
            logger.warning(f"Zep检索超时 ({entity_name})")
        except Exception as e:
            logger.warning(f"Zep检索Failed ({entity_name}): {e}")
        
        return results
    
    def _build_entity_context(self, entity: EntityNode) -> str:
        """
        构建Entity的完整上下文Info
        
        Include：
        1. Entity本身的边Info（事实）
        2. 关联Nodes的详细Info
        3. Zep混合检索到的丰富Info
        """
        context_parts = []
        
        # 1. 添加EntityAttributesInfo
        if entity.attributes:
            attrs = []
            for key, value in entity.attributes.items():
                if value and str(value).strip():
                    attrs.append(f"- {key}: {value}")
            if attrs:
                context_parts.append("### EntityAttributes\n" + "\n".join(attrs))
        
        # 2. 添加相关边Info（事实/Relation）
        existing_facts = set()
        if entity.related_edges:
            relationships = []
            for edge in entity.related_edges:  # 不限制数量
                fact = edge.get("fact", "")
                edge_name = edge.get("edge_name", "")
                direction = edge.get("direction", "")
                
                if fact:
                    relationships.append(f"- {fact}")
                    existing_facts.add(fact)
                elif edge_name:
                    if direction == "outgoing":
                        relationships.append(f"- {entity.name} --[{edge_name}]--> (相关Entity)")
                    else:
                        relationships.append(f"- (相关Entity) --[{edge_name}]--> {entity.name}")
            
            if relationships:
                context_parts.append("### 相关事实和Relation\n" + "\n".join(relationships))
        
        # 3. 添加关联Nodes的详细Info
        if entity.related_nodes:
            related_info = []
            for node in entity.related_nodes:  # 不限制数量
                node_name = node.get("name", "")
                node_labels = node.get("labels", [])
                node_summary = node.get("summary", "")
                
                # 过滤掉默认标签
                custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
                label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""
                
                if node_summary:
                    related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
                else:
                    related_info.append(f"- **{node_name}**{label_str}")
            
            if related_info:
                context_parts.append("### 关联EntityInfo\n" + "\n".join(related_info))
        
        # 4. 使用Zep混合检索Get更丰富的Info
        zep_results = self._search_zep_for_entity(entity)
        
        if zep_results.get("facts"):
            # 去重：排除Completed存在的事实
            new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
            if new_facts:
                context_parts.append("### Zep检索到的事实Info\n" + "\n".join(f"- {f}" for f in new_facts[:15]))
        
        if zep_results.get("node_summaries"):
            context_parts.append("### Zep检索到的相关Nodes\n" + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10]))
        
        return "\n\n".join(context_parts)
    
    def _is_individual_entity(self, entity_type: str) -> bool:
        """判断是否是items人TypeEntity"""
        return entity_type.lower() in self.INDIVIDUAL_ENTITY_TYPES
    
    def _is_group_entity(self, entity_type: str) -> bool:
        """判断是否是群体/机构TypeEntity"""
        return entity_type.lower() in self.GROUP_ENTITY_TYPES
    
    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> Dict[str, Any]:
        """
        使用LLM生成非常详细的人设
        
        根据EntityType区分：
        - items人Entity：生成具体的人物设定
        - 群体/机构Entity：生成代表性账号设定
        """
        
        is_individual = self._is_individual_entity(entity_type)
        
        if is_individual:
            prompt = self._build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = self._build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        # 尝试多次生成，直到Successor达到最大Retry次数
        max_attempts = 3
        last_error = no
        
        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": self._get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1)  # 每次Retry降低温度
                    # 不设置max_tokens，让LLM自由发挥
                )
                
                content = response.choices[0].message.content
                
                # Check是否被截断（finish_reason不是'stop'）
                finish_reason = response.choices[0].finish_reason
                if finish_reason == 'length':
                    logger.warning(f"LLMOutput被截断 (attempt {attempt+1}), 尝试修复...")
                    content = self._fix_truncated_json(content)
                
                # 尝试解析JSON
                try:
                    result = json.loads(content)
                    
                    # Verify必需字段
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}"
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name}是一items{entity_type}。"
                    
                    return result
                    
                except json.JSONDecodeError as je:
                    logger.warning(f"JSON解析Failed (attempt {attempt+1}): {str(je)[:80]}")
                    
                    # 尝试修复JSON
                    result = self._try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result
                    
                    last_error = je
                    
            except Exception as e:
                logger.warning(f"LLM调用Failed (attempt {attempt+1}): {str(e)[:80]}")
                last_error = e
                import time
                time.sleep(1 * (attempt + 1))  # 指数退避
        
        logger.warning(f"LLM生成人设Failed（{max_attempts}次尝试）: {last_error}, 使用规则生成")
        return self._generate_profile_rule_based(
            entity_name, entity_type, entity_summary, entity_attributes
        )
    
    def _fix_truncated_json(self, content: str) -> str:
        """修复被截断的JSON（Output被max_tokens限制截断）"""
        import re
        
        # IfJSON被截断，尝试闭合它
        content = content.strip()
        
        # 计算未闭合的括号
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        
        # Check是否yes未闭合的字符串
        # 简单Check：If最后一items引号后没yes逗号or闭合括号，可能是字符串被截断
        if content and content[-1] not in '",}]':
            # 尝试闭合字符串
            content += '"'
        
        # 闭合括号
        content += ']' * open_brackets
        content += '}' * open_braces
        
        return content
    
    def _try_fix_json(self, content: str, entity_name: str, entity_type: str, entity_summary: str = "") -> Dict[str, Any]:
        """尝试修复损坏的JSON"""
        import re
        
        # 1. 首先尝试修复被截断的情况
        content = self._fix_truncated_json(content)
        
        # 2. 尝试提取JSON部分
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group()
            
            # 3. Handle字符串中的换行符问题
            # 找到所yes字符串Valueand替换Among them的换行符
            def fix_string_newlines(match):
                s = match.group(0)
                # 替换字符串内的实际换行符为空格
                s = s.replace('\n', ' ').replace('\r', ' ')
                # 替换多余空格
                s = re.sub(r'\s+', ' ', s)
                return s
            
            # 匹配JSON字符串Value
            json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)
            
            # 4. 尝试解析
            try:
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except json.JSONDecodeError as e:
                # 5. If还是Failed，尝试更激进的修复
                try:
                    # 移除所yes控制字符
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                    # 替换所yes连续空白
                    json_str = re.sub(r'\s+', ' ', json_str)
                    result = json.loads(json_str)
                    result["_fixed"] = True
                    return result
                except:
                    pass
        
        # 6. 尝试从内容中提取部分Info
        bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
        persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # 可能被截断
        
        bio = bio_match.group(1) if bio_match else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
        persona = persona_match.group(1) if persona_match else (entity_summary or f"{entity_name}是一items{entity_type}。")
        
        # If提取到了yes意义的内容，标记为Completed修复
        if bio_match or persona_match:
            logger.info(f"从损坏的JSON中提取了部分Info")
            return {
                "bio": bio,
                "persona": persona,
                "_fixed": True
            }
        
        # 7. 完全Failed，Back基础结构
        logger.warning(f"JSON修复Failed，Back基础结构")
        return {
            "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": entity_summary or f"{entity_name}是一items{entity_type}。"
        }
    
    def _get_system_prompt(self, is_individual: bool) -> str:
        """Get系统Notice词"""
        base_prompt = "你是社交媒体用户画像生成专家。生成详细、真实的人设用于舆论模拟,最大程度还原Completedyes现实情况。必须Backyes效的JSON格式，所yes字符串Value不能Contain未转义的换行符。使用中文。"
        return base_prompt
    
    def _build_individual_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """构建items人Entity的详细人设Notice词"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "no"
        context_str = context[:3000] if context else "no额外上下文"
        
        return f"""为Entity生成详细的社交媒体用户人设,最大程度还原Completedyes现实情况。

Entity名称: {entity_name}
EntityType: {entity_type}
Entity摘要: {entity_summary}
EntityAttributes: {attrs_str}

上下文Info:
{context_str}

请生成JSON，Contain以下字段:

1. bio: 社交媒体简介，200字
2. persona: 详细人设描述（2000字的纯文本），需Contain:
   - 基本Info（年龄、职业、教育背景、所在地）
   - 人物背景（重要经历、and事件的关联、社会Relation）
   - 性格特征（MBTIType、核心性格、情绪表达方式）
   - 社交媒体行为（发帖频率、内容偏好、互动风格、语言特点）
   - 立场观点（对话题的态度、可能被激怒/感动的内容）
   - 独特特征（口头禅、特殊经历、items人爱好）
   - items人记忆（人设的重要部分，要介绍这itemsitems体and事件的关联，以及这itemsitems体在事件中的Completedyes动作and反应）
3. age: 年龄数字（必须是整数）
4. gender: 性别，必须是英文: "male" or "female"
5. mbti: MBTIType（如INTJ、ENFP等）
6. country: 国家（使用中文，如"中国"）
7. profession: 职业
8. interested_topics: 感兴趣话题数组

重要:
- 所yes字段Value必须是字符串or数字，不要使用换行符
- persona必须是一段连贯的文字描述
- 使用中文（Exceptgender字段必须用英文male/female）
- 内容要andEntityInfo保持一致
- age必须是yes效的整数，gender必须是"male"or"female"
"""

    def _build_group_persona_prompt(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str
    ) -> str:
        """构建群体/机构Entity的详细人设Notice词"""
        
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "no"
        context_str = context[:3000] if context else "no额外上下文"
        
        return f"""为机构/群体Entity生成详细的社交媒体账号设定,最大程度还原Completedyes现实情况。

Entity名称: {entity_name}
EntityType: {entity_type}
Entity摘要: {entity_summary}
EntityAttributes: {attrs_str}

上下文Info:
{context_str}

请生成JSON，Contain以下字段:

1. bio: 官方账号简介，200字，专业得体
2. persona: 详细账号设定描述（2000字的纯文本），需Contain:
   - 机构基本Info（正式名称、机构性质、成立背景、主要职能）
   - 账号定位（账号Type、Target受众、核心功能）
   - 发言风格（语言特点、常用表达、禁忌话题）
   - 发布内容特点（内容Type、发布频率、活跃时间段）
   - 立场态度（对核心话题的官方立场、面对争议的Handle方式）
   - 特殊说明（代表的群体画像、运营习惯）
   - 机构记忆（机构人设的重要部分，要介绍这items机构and事件的关联，以及这items机构在事件中的Completedyes动作and反应）
3. age: 固定填30（机构账号的虚拟年龄）
4. gender: 固定填"other"（机构账号使用other表示非items人）
5. mbti: MBTIType，用于描述账号风格，如ISTJ代表严谨保守
6. country: 国家（使用中文，如"中国"）
7. profession: 机构职能描述
8. interested_topics: 关注领域数组

重要:
- 所yes字段Value必须是字符串or数字，不允许nullValue
- persona必须是一段连贯的文字描述，不要使用换行符
- 使用中文（Exceptgender字段必须用英文"other"）
- age必须是整数30，gender必须是字符串"other"
- 机构账号发言要符合其身份定位"""
    
    def _generate_profile_rule_based(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """使用规则生成基础人设"""
        
        # 根据EntityType生成不同的人设
        entity_type_lower = entity_type.lower()
        
        if entity_type_lower in ["student", "alumni"]:
            return {
                "bio": f"{entity_type} with interests in academics and social issues.",
                "persona": f"{entity_name} is a {entity_type.lower()} who is actively engaged in academic and social discussions. They enjoy sharing perspectives and connecting with peers.",
                "age": random.randint(18, 30),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": "Student",
                "interested_topics": ["Education", "Social Issues", "Technology"],
            }
        
        elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
            return {
                "bio": f"Expert and thought leader in their field.",
                "persona": f"{entity_name} is a recognized {entity_type.lower()} who shares insights and opinions on important matters. They are known for their expertise and influence in public discourse.",
                "age": random.randint(35, 60),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_attributes.get("occupation", "Expert"),
                "interested_topics": ["Politics", "Economics", "Culture & Society"],
            }
        
        elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
            return {
                "bio": f"Official account for {entity_name}. News and updates.",
                "persona": f"{entity_name} is a media entity that reports news and facilitates public discourse. The account shares timely updates and engages with the audience on current events.",
                "age": 30,  # 机构虚拟年龄
                "gender": "other",  # 机构使用other
                "mbti": "ISTJ",  # 机构风格：严谨保守
                "country": "中国",
                "profession": "Media",
                "interested_topics": ["General News", "Current Events", "Public Affairs"],
            }
        
        elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
            return {
                "bio": f"Official account of {entity_name}.",
                "persona": f"{entity_name} is an institutional entity that communicates official positions, announcements, and engages with stakeholders on relevant matters.",
                "age": 30,  # 机构虚拟年龄
                "gender": "other",  # 机构使用other
                "mbti": "ISTJ",  # 机构风格：严谨保守
                "country": "中国",
                "profession": entity_type,
                "interested_topics": ["Public Policy", "Community", "Official Announcements"],
            }
        
        else:
            # 默认人设
            return {
                "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
                "persona": entity_summary or f"{entity_name} is a {entity_type.lower()} participating in social discussions.",
                "age": random.randint(25, 50),
                "gender": random.choice(["male", "female"]),
                "mbti": random.choice(self.MBTI_TYPES),
                "country": random.choice(self.COUNTRIES),
                "profession": entity_type,
                "interested_topics": ["General", "Social Issues"],
            }
    
    def set_graph_id(self, graph_id: str):
        """设置GraphID用于Zep检索"""
        self.graph_id = graph_id
    
    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[callable] = no,
        graph_id: Optional[str] = no,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = no,
        output_platform: str = "reddit"
    ) -> List[OasisAgentProfile]:
        """
        批量从Entity生成Agent Profile（支持and行生成）
        
        Args:
            entities: Entity列表
            use_llm: 是否使用LLM生成详细人设
            progress_callback: 进度回调函数 (current, total, message)
            graph_id: GraphID，用于Zep检索Get更丰富上下文
            parallel_count: and行生成数量，默认5
            realtime_output_path: 实时写入的文件路径（If提供，每生成一items就写入一次）
            output_platform: Output平台格式 ("reddit" or "twitter")
            
        Returns:
            Agent Profile列表
        """
        import concurrent.futures
        from threading import Lock
        
        # 设置graph_id用于Zep检索
        if graph_id:
            self.graph_id = graph_id
        
        total = len(entities)
        profiles = [no] * total  # 预分配列表保持顺序
        completed_count = [0]  # 使用列表以便在闭包中修改
        lock = Lock()
        
        # 实时写入文件的辅助函数
        def save_profiles_realtime():
            """实时SaveCompleted生成的 profiles 到文件"""
            if not realtime_output_path:
                return
            
            with lock:
                # 过滤出Completed生成的 profiles
                existing_profiles = [p for p in profiles if p is not no]
                if not existing_profiles:
                    return
                
                try:
                    if output_platform == "reddit":
                        # Reddit JSON 格式
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        # Twitter CSV 格式
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"实时Save profiles Failed: {e}")
        
        def generate_single_profile(idx: int, entity: EntityNode) -> tuple:
            """生成单itemsprofile的工作函数"""
            entity_type = entity.get_entity_type() or "Entity"
            
            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm
                )
                
                # 实时Output生成的人设到控制台和日志
                self._print_generated_profile(entity.name, entity_type, profile)
                
                return idx, profile, no
                
            except Exception as e:
                logger.error(f"生成Entity {entity.name} 的人设Failed: {str(e)}")
                # Create一items基础profile
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=self._generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or f"A participant in social discussions.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)
        
        logger.info(f"开始and行生成 {total} itemsAgent人设（and行数: {parallel_count}）...")
        print(f"\n{'='*60}")
        print(f"开始生成Agent人设 - Total {total} itemsEntity，and行数: {parallel_count}")
        print(f"{'='*60}\n")
        
        # 使用线程池and行Execute
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            # 提交所yes任务
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"
                
                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile
                    
                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]
                    
                    # 实时写入文件
                    save_profiles_realtime()
                    
                    if progress_callback:
                        progress_callback(
                            current, 
                            total, 
                            f"Completed {current}/{total}: {entity.name}（{entity_type}）"
                        )
                    
                    if error:
                        logger.warning(f"[{current}/{total}] {entity.name} 使用备用人设: {error}")
                    else:
                        logger.info(f"[{current}/{total}] Success生成人设: {entity.name} ({entity_type})")
                        
                except Exception as e:
                    logger.error(f"HandleEntity {entity.name} 时发生异常: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=self._generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "A participant in social discussions.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    # 实时写入文件（That is使是备用人设）
                    save_profiles_realtime()
        
        print(f"\n{'='*60}")
        print(f"人设生成Complete！Total生成 {len([p for p in profiles if p])} itemsAgent")
        print(f"{'='*60}\n")
        
        return profiles
    
    def _print_generated_profile(self, entity_name: str, entity_type: str, profile: OasisAgentProfile):
        """实时Output生成的人设到控制台（Full Content，不截断）"""
        separator = "-" * 70
        
        # 构建完整Output内容（不截断）
        topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else 'no'
        
        output_lines = [
            f"\n{separator}",
            f"[Completed生成] {entity_name} ({entity_type})",
            f"{separator}",
            f"用户名: {profile.user_name}",
            f"",
            f"【简介】",
            f"{profile.bio}",
            f"",
            f"【详细人设】",
            f"{profile.persona}",
            f"",
            f"【基本Attributes】",
            f"年龄: {profile.age} | 性别: {profile.gender} | MBTI: {profile.mbti}",
            f"职业: {profile.profession} | 国家: {profile.country}",
            f"兴趣话题: {topics_str}",
            separator
        ]
        
        output = "\n".join(output_lines)
        
        # 只Output到控制台（避免重复，logger不再OutputFull Content）
        print(output)
    
    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """
        SaveProfile到文件（根据平台选择正确格式）
        
        OASIS平台格式要求：
        - Twitter: CSV格式
        - Reddit: JSON格式
        
        Args:
            profiles: Profile列表
            file_path: 文件路径
            platform: 平台Type ("reddit" or "twitter")
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)
    
    def _save_twitter_csv(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        SaveTwitter Profile为CSV格式（符合OASIS官方要求）
        
        OASIS Twitter要求的CSV字段：
        - user_id: 用户ID（根据CSV顺序从0开始）
        - name: 用户真实姓名
        - username: 系统中的用户名
        - user_char: 详细人设描述（注入到LLM系统Notice中，指导Agent行为）
        - description: 简短的公开简介（显示在用户资料page面）
        
        user_char vs description 区别：
        - user_char: 内部使用，LLM系统Notice，决定Agent如何思考和行动
        - description: 外部显示，其他用户可见的简介
        """
        import csv
        
        # 确保文件扩展名是.csv
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')
        
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 写入OASIS要求的表头
            headers = ['user_id', 'name', 'username', 'user_char', 'description']
            writer.writerow(headers)
            
            # 写入数据行
            for idx, profile in enumerate(profiles):
                # user_char: 完整人设（bio + persona），用于LLM系统Notice
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                # Handle换行符（CSV中用空格替代）
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')
                
                # description: 简短简介，用于外部显示
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')
                
                row = [
                    idx,                    # user_id: 从0开始的顺序ID
                    profile.name,           # name: 真实姓名
                    profile.user_name,      # username: 用户名
                    user_char,              # user_char: 完整人设（内部LLM使用）
                    description             # description: 简短简介（外部显示）
                ]
                writer.writerow(row)
        
        logger.info(f"CompletedSave {len(profiles)} itemsTwitter Profile到 {file_path} (OASIS CSV格式)")
    
    def _normalize_gender(self, gender: Optional[str]) -> str:
        """
        标准化gender字段为OASIS要求的英文格式
        
        OASIS要求: male, female, other
        """
        if not gender:
            return "other"
        
        gender_lower = gender.lower().strip()
        
        # 中文映射
        gender_map = {
            "男": "male",
            "女": "female",
            "机构": "other",
            "其他": "other",
            # 英文Completedyes
            "male": "male",
            "female": "female",
            "other": "other",
        }
        
        return gender_map.get(gender_lower, "other")
    
    def _save_reddit_json(self, profiles: List[OasisAgentProfile], file_path: str):
        """
        SaveReddit Profile为JSON格式
        
        使用and to_reddit_format() 一致的格式，确保 OASIS 能正确读取。
        必须Contain user_id 字段，这是 OASIS agent_graph.get_agent() 匹配的关键！
        
        必需字段：
        - user_id: 用户ID（整数，用于匹配 initial_posts 中的 poster_agent_id）
        - username: 用户名
        - name: 显示名称
        - bio: 简介
        - persona: 详细人设
        - age: 年龄（整数）
        - gender: "male", "female", or "other"
        - mbti: MBTIType
        - country: 国家
        """
        data = []
        for idx, profile in enumerate(profiles):
            # 使用and to_reddit_format() 一致的格式
            item = {
                "user_id": profile.user_id if profile.user_id is not no else idx,  # 关键：必须Contain user_id
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name} is a participant in social discussions.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASIS必需字段 - 确保都yes默认Value
                "age": profile.age if profile.age else 30,
                "gender": self._normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "中国",
            }
            
            # 可选字段
            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics
            
            data.append(item)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"CompletedSave {len(profiles)} itemsReddit Profile到 {file_path} (JSON格式，Containuser_id字段)")
    
    # 保留旧方法名作为别名，保持向后兼容
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit"
    ):
        """[Completed废弃] 请使用 save_profiles() 方法"""
        logger.warning("save_profiles_to_jsonCompleted废弃，请使用save_profiles方法")
        self.save_profiles(profiles, file_path, platform)

