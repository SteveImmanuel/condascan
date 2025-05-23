import argparse

def parse_args():
    parser = argparse.ArgumentParser(prog='condascout', description='condascout: a tool to find conda environments which contain specified package(s)')
    subparsers = parser.add_subparsers(dest='command', required=True)

    subparser_have = subparsers.add_parser('have', description='find conda environments that have the specified package(s)', help='find conda environments that have the specified package(s)')
    subparser_have.add_argument('packages', nargs='+', help='package(s) to search for in conda environments')
    
    subparser_exe = subparsers.add_parser('can-execute', description='find conda environments that can execute the specified command', help='find conda environments that can execute the specified command')
    subparser_exe.add_argument('command', nargs='+', help='command to execute')

    subparser_compare = subparsers.add_parser('compare', description='compare different environments to find overlapping and distinct packages', help='compare different environments to find overlapping and distinct packages')
    subparser_compare.add_argument('envs', nargs='+', help='environments to compare')

    parser.add_argument('--no-cache', action='store_true', help='force to run without using cached results from previous runs')
    parser.add_argument('--first', action='store_true', help='immediately return the first environment that satisfies the requirements. By default, perform a full search over all conda environments')
    parser.add_argument('--verbose', action='store_true', help='enable verbose output')
    parser.add_argument('--limit', type=int, help='limit the number of environments displayed in the output. Use in conjunction with verbose', default=-1)
    args = parser.parse_args()
    return args
