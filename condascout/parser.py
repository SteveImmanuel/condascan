import argparse
import os.path as osp
import sys
import yaml
from packaging.requirements import Requirement, InvalidRequirement
from rich.console import Console

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(prog='condascout', description='condascout: a tool to find conda environments which contain specified package(s)')
    subparsers = parser.add_subparsers(dest='subcommand', required=True)

    subparser_have = subparsers.add_parser('have', description='find conda environments that have the specified package(s)', help='find conda environments that have the specified package(s)')
    subparser_have.add_argument('packages', type=str, help='package(s) to search for in conda environments')
    subparser_have.add_argument('--no-cache', action='store_true', help='force to run without using cached results from previous runs')
    subparser_have.add_argument('--first', action='store_true', help='immediately return the first environment that satisfies the requirements. By default, perform a full search over all conda environments')
    subparser_have.add_argument('--limit', type=int, help='limit the number of environments displayed in the output. Use in conjunction with verbose', default=-1)
    subparser_have.add_argument('--verbose', action='store_true', help='enable verbose output')

    subparser_exe = subparsers.add_parser('can-execute', description='find conda environments that can execute the specified command', help='find conda environments that can execute the specified command')
    subparser_exe.add_argument('command', type=str, help='command to execute')
    subparser_exe.add_argument('--no-cache', action='store_true', help='force to run without using cached results from previous runs')
    subparser_exe.add_argument('--first', action='store_true', help='immediately return the first environment that satisfies the requirements. By default, perform a full search over all conda environments')
    subparser_exe.add_argument('--limit', type=int, help='limit the number of environments displayed in the output. Use in conjunction with verbose', default=-1)
    subparser_exe.add_argument('--verbose', action='store_true', help='enable verbose output')

    subparser_compare = subparsers.add_parser('compare', description='compare different environments to find overlapping and distinct packages', help='compare different environments to find overlapping and distinct packages')
    subparser_compare.add_argument('envs', type=str, help='environments to compare')
    subparser_compare.add_argument('--no-cache', action='store_true', help='force to run without using cached results from previous runs')
    subparser_compare.add_argument('--verbose', action='store_true', help='enable verbose output')

    args = parser.parse_args()
    
    return args

def parse_packages(packages: str):
    if packages.endswith('.txt') or packages.endswith('.yaml') or packages.endswith('.yml'):
        if not osp.exists(packages):
            console.print(f':x:[red] File "{packages}" does not exist[/red]')
            sys.exit(1)

        requirements = []

        if packages.endswith('.txt'):
            with open(packages, 'r') as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == '' or line.startswith('#'):
                        continue
                    if 'git+' in line:
                        console.print(f':warning:[yellow] Skipping git package requirement "{line}"[/yellow]')
                        continue
                    if '@' in line:
                        line = line.split('@')[0].strip()
                    requirements.append(line)
        else:
            with open(packages, 'r') as f:
                raw_req = yaml.safe_load(f)
            
            for dep in raw_req.get('dependencies', []):
                if isinstance(dep, str):
                    if dep.startswith('_'):
                        continue
                    dep = dep.strip().split('=')
                    requirements.append(f'{dep[0]}=={dep[1]}' if len(dep) > 1 else dep[0])
                elif isinstance(dep, dict):
                    for pip_dep in dep.get('pip', []):
                        requirements.append(pip_dep.strip())

    else:
        requirements = [x for x in packages.split(' ') if x != '']

    for i in range(len(requirements)):
        try:
            requirements[i] = Requirement(requirements[i])
        except InvalidRequirement as e:
            console.print(f':x:[red] Invalid requirement "{requirements[i]}"[/red]')
            sys.exit(1)

    return requirements