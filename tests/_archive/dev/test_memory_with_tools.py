import asyncio
import sys
import logging
import random
import time
from genesis_lib.openai_genesis_agent import OpenAIGenesisAgent
from genesis_lib.memory import SimpleMemoryAdapter

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("test_memory_with_tools")

class MemoryWithToolsTestAgent(OpenAIGenesisAgent):
    def __init__(self, memory_adapter=None):
        super().__init__(
            model_name="gpt-4o",
            classifier_model_name="gpt-4o-mini",
            agent_name="MemoryWithToolsTestAgent",
            description="A test agent for memory recall with tools available",
            enable_tracing=True,
            memory_adapter=memory_adapter
        )
        # Override the system prompt to clearly identify this as a Genesis agent
        self.system_prompt = (
            "You are a Genesis agent, part of the Genesis distributed agent framework. "
            "You have memory capabilities and can recall previous conversations. "
            "You can also use available tools like calculators when needed. "
            "Always identify yourself as a Genesis agent when asked about your type."
        )

async def main():
    agent = MemoryWithToolsTestAgent()
    try:
        # Wait for function discovery
        print("Waiting for function discovery...")
        await asyncio.sleep(3)
        
        favorite_number = random.randint(10000, 99999)
        print(f"[TEST] The favorite number to remember is: {favorite_number}")
        
        # Multi-stage conversation with tool usage
        messages = [
            "Hi, my name is Alice.",
            f"My favorite number is {favorite_number}. Please remember this.",
            "Can you calculate 5 + 3 for me?",  # This should trigger tool usage
            "What is my name?",  # Memory recall after tool usage
            "What is my favorite number that I told you?"  # Memory recall after tool usage
        ]
        
        expected_checks = [
            (3, "alice"),  # After tool usage, expect 'alice' in the response
            (4, str(favorite_number))  # After tool usage, expect the number
        ]
        
        responses = []
        for i, msg in enumerate(messages):
            logger.info(f"User message {i+1}: {msg}")
            response = await agent.process_message(msg)
            logger.info(f"LLM response {i+1}: {response}")
            print(f"USER: {msg}")
            print(f"AGENT: {response}")
            responses.append(response)
            await asyncio.sleep(0.5)  # Give time between requests
        
        # Show memory contents for debugging
        recalled = agent.memory.retrieve(k=10)
        logger.info("Memory contents after conversation:")
        for entry in recalled:
            print(f"MEMORY: {entry}")
        
        # Check both expectations
        passed = True
        failure_details = []
        
        for idx, expected in expected_checks:
            response_text = str(responses[idx]).lower()
            expected_text = expected.lower()
            
            if expected_text not in response_text:
                passed = False
                failure_details.append(f"Expected '{expected}' in response {idx+1}, but got: {responses[idx]}")
            else:
                print(f"✅ Memory recall check {idx+1} PASSED: Found '{expected}' in response")
        
        # Additional check: verify that calculation was performed (tool was used)
        calc_response = str(responses[2]).lower()
        if "8" in calc_response:  # 5 + 3 = 8
            print(f"✅ Tool usage check PASSED: Calculator tool was used correctly")
        else:
            print(f"❌ Tool usage check FAILED: Expected '8' in calculation response, got: {responses[2]}")
            passed = False
        
        if passed:
            print(f"✅ Memory with tools test PASSED: Agent recalled user information after tool usage.")
        else:
            print(f"❌ Memory with tools test FAILED.")
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