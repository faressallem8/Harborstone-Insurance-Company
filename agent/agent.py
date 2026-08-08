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

Run from the project root:

    python agent/agent.py
"""

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
# PROJECT CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

SERVER_FILE = PROJECT_ROOT / "mcp_server" / "server.py"

load_dotenv(PROJECT_ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

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
        # MEMORY
        # ====================================================

        self.short_term_memory = ShortTermMemory(
            conversation_id="harborstone_agent"
        )

        self.episodic_memory = EpisodicMemory()

        self.semantic_memory = SemanticMemory()

        self.consolidation_engine = ConsolidationEngine(
            short_term=self.short_term_memory,
            episodic=self.episodic_memory,
            semantic=self.semantic_memory,
        )

        print("\n")
        print("=" * 70)
        print("MEMORY INITIALIZED")
        print("=" * 70)
        print("Short-Term Memory: READY")
        print("Episodic Memory: READY")
        print("Semantic Memory: READY")
        print("Consolidation Engine: READY")
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

        The ConsolidationEngine is responsible for deciding
        whether the message should later remain in STM,
        move to Episodic Memory, or move to Semantic Memory.
        """

        try:

            message = self.short_term_memory.add_message(
                role=role,
                content=content,
                msg_type=msg_type,
            )

            print(
                f"[MEMORY] Stored "
                f"{role.value} message "
                f"(seq={message.sequence})"
            )

            self._maybe_consolidate()

            return message

        except Exception as exc:

            print(
                f"[MEMORY] Failed to store message: {exc}"
            )

            return None


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

        Priority:

        1. Short-Term Memory
        2. Semantic Memory
        3. Episodic Memory
        4. Scratchpad
        """

        sections = []


        # ----------------------------------------------------
        # SHORT-TERM MEMORY
        # ----------------------------------------------------

        short_term_messages = (
            self.short_term_memory.get_messages()
        )

        if short_term_messages:

            lines = []

            for message in short_term_messages[-10:]:

                role = (
                    message.role.value
                    if hasattr(message.role, "value")
                    else str(message.role)
                )

                lines.append(
                    f"{role}: {message.content}"
                )

            sections.append(
                "SHORT-TERM MEMORY:\n"
                + "\n".join(lines)
            )


        # ----------------------------------------------------
        # SEMANTIC MEMORY
        # ----------------------------------------------------

        semantic_messages = (
            self.semantic_memory.get_all()
        )

        if semantic_messages:

            lines = []

            for message in semantic_messages[-10:]:

                fact_key = (
                    message.metadata.get(
                        "fact_key",
                        "unknown"
                    )
                )

                lines.append(
                    f"{fact_key}: {message.content}"
                )

            sections.append(
                "SEMANTIC MEMORY:\n"
                + "\n".join(lines)
            )


        # ----------------------------------------------------
        # EPISODIC MEMORY
        # ----------------------------------------------------

        episodic_messages = (
            self.episodic_memory.get_all()
        )

        if episodic_messages:

            lines = []

            for message in episodic_messages[-10:]:

                role = (
                    message.role.value
                    if hasattr(message.role, "value")
                    else str(message.role)
                )

                lines.append(
                    f"{role}: {message.content}"
                )

            sections.append(
                "EPISODIC MEMORY:\n"
                + "\n".join(lines)
            )


        # ----------------------------------------------------
        # SCRATCHPAD
        # ----------------------------------------------------

        scratchpad = (
            self.short_term_memory.get_scratchpad()
        )

        if scratchpad:

            sections.append(
                "SCRATCHPAD:\n"
                + json.dumps(
                    scratchpad,
                    indent=2,
                    default=str
                )
            )


        if not sections:

            return "No previous memory available."


        return "\n\n".join(sections)


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

    async def ask_llm(
        self,
        user_message: str
    ):

        if not self.session:

            raise RuntimeError(
                "MCP session is not connected."
            )


        if not self.logged_in:

            return (
                "Please login first. "
                "Use the login command."
            )


        # ====================================================
        # STORE USER MESSAGE
        # ====================================================

        self._store_memory_message(
            role=RoleEnum.USER,
            content=user_message,
            msg_type=MessageType.CHAT,
        )


        # ====================================================
        # MEMORY CONTEXT
        # ====================================================

        memory_context = (
            self._get_memory_context()
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


                    # ----------------------------------------
                    # STORE RAG ANSWER IN MEMORY
                    # ----------------------------------------

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

  resource <URI>
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
                        self.short_term_memory
                        .get_scratchpad()
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
    # CONNECT
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


        server_params = (
            StdioServerParameters(

                command=sys.executable,

                args=[
                    str(SERVER_FILE)
                ],

                cwd=str(PROJECT_ROOT),
            )
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

async def main():

    agent = HarborstoneAgent()


    try:

        await agent.run()


    except KeyboardInterrupt:

        print(
            "\nAgent stopped."
        )


    except Exception as exc:

        print(
            "\nFatal error:"
        )

        print(exc)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())