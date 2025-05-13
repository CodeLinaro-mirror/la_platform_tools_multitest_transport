# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Setup for mtt cli."""
import setuptools

VERSION = '0.0'

setuptools.setup(
    name='Android_Test_Station_CLI',
    description='CLI for Android Test Station.',
    url='https://source.android.com/compatibility/tests/development/android-test-station/ats-user-guide',
    version=VERSION,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    packages=setuptools.find_packages(),
    package_data={
        'multitest_transport.cli': ['seccomp.json'],
    },
    # The package works for 3.8 and up, but not for python 4 yet.
    python_requires='~=3.8',
    entry_points={
        'console_scripts': ['mtt=multitest_transport.cli.cli:Main'],
    },
    install_requires=[
        'ansible-base',
        'appengine-python-standard >= 1.0.0',
        'attrs',
        'fabric',
        'grpcio == 1.49.1',
        'grpcio-status == 1.49.1',
        'google-api-core == 2.11.1',
        'google-api-python-client==2.94.0',
        'google-auth==2.22.0',
        'google-cloud-core==2.3.3',
        'google-cloud-logging==3.6.0',
        'google-cloud-secret-manager==2.16.2',
        'google-cloud-storage==2.10.0',
        'urllib3 == 1.26.16',
        'packaging',
        'python-dateutil',
        # Temporary fix for proto dependency bug.
        'protobuf == 4.23.1',
        'pytz',
        'pyOpenSSL == 23.2.0',
        'requests == 2.31.0',
        'SecretStorage',
        'six == 1.15.0',
        'strictyaml',
    ]
)
