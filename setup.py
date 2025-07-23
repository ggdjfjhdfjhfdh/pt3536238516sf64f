from setuptools import setup, find_packages

setup(
    name="pentest",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'pentest': ['mitre_mapping.yaml'],
        '': ['templates/*.html'],
    },
    install_requires=[
        "redis",
        "rq",
        "requests",
        "jinja2",
        "weasyprint",
        "pdfkit",
        "defusedxml",
        "amass",
        "sslyze",
        "httpx",
        "PyYAML",
    ],
    entry_points={
        "console_scripts": [
            "pentest-worker=pentest.core:start_worker",
        ],
    },
    python_requires=">=3.8",
    author="Auditátetumismo",
    author_email="informes@auditatetumismo.es",
    description="Escáner de seguridad modular y tipado",
    keywords="security, pentest, scanner",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Information Technology",
        "Topic :: Security",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)