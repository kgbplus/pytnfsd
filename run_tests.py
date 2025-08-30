#!/usr/bin/env python3
"""
Test runner script for TNFS daemon
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_tests(test_type="all", coverage=True, verbose=False, markers=None):
    """Run the test suite with specified options"""
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add coverage if requested
    if coverage:
        cmd.extend(["--cov=tnfsd", "--cov-report=term-missing"])
    
    # Add verbose output if requested
    if verbose:
        cmd.append("-v")
    
    # Add specific test types
    if test_type == "unit":
        cmd.append("-m")
        cmd.append("unit")
    elif test_type == "integration":
        cmd.append("-m")
        cmd.append("integration")
    elif test_type == "windows":
        cmd.append("-m")
        cmd.append("windows")
    elif test_type == "linux":
        cmd.append("-m")
        cmd.append("linux")
    
    # Add custom markers
    if markers:
        for marker in markers:
            cmd.extend(["-m", marker])
    
    # Add test directory
    cmd.append("tests/")
    
    print(f"Running tests with command: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True)
        print("-" * 60)
        print("All tests passed!")
        return True
    except subprocess.CalledProcessError as e:
        print("-" * 60)
        print(f"Tests failed with exit code: {e.returncode}")
        return False


def run_specific_test(test_file, test_function=None):
    """Run a specific test file or function"""
    
    cmd = ["python", "-m", "pytest"]
    
    if test_function:
        cmd.append(f"tests/{test_file}::{test_function}")
    else:
        cmd.append(f"tests/{test_file}")
    
    print(f"Running specific test: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, check=True)
        print("-" * 60)
        print("Test passed!")
        return True
    except subprocess.CalledProcessError as e:
        print("-" * 60)
        print(f"Test failed with exit code: {e.returncode}")
        return False


def list_tests():
    """List all available tests"""
    
    cmd = ["python", "-m", "pytest", "--collect-only", "-q", "tests/"]
    
    print("Available tests:")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            if line.strip() and not line.startswith('='):
                print(line)
                
    except subprocess.CalledProcessError as e:
        print(f"Failed to list tests: {e}")


def main():
    """Main function"""
    
    parser = argparse.ArgumentParser(description="Run TNFS daemon tests")
    parser.add_argument("--type", choices=["all", "unit", "integration", "windows", "linux"], 
                       default="all", help="Type of tests to run")
    parser.add_argument("--no-coverage", action="store_true", 
                       help="Disable coverage reporting")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Verbose output")
    parser.add_argument("--markers", nargs="+", 
                       help="Additional pytest markers to filter tests")
    parser.add_argument("--list", action="store_true", 
                       help="List all available tests")
    parser.add_argument("--test-file", 
                       help="Run tests from specific file")
    parser.add_argument("--test-function", 
                       help="Run specific test function")
    
    args = parser.parse_args()
    
    # Check if tests directory exists
    if not Path("tests").exists():
        print("Error: tests directory not found!")
        print("Please run this script from the project root directory.")
        sys.exit(1)
    
    # List tests if requested
    if args.list:
        list_tests()
        return
    
    # Run specific test if requested
    if args.test_file:
        success = run_specific_test(args.test_file, args.test_function)
        sys.exit(0 if success else 1)
    
    # Run full test suite
    success = run_tests(
        test_type=args.type,
        coverage=not args.no_coverage,
        verbose=args.verbose,
        markers=args.markers
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
