from glob import glob
import os

from setuptools import find_packages, setup

package_name = "fleet_simulator"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        ("share/" + package_name, ["package.xml"]),
        (
            os.path.join("share", package_name, "launch"),
            glob(os.path.join("launch", "*.launch.py")),
        ),
        (
            os.path.join("share", package_name, "worlds"),
            glob(os.path.join("worlds", "*.sdf")),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="utsav-5756",
    maintainer_email="37643534+utsav-5756@users.noreply.github.com",
    description=(
        "Deterministic kinematic fleet simulator for the Agentic Robotics "
        "Fleet Operations Center."
    ),
    license="MIT",
    tests_require=[],
    entry_points={
        "console_scripts": [
            "fleet_simulator = fleet_simulator.node:main",
            "fleet_telemetry_bridge = fleet_simulator.telemetry_bridge:main",
        ],
    },
)
