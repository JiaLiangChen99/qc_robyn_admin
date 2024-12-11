from setuptools import setup, find_packages

setup(
    name="qc-robyn-admin",
    version="0.1.0",
    author="0x7eQiChen",
    author_email="1356617750@qq.com",
    description="A backend framework based on Robyn and Tortoise-ORM, providing modules for model filtering, query joining, authentication, and more",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/0x7eQiChen/robyn-admin",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "robyn",
        "tortoise-orm",
        "jinja2"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
) 