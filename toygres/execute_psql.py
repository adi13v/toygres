from . import db


def run(command):
    output = db.executepsql(command)
    if output:
        print(output)
