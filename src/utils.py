from pathlib import Path


def make_directories(directories):

    for d in directories:

        Path(d).mkdir(

            parents=True,

            exist_ok=True

        )