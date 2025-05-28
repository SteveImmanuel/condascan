import argparse
import subprocess
import sys
from typing import List, Union, Tuple, Dict
from rich.console import Console
from packaging.version import Version
from packaging.requirements import Requirement
from condascan.parser import parse_args, parse_packages, parse_commands, parse_envs, standarize_package_name
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

def is_conda_installed() -> bool:
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

class Task:
    def __init__(self, args: argparse.Namespace):
        self.args = args

    def parse_args(self):
        raise NotImplementedError()
    
    def initialize_and_verify(self):
        console.print('[bold]Initial checks[/bold]')
        if self.args.subcommand != 'compare' and self.args.limit <= 0 and self.args.limit != -1:
            console.print('[red]Limit argument must be greater than 0[/red]')
            sys.exit(1)

        if is_conda_installed():
            console.print('[green]:heavy_check_mark: Conda is installed[/green]')
        else:
            console.print('[red]:x: Conda is not installed or not found in PATH[/red]')
            sys.exit(1)
        
        self.conda_envs = get_conda_envs()
        self.process_args = self.parse_args()

        console.print()
        if not self.args.no_cache:
            self.cached_envs = get_cache(self.cache_type)
        else:
            self.cached_envs = {}
            console.print('[bold yellow]Running without cache, this may take a while[/bold yellow]')

    def process(self):
        raise NotImplementedError()

    @staticmethod
    def from_args(args: argparse.Namespace):
        if args.subcommand == 'have':
            return TaskFind(args)
        elif args.subcommand == 'can-execute':
            return TaskCanExecute(args)
        else:
            return TaskCompare(args)

class TaskFind(Task):
    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        self.cache_type = CacheType.PACKAGES

    def parse_args(self):
        return parse_packages(self.args.packages)

    def _check_packages_in_env(self, env: str, requirements: List[Requirement]) -> Tuple[Tuple, List, str, bool]:
        if self.cached_envs.get(env) is None:
            result = run_shell_command(['conda', 'list', '-n', env])
            if result[0] != ReturnCode.EXECUTED:
                return (), [('', (PackageCode.ERROR, 'Error checking environment'))], '', False
            self.cached_envs[env] = result[1].stdout.splitlines()
        installed_packages = self.cached_envs[env]

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
    
    def process(self):
        filtered_envs = []

        with get_progress_bar(console) as progress:
            task = progress.add_task('Checking conda environments', total=len(self.conda_envs))
            for env in self.conda_envs:
                progress.update(task, description=f'Checking "{env}"')
                result = (env,  *self._check_packages_in_env(env, self.process_args))
                filtered_envs.append(result)
                progress.advance(task)
                if self.args.first and result[-1]:
                    filtered_envs = [result]
                    break
        
        write_cache(self.cached_envs, self.cache_type)
        filtered_envs.sort(key=lambda x: (-x[1][0], -x[1][1], -x[1][2], x[1][3]))
        display_have_output(filtered_envs, self.args.limit, self.args.verbose, self.args.first)
    
class TaskCanExecute(Task):
    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        self.cache_type = CacheType.COMMANDS

    def parse_args(self):
        return parse_commands(self.args.commands)
    
    def _can_execute_in_env(self, env: str, commands: List[str]) -> Tuple[List, str, bool]:
        results = []
        valid = True
        
        python_version = 'Not Available'
        python_command = 'python --version'
        if self.cached_envs.get(env, {}).get(python_command) is None:
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
            self.cached_envs.setdefault(env, {})[python_command] = (True, exec_result)
        python_version = self.cached_envs[env][python_command][1]

        for command in commands:
            if self.cached_envs.get(env, {}).get(command) is None:
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

                self.cached_envs.setdefault(env, {})[command] = exec_result
            exec_result = self.cached_envs[env][command]
            valid = valid and exec_result[0]
            
            results.append((command, exec_result))

        return results, python_version, valid
    
    def process(self):
        filtered_envs = []
        with get_progress_bar(console) as progress:
            task = progress.add_task('Checking conda environments', total=len(self.conda_envs))
            
            for env in self.conda_envs:
                progress.update(task, description=f'Checking "{env}"')
                result = (env,  *self._can_execute_in_env(env, self.process_args))
                filtered_envs.append(result)
                progress.advance(task)
                if self.args.first and result[-1]:
                    filtered_envs = [result]
                    break
        
        write_cache(self.cached_envs, self.cache_type)
        filtered_envs.sort(key=lambda x: (-x[3]))
        display_can_exec_output(filtered_envs, self.args.limit, self.args.verbose, self.args.first)

class TaskCompare(Task):
    def __init__(self, args: argparse.Namespace):
        super().__init__(args)
        self.cache_type = CacheType.PACKAGES

    def parse_args(self):
        return parse_envs(self.args.envs)
    
    def process(self):
        with get_progress_bar(console) as progress:
            all_envs = set(self.conda_envs)
            envs = set(self.process_args)
            if not envs.issubset(all_envs):
                console.print(f'[red]Error: Some environments {envs - all_envs} are not found in the installed environments[/red]')
                sys.exit(1)

            task = progress.add_task('Checking conda environments', total=len(envs))
            installed_packages = {}
            packages_version = {}

            for env in envs:
                progress.update(task, description=f'Checking "{env}"')

                if self.cached_envs.get(env) is None:
                    result = run_shell_command(['conda', 'list', '-n', env])
                    if result[0] != ReturnCode.EXECUTED:
                        return (), [('', (PackageCode.ERROR, 'Error checking environment'))], '', False #TODO: check this
                    
                    self.cached_envs[env] = result[1].stdout.splitlines()

                out = [x for x in self.cached_envs[env] if x != '' and not x.startswith('#')]
                out = [[y for y in x.split(' ') if y != ''] for x in out]
                out = [(standarize_package_name(x[0]), x[1].strip()) for x in out if not self.args.pip or x[-1] == 'pypi']
                
                installed_packages[env] = set([x[0] for x in out])
                for package, version in out:
                    packages_version.setdefault(env, {})[package] = version
                
                progress.advance(task)

        env_names = list(installed_packages.keys())
        env_packages = [installed_packages[env] for env in env_names]
        common_packages = sorted(list(set.intersection(*env_packages)))
        distinct_packages = [s - set.union(*(env_packages[:i] + env_packages[i+1:])) for i, s in enumerate(env_packages)]
        distinct_packages = {env_names[i]: sorted(list(distinct_packages[i])) for i in range(len(env_names))}

        write_cache(self.cached_envs, self.cache_type)
        display_compare_output(common_packages, distinct_packages, packages_version)

