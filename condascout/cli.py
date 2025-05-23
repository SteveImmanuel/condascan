import subprocess
from tqdm import tqdm
from packaging.version import Version
from packaging.requirements import Requirement, InvalidRequirement
from condascout.parser import parse_args
from condascout.codes import ReturnCode, PackageCode
from typing import List, Union, Tuple

def run_shell_command(command: List[str]) -> Tuple[ReturnCode, Union[subprocess.CompletedProcess, Exception]]:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        return (ReturnCode.EXECUTED, result)
    except FileNotFoundError as e:
        return (ReturnCode.COMMAND_NOT_FOUND, e)
    except Exception as e:
        return (ReturnCode.UNHANDLED_ERROR, e)

def check_conda_installed():
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

def check_packages_in_env(env: str, requirements: List[Requirement]) -> List[str]:
    result = run_shell_command(['conda', 'list', '-n', env])
    if result[0] != ReturnCode.EXECUTED:
        return []

    package_status = {x.name: (PackageCode.MISSING, x.specifier) for x in requirements}
    total_found = 0
    installed_packages = result[1].stdout.splitlines()
    try:
        for line in installed_packages:
            if line != '' and not line.startswith('#'):
                line = [x for x in line.split(' ') if x != '']
                package, version = line[0], line[1]
                if package == '':
                    continue
                
                version = try_get_version(version)

                for req in requirements:
                    if req.name == package:
                        if version is None:
                            package_status[req.name] = (PackageCode.VERSION_INVALID, f'Expected "{req.specifier}", found "{version}". Version is not in PEP 440 format.')
                        elif req.specifier == '' or req.specifier.contains(version):
                            package_status[req.name] = (PackageCode.FOUND, '')
                            total_found += 1
                        else:
                            package_status[req.name] = (PackageCode.VERSION_MISMATCH, f'Expected "{req.specifier}", found "{version}"')
                
                if total_found == len(requirements):
                    break
    except Exception as e:
        
        print(f"Error processing environment {env}: {e} {version} {package}")
        raise e
        # return []

    score = sum([x[0].value for x in package_status.values()])
    return score, len(installed_packages), [(package, status) for package, status in package_status.items() if status[0] != PackageCode.FOUND]

def main():
    args = parse_args()
    # print('asdasd')
    # print(f"Arguments received: {args}")

    requirements = []
    for package in args.have:
        try:
            req = Requirement(package)
            print(req.name, req.specifier)
            requirements.append(req)
        except InvalidRequirement as e:
            # print(e)
            return
    print(requirements)

    check_conda_installed()

    conda_envs = get_conda_envs()
    filtered_envs = []
    pbar = tqdm(conda_envs, total=len(conda_envs))
    for env in pbar:
        pbar.set_description(f'Checking "{env}"')
        missing_packages = (env, *check_packages_in_env(env, requirements))
        filtered_envs.append(missing_packages)
    filtered_envs.sort(key=lambda x: (x[1], x[2]))
    import pdb; pdb.set_trace()

if __name__ == '__main__':
    main()