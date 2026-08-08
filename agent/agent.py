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


from RAG import get_retriever, SelfRAGVerifier
from RAG.config import DEFAULT_RETRIEVER




PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Change this only if your server file has another name.
SERVER_FILE = PROJECT_ROOT / "mcp_server" / "server.py"

load_dotenv(PROJECT_ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# You can change this model if needed.
# llama-3.3-70b-versatile has solid tool-calling support and a
# generous free-tier quota. openai/gpt-oss-120b is another good option.
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is missing.\n"
        "Put it in the .env file:\n\n"
        "GROQ_API_KEY=your_key_here"
    )


# Groq client (OpenAI-compatible)
groq_client = Groq(api_key=GROQ_API_KEY)


# ============================================================
# AGENT
# ============================================================

class HarborstoneAgent:
    """
    MCP client/agent for the Harborstone Insurance server.
    """

    def __init__(self):
        self.session: ClientSession | None = None

        self.server_capabilities = None

        self.tools: dict[str, Any] = {}
        self.resources: dict[str, Any] = {}
        self.prompts: dict[str, Any] = {}

        self.logged_in = False
        self.username: str | None = None
        self.role: str | None = None


        try:
            self.rag = get_retriever(DEFAULT_RETRIEVER)
            self.verifier = SelfRAGVerifier()
            # Show how many chunks are in the vector store
            chunk_count = len(self.rag.vector_store.collection.get()["ids"])
            print(f"RAG initialized with '{DEFAULT_RETRIEVER}' retriever")
            print(f"Vector store contains {chunk_count} chunks")
        except Exception as e:
            print(f"RAG initialization failed: {e}")
            print("The agent will fall back to tool-based mode only.")
            self.rag = None
            self.verifier = None
        print("=" * 70 + "\n")

    # ============================================================
    # KNOWLEDGE DETECTION
    # ============================================================

    def _is_knowledge_question(self, query: str) -> bool:
        """
        Detect if a query is a knowledge/document question vs a database query.

        Returns:
            True if this should be handled by RAG, False if it should go to MCP tools.
        """
        # Quick check: if it's a command, skip
        if query.lower() in {"tools", "resources", "prompts", "login", "help", "exit", "quit"}:
            return False

        # Keywords that suggest a knowledge/document question
        knowledge_keywords = [
            "policy", "rule", "guideline", "manual", "section",
            "what", "how", "why", "is", "does", "can",
            "underwriting", "compliance", "regulation", "standard",
            "protocol", "procedure", "requirement", "eligibility",
            "deductible", "coverage", "premium", "claim", "risk",
            "fishing", "vessel", "cardiac", "engine", "inspection"
        ]

        # Check for citation patterns like "Section 4.2b", "4.2b", "2.2"
        citation_pattern = r"(?:section|sec\.?)\s*[\d\.]+[a-z]?|[\d]+\.[\d]+[a-z]?"

        query_lower = query.lower()

        return (
            any(kw in query_lower for kw in knowledge_keywords) or
            bool(re.search(citation_pattern, query_lower, re.IGNORECASE))
        )

    # ========================================================
    # MCP CALLBACK: SAMPLING
    # ========================================================

    async def handle_sampling(self, context, params):
        """
        The Harborstone server calls ctx.sample() inside assess_risk().

        That means:

            Server
                ↓
            MCP sampling request
                ↓
            Agent
                ↓
            Groq
                ↓
            Agent response
                ↓
            MCP server
        """

        print("\n")
        print("=" * 70)
        print("MCP SAMPLING REQUEST")
        print("=" * 70)

        try:
            # Convert MCP sampling messages into OpenAI-style chat messages.
            chat_messages = []

            for message in params.messages:
                content = message.content

                if hasattr(content, "text"):
                    text = content.text
                elif isinstance(content, str):
                    text = content
                else:
                    text = str(content)

                # MCP roles are "user"/"assistant"; Groq expects the same.
                role = message.role if message.role in ("user", "assistant") else "user"

                chat_messages.append({"role": role, "content": text})

            if params.systemPrompt:
                chat_messages.insert(
                    0, {"role": "system", "content": params.systemPrompt}
                )

            print("Server requested Groq analysis...")
            print("-" * 70)

            response = await asyncio.to_thread(
                groq_client.chat.completions.create,
                model=GROQ_MODEL,
                messages=chat_messages,
                max_tokens=params.maxTokens or 1024,
            )

            text = response.choices[0].message.content or ""

            print("Groq sampling response:")
            print(text)
            print("=" * 70)

            # MCP sampling response
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
            print(f"Sampling error: {exc}")

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

    async def handle_elicitation(self, context, params):
        """
        Handles human confirmation requested by approve_claim().

        The server uses elicitation when:

            claim amount > $10,000

        The agent pauses and asks the real human.
        """

        print("\n")
        print("=" * 70)
        print("HUMAN APPROVAL REQUIRED")
        print("=" * 70)

        print(params.message)

        schema = params.requestedSchema

        print("\nRequired information:")

        properties = schema.get("properties", {})

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
                    print("Please provide a value.")
                    continue

                if definition.get("enum"):
                    allowed = definition["enum"]

                    if value not in allowed:
                        print(
                            f"Please enter one of: "
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
        """
        Re-discover tools after tools/list_changed.
        """

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
        print("The server changed the available tools.")
        print("New tool list:")

        for name in self.tools:
            print(f"  • {name}")

        print("=" * 70)

    async def handle_notification(self, notification):
        """
        Generic notification handler.

        We specifically watch for tools/list_changed.
        """

        try:
            method = getattr(
                notification,
                "method",
                ""
            )

            if method == "notifications/tools/list_changed":
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

        # ----------------------------
        # CAPABILITIES
        # ----------------------------

        self.server_capabilities = (
            self.session.get_server_capabilities()
        )

        print("\nServer capabilities:")

        if self.server_capabilities:
            print(
                self.server_capabilities.model_dump(
                    exclude_none=True
                )
            )
        else:
            print("No capabilities reported.")

        # ----------------------------
        # TOOLS
        # ----------------------------

        tool_result = await self.session.list_tools()

        self.tools = {
            tool.name: tool
            for tool in tool_result.tools
        }

        print("\nAvailable tools:")

        for tool in tool_result.tools:
            print(
                f"  • {tool.name}: "
                f"{tool.description or 'No description'}"
            )

        # ----------------------------
        # RESOURCES
        # ----------------------------

        try:

            resource_result = (
                await self.session.list_resources()
            )

            self.resources = {
                str(resource.uri): resource
                for resource in resource_result.resources
            }

            print("\nAvailable resources:")

            for resource in resource_result.resources:
                print(f"  • {resource.uri}")

        except Exception as exc:
            print(
                f"\nResource discovery unavailable: {exc}"
            )

        # ----------------------------
        # PROMPTS
        # ----------------------------

        try:

            prompt_result = (
                await self.session.list_prompts()
            )

            self.prompts = {
                prompt.name: prompt
                for prompt in prompt_result.prompts
            }

            print("\nAvailable prompts:")

            for prompt in prompt_result.prompts:
                print(f"  • {prompt.name}")

        except Exception as exc:
            print(
                f"\nPrompt discovery unavailable: {exc}"
            )

        print("=" * 70)

    # ========================================================
    # MCP TOOL -> GROQ (OPENAI-STYLE) TOOL DEFINITION
    # ========================================================

    def groq_tool_definitions(self):
        """
        Convert MCP tool definitions into the OpenAI-compatible
        "tools" format Groq expects:

            {
                "type": "function",
                "function": {
                    "name": ...,
                    "description": ...,
                    "parameters": <JSON schema>,
                },
            }
        """

        definitions = []

        for tool in self.tools.values():

            schema = tool.inputSchema or {
                "type": "object",
                "properties": {},
            }

            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": schema,
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
                pieces.append(content.text)

            else:
                pieces.append(str(content))

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
        print(f"MCP TOOL CALL: {name}")
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

        text = self.tool_result_to_text(result)

        print("\nMCP RESULT:")
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

            # Extract role from login response.
            for line in result.splitlines():

                if line.startswith("Role:"):

                    self.role = (
                        line.split(
                            ":", 1
                        )[1]
                        .strip()
                        .lower()
                    )

                    break

            print("\nLogin successful.")

            # This is important:
            # the server changes available tools after login.
            await asyncio.sleep(0.2)

            await self.refresh_tools()

        else:

            print("\nLogin failed.")

    # ========================================================
    # GROQ AGENT LOOP (WITH RAG)
    # ========================================================

    async def ask_llm(self, user_message: str):
        if not self.session:
            raise RuntimeError("MCP session is not connected.")

        if not self.logged_in:
            return "Please login first. Use the login command."


        if self.rag and self.verifier and self._is_knowledge_question(user_message):
            print("\n" + "=" * 70)
            print("RAG KNOWLEDGE QUERY DETECTED")
            print("=" * 70)
            print(f"Query: {user_message}")
            print("-" * 70)

            try:
                # Get RAG answer
                rag_result = self.rag.answer(user_message)

                # Self-RAG verification
                verification = self.verifier.verify(
                    user_message,
                    rag_result["answer"],
                    rag_result["sources"]
                )

                print(f"Verification passed: {verification['passed']}")
                print(f"   {verification['reason']}")

                if verification["passed"]:
                    # Format the answer with a source citation
                    answer = rag_result["answer"]

                    # Add source info
                    if rag_result.get("sources") and len(rag_result["sources"]) > 0:
                        source = rag_result["sources"][0]
                        source_info = source.get("metadata", {}).get("source", "policy manual")
                        answer += f"\n\n*Source: {source_info}*"

                    print("=" * 70)
                    return answer
                else:
                    print("Verification failed - falling back to tool-based approach")
                    print("=" * 70)

            except Exception as e:
                print(f"RAG error: {e}")
                print("Falling back to tool-based approach")
                print("=" * 70)

        # ============================================================
        # TOOL-BASED LLM LOOP (Original)
        # ============================================================
        tool_definitions = self.groq_tool_definitions()

        if not tool_definitions:
            return "No MCP tools are currently available."

        system_instruction = """
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

Available MCP resources and prompts should be used when appropriate.
"""

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_message},
        ]

        # AGENT TOOL-CALL LOOP
        for _ in range(10):
            response = await asyncio.to_thread(
                groq_client.chat.completions.create,
                model=GROQ_MODEL,
                messages=messages,
                tools=tool_definitions,
                tool_choice="auto",
            )

            choice = response.choices[0] if response.choices else None

            if not choice:
                return "Groq did not return a response."

            message = choice.message

            tool_calls = message.tool_calls or []

            # NO TOOL CALL
            if not tool_calls:
                return message.content or "Groq returned an empty response."

            # RECORD THE ASSISTANT'S TOOL-CALL REQUEST
            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                        for tool_call in tool_calls
                    ],
                }
            )

            # EXECUTE MCP TOOL CALLS
            for tool_call in tool_calls:
                tool_name = tool_call.function.name

                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                try:
                    result = await self.call_mcp_tool(
                        tool_name,
                        arguments,
                    )
                except Exception as exc:
                    result = f"ERROR calling MCP tool {tool_name}: {exc}"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

        return "The agent reached its maximum tool-call depth."

    # ========================================================
    # RESOURCE READER
    # ========================================================

    async def read_resource(self, uri: str):

        if not self.session:
            raise RuntimeError(
                "MCP session is not connected."
            )

        result = await self.session.read_resource(
            uri
        )

        print("\n")
        print("=" * 70)
        print(f"RESOURCE: {uri}")
        print("=" * 70)

        for content in result.contents:

            if hasattr(content, "text"):
                print(content.text)
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
        print(f"PROMPT: {name}")
        print("=" * 70)

        for message in result.messages:

            content = message.content

            if hasattr(content, "text"):
                print(content.text)
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

            except (KeyboardInterrupt, EOFError):

                print("\nGoodbye.")
                break

            if not user_input:
                continue


            if user_input.lower() in {
                "exit",
                "quit",
            }:

                print("Goodbye.")
                break

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


            if user_input.lower() == "tools":

                print("\nAvailable MCP tools:")

                for name, tool in self.tools.items():

                    print(
                        f"  • {name}: "
                        f"{tool.description or ''}"
                    )

                continue



            if user_input.lower() == "resources":

                print("\nAvailable resources:")

                for uri in self.resources:

                    print(f"  • {uri}")

                continue



            if user_input.lower() == "prompts":

                print("\nAvailable prompts:")

                for name in self.prompts:

                    print(f"  • {name}")

                continue



            if user_input.lower().startswith(
                "resource "
            ):

                uri = user_input[
                    len("resource "):
                ].strip()

                await self.read_resource(uri)

                continue



            if user_input.lower() == "login":

                await self.login()

                continue



            try:

                answer = await self.ask_llm(
                    user_input
                )

                print("\nAgent:")
                print(answer)

            except Exception as exc:

                print(
                    f"\nAgent error: {exc}"
                )



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
                str(SERVER_FILE)
            ],
            cwd=str(PROJECT_ROOT),
        )

        print("\nConnecting over MCP stdio...")

        # ----------------------------------------------------
        # Start MCP server
        # ----------------------------------------------------

        async with stdio_client(
            server_params
        ) as (read, write):

            # ------------------------------------------------
            # Create MCP session
            # ------------------------------------------------

            async with ClientSession(
                read,
                write,
                sampling_callback=self.handle_sampling,
                elicitation_callback=self.handle_elicitation,
            ) as session:

                self.session = session

                # --------------------------------------------
                # MCP INITIALIZE HANDSHAKE
                # --------------------------------------------

                print("\nPerforming MCP initialize...")

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

                # --------------------------------------------
                # DISCOVER SERVER
                # --------------------------------------------

                await self.discover_server()

                # --------------------------------------------
                # LOGIN
                # --------------------------------------------

                await self.login()

                # --------------------------------------------
                # START CHAT
                # --------------------------------------------

                await self.chat()


# ============================================================
# MAIN
# ============================================================

async def main():

    agent = HarborstoneAgent()

    try:

        await agent.run()

    except KeyboardInterrupt:

        print("\nAgent stopped.")

    except Exception as exc:

        print(
            "\nFatal error:"
        )

        print(exc)


if __name__ == "__main__":

    asyncio.run(main())