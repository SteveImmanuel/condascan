import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='condascout: a tool to find conda environments which contain specified package(s)')
    parser.add_argument('--have', nargs='+', help='Package(s) to search for in conda environments', metavar='PACKAGE')
    parser.add_argument('--full', action='store_true', help='Perform a full search over all conda environments. By default, the first environment that satisfies the requirements is returned.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

    args = parser.parse_args()
    return args
