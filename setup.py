from setuptools import setup

setup(
    name="spark-cli",
    version="2.0.0",
    py_modules=["cli"],
    install_requires=[
        "click",
        "pyyaml"
    ],
    entry_points={
        "console_scripts": [
            "spark-cli = cli:cli"
        ]
    }
)