import subprocess
import sys
from typing import List, Union, Tuple, Dict
from rich.console import Console
from packaging.version import Version
from packaging.requirements import Requirement
from condascout.parser import parse_args, parse_packages, standarize_package_name, parse_commands
from condascout.codes import ReturnCode, PackageCode
from condascout.cache import get_cache, write_cache, CacheType
from condascout.display import display_table_output, get_progress_bar

console = Console()

def run_shell_command(command: List[str]) -> Tuple[ReturnCode, Union[subprocess.CompletedProcess, Exception]]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        return (ReturnCode.EXECUTED, result)
    except FileNotFoundError as e:
        return (ReturnCode.COMMAND_NOT_FOUND, e)
    except Exception as e:
        return (ReturnCode.UNHANDLED_ERROR, e)

def check_conda_installed() -> bool:
    result = run_shell_command(['conda', '--version'])
    if result[0] == ReturnCode.EXECUTED:
        return result[1].returncode == 0
    return False

def get_conda_envs() -> List[str]:
    result = run_shell_command(['conda', 'env', 'list'])
    if result[0] != ReturnCode.EXECUTED:
        return []

    envs = []
    for line in result[1].stdout.splitlines():
        if line != '' and not line.startswith('#'):
            env = line.split(' ')[0]
            if env != '':
                envs.append(env)
    return envs

def try_get_version(version: str) -> bool:
    try:
        return Version(version)
    except Exception:
        return None

def check_packages_in_env(env: str, requirements: List[Requirement], cache: Dict) -> Tuple[Tuple, List, str, bool]:
    if cache.get(env) is None:
        result = run_shell_command(['conda', 'list', '-n', env])
        if result[0] != ReturnCode.EXECUTED:
            return float('inf'), float('inf'), [('', (PackageCode.ERROR, 'Error checking environment'))]
        installed_packages = result[1].stdout.splitlines()
        cache[env] = installed_packages
    else:
        installed_packages = cache[env]

    package_status = {x.name: (PackageCode.MISSING, x.specifier) for x in requirements}
    scores = [0, 0, 0, len(installed_packages)] # found, invalid, mismatch, #packages 
    python_version = 'Not Available'

    try:
        for line in installed_packages:
            if line != '' and not line.startswith('#'):
                line = [x for x in line.split(' ') if x != '']
                package, version = line[0], line[1]
                if package == '':
                    continue
                
                package = standarize_package_name(package)
                version = try_get_version(version)

                for req in requirements:
                    if req.name == package:
                        if version is None:
                            package_status[req.name] = (PackageCode.VERSION_INVALID, f'Expected "{req.specifier}", found "{version}". Version is not in PEP 440 format.')
                            scores[1] += 1
                        elif req.specifier == '' or req.specifier.contains(version):
                            package_status[req.name] = (PackageCode.FOUND, version)
                            scores[0] += 1
                        else:
                            package_status[req.name] = (PackageCode.VERSION_MISMATCH, f'Expected "{req.specifier}", found "{version}"')
                            scores[2] += 1
                
                if package == 'python':
                    python_version = version

                if scores[0] == len(requirements):
                    break
    except Exception as e:
        console.print(f'[red]Unhandled Error in processing "{env}": {str(e)} [/red]')
        sys.exit(1)

    return scores, [(package, status) for package, status in package_status.items()], python_version, scores[0] == len(requirements)

def can_execute_in_env(env: str, command: str) -> Tuple[bool, str]:
    result = run_shell_command(['conda', 'run', '-n', env, *command.split(' ')])
    if result[0] != ReturnCode.EXECUTED:
        return False, ''
    
    if result[1].returncode == 0:
        return True, result[1].stdout
    else:
        return False, result[1].stderr

def main():
    args = parse_args()

    console.print('[bold]Initial checks[/bold]')
    if args.limit <= 0 and args.limit != -1:
        console.print('[red]Limit argument must be greater than 0[/red]')
        sys.exit(1)

    if check_conda_installed():
        console.print('[green]:heavy_check_mark: Conda is installed[/green] ')
    else:
        console.print('[red]:x: Conda is not installed or not found in PATH[/red]')
        sys.exit(1)
    
    if args.subcommand == 'have':
        cache_type = CacheType.PACKAGES
        requirements = parse_packages(args.packages)
    elif args.subcommand == 'can-execute':
        cache_type = CacheType.COMMANDS
        commands = parse_commands(args.command)
    elif args.subcommand == 'compare':
        cache_type = CacheType.COMMANDS
        raise NotImplementedError()

    if not args.no_cache:
        cached_envs = get_cache(cache_type)
    else:
        cached_envs = {}
        console.print('[bold yellow]Running without cache, this may take a while[/bold yellow]')

    conda_envs = get_conda_envs()
    filtered_envs = []
    with get_progress_bar(console) as progress:
        task = progress.add_task('Checking conda environments', total=len(conda_envs))
        
        for env in conda_envs:
            progress.update(task, description=f'Checking "{env}"')
            result = (env, *check_packages_in_env(env, requirements, cached_envs))
            filtered_envs.append(result)
            progress.advance(task)
            if args.first and result[-1]:
                break
    filtered_envs.sort(key=lambda x: (-x[1][0], -x[1][1], -x[1][2], x[1][3]))

    write_cache(cached_envs, cache_type)
    
    display_table_output(filtered_envs, args.limit, args.verbose, args.first)


if __name__ == '__main__':
    main()