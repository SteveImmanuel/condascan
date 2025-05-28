from condascan.parser import parse_args
from condascan.task import Task

def main():
    args = parse_args()
    task = Task.from_args(args)
    task.initialize_and_verify()
    task.process()

if __name__ == '__main__':
    main()