# condascan
CLI tool to scan through existing `conda` environments. It helps you manage your conda environments by:
- Finding environments that satisfy a `requirements.txt` or `environment.yml` file. You can then clone them, instead of creating a new environment from scratch.
- Checking if a command is available in some environments, as well as getting the result of executing the command.
- Compare different environments to see which packages are unique or shared. Then, you can delete environments that are not needed anymore.

## Installation
You can install `condascan` using `pip`:
```bash
pip install condascan
```

Additionally, `conda` has to be installed on your system, either using `miniconda`, `anaconda`, `miniforge`, `mambaforge`, etc. Make sure that you can execute the following command:
```bash
conda --version
```

## Usage

### Search by Requirements
Using the `have` command, you can scan through your conda environments and find those that satisfy a given requirement. The bash command is as follows:
```bash
condascan have <requirement>
```
`<requirement>` can be one of the following:
- A string enclosed in quotes, specifying space-separated package names in PEP 440 format, e.g., `"numpy pandas"`, `"numpy==1.2.* pandas>=2.1.0"`.
- A path to a `requirements.txt` file, generated by `pip freeze`
- A path to a `environment.yml` file, generated by `conda env export`

### Check Command Availability
To see if a command is available in any of your conda environments, use the `can-execute` command:
```bash
condascan can-execute <command>
```
`<command>` can be one of the following:
- A string enclosed in quotes, specifying the command to run, e.g., `"nvcc --version"`
- A path to `.txt` file containing list of commands, one per line.

**Note**: To determine if a command can be executed in a given environment, `condascan` will actually **run** the command inside each environment. This means any side effects (e.g., creating files, modifying state, or triggering installations) will occur if the command succeeds. Make sure the commands you're testing are safe and have predictable behavior across environments.

### Compare Environments
To compare two or more environments, use the `compare` command:
```bash
condascan compare <envs>
```
<envs> can be one of the following:
- A string enclosed in quotes, specifying space-separated installed environment names, e.g., `"base env1 env2"`
- A path to a `.txt` file containing list of installed environment names, one per line.

## Caching
To speed up execution, `condascan` caches the results of previous runs. The cache is stored in `~/.cache/condascan`. If in-between executing `condascan` you modify your conda environments or you want to run without cache, you can do so by adding `--no-cache` flag. For example:
```bash
condascan have "numpy pandas" --no-cache
```

## Formatting Output

### `--verbose`, `--limit`, and `--first` Flags
**Note:** These flags are only applicable for `have` and `can-execute` commands

To get the detailed output of `condascan`, you can add `--verbose` flag. For example:
```bash
condascan can-execute "nvcc --version" --verbose
```
To limit the number of environments displayed in the output, you can use the `--limit` flag. Note that this is only applicable for `have` and `can-execute` commands. For example:
```bash
condascan have "numpy pandas" --limit 5
```
To find the first environment that satisfies the requirement, you can use the `--first` flag. Note that in this case, `condascan` will only scan the environments until it finds the first one that satisfies the requirement, and then it will stop scanning further. This can significantly speed up the search if you only need one environment that meets the requirement.
For example:
```bash
condascan have "numpy pandas" --first
```

### `--pip` Flag
**Note:** These flags are only applicable for `compare` command

By default, the `compare` command will compare every installed package from any channel in the environments. If you want to compare only packages installed from `pip`, you can use the `--pip` flag. For example:
```bash
condascan compare "env1 env2" --pip
```

