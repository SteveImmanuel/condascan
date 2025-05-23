import argparse

def parse_args():
    parser = argparse.ArgumentParser(description='condascout: a tool to find conda environments which contain specified package(s)')
    parser.add_argument('--have', nargs='+', help='Package(s) to search for in conda environments', metavar='PACKAGE')

    args = parser.parse_args()
    return args
