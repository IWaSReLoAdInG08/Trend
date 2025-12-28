import fastmcp
import os

path = os.path.dirname(fastmcp.__file__)
target = os.path.join(path, "server", "server.py")

with open(target, 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines[611:640], start=611):
        print(f"{i}: {line.rstrip()}")
