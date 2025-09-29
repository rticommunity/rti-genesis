#!/usr/bin/env python3

import logging
import asyncio
from text_processor_service import TextProcessorService

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("text_processor_test")

async def test_service_lifecycle():
    """Test the service lifecycle including proper cleanup"""
    logger.info("Starting service lifecycle test...")
    
    # Create and start the service
    service = TextProcessorService()
    
    try:
        # Start the service in a background task
        service_task = asyncio.create_task(service.run())
        
        # Wait a bit to let the service initialize
        await asyncio.sleep(2)
        
        # Test that the service is running by checking if functions are advertised
        assert len(service.functions) > 0, "Service should have registered functions"
        logger.info(f"Service has {len(service.functions)} registered functions")
        
        # Explicitly close the service
        logger.info("Testing explicit service close...")
        service.close()
        
        # Wait for the service task to complete
        await service_task
        
        logger.info("Service lifecycle test completed successfully")
        
    except Exception as e:
        logger.error(f"Error during service lifecycle test: {str(e)}", exc_info=True)
        raise
    finally:
        # Ensure service is closed even if test fails
        if 'service' in locals():
            service.close()

def main():
    """Main entry point"""
    logger.info("Starting text processor service lifecycle test")
    try:
        asyncio.run(test_service_lifecycle())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error in main: {str(e)}", exc_info=True)
    finally:
        logger.info("Test completed")

if __name__ == "__main__":
    main() 