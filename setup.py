from setuptools import setup, find_packages

setup(
    name="qc-robyn-admin",
    version="0.1.3",
    author="0x7eQiChen",
    author_email="1356617750@qq.com",
    description="A backend framework based on Robyn and Tortoise-ORM",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/0x7eQiChen/robyn-admin",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'qc_robyn_admin': [
            'templates/**/*.html',
            'static/**/*',
            'i18n/**/*',
            'core/**/*',
            'orm/**/*',
            'renderers/**/*',
            'auth_admin.py',
            'auth_models.py',
            'models.py'
        ]
    },
    install_requires=[
        "robyn",
        "tortoise-orm",
        "jinja2",
        "pandas",
        "openpyxl",
        "aiosqlite"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
) 