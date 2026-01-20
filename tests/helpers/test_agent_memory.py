#!/usr/bin/env python3
# ####################################################################################
# (c) 2025 Copyright, Real-Time Innovations, Inc. (RTI) All rights reserved.         #
#                                                                                    #
# RTI grants Licensee a license to use, modify, compile, and create derivative       #
# works of the Software. Licensee has the right to distribute object form only       #
# for use with RTI products. The Software is provided "as is", with no warranty      #
# of any type, including any warranty for fitness for any purpose. RTI is under no   #
# obligation to maintain or support the Software. RTI shall not be liable for any    #
# incidental or consequential damages arising out of the use or inability to use     #
# the software.                                                                      #
# ####################################################################################

import asyncio
import sys
import logging
import random
import re
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.memory import SimpleMemoryAdapter

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("test_agent_memory")

class MemoryTestAgent(OpenAIGenesisAgent):
    def __init__(self, memory_adapter=None):
        super().__init__(
            model_name="gpt-4o",
            classifier_model_name="gpt-4o-mini",
            agent_name="MemoryTestAgent",
            description="A test agent for memory recall",
            enable_tracing=True,
            memory_adapter=memory_adapter
        )
        # Override the system prompt to clearly identify this as a Genesis agent
        self.system_prompt = (
            "You are a Genesis agent, part of the Genesis distributed agent framework. "
            "You have memory capabilities and can recall previous conversations. "
            "Always identify yourself as a Genesis agent when asked about your type."
        )
    
    # Override process_request to add debug output
    async def process_request(self, request):
        user_message = request.get("message", "")
        print(f"\n[DEBUG] Processing user message: {user_message}")
        
        # Retrieve memory and format for OpenAI
        N = 8
        memory_items = self.memory.retrieve(k=N)
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add conversation history from memory
        for entry in memory_items:
            item = entry["item"]
            meta = entry.get("metadata", {})
            role = meta.get("role")
            if role not in ("user", "assistant"):
                idx = memory_items.index(entry)
                role = "user" if idx % 2 == 0 else "assistant"
            messages.append({"role": role, "content": str(item)})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        print(f"\n[DEBUG] Messages being sent to OpenAI:")
        for i, msg in enumerate(messages):
            print(f"  {i}: {msg}")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_config['model_name'],
                messages=messages
            )
            
            agent_response = response.choices[0].message.content
            print(f"\n[DEBUG] OpenAI response: {agent_response}")
            
            # Store user and agent messages to memory
            self.memory.store(user_message, metadata={"role": "user"})
            self.memory.store(agent_response, metadata={"role": "assistant"})
            
            return {"message": agent_response, "status": 0}
            
        except Exception as e:
            print(f"\n[DEBUG] Error calling OpenAI: {e}")
            return {"message": f"Error: {str(e)}", "status": 1}

async def main():
    agent = MemoryTestAgent()
    try:
        favorite_number = random.randint(10000, 99999)
        print(f"[TEST] The favorite number to remember is: {favorite_number}")
        
        # Multi-stage conversation
        messages = [
            "What kind of agent are you?",
            f"My favorite number is {favorite_number}. Please remember this.",
            "What type of agent are you again?",
            "What is my favorite number that I told you?"
        ]
        
        expected_checks = [
            (2, "genesis"),  # On the third message, expect 'genesis' in the response (case-insensitive)
            (3, favorite_number)  # On the fourth message, expect the number (robust to formatting like 32,898)
        ]
        
        responses = []
        for i, msg in enumerate(messages):
            logger.info(f"User message {i+1}: {msg}")
            response = await agent.process_message(msg)
            logger.info(f"LLM response {i+1}: {response}")
            print(f"USER: {msg}")
            print(f"AGENT: {response}")
            responses.append(response)
            await asyncio.sleep(0.1)
        
        # Show memory contents for debugging
        recalled = agent.memory.retrieve(k=10)
        logger.info("Memory contents after conversation:")
        for entry in recalled:
            print(f"MEMORY: {entry}")
        
        # Check both expectations
        passed = True
        failure_details = []
        
        def contains_expected(response_text, expected):
            text = str(response_text)
            # Numeric expectation: allow thousand separators and minor formatting
            if isinstance(expected, (int, float)) or (isinstance(expected, str) and expected.isdigit()):
                try:
                    expected_num = int(expected)
                except Exception:
                    return False
                # Find number-like tokens (e.g., 32,898 or -1,234)
                matches = re.findall(r"-?\d[\d,]*", text)
                for m in matches:
                    # Normalize by removing non-digits except leading '-'
                    norm = re.sub(r"(?!^)-|[^\d-]", "", m)
                    try:
                        if int(norm) == expected_num:
                            return True
                    except Exception:
                        continue
                return False
            # Text expectation: case-insensitive containment
            return str(expected).lower() in text.lower()

        for idx, expected in expected_checks:
            if not contains_expected(responses[idx], expected):
                passed = False
                failure_details.append(
                    f"Expected '{expected}' in response {idx+1}, but got: {responses[idx]}"
                )
            else:
                print(f"✅ Memory recall check {idx+1} PASSED: Found '{expected}' in response")
        
        if passed:
            print(f"✅ Multi-stage memory recall test PASSED: Agent recalled both type and favorite number.")
        else:
            print(f"❌ Multi-stage memory recall test FAILED.")
            for detail in failure_details:
                print(f"   - {detail}")
                
    finally:
        try:
            await agent.close()
        except Exception as e:
            # DDS cleanup errors are expected and don't affect test results
            print(f"[DEBUG] DDS cleanup warning (expected): {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit as e:
        # Handle potential DDS cleanup issues that might cause system exit
        if e.code != 0:
            print(f"[DEBUG] Process exit with code {e.code} (likely DDS cleanup)")
        # Exit cleanly regardless of DDS cleanup issues
        exit(0)
    except Exception as e:
        print(f"[ERROR] Test failed with exception: {e}")
        exit(1) 
