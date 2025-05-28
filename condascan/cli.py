import subprocess
import sys
from typing import List, Union, Tuple, Dict
from rich.console import Console
from packaging.version import Version
from packaging.requirements import Requirement
from condascan.parser import parse_args, parse_packages, standarize_package_name, parse_commands, parse_envs
from condascan.codes import ReturnCode, PackageCode
from condascan.cache import get_cache, write_cache, CacheType
from condascan.display import display_have_output, get_progress_bar, display_can_exec_output, display_compare_output

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
            return (), [('', (PackageCode.ERROR, 'Error checking environment'))], '', False
        cache[env] = result[1].stdout.splitlines()
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

                if scores[0] == len(requirements) and python_version != 'Not Available':
                    break
    except Exception as e:
        console.print(f'[red]Unhandled Error in processing "{env}": {str(e)} [/red]')
        sys.exit(1)

    return scores, [(package, status) for package, status in package_status.items()], python_version, scores[0] == len(requirements)

def can_execute_in_env(env: str, commands: List[str], cache: Dict) -> Tuple[List, str, bool]:
    results = []
    valid = True
    
    python_version = 'Not Available'
    python_command = 'python --version'
    if cache.get(env, {}).get(python_command) is None:
        result = run_shell_command(['conda', 'run', '-n', env, *python_command.split(' ')])
        if result[0] != ReturnCode.EXECUTED:
            return [('', (PackageCode.ERROR, 'Error checking environment'))], '', False
        if result[1].returncode == 0:
            exec_result = result[1].stdout.strip()
            if exec_result.startswith('Python '):
                python_version = exec_result.split(' ')[1]
            else:
                python_version = exec_result
            exec_result = python_version
        cache.setdefault(env, {})[python_command] = (True, exec_result)
    python_version = cache[env][python_command][1]

    for command in commands:
        if cache.get(env, {}).get(command) is None:
            result = run_shell_command(['conda', 'run', '-n', env, *command.split(' ')])
            if result[0] != ReturnCode.EXECUTED:
                return [('', (PackageCode.ERROR, 'Error checking environment'))], '', False
            if result[1].returncode == 0:
                exec_result = (True, result[1].stdout.strip())
            else:
                valid = False
                error = result[1].stderr.strip()
                conda_log_idx = error.index('\n\nERROR conda.cli.main_run:execute')
                error = error[:conda_log_idx]
                exec_result = (False, error)

            cache.setdefault(env, {})[command] = exec_result
        exec_result = cache[env][command]
        valid = valid and exec_result[0]
        
        results.append((command, exec_result))

    return results, python_version, valid

def compare_envs(envs: List[str], all_envs: List[str], cache: Dict) -> Tuple[List, Dict[str, List[str]], Dict[str, Dict[str, str]]]:
    all_envs = set(all_envs)
    envs = set(envs)
    if not envs.issubset(all_envs):
        console.print(f'[red]Error: Some environments {envs - all_envs} are not found in the installed environments[/red]')
        sys.exit(1)

    installed_packages = {}
    packages_version = {}

    for env in envs:
        if cache.get(env) is None:
            result = run_shell_command(['conda', 'list', '-n', env])
            if result[0] != ReturnCode.EXECUTED:
                return (), [('', (PackageCode.ERROR, 'Error checking environment'))], '', False
            out = [x for x in result[1].stdout.splitlines() if x != '' and not x.startswith('#')]
            out = [[y for y in x.split(' ') if y != ''] for x in out]
            out = [(standarize_package_name(x[0]), x[1].strip()) for x in out]

            cache[env] = out
        
        installed_packages[env] = set([x[0] for x in cache[env]])
        for package, version in cache[env]:
            packages_version.setdefault(env, {})[package] = version

    env_names = list(installed_packages.keys())
    env_packages = [installed_packages[env] for env in env_names]
    common_packages = sorted(list(set.intersection(*env_packages)))
    distinct_packages = [s - set.union(*(env_packages[:i] + env_packages[i+1:])) for i, s in enumerate(env_packages)]
    distinct_packages = {env_names[i]: sorted(list(distinct_packages[i])) for i in range(len(env_names))}

    return common_packages, distinct_packages, packages_version

def main():
    args = parse_args()

    console.print('[bold]Initial checks[/bold]')
    if args.subcommand != 'compare' and args.limit <= 0 and args.limit != -1:
        console.print('[red]Limit argument must be greater than 0[/red]')
        sys.exit(1)

    if check_conda_installed():
        console.print('[green]:heavy_check_mark: Conda is installed[/green]')
    else:
        console.print('[red]:x: Conda is not installed or not found in PATH[/red]')
        sys.exit(1)
    
    conda_envs = get_conda_envs()

    if args.subcommand == 'have':
        cache_type = CacheType.PACKAGES
        func = check_packages_in_env
        func_args = parse_packages(args.packages)
    elif args.subcommand == 'can-execute':
        cache_type = CacheType.COMMANDS
        func = can_execute_in_env
        func_args = parse_commands(args.command)
    elif args.subcommand == 'compare':
        cache_type = CacheType.PACKAGES
        func_args = parse_envs(args.envs)
        result = compare_envs(func_args, conda_envs, {})
        # import pdb; pdb.set_trace()
        display_compare_output(*result)
        # print(result)
        sys.exit(0)

    if not args.no_cache:
        cached_envs = get_cache(cache_type)
    else:
        cached_envs = {}
        console.print('[bold yellow]Running without cache, this may take a while[/bold yellow]')

    filtered_envs = []
    with get_progress_bar(console) as progress:
        task = progress.add_task('Checking conda environments', total=len(conda_envs))
        
        for env in conda_envs:
            progress.update(task, description=f'Checking "{env}"')
            result = (env, *func(env, func_args, cached_envs))
            filtered_envs.append(result)
            progress.advance(task)
            if args.first and result[-1]:
                filtered_envs = [result]
                break
    write_cache(cached_envs, cache_type)

    if args.subcommand == 'have':
        filtered_envs.sort(key=lambda x: (-x[1][0], -x[1][1], -x[1][2], x[1][3]))
        display_have_output(filtered_envs, args.limit, args.verbose, args.first)
    elif args.subcommand == 'can-execute':
        filtered_envs.sort(key=lambda x: (-x[3]))
        display_can_exec_output(filtered_envs, args.limit, args.verbose, args.first)
    elif args.subcommand == 'compare':
        raise NotImplementedError()
        


if __name__ == '__main__':
    main()