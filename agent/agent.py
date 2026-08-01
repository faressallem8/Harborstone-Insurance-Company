
"""
Harborstone Insurance - MCP Agent

This agent:
1. Starts the Harborstone MCP server over stdio.
2. Performs the MCP initialize handshake.
3. Checks server capabilities.
4. Discovers tools, resources, and prompts.
5. Logs in through the MCP server.
6. Detects tools/list_changed notifications.
7. Uses Gemini to decide which MCP tool to call.
8. Handles MCP elicitation requests for human confirmation.
9. Handles MCP sampling requests from assess_risk().
10. Provides an interactive terminal chat.

Run from the project root:

    python agent/agent.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from google import genai
from google.genai import types

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Change this only if your server file has another name.
SERVER_FILE = PROJECT_ROOT / "mcp_server" / "server.py"

load_dotenv(PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# You can change this model if needed.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing.\n"
        "Put it in the .env file:\n\n"
        "GEMINI_API_KEY=your_key_here"
    )


# Gemini client
gemini = genai.Client(api_key=GEMINI_API_KEY)


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
            Gemini
                ↓
            Agent response
                ↓
            MCP server
        """

        print("\n")
        print("=" * 70)
        print("🤖 MCP SAMPLING REQUEST")
        print("=" * 70)

        try:
            prompt_parts = []

            for message in params.messages:
                content = message.content

                if hasattr(content, "text"):
                    text = content.text
                elif isinstance(content, str):
                    text = content
                else:
                    text = str(content)

                prompt_parts.append(
                    f"[{message.role}]\n{text}"
                )

            prompt = "\n\n".join(prompt_parts)

            print("Server requested Gemini analysis...")
            print("-" * 70)

            response = await asyncio.to_thread(
                gemini.models.generate_content,
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=params.maxTokens or 1024
                ),
            )

            text = response.text or ""

            print("Gemini sampling response:")
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
                model=GEMINI_MODEL,
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
        print("⚠️  HUMAN APPROVAL REQUIRED")
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
        print("🔔 TOOLS/LIST_CHANGED")
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
    # MCP TOOL -> GEMINI FUNCTION DECLARATION
    # ========================================================

    def gemini_function_declarations(self):
    
     declarations = []

     for tool in self.tools.values():

        schema = tool.inputSchema or {
            "type": "object",
            "properties": {},
        }

        # Gemini does not accept additionalProperties /
        # additional_properties in the function parameter schema.
        schema = dict(schema)
        schema.pop("additionalProperties", None)
        schema.pop("additional_properties", None)

        declaration = types.FunctionDeclaration(
            name=tool.name,
            description=tool.description or "",
            parameters=schema,
        )

        declarations.append(declaration)

     return declarations

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
        print(f"🔧 MCP TOOL CALL: {name}")
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

            print("\n✅ Login successful.")

            # This is important:
            # the server changes available tools after login.
            await asyncio.sleep(0.2)

            await self.refresh_tools()

        else:

            print("\n❌ Login failed.")

    # ========================================================
    # GEMINI AGENT LOOP
    # ========================================================

    async def ask_gemini(self, user_message: str):

        if not self.session:
            raise RuntimeError(
                "MCP session is not connected."
            )

        if not self.logged_in:

            return (
                "Please login first. "
                "Use the login command."
            )

        function_declarations = (
            self.gemini_function_declarations()
        )

        if not function_declarations:

            return (
                "No MCP tools are currently "
                "available."
            )

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

        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=user_message
                    )
                ],
            )
        ]

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[
                types.Tool(
                    function_declarations=
                    function_declarations
                )
            ],
        )

        # ----------------------------------------------------
        # AGENT TOOL-CALL LOOP
        # ----------------------------------------------------

        for _ in range(10):

            response = await asyncio.to_thread(
                gemini.models.generate_content,
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )

            candidate = (
                response.candidates[0]
                if response.candidates
                else None
            )

            if not candidate:

                return (
                    "Gemini did not return a response."
                )

            model_content = candidate.content

            contents.append(model_content)

            function_calls = []

            for part in model_content.parts:

                if getattr(part, "function_call", None):

                    function_calls.append(
                        part.function_call
                    )

            # ------------------------------------------------
            # NO TOOL CALL
            # ------------------------------------------------

            if not function_calls:

                return response.text or (
                    "Gemini returned an empty response."
                )

            # ------------------------------------------------
            # EXECUTE MCP TOOL CALLS
            # ------------------------------------------------

            function_response_parts = []

            for function_call in function_calls:

                tool_name = function_call.name

                arguments = dict(
                    function_call.args or {}
                )

                try:

                    result = await self.call_mcp_tool(
                        tool_name,
                        arguments,
                    )

                except Exception as exc:

                    result = (
                        f"ERROR calling MCP tool "
                        f"{tool_name}: {exc}"
                    )

                function_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={
                            "result": result
                        },
                    )
                )

            contents.append(
                types.Content(
                    role="user",
                    parts=function_response_parts,
                )
            )

        return (
            "The agent reached its maximum "
            "tool-call depth."
        )

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
        print("🏢 HARBORSTONE INSURANCE AI AGENT")
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

            # ----------------------------------------------
            # EXIT
            # ----------------------------------------------

            if user_input.lower() in {
                "exit",
                "quit",
            }:

                print("Goodbye.")
                break

            # ----------------------------------------------
            # HELP
            # ----------------------------------------------

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

            # ----------------------------------------------
            # TOOLS
            # ----------------------------------------------

            if user_input.lower() == "tools":

                print("\nAvailable MCP tools:")

                for name, tool in self.tools.items():

                    print(
                        f"  • {name}: "
                        f"{tool.description or ''}"
                    )

                continue

            # ----------------------------------------------
            # RESOURCES
            # ----------------------------------------------

            if user_input.lower() == "resources":

                print("\nAvailable resources:")

                for uri in self.resources:

                    print(f"  • {uri}")

                continue

            # ----------------------------------------------
            # PROMPTS
            # ----------------------------------------------

            if user_input.lower() == "prompts":

                print("\nAvailable prompts:")

                for name in self.prompts:

                    print(f"  • {name}")

                continue

            # ----------------------------------------------
            # RESOURCE
            # ----------------------------------------------

            if user_input.lower().startswith(
                "resource "
            ):

                uri = user_input[
                    len("resource "):
                ].strip()

                await self.read_resource(uri)

                continue

            # ----------------------------------------------
            # LOGIN
            # ----------------------------------------------

            if user_input.lower() == "login":

                await self.login()

                continue

            # ----------------------------------------------
            # NORMAL AGENT QUERY
            # ----------------------------------------------

            try:

                answer = await self.ask_gemini(
                    user_input
                )

                print("\nAgent:")
                print(answer)

            except Exception as exc:

                print(
                    f"\n❌ Agent error: {exc}"
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
                print("✅ MCP INITIALIZE COMPLETE")
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
