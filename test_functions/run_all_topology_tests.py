#!/usr/bin/env python3
"""
Genesis Topology Test Suite Runner

This script runs both basic and multi-agent topology validation tests:
1. Basic Topology Test (Interface → Agent → Service → Functions)
2. Multi-Agent Topology Test (Interface → Agent → Agent → Service → Functions)

Provides comprehensive regression testing and advanced scenario validation.

Copyright (c) 2025, RTI & Jason Upchurch
"""

import subprocess
import sys
import os
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TopologyTestSuite:
    """
    Comprehensive test suite for Genesis topology validation.
    Runs both basic and multi-agent scenarios with detailed reporting.
    """
    
    def __init__(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.results = {}
        
    def run_basic_topology_test(self):
        """Run the basic topology validation test (regression test)"""
        logger.info("🧪 Running Basic Topology Test (Regression)")
        logger.info("=" * 50)
        
        test_script = os.path.join(self.project_root, 'test_functions', 'test_graph_connectivity_validation.py')
        
        try:
            start_time = time.time()
            
            # Run the basic topology test
            result = subprocess.run(
                [sys.executable, test_script],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120  # 2 minutes timeout
            )
            
            duration = time.time() - start_time
            
            self.results['basic_topology'] = {
                'passed': result.returncode == 0,
                'duration': duration,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'return_code': result.returncode
            }
            
            if result.returncode == 0:
                logger.info(f"✅ Basic Topology Test PASSED (Duration: {duration:.1f}s)")
            else:
                logger.error(f"❌ Basic Topology Test FAILED (Duration: {duration:.1f}s)")
                logger.error(f"Return code: {result.returncode}")
                if result.stderr:
                    logger.error(f"STDERR: {result.stderr}")
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            logger.error("❌ Basic Topology Test TIMED OUT")
            self.results['basic_topology'] = {
                'passed': False,
                'duration': 120,
                'error': 'Test timed out after 120 seconds'
            }
            return False
        except Exception as e:
            logger.error(f"❌ Basic Topology Test ERROR: {e}")
            self.results['basic_topology'] = {
                'passed': False,
                'duration': 0,
                'error': str(e)
            }
            return False
    
    def run_multi_agent_topology_test(self):
        """Run the multi-agent topology validation test"""
        logger.info("\n🧪 Running Multi-Agent Topology Test")
        logger.info("=" * 50)
        
        test_script = os.path.join(self.project_root, 'test_functions', 'test_graph_connectivity_validation_multi_agent.py')
        
        try:
            start_time = time.time()
            
            # Run the multi-agent topology test
            result = subprocess.run(
                [sys.executable, test_script],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=180  # 3 minutes timeout (longer for multi-agent)
            )
            
            duration = time.time() - start_time
            
            self.results['multi_agent_topology'] = {
                'passed': result.returncode == 0,
                'duration': duration,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'return_code': result.returncode
            }
            
            if result.returncode == 0:
                logger.info(f"✅ Multi-Agent Topology Test PASSED (Duration: {duration:.1f}s)")
            else:
                logger.error(f"❌ Multi-Agent Topology Test FAILED (Duration: {duration:.1f}s)")
                logger.error(f"Return code: {result.returncode}")
                if result.stderr:
                    logger.error(f"STDERR: {result.stderr}")
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            logger.error("❌ Multi-Agent Topology Test TIMED OUT")
            self.results['multi_agent_topology'] = {
                'passed': False,
                'duration': 180,
                'error': 'Test timed out after 180 seconds'
            }
            return False
        except Exception as e:
            logger.error(f"❌ Multi-Agent Topology Test ERROR: {e}")
            self.results['multi_agent_topology'] = {
                'passed': False,
                'duration': 0,
                'error': str(e)
            }
            return False
    
    def run_performance_benchmark(self):
        """Run performance benchmarks for topology discovery"""
        logger.info("\n📊 Running Performance Benchmarks")
        logger.info("=" * 50)
        
        # Basic topology discovery time
        basic_duration = self.results.get('basic_topology', {}).get('duration', 0)
        multi_agent_duration = self.results.get('multi_agent_topology', {}).get('duration', 0)
        
        logger.info(f"Basic Topology Discovery Time: {basic_duration:.1f}s")
        logger.info(f"Multi-Agent Topology Discovery Time: {multi_agent_duration:.1f}s")
        
        # Performance thresholds
        basic_threshold = 60  # 1 minute
        multi_agent_threshold = 120  # 2 minutes
        
        basic_performance_ok = basic_duration <= basic_threshold
        multi_agent_performance_ok = multi_agent_duration <= multi_agent_threshold
        
        logger.info(f"Basic Topology Performance: {'✅ GOOD' if basic_performance_ok else '⚠️ SLOW'}")
        logger.info(f"Multi-Agent Topology Performance: {'✅ GOOD' if multi_agent_performance_ok else '⚠️ SLOW'}")
        
        self.results['performance'] = {
            'basic_duration': basic_duration,
            'multi_agent_duration': multi_agent_duration,
            'basic_performance_ok': basic_performance_ok,
            'multi_agent_performance_ok': multi_agent_performance_ok
        }
        
        return basic_performance_ok and multi_agent_performance_ok
    
    def generate_test_report(self):
        """Generate a comprehensive test report"""
        logger.info("\n📋 Test Suite Report")
        logger.info("=" * 50)
        
        # Overall results
        basic_passed = self.results.get('basic_topology', {}).get('passed', False)
        multi_agent_passed = self.results.get('multi_agent_topology', {}).get('passed', False)
        performance_ok = self.results.get('performance', {}).get('basic_performance_ok', False) and \
                        self.results.get('performance', {}).get('multi_agent_performance_ok', False)
        
        overall_passed = basic_passed and multi_agent_passed
        
        logger.info(f"Basic Topology Test: {'✅ PASSED' if basic_passed else '❌ FAILED'}")
        logger.info(f"Multi-Agent Topology Test: {'✅ PASSED' if multi_agent_passed else '❌ FAILED'}")
        logger.info(f"Performance Benchmarks: {'✅ GOOD' if performance_ok else '⚠️ NEEDS ATTENTION'}")
        logger.info(f"Overall Result: {'✅ ALL TESTS PASSED' if overall_passed else '❌ SOME TESTS FAILED'}")
        
        # Detailed results
        if not basic_passed:
            basic_error = self.results.get('basic_topology', {}).get('error')
            if basic_error:
                logger.error(f"Basic Topology Error: {basic_error}")
        
        if not multi_agent_passed:
            multi_agent_error = self.results.get('multi_agent_topology', {}).get('error')
            if multi_agent_error:
                logger.error(f"Multi-Agent Topology Error: {multi_agent_error}")
        
        # Save detailed report to file
        self.save_detailed_report()
        
        return overall_passed
    
    def save_detailed_report(self):
        """Save a detailed test report to file"""
        try:
            report_filename = f"topology_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            report_path = os.path.join(self.project_root, report_filename)
            
            with open(report_path, 'w') as f:
                f.write("Genesis Topology Test Suite Report\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Test Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                # Basic topology results
                f.write("Basic Topology Test Results:\n")
                f.write("-" * 30 + "\n")
                basic_result = self.results.get('basic_topology', {})
                f.write(f"Status: {'PASSED' if basic_result.get('passed', False) else 'FAILED'}\n")
                f.write(f"Duration: {basic_result.get('duration', 0):.1f} seconds\n")
                f.write(f"Return Code: {basic_result.get('return_code', 'N/A')}\n")
                if basic_result.get('error'):
                    f.write(f"Error: {basic_result['error']}\n")
                f.write("\n")
                
                # Multi-agent topology results
                f.write("Multi-Agent Topology Test Results:\n")
                f.write("-" * 35 + "\n")
                multi_result = self.results.get('multi_agent_topology', {})
                f.write(f"Status: {'PASSED' if multi_result.get('passed', False) else 'FAILED'}\n")
                f.write(f"Duration: {multi_result.get('duration', 0):.1f} seconds\n")
                f.write(f"Return Code: {multi_result.get('return_code', 'N/A')}\n")
                if multi_result.get('error'):
                    f.write(f"Error: {multi_result['error']}\n")
                f.write("\n")
                
                # Performance results
                f.write("Performance Benchmark Results:\n")
                f.write("-" * 30 + "\n")
                perf_result = self.results.get('performance', {})
                f.write(f"Basic Topology Discovery: {perf_result.get('basic_duration', 0):.1f}s\n")
                f.write(f"Multi-Agent Topology Discovery: {perf_result.get('multi_agent_duration', 0):.1f}s\n")
                f.write(f"Basic Performance OK: {perf_result.get('basic_performance_ok', False)}\n")
                f.write(f"Multi-Agent Performance OK: {perf_result.get('multi_agent_performance_ok', False)}\n")
                f.write("\n")
                
                # Overall summary
                overall_passed = basic_result.get('passed', False) and multi_result.get('passed', False)
                f.write("Overall Summary:\n")
                f.write("-" * 15 + "\n")
                f.write(f"All Tests Passed: {overall_passed}\n")
                f.write(f"Ready for Production: {overall_passed and perf_result.get('basic_performance_ok', False) and perf_result.get('multi_agent_performance_ok', False)}\n")
            
            logger.info(f"📁 Detailed report saved to: {report_filename}")
            
        except Exception as e:
            logger.error(f"❌ Failed to save detailed report: {e}")
    
    def run_all_tests(self):
        """Run the complete test suite"""
        logger.info("🚀 Starting Genesis Topology Test Suite")
        logger.info("=" * 60)
        
        start_time = time.time()
        
        # Run basic topology test (regression)
        basic_passed = self.run_basic_topology_test()
        
        # Run multi-agent topology test
        multi_agent_passed = self.run_multi_agent_topology_test()
        
        # Run performance benchmarks
        performance_ok = self.run_performance_benchmark()
        
        # Generate comprehensive report
        overall_passed = self.generate_test_report()
        
        total_duration = time.time() - start_time
        
        logger.info(f"\n🏁 Test Suite Completed in {total_duration:.1f} seconds")
        logger.info(f"Final Result: {'✅ SUCCESS' if overall_passed else '❌ FAILURE'}")
        
        return overall_passed


def main():
    """Main entry point"""
    print("🧪 Genesis Topology Test Suite")
    print("=" * 40)
    print("This suite validates both basic and multi-agent topologies")
    print("ensuring comprehensive coverage of Genesis system scenarios.\n")
    
    # Check environment
    if not os.environ.get('OPENAI_API_KEY'):
        print("⚠️ Warning: OPENAI_API_KEY not set. Some tests may use fallback modes.")
    
    if not os.environ.get('OPENWEATHERMAP_API_KEY'):
        print("⚠️ Warning: OPENWEATHERMAP_API_KEY not set. Weather agent will use mock data.")
    
    print()
    
    # Run test suite
    test_suite = TopologyTestSuite()
    success = test_suite.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 