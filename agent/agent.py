"""
Harborstone Insurance - MCP Agent

This agent:

1. Starts the Harborstone MCP server over stdio.
2. Performs the MCP initialize handshake.
3. Checks server capabilities.
4. Discovers tools, resources, and prompts.
5. Logs in through the MCP server.
6. Detects tools/list_changed notifications.
7. Uses Groq (OpenAI-compatible chat completions) to decide which MCP tool to call.
8. Handles MCP elicitation requests for human confirmation.
9. Handles MCP sampling requests from assess_risk().
10. Provides an interactive terminal chat.
11. Uses RAG (Retrieval-Augmented Generation) for knowledge/document questions.
12. Uses Short-Term, Episodic, Semantic and Consolidation Memory.
"""
from memory.self_rag import MemorySelfRAGVerifier
import asyncio
import json
import os
import sys
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ============================================================
# RAG
# ============================================================

from RAG import get_retriever, SelfRAGVerifier
from RAG.config import DEFAULT_RETRIEVER


# ============================================================
# MEMORY
# ============================================================

from memory.short_term import ShortTermMemory
from memory.episodic_memory import EpisodicMemory
from memory.semantic_memory import SemanticMemory
from memory.consolidation import ConsolidationEngine

from memory.schema import (
    MessageType,
    RoleEnum,
)


# ============================================================
# PATHS
# ============================================================
def _safe_content_to_str(content: Any) -> str:
    """
    Convert message content to string safely.
    Handles lists, dicts, and other types.
    """
    if content is None:
        return ""
    if isinstance(content, list):
        return json.dumps(content, default=str)
    if isinstance(content, dict):
        return json.dumps(content, default=str)
    return str(content)

BASE_DIR = Path(__file__).resolve().parent.parent

MANUAL_PATH = (
    BASE_DIR
    / "data"
    / "harborstone_manual.txt"
)

SERVER_PATH = (
    BASE_DIR
    / "mcp_server"
    / "server.py"
)


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SERVER_FILE = (
    PROJECT_ROOT
    / "mcp_server"
    / "server.py"
)

load_dotenv(
    PROJECT_ROOT / ".env"
)


GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile"
)


if not GROQ_API_KEY:

    raise RuntimeError(
        "GROQ_API_KEY is missing.\n"
        "Put it in the .env file:\n\n"
        "GROQ_API_KEY=your_key_here"
    )


# ============================================================
# GROQ CLIENT
# ============================================================

groq_client = Groq(
    api_key=GROQ_API_KEY
)


# ============================================================
# AGENT
# ============================================================

class HarborstoneAgent:
    """
    MCP client/agent for the Harborstone Insurance server.

    Memory architecture:

        User
          ↓
        Short-Term Memory
          ↓
        Agent / MCP / RAG
          ↓
        Short-Term Memory
          ↓
        Consolidation
          ↓
        Episodic / Semantic Memory
    """

    def _extract_fact_key(self, text: str) -> str | None:
        """
        Detect simple user facts that should be stored in
        Semantic Memory.
        """
        text = text.strip()

        patterns = {
            "favorite_vessel": [
                r"my favorite vessel is (.+)",
                r"my favourite vessel is (.+)",
            ],
            "favorite_club": [
                r"my favorite club is (.+)",
                r"my favourite club is (.+)",
            ],
            "favorite_team": [
                r"my favorite team is (.+)",
                r"my favourite team is (.+)",
            ],
            "favorite_player": [
                r"my favorite player is (.+)",
                r"my favourite player is (.+)",
            ],
            "favorite_color": [
                r"my favorite color is (.+)",
                r"my favourite color is (.+)",
            ],
        }

        for fact_key, regexes in patterns.items():
            for pattern in regexes:
                match = re.match(
                    pattern,
                    text,
                    re.IGNORECASE
                )
                if match:
                    value = match.group(1).strip()
                    if value:
                        return fact_key

        return None

    def __init__(self):

        # ====================================================
        # MCP STATE
        # ====================================================

        self.session: ClientSession | None = None

        self.server_capabilities = None

        self.tools: dict[str, Any] = {}
        self.resources: dict[str, Any] = {}
        self.prompts: dict[str, Any] = {}

        self.logged_in = False
        self.username: str | None = None
        self.role: str | None = None


        # ====================================================
        # MEMORY SYSTEM & PERSISTENCE
        # ====================================================

        # Path for persistence
        data_dir = BASE_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        self.short_term_memory = ShortTermMemory(
            conversation_id="harborstone_agent"
        )

        self.episodic_memory = EpisodicMemory(
            persistence_file=data_dir / "episodic_memory.json"
        )

        self.semantic_memory = SemanticMemory(
            persistence_file=data_dir / "semantic_memory.json"
        )

        self.memory_verifier = MemorySelfRAGVerifier()

        self.consolidation_engine = ConsolidationEngine(
            short_term=self.short_term_memory,
            episodic=self.episodic_memory,
            semantic=self.semantic_memory,
        )


        print("\n")
        print("=" * 70)
        print("MEMORY INITIALIZED WITH PERSISTENCE & SELF-RAG")
        print("=" * 70)
        print("Short-Term Memory: READY")
        print("Episodic Memory:   READY (Persistence Enabled)")
        print("Semantic Memory:   READY (Persistence Enabled)")
        print("Memory Verifier:   READY (Self-RAG Enabled)")
        print("Consolidation:     READY")
        print("=" * 70)


        # ====================================================
        # RAG
        # ====================================================

        try:

            self.rag = get_retriever(
                DEFAULT_RETRIEVER
            )

            self.verifier = SelfRAGVerifier()

            chunk_count = len(
                self.rag.vector_store.collection.get()["ids"]
            )

            print(
                f"RAG initialized with "
                f"'{DEFAULT_RETRIEVER}' retriever"
            )

            print(
                f"Vector store contains "
                f"{chunk_count} chunks"
            )

        except Exception as e:

            print(
                f"RAG initialization failed: {e}"
            )

            print(
                "The agent will fall back "
                "to tool-based mode only."
            )

            self.rag = None
            self.verifier = None

        print("=" * 70 + "\n")


    # ========================================================
    # MEMORY: STORE MESSAGE
    # ========================================================

    def _store_memory_message(
        self,
        role: RoleEnum,
        content: Any,
        msg_type: MessageType = MessageType.CHAT,
    ):
        """
        Store a message in Short-Term Memory.

        If the user explicitly states a personal fact,
        attach a fact_key so the consolidation engine can
        promote it to Semantic Memory.
        """

        try:

            metadata = {}

            # ------------------------------------------------
            # Detect semantic fact
            # ------------------------------------------------

            if role == RoleEnum.USER and isinstance(content, str):

                fact_key = self._extract_fact_key(content)

                if fact_key:

                    metadata["fact_key"] = fact_key

                    print(
                        f"[MEMORY] Detected semantic fact: "
                        f"{fact_key}"
                    )

            # ------------------------------------------------
            # Store message
            # ------------------------------------------------

            message = self.short_term_memory.add_message(

                role=role,

                content=content,

                msg_type=msg_type,

                metadata=metadata,
            )

            print(
                f"[MEMORY] Stored "
                f"{role.value} message "
                f"(seq={message.sequence if message else 'N/A'})"
            )

            # ------------------------------------------------
            # Consolidation
            # ------------------------------------------------

            self._maybe_consolidate()

            return message

        except Exception as exc:

            print(
                f"[MEMORY] Failed to store message: {exc}"
            )

            return None

    def _is_memory_query(self, text: str) -> bool:
        """
        Check if the user prompt is asking about stored memory or facts.
        """
        text_lower = text.lower()
        memory_keywords = [
            "my favorite", "my favourite", "what is my", "who is my",
            "do you know my", "remember", "what did i say", "my club",
            "my name", "my age", "my person", "my job"
        ]
        return any(keyword in text_lower for keyword in memory_keywords)
    # ========================================================
    # MEMORY: CONSOLIDATION
    # ========================================================

    def _maybe_consolidate(self):

        """
        Consolidate only when Short-Term Memory is getting full.

        This prevents us from immediately moving every message
        out of Short-Term Memory.
        """

        try:

            current = (
                self.short_term_memory.current_token_usage
            )

            limit = (
                self.short_term_memory.max_token_limit
            )

            if limit <= 0:
                return

            usage_ratio = current / limit

            if usage_ratio >= 0.80:

                print("\n")
                print("=" * 70)
                print("MEMORY CONSOLIDATION")
                print("=" * 70)

                print(
                    f"STM usage: "
                    f"{current}/{limit} "
                    f"({usage_ratio:.0%})"
                )

                self.consolidation_engine.consolidate()

                print(
                    f"STM after consolidation: "
                    f"{self.short_term_memory.current_token_usage}"
                )

                print(
                    f"Episodic memories: "
                    f"{len(self.episodic_memory)}"
                )

                print(
                    f"Semantic memories: "
                    f"{len(self.semantic_memory)}"
                )

                print("=" * 70)

        except Exception as exc:

            print(
                f"[MEMORY] Consolidation failed: {exc}"
            )


        # ========================================================
    # MEMORY: BUILD CONTEXT
    # ========================================================

    def _get_memory_context(self) -> str:
        """
        Build a compact context from the available memory layers.
        """
        sections = []

        # ----------------------------------------------------
        # SHORT-TERM MEMORY
        # ----------------------------------------------------
        short_term_messages = self.short_term_memory.get_messages()
        if short_term_messages:
            lines = []
            for message in short_term_messages[-10:]:
                role = message.role.value if hasattr(message.role, "value") else str(message.role)
                content_str = _safe_content_to_str(message.content)
                lines.append(f"{role}: {content_str}")
            sections.append("SHORT-TERM MEMORY:\n" + "\n".join(lines))

        # ----------------------------------------------------
        # SEMANTIC MEMORY
        # ----------------------------------------------------
        semantic_messages = self.semantic_memory.get_all()
        if semantic_messages:
            lines = []
            for message in semantic_messages[-10:]:
                fact_key = message.metadata.get("fact_key", "unknown")
                content_str = _safe_content_to_str(message.content)
                lines.append(f"{fact_key}: {content_str}")
            sections.append("SEMANTIC MEMORY:\n" + "\n".join(lines))

        # ----------------------------------------------------
        # EPISODIC MEMORY
        # ----------------------------------------------------
        episodic_messages = self.episodic_memory.get_all()
        if episodic_messages:
            lines = []
            for message in episodic_messages[-10:]:
                role = message.role.value if hasattr(message.role, "value") else str(message.role)
                content_str = _safe_content_to_str(message.content)
                lines.append(f"{role}: {content_str}")
            sections.append("EPISODIC MEMORY:\n" + "\n".join(lines))

        # ----------------------------------------------------
        # SCRATCHPAD
        # ----------------------------------------------------
        scratchpad = self.short_term_memory.get_scratchpad()
        if scratchpad:
            sections.append("SCRATCHPAD:\n" + json.dumps(scratchpad, indent=2, default=str))

        if not sections:
            return "No previous memory available."

        return "\n\n".join(sections)

    # ========================================================
    # MEMORY: DETECTION
    # ========================================================

    def _is_memory_question(
        self,
        query: str
    ) -> bool:

        """
        Detect questions that should primarily be answered
        from user memory rather than RAG or MCP tools.

        Examples:

            What is my favorite vessel?
            What is my favorite ship?
            What did I tell you about my vessel?
            Do you remember my favorite vessel?
        """

        query_lower = query.lower().strip()

        memory_keywords = [

            "my favorite",
            "my favourite",

            "what is my",
            "what's my",
            "what was my",

            "do you remember",
            "did i tell you",

            "what did i tell you",
            "remember my",

            "my preference",
            "my preferences",

            "i told you",
            "i said",

            "what did i say",
        ]

        return any(
            keyword in query_lower
            for keyword in memory_keywords
        )


    # ========================================================
    # MEMORY: CHECK RELEVANT FACT
    # ========================================================

    def _memory_contains_relevant_fact(
        self,
        query: str
    ) -> bool:

        """
        Check whether the current memory context contains
        information relevant to the user's question.

        This does NOT change _get_memory_context().
        """

        memory_context = (
            self._get_memory_context()
        )

        if not memory_context:

            return False


        query_lower = query.lower()


        # Extract meaningful words.
        words = re.findall(
            r"\b[a-zA-Z]{3,}\b",
            query_lower
        )


        ignored_words = {
            "what",
            "what's",
            "what_is",
            "was",
            "were",
            "are",
            "is",
            "the",
            "my",
            "your",
            "favorite",
            "favourite",
            "did",
            "tell",
            "remember",
            "about",
            "does",
            "do",
            "you",
            "know",
            "said",
        }


        meaningful_words = [

            word

            for word in words

            if word not in ignored_words
        ]


        memory_lower = (
            memory_context.lower()
        )


        # Direct overlap.
        if meaningful_words:

            matches = sum(

                1

                for word in meaningful_words

                if word in memory_lower
            )

            if matches > 0:

                return True


        # ----------------------------------------------------
        # Special handling for preference questions
        # ----------------------------------------------------

        if (
            "favorite" in query_lower
            or
            "favourite" in query_lower
            or
            "do you remember" in query_lower
            or
            "my preference" in query_lower
        ):

            if (
                "favorite" in memory_lower
                or
                "favourite" in memory_lower
                or
                "preference" in memory_lower
            ):

                return True


        return False


    # ========================================================
    # KNOWLEDGE DETECTION
    # ========================================================

    def _is_knowledge_question(
        self,
        query: str
    ) -> bool:

        """
        Detect if a query is a knowledge/document question
        vs a database query.
        """

        if query.lower() in {
            "tools",
            "resources",
            "prompts",
            "login",
            "help",
            "exit",
            "quit"
        }:

            return False


        knowledge_keywords = [

            "policy",
            "rule",
            "guideline",
            "manual",
            "section",

            "what",
            "how",
            "why",
            "is",
            "does",
            "can",

            "underwriting",
            "compliance",
            "regulation",
            "standard",

            "protocol",
            "procedure",
            "requirement",
            "eligibility",

            "deductible",
            "coverage",
            "premium",
            "claim",
            "risk",

            "fishing",
            "vessel",
            "cardiac",
            "engine",
            "inspection"
        ]


        citation_pattern = (
            r"(?:section|sec\.?)\s*"
            r"[\d\.]+[a-z]?|"
            r"[\d]+\.[\d]+[a-z]?"
        )


        query_lower = query.lower()


        return (
            any(
                kw in query_lower
                for kw in knowledge_keywords
            )
            or
            bool(
                re.search(
                    citation_pattern,
                    query_lower,
                    re.IGNORECASE
                )
            )
        )


    # ========================================================
    # MCP CALLBACK: SAMPLING
    # ========================================================

    async def handle_sampling(
        self,
        context,
        params
    ):

        print("\n")
        print("=" * 70)
        print("MCP SAMPLING REQUEST")
        print("=" * 70)

        try:

            chat_messages = []


            for message in params.messages:

                content = message.content


                if hasattr(content, "text"):

                    text = content.text

                elif isinstance(content, str):

                    text = content

                else:

                    text = str(content)


                role = (
                    message.role
                    if message.role
                    in ("user", "assistant")
                    else "user"
                )


                chat_messages.append(
                    {
                        "role": role,
                        "content": text
                    }
                )


            if params.systemPrompt:

                chat_messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": params.systemPrompt
                    }
                )


            print(
                "Server requested Groq analysis..."
            )

            print("-" * 70)


            response = await asyncio.to_thread(

                groq_client.chat.completions.create,

                model=GROQ_MODEL,

                messages=chat_messages,

                max_tokens=(
                    params.maxTokens or 1024
                ),
            )


            text = (
                response.choices[0]
                .message.content
                or ""
            )


            print(
                "Groq sampling response:"
            )

            print(text)

            print("=" * 70)


            from mcp import types as mcp_types


            return mcp_types.CreateMessageResult(

                role="assistant",

                content=mcp_types.TextContent(
                    type="text",
                    text=text,
                ),

                model=GROQ_MODEL,

                stopReason="endTurn",
            )


        except Exception as exc:

            print(
                f"Sampling error: {exc}"
            )

            from mcp import types as mcp_types


            return mcp_types.CreateMessageResult(

                role="assistant",

                content=mcp_types.TextContent(
                    type="text",
                    text=f"Sampling failed: {exc}",
                ),

                model="error",

                stopReason="endTurn",
            )


    # ========================================================
    # MCP CALLBACK: ELICITATION
    # ========================================================

    async def handle_elicitation(
        self,
        context,
        params
    ):

        print("\n")
        print("=" * 70)
        print("HUMAN APPROVAL REQUIRED")
        print("=" * 70)

        print(params.message)

        schema = params.requestedSchema

        print("\nRequired information:")

        properties = schema.get(
            "properties",
            {}
        )

        answers = {}


        for name, definition in properties.items():

            description = definition.get(
                "description",
                name
            )


            while True:

                value = input(
                    f"\n{description}: "
                ).strip()


                if not value:

                    print(
                        "Please provide a value."
                    )

                    continue


                if definition.get("enum"):

                    allowed = (
                        definition["enum"]
                    )


                    if value not in allowed:

                        print(
                            "Please enter one of: "
                            f"{', '.join(allowed)}"
                        )

                        continue


                answers[name] = value

                break


        print("=" * 70)


        from mcp import types as mcp_types


        return mcp_types.ElicitResult(

            action="accept",

            content=answers,
        )


    # ========================================================
    # MCP NOTIFICATIONS
    # ========================================================

    async def refresh_tools(self):

        if not self.session:

            return


        result = await self.session.list_tools()


        self.tools = {
            tool.name: tool
            for tool in result.tools
        }


        print("\n")
        print("=" * 70)
        print("TOOLS/LIST_CHANGED")
        print("=" * 70)

        print(
            "The server changed "
            "the available tools."
        )

        print("New tool list:")


        for name in self.tools:

            print(
                f"  • {name}"
            )


        print("=" * 70)


    async def handle_notification(
        self,
        notification
    ):

        try:

            method = getattr(
                notification,
                "method",
                ""
            )


            if (
                method
                == "notifications/tools/list_changed"
            ):

                await self.refresh_tools()


        except Exception as exc:

            print(
                f"Notification handling error: {exc}"
            )


    # ========================================================
    # SERVER DISCOVERY
    # ========================================================

    async def discover_server(self):

        if not self.session:

            raise RuntimeError(
                "MCP session is not initialized."
            )


        print("\n")
        print("=" * 70)
        print("MCP SERVER DISCOVERY")
        print("=" * 70)


        # ----------------------------------------------------
        # CAPABILITIES
        # ----------------------------------------------------

        self.server_capabilities = (
            self.session.get_server_capabilities()
        )


        print(
            "\nServer capabilities:"
        )


        if self.server_capabilities:

            print(
                self.server_capabilities.model_dump(
                    exclude_none=True
                )
            )

        else:

            print(
                "No capabilities reported."
            )


        # ----------------------------------------------------
        # TOOLS
        # ----------------------------------------------------

        tool_result = (
            await self.session.list_tools()
        )


        self.tools = {
            tool.name: tool
            for tool in tool_result.tools
        }


        print(
            "\nAvailable tools:"
        )


        for tool in tool_result.tools:

            print(
                f"  • {tool.name}: "
                f"{tool.description or 'No description'}"
            )


        # ----------------------------------------------------
        # RESOURCES
        # ----------------------------------------------------

        try:

            resource_result = (
                await self.session.list_resources()
            )


            self.resources = {
                str(resource.uri): resource
                for resource
                in resource_result.resources
            }


            print(
                "\nAvailable resources:"
            )


            for resource in (
                resource_result.resources
            ):

                print(
                    f"  • {resource.uri}"
                )


        except Exception as exc:

            print(
                f"\nResource discovery unavailable: {exc}"
            )


        # ----------------------------------------------------
        # PROMPTS
        # ----------------------------------------------------

        try:

            prompt_result = (
                await self.session.list_prompts()
            )


            self.prompts = {
                prompt.name: prompt
                for prompt in prompt_result.prompts
            }


            print(
                "\nAvailable prompts:"
            )


            for prompt in prompt_result.prompts:

                print(
                    f"  • {prompt.name}"
                )


        except Exception as exc:

            print(
                f"\nPrompt discovery unavailable: {exc}"
            )


        print("=" * 70)


    # ========================================================
    # MCP TOOL -> GROQ
    # ========================================================

    def groq_tool_definitions(self):

        definitions = []


        for tool in self.tools.values():

            schema = (
                tool.inputSchema
                or
                {
                    "type": "object",
                    "properties": {},
                }
            )


            definitions.append(

                {
                    "type": "function",

                    "function":
                    {
                        "name": tool.name,

                        "description":
                            tool.description or "",

                        "parameters":
                            schema,
                    },
                }
            )


        return definitions


    # ========================================================
    # TOOL RESULT -> TEXT
    # ========================================================

    @staticmethod
    def tool_result_to_text(result):

        pieces = []


        for content in getattr(
            result,
            "content",
            []
        ):

            if hasattr(content, "text"):

                pieces.append(
                    content.text
                )

            else:

                pieces.append(
                    str(content)
                )


        if not pieces:

            structured = getattr(
                result,
                "structuredContent",
                None
            )


            if structured:

                return json.dumps(
                    structured,
                    indent=2,
                    default=str
                )


            return str(result)


        return "\n".join(pieces)


    # ========================================================
    # DIRECT MCP TOOL CALL
    # ========================================================

    async def call_mcp_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ):

        if not self.session:

            raise RuntimeError(
                "Not connected to MCP server."
            )


        if name not in self.tools:

            raise ValueError(
                f"Tool '{name}' is not currently available."
            )


        print("\n")
        print("=" * 70)
        print(
            f"MCP TOOL CALL: {name}"
        )
        print("=" * 70)


        print(
            json.dumps(
                arguments,
                indent=2,
                default=str
            )
        )


        result = await self.session.call_tool(

            name,

            arguments=arguments,
        )


        text = (
            self.tool_result_to_text(
                result
            )
        )


        print(
            "\nMCP RESULT:"
        )

        print(text)

        print("=" * 70)


        return text


    # ========================================================
    # LOGIN
    # ========================================================

    async def login(self):

        print("\n")
        print("=" * 70)
        print("HARBORSTONE INSURANCE LOGIN")
        print("=" * 70)


        username = input(
            "Username: "
        ).strip()


        password = input(
            "Password: "
        ).strip()


        result = await self.call_mcp_tool(

            "login",

            {
                "username": username,
                "password": password,
            },
        )


        if "LOGIN SUCCESSFUL" in result:

            self.logged_in = True

            self.username = username


            for line in result.splitlines():

                if line.startswith("Role:"):

                    self.role = (
                        line.split(
                            ":",
                            1
                        )[1]
                        .strip()
                        .lower()
                    )

                    break


            print(
                "\nLogin successful."
            )


            await asyncio.sleep(
                0.2
            )


            await self.refresh_tools()


        else:

            print(
                "\nLogin failed."
            )


    # ========================================================
    # GROQ AGENT LOOP WITH RAG + MEMORY
    # ========================================================

    async def ask_llm(self, user_message: str):
        # ====================================================
        # VALIDATION CHECKS
        # ====================================================
        if not self.session:
            raise RuntimeError("MCP session is not connected.")

        if not self.logged_in:
            return "Please login first. Use the login command."

        # ====================================================
        # STORE USER MESSAGE
        # ====================================================
        self._store_memory_message(
            role=RoleEnum.USER,
            content=user_message,
            msg_type=MessageType.CHAT,
        )


        # ====================================================
        # STORE USER MESSAGE (اول حاجة)
        # ====================================================
        self._store_memory_message(
            role=RoleEnum.USER,
            content=user_message,
            msg_type=MessageType.CHAT,
        )

        # ====================================================
        # MEMORY CONTEXT
        # ====================================================
        memory_context = self._get_memory_context()

        # ====================================================
        # MEMORY-FIRST ROUTING
        # ====================================================
        is_memory_question = self._is_memory_question(user_message)
        memory_has_answer = self._memory_contains_relevant_fact(user_message)

        # Self-RAG verification for memory
        if is_memory_question and memory_has_answer:
            verification = self.memory_verifier.verify(user_message, memory_context)
            if not verification["passed"]:
                print(f"[MEMORY SELF-RAG] Rejected: {verification['reason']}")
                memory_has_answer = False
            else:
                print(f"[MEMORY SELF-RAG] Verified: {verification['reason']}")

        # ====================================================
        # MEMORY-ONLY QUERY
        # ====================================================

        if (
            is_memory_question
            and
            memory_has_answer
        ):

            print("\n" + "=" * 70)
            print("MEMORY QUERY DETECTED")
            print("=" * 70)

            print(
                "Answering from memory."
            )

            print("=" * 70)


            memory_system_instruction = f"""
You are the Harborstone Insurance Agent.

The user is asking about information they previously
provided in the conversation.

IMPORTANT RULES:

1. Answer using ONLY the provided memory context.
2. Do NOT call any MCP tool.
3. Do NOT use RAG.
4. Do NOT invent information.
5. If the answer is not present in memory, say that
   you do not have that information in memory.
6. Treat memory as user-provided context, not as
   current Harborstone database state.
7. Be concise.

MEMORY CONTEXT:
{memory_context}
"""


            memory_messages = [

                {
                    "role": "system",
                    "content":
                        memory_system_instruction
                },

                {
                    "role": "user",
                    "content":
                        user_message
                },
            ]


            try:

                response = await asyncio.to_thread(

                    groq_client.chat.completions.create,

                    model=GROQ_MODEL,

                    messages=memory_messages,

                    tool_choice="none",
                )


                answer = (
                    response.choices[0]
                    .message.content
                    or
                    "I could not find that information "
                    "in memory."
                )


                self._store_memory_message(
                    role=RoleEnum.ASSISTANT,
                    content=answer,
                    msg_type=MessageType.CHAT,
                )


                return answer


            except Exception as exc:

                print(
                    f"Memory query error: {exc}"
                )

                return (
                    "I couldn't retrieve the requested "
                    "information from memory."
                )


        # ====================================================
        # RAG
        # ====================================================

        if (
            self.rag
            and self.verifier
            and self._is_knowledge_question(
                user_message
            )
        ):

            print("\n" + "=" * 70)
            print("RAG KNOWLEDGE QUERY DETECTED")
            print("=" * 70)

            print(
                f"Query: {user_message}"
            )

            print("-" * 70)


            try:

                rag_result = (
                    self.rag.answer(
                        user_message
                    )
                )


                verification = (
                    self.verifier.verify(

                        user_message,

                        rag_result["answer"],

                        rag_result["sources"]
                    )
                )


                print(
                    "Verification passed: "
                    f"{verification['passed']}"
                )


                print(
                    f"   {verification['reason']}"
                )


                if verification["passed"]:

                    answer = (
                        rag_result["answer"]
                    )


                    if (
                        rag_result.get(
                            "sources"
                        )
                        and
                        len(
                            rag_result["sources"]
                        ) > 0
                    ):

                        source = (
                            rag_result["sources"][0]
                        )


                        source_info = (
                            source
                            .get("metadata", {})
                            .get(
                                "source",
                                "policy manual"
                            )
                        )


                        answer += (
                            f"\n\n"
                            f"*Source: {source_info}*"
                        )


                    # ------------------------------------
                    # STORE RAG ANSWER IN MEMORY
                    # ------------------------------------

                    self._store_memory_message(
                        role=RoleEnum.ASSISTANT,
                        content=answer,
                        msg_type=MessageType.CHAT,
                    )


                    print("=" * 70)

                    return answer


                else:

                    print(
                        "Verification failed - "
                        "falling back to tool-based approach"
                    )

                    print("=" * 70)


            except Exception as e:

                print(
                    f"RAG error: {e}"
                )

                print(
                    "Falling back to "
                    "tool-based approach"
                )

                print("=" * 70)


        # ====================================================
        # TOOL-BASED LLM LOOP
        # ====================================================

        tool_definitions = (
            self.groq_tool_definitions()
        )


        if not tool_definitions:

            return (
                "No MCP tools are currently available."
            )


        system_instruction = f"""
You are the Harborstone Insurance Agent.

You interact with a Harborstone Insurance MCP server.

IMPORTANT RULES:

1. Never access the SQLite database directly.
2. Never invent customer, policy, or claim information.
3. Use MCP tools whenever real Harborstone data is required.
4. Only use tools currently provided by the MCP server.
5. Respect role-based permissions enforced by the server.
6. Do not attempt to bypass authorization.
7. If a tool returns an error, explain it clearly.
8. For claim approval, allow the MCP server to perform its own authorization and human elicitation.
9. Do not claim that an action succeeded unless the MCP server confirms it.
10. Be concise and professional.
11. Use the memory context when it is relevant.
12. Treat memory as context, not as proof of current database state.
13. If current Harborstone data is required, use the MCP tools.
14. If the user's question is about information they previously
    told you, use the MEMORY CONTEXT instead of calling an MCP tool.
15. Do not call get_customer_info, get_policy_details, or any
    other MCP tool merely to answer a personal-memory question.
16. If the answer exists in memory, answer directly.

CURRENT AGENT USER:
Username: {self.username}
Role: {self.role}

MEMORY CONTEXT:
{memory_context}

Available MCP resources and prompts should be used when appropriate.
"""


        messages = [

            {
                "role": "system",
                "content": system_instruction
            },

            {
                "role": "user",
                "content": user_message
            },
        ]


        # ====================================================
        # AGENT TOOL-CALL LOOP
        # ====================================================

        for _ in range(10):

            response = await asyncio.to_thread(

                groq_client.chat.completions.create,

                model=GROQ_MODEL,

                messages=messages,

                tools=tool_definitions,

                tool_choice="auto",
            )


            choice = (
                response.choices[0]
                if response.choices
                else None
            )


            if not choice:

                answer = (
                    "Groq did not return a response."
                )

                self._store_memory_message(
                    role=RoleEnum.ASSISTANT,
                    content=answer,
                )

                return answer


            message = choice.message


            tool_calls = (
                message.tool_calls
                or []
            )


            # ------------------------------------------------
            # NO TOOL CALL
            # ------------------------------------------------

            if not tool_calls:

                answer = (
                    message.content
                    or
                    "Groq returned an empty response."
                )


                self._store_memory_message(
                    role=RoleEnum.ASSISTANT,
                    content=answer,
                    msg_type=MessageType.CHAT,
                )


                return answer


            # ------------------------------------------------
            # RECORD TOOL-CALL REQUEST
            # ------------------------------------------------

            messages.append(

                {
                    "role": "assistant",

                    "content":
                        message.content,

                    "tool_calls":
                    [
                        {
                            "id":
                                tool_call.id,

                            "type":
                                "function",

                            "function":
                            {
                                "name":
                                    tool_call.function.name,

                                "arguments":
                                    tool_call.function.arguments,
                            },
                        }

                        for tool_call
                        in tool_calls
                    ],
                }
            )


            # ------------------------------------------------
            # EXECUTE MCP TOOL CALLS
            # ------------------------------------------------

            for tool_call in tool_calls:

                tool_name = (
                    tool_call.function.name
                )


                try:

                    arguments = json.loads(
                        tool_call.function.arguments
                        or
                        "{}"
                    )


                except json.JSONDecodeError:

                    arguments = {}


                try:

                    result = (
                        await self.call_mcp_tool(

                            tool_name,

                            arguments,
                        )
                    )


                except Exception as exc:

                    result = (
                        f"ERROR calling MCP tool "
                        f"{tool_name}: {exc}"
                    )


                messages.append(

                    {
                        "role": "tool",

                        "tool_call_id":
                            tool_call.id,

                        "content":
                            result,
                    }
                )


        answer = (
            "The agent reached its maximum "
            "tool-call depth."
        )


        self._store_memory_message(
            role=RoleEnum.ASSISTANT,
            content=answer,
        )


        return answer


    # ========================================================
    # RESOURCE READER
    # ========================================================

    async def read_resource(
        self,
        uri: str
    ):

        if not self.session:

            raise RuntimeError(
                "MCP session is not connected."
            )


        result = await self.session.read_resource(
            uri
        )


        print("\n")
        print("=" * 70)
        print(
            f"RESOURCE: {uri}"
        )
        print("=" * 70)


        for content in result.contents:

            if hasattr(
                content,
                "text"
            ):

                print(
                    content.text
                )

            else:

                print(content)


        print("=" * 70)


    # ========================================================
    # PROMPT READER
    # ========================================================

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, str],
    ):

        if not self.session:

            raise RuntimeError(
                "MCP session is not connected."
            )


        result = await self.session.get_prompt(

            name,

            arguments=arguments,
        )


        print("\n")
        print("=" * 70)

        print(
            f"PROMPT: {name}"
        )

        print("=" * 70)


        for message in result.messages:

            content = message.content


            if hasattr(
                content,
                "text"
            ):

                print(
                    content.text
                )

            else:

                print(content)


        print("=" * 70)


    # ========================================================
    # INTERACTIVE CHAT
    # ========================================================

    async def chat(self):

        print("\n")
        print("=" * 70)
        print("HARBORSTONE INSURANCE AI AGENT")
        print("=" * 70)

        print(
            "Type 'help' for commands."
        )


        while True:

            try:

                user_input = input(
                    "\nYou: "
                ).strip()


            except (
                KeyboardInterrupt,
                EOFError
            ):

                print(
                    "\nGoodbye."
                )

                break


            if not user_input:

                continue


            # ------------------------------------------------
            # EXIT
            # ------------------------------------------------

            if user_input.lower() in {
                "exit",
                "quit",
            }:

                print(
                    "Goodbye."
                )

                break


            # ------------------------------------------------
            # HELP
            # ------------------------------------------------

            if user_input.lower() == "help":

                print(
                    """
Commands:

tools
Show currently available MCP tools.

resources
Show available MCP resources.

prompts
Show available MCP prompts.

resource <uri>
Read an MCP resource.

memory
Show current memory statistics.

memory_show
Show current stored memories.

consolidate
Manually consolidate Short-Term Memory.

login
Login to Harborstone Insurance.

exit
Exit the agent.

Examples:

Check claim 1.

Show me policy 2.

What is the status of claim 3?

File a claim for policy 2 for $5000
because the vessel was damaged during a storm.

Assess the risk of policy 1.

Approve claim 4.
"""
                )

                continue


            # ------------------------------------------------
            # MEMORY STATUS
            # ------------------------------------------------

            if user_input.lower() == "memory":

                print("\n")
                print("=" * 70)
                print("MEMORY STATUS")
                print("=" * 70)

                print(
                    "Short-Term messages:",
                    self.short_term_memory.message_count
                )

                print(
                    "Short-Term tokens:",
                    self.short_term_memory.current_token_usage
                )

                print(
                    "Episodic memories:",
                    len(self.episodic_memory)
                )

                print(
                    "Semantic memories:",
                    len(self.semantic_memory)
                )

                print(
                    "Scratchpad keys:",
                    self.short_term_memory.size
                    if hasattr(
                        self.short_term_memory,
                        "size"
                    )
                    else len(
                        str(self.short_term_memory
                        .get_scratchpad())
                    )
                )

                print("=" * 70)

                continue


            # ------------------------------------------------
            # MEMORY SHOW
            # ------------------------------------------------

            if user_input.lower() == "memory_show":

                print("\n")
                print("=" * 70)
                print("CURRENT MEMORY")
                print("=" * 70)


                print("\nSHORT-TERM:")

                for message in (
                    self.short_term_memory
                    .get_messages()
                ):

                    print(
                        f"[{message.sequence}] "
                        f"{message.role}: "
                        f"{message.content}"
                    )


                print("\nEPISODIC:")

                for message in (
                    self.episodic_memory
                    .get_all()
                ):

                    print(
                        f"[{message.sequence}] "
                        f"{message.role}: "
                        f"{message.content}"
                    )


                print("\nSEMANTIC:")

                for message in (
                    self.semantic_memory
                    .get_all()
                ):

                    fact_key = (
                        message.metadata
                        .get(
                            "fact_key",
                            "unknown"
                        )
                    )

                    print(
                        f"[{fact_key}] "
                        f"{message.content}"
                    )


                print("\nSCRATCHPAD:")

                print(
                    json.dumps(
                        self.short_term_memory
                        .get_scratchpad(),
                        indent=2,
                        default=str
                    )
                )


                print("=" * 70)

                continue


            # ------------------------------------------------
            # MANUAL CONSOLIDATION
            # ------------------------------------------------

            if user_input.lower() == "consolidate":

                print("\n")
                print(
                    "Running memory consolidation..."
                )

                self.consolidation_engine.consolidate()

                print(
                    "Consolidation completed."
                )

                continue


            # ------------------------------------------------
            # TOOLS
            # ------------------------------------------------

            if user_input.lower() == "tools":

                print(
                    "\nAvailable MCP tools:"
                )


                for name, tool in (
                    self.tools.items()
                ):

                    print(
                        f"  • {name}: "
                        f"{tool.description or ''}"
                    )


                continue


            # ------------------------------------------------
            # RESOURCES
            # ------------------------------------------------

            if user_input.lower() == "resources":

                print(
                    "\nAvailable resources:"
                )


                for uri in self.resources:

                    print(
                        f"  • {uri}"
                    )


                continue


            # ------------------------------------------------
            # PROMPTS
            # ------------------------------------------------

            if user_input.lower() == "prompts":

                print(
                    "\nAvailable prompts:"
                )


                for name in self.prompts:

                    print(
                        f"  • {name}"
                    )


                continue


            # ------------------------------------------------
            # RESOURCE
            # ------------------------------------------------

            if user_input.lower().startswith(
                "resource "
            ):

                uri = (
                    user_input[
                        len("resource "):
                    ].strip()
                )


                await self.read_resource(
                    uri
                )


                continue


            # ------------------------------------------------
            # LOGIN
            # ------------------------------------------------

            if user_input.lower() == "login":

                await self.login()

                continue


            # ------------------------------------------------
            # NORMAL AGENT QUERY
            # ------------------------------------------------

            try:

                answer = await self.ask_llm(
                    user_input
                )


                print(
                    "\nAgent:"
                )

                print(answer)


            except Exception as exc:

                print(
                    f"\nAgent error: {exc}"
                )


    # ========================================================
    # CONNECT & RUN
    # ========================================================

    async def run(self):

        if not SERVER_FILE.exists():

            raise FileNotFoundError(

                f"MCP server not found:\n"
                f"{SERVER_FILE}\n\n"
                f"Expected:\n"
                f"mcp_server/server.py"
            )


        print(
            f"Starting MCP server:\n"
            f"{SERVER_FILE}"
        )


        server_params = StdioServerParameters(

            command=sys.executable,

            args=[
                "-m",
                "mcp_server.server"
            ],

            cwd=str(PROJECT_ROOT),
        )


        print(
            "\nConnecting over MCP stdio..."
        )


        # ====================================================
        # START MCP SERVER
        # ====================================================

        async with stdio_client(
            server_params
        ) as (read, write):


            # =================================================
            # CREATE MCP SESSION
            # =================================================

            async with ClientSession(

                read,

                write,

                sampling_callback=
                    self.handle_sampling,

                elicitation_callback=
                    self.handle_elicitation,

            ) as session:


                self.session = session


                # =============================================
                # MCP INITIALIZE
                # =============================================

                print(
                    "\nPerforming MCP initialize..."
                )


                initialization = (
                    await session.initialize()
                )


                print("\n")
                print("=" * 70)
                print("MCP INITIALIZE COMPLETE")
                print("=" * 70)


                print(
                    f"Server: "
                    f"{initialization.serverInfo.name}"
                )


                print(
                    f"Version: "
                    f"{initialization.serverInfo.version}"
                )


                print(
                    f"Protocol version: "
                    f"{initialization.protocolVersion}"
                )


                print(
                    "\nClient and server successfully "
                    "completed the MCP handshake."
                )


                # =============================================
                # DISCOVER SERVER
                # =============================================

                await self.discover_server()


                # =============================================
                # LOGIN
                # =============================================

                await self.login()


                # =============================================
                # START CHAT
                # =============================================

                await self.chat()


# ============================================================
# MAIN
# ============================================================

import sys
import traceback

async def main():
    agent = HarborstoneAgent()

    try:
        await agent.run()
    except ExceptionGroup as eg:
        import traceback
        print("\n" + "=" * 50)
        print("REAL ERROR INSIDE TASKGROUP:")
        print("=" * 50)
        for exc in eg.exceptions:
            traceback.print_exception(type(exc), exc, exc.__traceback__)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())